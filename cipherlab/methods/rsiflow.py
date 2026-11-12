"""RSIFlow-style adaptive workflow with an evolving meta-agent (after arXiv:2610.21791).

The improvement procedure is a workflow of stages:

    PROFILE -> PROPOSE -> SCREEN -> EVALUATE -> INTEGRATE

A static workflow always runs PROPOSE -> EVALUATE -> INTEGRATE. The adaptive
workflow has a meta-agent that watches execution feedback (acceptance rate,
cost per gain, which targets keep failing, whether runs hit the cap) and
rewires the workflow with rules:

    screen_on_low_yield   acceptance < 25% over 6 steps -> insert SCREEN
                          (Budget RSI readout picks 1 of 6 proposals)
    profile_on_stall      4 rejections in a row -> run PROFILE (probes) and
                          restrict PROPOSE to the diagnosed remedies for 4 steps
    cap_guard             most runs hit the harness cap -> ban "search longer"
    drop_dead_target      a target with 4 failures and no success -> damp it

The meta-agent itself evolves: every rule keeps a usefulness score (mean gain
in the steps it shaped, minus the mean gain of steps it did not) and a rule
whose usefulness stays negative after 3 activations is switched off.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..edits import BY_NAME, SYMPTOM_PRIOR, applicable, sample_op
from ..evaluate import Evaluator
from ..loop import Budget, Scorer
from ..probes import probe
from ..program import BASELINE, Genome
from .budget_rsi import LinearReadout, edit_row


@dataclass
class Rule:
    name: str
    enabled: bool = True
    activations: int = 0
    gains: List[float] = field(default_factory=list)

    def usefulness(self, baseline: float) -> float:
        return float(np.mean(self.gains)) - baseline if self.gains else 0.0


class MetaAgent:
    def __init__(self):
        self.rules = {n: Rule(n) for n in ("screen_on_low_yield", "profile_on_stall", "cap_guard", "drop_dead_target")}
        self.restrict: List[str] = []
        self.restrict_left = 0
        self.banned: set = set()
        self.damped: Counter = Counter()
        self.screen = False

    def evolve(self, untouched_mean: float):
        for r in self.rules.values():
            if r.enabled and r.activations >= 3 and r.usefulness(untouched_mean) < 0:
                r.enabled = False

    def graph(self) -> str:
        stages = []
        if self.restrict_left:
            stages.append("PROFILE")
        stages.append("PROPOSE" + (f"[{len(self.restrict)} remedies]" if self.restrict_left else ""))
        if self.screen:
            stages.append("SCREEN")
        stages += ["EVALUATE", "INTEGRATE"]
        return " -> ".join(stages)


def run(ev: Evaluator, budget_runs: int, seed: int, adaptive: bool = True,
        readout: Optional[LinearReadout] = None, start: Genome = BASELINE, log=None) -> dict:
    rng = np.random.default_rng(seed)
    budget = Budget(budget_runs)
    steer = Scorer(ev, "steering", (0,), budget, caller=f"rsiflow-{'adaptive' if adaptive else 'static'}")
    meta = MetaAgent()
    cur = start
    cur_s = steer(cur)
    recent = deque(maxlen=6)
    fails_by_target, wins_by_target = Counter(), Counter()
    streak, step = 0, 0
    shaped_by: List[str] = []
    untouched: List[float] = []
    graphs, curve = [], []
    while budget.can_afford(steer.cost()):
        step += 1
        shaped_by = []
        weights = dict(SYMPTOM_PRIOR)
        if adaptive:
            if meta.rules["screen_on_low_yield"].enabled and len(recent) == 6 and np.mean(recent) < 0.25 and readout is not None:
                if not meta.screen:
                    meta.rules["screen_on_low_yield"].activations += 1
                meta.screen = True
            if meta.rules["profile_on_stall"].enabled and streak >= 4 and budget.can_afford(2 * steer.cost()):
                d = probe(ev, cur, budget, caller="rsiflow-profile")
                meta.restrict, meta.restrict_left, streak = d.recommended(), 4, 0
                meta.rules["profile_on_stall"].activations += 1
                if log:
                    log(f"    PROFILE: {d.mechanisms} -> remedies {d.recommended()[:4]}")
            if meta.rules["cap_guard"].enabled and cur_s.rows and np.mean([r["hit_cap"] for r in cur_s.rows]) > 0.5:
                if not meta.banned:
                    meta.rules["cap_guard"].activations += 1
                meta.banned = {"iters_up", "restarts_up", "add_polish"}
            if meta.rules["drop_dead_target"].enabled:
                for t, n in fails_by_target.items():
                    if n >= 4 and wins_by_target[t] == 0 and t not in meta.damped:
                        meta.damped[t] = 1
                        meta.rules["drop_dead_target"].activations += 1
            for op in list(weights):
                if op in meta.banned:
                    weights[op] = 0.0
                    shaped_by.append("cap_guard")
                if BY_NAME[op].target in meta.damped:
                    weights[op] *= 0.15
                    shaped_by.append("drop_dead_target")
            if meta.restrict_left:
                weights = {k: (v * 5 + 0.05 if k in meta.restrict else v * 0.2) for k, v in weights.items()}
                meta.restrict_left -= 1
                shaped_by.append("profile_on_stall")
        if adaptive and meta.screen and meta.rules["screen_on_low_yield"].enabled:
            props = []
            for _ in range(6):
                op = sample_op(cur, rng, weights)
                if op and op.name not in [p.name for p in props]:
                    props.append(op)
            if not props:
                break
            pred = readout.predict(np.array([edit_row(cur, cur_s.mean_acc, p.apply(cur)) for p in props]))
            op = props[int(np.argmax(pred))]
            shaped_by.append("screen_on_low_yield")
        else:
            op = sample_op(cur, rng, weights)
        if op is None:
            break
        child = op.apply(cur)
        s = steer(child)
        ok = s.beats(cur_s)
        gain = s.rate - cur_s.rate if ok else 0.0
        recent.append(1.0 if ok else 0.0)
        streak = 0 if ok else streak + 1
        (wins_by_target if ok else fails_by_target)[op.target] += 1
        for rname in set(shaped_by):
            meta.rules[rname].gains.append(gain)
        if not shaped_by:
            untouched.append(gain)
        if adaptive:
            meta.evolve(float(np.mean(untouched)) if untouched else 0.0)
        if ok:
            cur, cur_s = child, s
        g = meta.graph() if adaptive else "PROPOSE -> EVALUATE -> INTEGRATE"
        if not graphs or graphs[-1][1] != g:
            graphs.append((step, g))
            if log:
                log(f"  step {step:02d} workflow: {g}")
        curve.append(cur_s.rate)
    return {"adaptive": adaptive, "seed": seed, "final": cur, "final_rate": cur_s.rate, "steps": step,
            "runs_spent": budget.spent, "curve": curve, "workflows": graphs,
            "rules": {n: {"enabled": r.enabled, "activations": r.activations,
                          "usefulness": round(r.usefulness(float(np.mean(untouched)) if untouched else 0.0), 4)}
                      for n, r in meta.rules.items()}}
