"""SO-RSI: second-order diagnostic inquiry (after arXiv:2610.05701).

First-order RSI (`second_order=False`) patches the symptom: the score is low,
so it samples an edit from a symptom-driven prior ("search harder" mostly),
keeps it if the steering score rises, repeats.

Second-order RSI (`second_order=True`) runs the SAME proposer and the SAME
acceptance rule, plus three things, all paid for from the same budget:

  1. an AnomalyDetector watching its own improvement trace for
       recurrence      the same edit keeps failing,
       opposing edits  an edit and its inverse alternate,
       mismatch        an edit expected to help changed nothing or hurt;
  2. diagnostic probes (probes.py) run when an anomaly fires, asking WHY;
  3. an InquiryMemory that keeps the causal findings across rounds and
     re-weights the proposer toward edits that address the diagnosed
     mechanism and away from edits the evidence says are futile.

(2) and (3) change *how the improver improves*: that is the second order.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..edits import BY_NAME, SYMPTOM_PRIOR, sample_op
from ..evaluate import Evaluator
from ..loop import Budget, Scorer, Step, Trace
from ..probes import Diagnosis, probe
from ..program import BASELINE, Genome

STEER_COST = 48


@dataclass
class Anomaly:
    kind: str       # recurrence | opposing | mismatch
    round: int
    evidence: str


class AnomalyDetector:
    def __init__(self, window: int = 6):
        self.window = window

    def check(self, trace: Trace) -> List[Anomaly]:
        if not trace:
            return []
        last, r = trace[-1], trace[-1].round
        recent = trace[-self.window:]
        out: List[Anomaly] = []
        # recurrence: this op has now failed >= 2 times in the recent window
        fails = sum(1 for s in recent if s.op == last.op and not s.accepted)
        if not last.accepted and fails >= 2:
            out.append(Anomaly("recurrence", r, f"{last.op} rejected {fails}x in the last {len(recent)} attempts"))
        # opposing: the op and its inverse both appear in the recent window
        inv = BY_NAME[last.op].inverse
        if any(s.op == inv for s in recent[:-1]):
            out.append(Anomaly("opposing", r, f"{last.op} follows its inverse {inv} within {len(recent)} steps"))
        # expectation mismatch: a gain was expected; nothing happened, or it hurt
        if last.expected >= 0.03 and last.delta <= 0:
            what = "no change at all" if last.delta == 0 else f"{last.delta:+.3f}"
            out.append(Anomaly("mismatch", r, f"{last.op} expected {last.expected:+.2f}, observed {what}"))
        return out


@dataclass
class Finding:
    round: int
    anomalies: List[str]
    mechanisms: List[str]
    evidence: List[str]
    recommended: List[str]
    futile: List[str]
    status: str = "open"   # open -> supported | inconclusive


@dataclass
class InquiryMemory:
    findings: List[Finding] = field(default_factory=list)
    refuted: Counter = field(default_factory=Counter)  # op -> rejections since last acceptance

    def record(self, round_: int, anomalies: List[Anomaly], d: Diagnosis):
        self.findings.append(Finding(round_, [a.kind for a in anomalies], d.mechanisms, d.evidence,
                                     d.recommended(), d.futile()))

    def observe(self, step: Step):
        if step.accepted:
            self.refuted.clear()
            for f in self.findings:
                if f.status == "open" and step.op in f.recommended:
                    f.status = "supported"
        else:
            self.refuted[step.op] += 1

    def weights(self, prior: Dict[str, float]) -> Dict[str, float]:
        w = dict(prior)
        # Only OPEN findings steer: a supported finding's mechanism has been fixed (its remedy was
        # accepted), so its remedies and its "futile" list describe a program that no longer exists.
        # (An earlier version also let supported findings steer; see the README, "What went wrong".)
        live = [f for f in self.findings if f.status == "open"][-2:]  # the latest open evidence wins
        for f in live:
            for op in f.recommended:
                w[op] = w.get(op, 0) * 4 + 0.05
            for op in f.futile:
                w[op] = w.get(op, 0) * 0.1
        for op, n in self.refuted.items():
            if n >= 2:  # tried twice from this parent, failed twice: the evidence beats the theory
                w[op] = w.get(op, 0) * 0.05
        return w

    def retire_stale(self, horizon: int, round_: int):
        for f in self.findings:
            if f.status == "open" and round_ - f.round > horizon:
                f.status = "inconclusive"


def run(ev: Evaluator, budget_runs: int, seed: int, second_order: bool,
        prior: Optional[Dict[str, float]] = None, start: Genome = BASELINE, log=None) -> dict:
    rng = np.random.default_rng(seed)
    prior = prior or SYMPTOM_PRIOR
    budget = Budget(budget_runs)
    steer = Scorer(ev, "steering", (0,), budget, caller="so-rsi" if second_order else "naive-rsi")
    detector, memory = AnomalyDetector(), InquiryMemory()
    current = start
    cur = steer(current)
    trace, anomalies_seen, diagnoses, probed = Trace(), [], [], set()
    rnd = 0
    while budget.can_afford(STEER_COST):
        rnd += 1
        weights = memory.weights(prior) if second_order else prior
        op = sample_op(current, rng, weights)
        if op is None:
            break
        child = op.apply(current)
        cs = steer(child)
        accepted = cs.beats(cur)
        step = Step(rnd, op.name, op.target, op.kind, current.short(), child.short(),
                    cur.rate, cs.rate, accepted, expected=op.expect)
        trace.append(step)
        memory.observe(step)
        if log:
            log(f"  r{rnd:02d} {op.name:15s} {cur.rate:.3f} -> {cs.rate:.3f} {'KEEP' if accepted else 'drop'}")
        if accepted:
            current, cur = child, cs
        if second_order:
            found = detector.check(trace)
            anomalies_seen += found
            # probe once per program: re-probing an unchanged program buys the same answer
            if found and current not in probed and budget.can_afford(STEER_COST + 48):
                d = probe(ev, current, budget, caller="so-rsi-probe")
                probed.add(current)
                memory.record(rnd, found, d)
                diagnoses.append({"round": rnd, "anomalies": [a.__dict__ for a in found],
                                  "diagnosis": d.line(), "mechanisms": d.mechanisms,
                                  "evidence": d.evidence, "recommended": d.recommended(), "futile": d.futile()})
                if log:
                    log(f"      anomaly {[a.kind for a in found]} -> probe: {d.line()}")
                    log(f"      mechanisms={d.mechanisms} recommend={d.recommended()[:4]}")
            memory.retire_stale(horizon=8, round_=rnd)
    detector_all = AnomalyDetector()  # count anomalies for both arms, for the behavioural comparison
    counts = Counter()
    for i in range(1, len(trace) + 1):
        for a in detector_all.check(Trace(trace[:i])):
            counts[a.kind] += 1
    return {
        "second_order": second_order, "seed": seed, "final": current, "final_rate": cur.rate,
        "rounds": rnd, "accepted": len(trace.accepted()), "runs_spent": budget.spent,
        "steps": [s.__dict__ for s in trace], "curve": trace.curve(),
        "anomaly_counts": dict(counts), "diagnoses": diagnoses,
        "findings": [f.__dict__ for f in memory.findings],
    }
