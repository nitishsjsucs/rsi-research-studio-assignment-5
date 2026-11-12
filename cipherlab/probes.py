"""Diagnostic probes: cheap experiments that ask WHY a program fails.

Probes run the current program on the `probe` split (24 ciphers x 2 seeds =
48 instance-runs, the price of one steering evaluation) and read signals a
plain solve rate hides. Every number below comes from `runtime.run_instance`,
which records, per cipher, the fitness of the key the program found AND the
fitness its own objective assigns to the true key.

    objective gap   failures where fitness(found) >= fitness(true key):
                    the objective PREFERS a wrong answer, so searching
                    harder cannot help. Fix the objective.
    stalled early   failures whose last improvement came in the first half
                    of the spent budget: the climb is trapped in a local
                    optimum. More iterations of the same climb will not help.
    undersearched   failures still improving in the last 20% of the work
                    the PROGRAM chose to do, below the harness cap: the
                    program stops too early. Searching longer is right.
    cap bound       failures that hit the HARNESS cap: more iterations or
                    restarts will be truncated. Spend the budget better.
    length gap      short ciphers fail where long ones pass: there is not
                    enough text for n-gram statistics; add prior knowledge.
    seed variance   the same cipher passes with one seed and fails with the
                    other: outcomes are luck, so diversify (restarts).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .evaluate import Evaluator
from .loop import Budget
from .program import Genome, render

PROBE_SEEDS = (0, 1)

# mechanism -> (ops that address it, ops it says are futile)
REMEDIES: Dict[str, tuple] = {
    "objective":     (["ngram_up", "add_words", "words_up", "smoothing_down", "vocab_up"],
                      ["iters_up", "restarts_up", "temp_up", "temp_down", "add_polish"]),
    "local_optima":  (["use_anneal", "restarts_up", "init_frequency", "temp_up"],
                      ["iters_up", "use_hill", "restarts_down"]),
    "undersearched": (["iters_up", "restarts_up"],
                      ["iters_down", "restarts_down"]),
    "cap_bound":     (["init_frequency", "restarts_down", "use_anneal", "remove_polish"],
                      ["iters_up", "restarts_up", "add_polish"]),
    "short_texts":   (["add_words", "words_up", "vocab_up"],
                      ["iters_up"]),
    "high_variance": (["restarts_up", "use_anneal"],
                      ["restarts_down"]),
}


@dataclass
class Diagnosis:
    genome: Genome
    failures: int
    runs: int
    objective_gap: float
    stalled_early: float
    undersearched: float
    cap_bound: float
    buckets: Dict[str, float]
    seed_variance: float
    mechanisms: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def recommended(self) -> List[str]:
        return list(dict.fromkeys(op for m in self.mechanisms for op in REMEDIES[m][0]))

    def futile(self) -> List[str]:
        rec = set(self.recommended())
        return list(dict.fromkeys(op for m in self.mechanisms for op in REMEDIES[m][1] if op not in rec))

    def line(self) -> str:
        b = " ".join(f"{k}={v:.2f}" for k, v in self.buckets.items())
        return (f"fail={self.failures}/{self.runs} obj_gap={self.objective_gap:.2f} "
                f"stalled={self.stalled_early:.2f} under={self.undersearched:.2f} "
                f"cap={self.cap_bound:.2f} var={self.seed_variance:.2f} [{b}]")


def diagnose_rows(genome: Genome, rows: List[dict]) -> Diagnosis:
    fails = [r for r in rows if not r["solved"]]
    nf = max(1, len(fails))
    obj = sum(1 for r in fails if r["fitness_found"] >= r["fitness_true"] - 1e-9) / nf
    stalled = sum(1 for r in fails if r["evals"] and r["last_improvement"] < 0.5 * r["evals"]) / nf
    under = sum(1 for r in fails if not r["hit_cap"] and r["evals"] and r["last_improvement"] > 0.8 * r["evals"]) / nf
    cap = sum(1 for r in fails if r["hit_cap"]) / nf
    buckets: Dict[str, List[bool]] = {}
    for r in rows:
        buckets.setdefault(r["bucket"], []).append(r["solved"])
    brate = {k: float(np.mean(v)) for k, v in sorted(buckets.items(), key=lambda kv: ["short", "medium", "long"].index(kv[0]))}
    by_uid: Dict[str, List[bool]] = {}
    for r in rows:
        by_uid.setdefault(r["uid"], []).append(r["solved"])
    var = float(np.mean([len(set(v)) > 1 for v in by_uid.values()])) if by_uid else 0.0

    d = Diagnosis(genome, len(fails), len(rows), obj, stalled, under, cap, brate, var)
    if not fails:
        return d
    if obj >= 0.35:
        d.mechanisms.append("objective")
        d.evidence.append(f"{obj:.0%} of failures score the wrong key at least as high as the true key")
    if stalled >= 0.5 and obj < 0.6:
        d.mechanisms.append("local_optima")
        d.evidence.append(f"{stalled:.0%} of failures stopped improving in the first half of their budget")
    if under >= 0.4:
        d.mechanisms.append("undersearched")
        d.evidence.append(f"{under:.0%} of failures were still improving when the program stopped itself")
    if cap >= 0.4:
        d.mechanisms.append("cap_bound")
        d.evidence.append(f"{cap:.0%} of failures hit the harness cap of evaluations")
    if brate.get("long", 0) - brate.get("short", 0) >= 0.4:
        d.mechanisms.append("short_texts")
        d.evidence.append(f"short ciphers solve {brate.get('short', 0):.0%} vs long {brate.get('long', 0):.0%}")
    if var >= 0.25:
        d.mechanisms.append("high_variance")
        d.evidence.append(f"{var:.0%} of ciphers flip between pass and fail across seeds")
    return d


def probe(ev: Evaluator, genome: Genome, budget: Optional[Budget] = None, caller: str = "probe") -> Diagnosis:
    from .tasks import load_split
    if budget is not None:
        budget.charge(len(load_split("probe")) * len(PROBE_SEEDS))
    r = ev.run(render(genome), "probe", PROBE_SEEDS, caller=caller)
    return diagnose_rows(genome, r.rows)
