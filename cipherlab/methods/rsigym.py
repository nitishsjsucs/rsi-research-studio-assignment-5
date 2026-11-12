"""RSIGym-style environment: Everything-as-a-Service, tracks, and the RSI-Index
(after arXiv:2610.10310).

Services. The improver never touches the evaluator directly. It calls named
services, each with a price and a permission list, against one shared budget:

    sandbox    compile a program's source; reject it before anything runs
    rollout    run a program on a few ciphers and return per-cipher traces
    evaluate   score a program on a named benchmark
    train      rebuild the language model a program uses (n-gram order,
               smoothing, dictionary): the "data" side of the system

Tracks. What the improver is permitted to change:

    data      objective/data edits only (n-gram order, word dictionary,
              smoothing, vocabulary): improve what the program knows
    harness   search/init/efficiency edits only: improve how it searches
    joint     both

RSI-Index. For each benchmark b, the fraction of the remaining gap closed:
    (final_b - initial_b) / (ideal_b - initial_b), ideal_b = 1.0,
and the index is the mean over benchmarks. (The course page writes the
numerator as initial - final, which is negative for any improvement; lab
10.15 shows the difference.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from ..edits import BY_NAME, OPS, applicable
from ..evaluate import Evaluator
from ..loop import Budget, Scored
from ..program import BASELINE, Genome, render
from ..tasks import load_split

TRACK_OPS = {
    "data": [op.name for op in OPS if op.target in ("objective", "data")],
    "harness": [op.name for op in OPS if op.target in ("search", "init", "efficiency")],
    "joint": [op.name for op in OPS],
}
TRACK_SERVICES = {
    "data": {"sandbox", "train", "evaluate"},
    "harness": {"sandbox", "rollout", "evaluate"},
    "joint": {"sandbox", "rollout", "train", "evaluate"},
}

# benchmark -> (split, family, subset predicate, cap)
BENCHMARKS = {
    "sherlock":      ("steering", "aristocrat", None, None),
    "short_only":    ("steering", "aristocrat", lambda inst: inst.bucket == "short", None),
    "patristocrat":  ("steering", "patristocrat", None, None),
    "tight_budget":  ("steering", "aristocrat", None, 5000),
    "frankenstein":  ("heldout", "aristocrat", None, None),
}


class PermissionDenied(RuntimeError):
    pass


@dataclass
class ServiceCall:
    service: str
    cost: int
    note: str


class RSIGym:
    def __init__(self, ev: Evaluator, track: str, budget_runs: int):
        self.ev, self.track = ev, track
        self.budget = Budget(budget_runs)
        self.calls: List[ServiceCall] = []
        self._cache: Dict = {}

    def _gate(self, service: str, cost: int, note: str):
        if service not in TRACK_SERVICES[self.track]:
            raise PermissionDenied(f"track '{self.track}' may not call '{service}'")
        if not self.budget.can_afford(cost):
            raise RuntimeError("budget exhausted")
        self.budget.charge(cost)
        self.calls.append(ServiceCall(service, cost, note))

    def sandbox(self, g: Genome) -> bool:
        self._gate("sandbox", 0, g.short())
        try:
            compile(render(g), "<sandbox>", "exec")
            return True
        except SyntaxError:
            return False

    def train(self, g: Genome) -> Genome:
        """The language-model side: free to call, but only the data track's edits use it."""
        self._gate("train", 0, f"lm n={g.ngram} k={g.smoothing} vocab={g.vocab}")
        return g

    def rollout(self, g: Genome, k: int = 4) -> List[dict]:
        self._gate("rollout", k, f"{k} ciphers")
        return self.ev.run(render(g), "probe", (0,), subset=range(k), caller=f"rsigym-{self.track}-rollout").rows

    def evaluate(self, g: Genome, bench: str = "sherlock", seeds=(0,), charge: bool = True) -> Scored:
        split, family, pred, cap = BENCHMARKS[bench]
        insts = load_split(split, family)
        subset = [i for i, inst in enumerate(insts) if pred is None or pred(inst)]
        key = (g, bench, tuple(seeds))
        if key not in self._cache:
            if charge:
                self._gate("evaluate", len(subset) * len(seeds), f"{bench} {g.short()}")
            r = self.ev.run(render(g), split, seeds, family=family, subset=subset, cap=cap,
                            caller=f"rsigym-{self.track}-{bench}")
            self._cache[key] = Scored(g, r.solved, len(r.rows), r.mean_acc, r.rows)
        elif charge:
            self._gate("evaluate", len(subset) * len(seeds), f"{bench} {g.short()} (repeat)")
        return self._cache[key]


def improve(gym: RSIGym, seed: int, start: Genome = BASELINE, log=None) -> Genome:
    """A plain greedy improver that may only use its track's edits and services."""
    rng = np.random.default_rng(seed)
    allowed = TRACK_OPS[gym.track]
    cur = start
    cur_s = gym.evaluate(cur)
    while gym.budget.can_afford(48):
        ops = [op for op in applicable(cur) if op.name in allowed]
        if not ops:
            break
        op = ops[int(rng.integers(len(ops)))]
        child = op.apply(cur)
        if not gym.sandbox(child):
            continue
        if op.target in ("objective", "data"):
            child = gym.train(child)
        s = gym.evaluate(child)
        if s.beats(cur_s):
            cur, cur_s = child, s
            if log:
                log(f"  {gym.track:8s} {op.name:15s} -> {s.rate:.3f}")
    return cur


def rsi_index(initial: Dict[str, float], final: Dict[str, float], ideal: float = 1.0) -> float:
    gaps = [(final[b] - initial[b]) / (ideal - initial[b]) for b in initial if ideal > initial[b]]
    return float(np.mean(gaps)) if gaps else 0.0


def rsi_index_as_printed(initial: Dict[str, float], final: Dict[str, float], ideal: float = 1.0) -> float:
    """The formula exactly as the course page prints it: (initial - final) / (ideal - initial)."""
    gaps = [(initial[b] - final[b]) / (ideal - initial[b]) for b in initial if ideal > initial[b]]
    return float(np.mean(gaps)) if gaps else 0.0
