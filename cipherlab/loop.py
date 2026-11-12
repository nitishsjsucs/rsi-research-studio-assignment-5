"""Shared machinery for every improver: scored candidates, a budget, a trace.

The three objects of RSI (course theme 09) map onto this repo as:

    task model   a solver *program* (Genome -> Python source)       program.py
    research     the loop that edits programs and keeps/discards    an Improver
    improver     the rules that decide how that loop proposes,      what each RSI
                 screens, diagnoses and inherits                    method changes

`Budget` counts steering instance-runs, the currency of every fair comparison
here. `Trace` is the improvement history SO-RSI mines for anomalies.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .evaluate import EvalResult, Evaluator
from .program import Genome, render

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


@dataclass
class Scored:
    genome: Genome
    solved: int
    total: int
    mean_acc: float
    rows: List[dict] = field(default_factory=list, repr=False)

    @property
    def rate(self) -> float:
        return self.solved / self.total if self.total else 0.0

    @property
    def key(self) -> float:
        """Solved count first; mean letter accuracy (< 1) only breaks ties."""
        return self.solved + self.mean_acc

    def beats(self, other: "Scored", margin: float = 0.005) -> bool:
        return self.key > other.key + margin


class Budget:
    """Steering instance-runs an improver may spend. Exhausting it ends the run."""

    def __init__(self, runs: int):
        self.limit = runs
        self.spent = 0

    def can_afford(self, runs: int) -> bool:
        return self.spent + runs <= self.limit

    def charge(self, runs: int):
        self.spent += runs

    @property
    def left(self) -> int:
        return self.limit - self.spent


class Scorer:
    """Evaluate genomes on a split.

    Every call is charged to `budget`, even for a program evaluated before: an
    agent that re-tries the same fix pays for the re-run, which is exactly the
    waste SO-RSI's recurrence detector exists to stop. (Results are memoised
    only to save wall-clock; runs are deterministic per genome and seed.)
    """

    def __init__(self, ev: Evaluator, split: str = "steering", seeds: Sequence[int] = (0,),
                 budget: Optional[Budget] = None, caller: str = "?", subset=None,
                 charge_repeats: bool = True):
        self.ev, self.split, self.seeds, self.budget, self.caller = ev, split, tuple(seeds), budget, caller
        self.subset = subset
        self.charge_repeats = charge_repeats
        self.cache: Dict[Genome, Scored] = {}
        self.calls = 0

    def cost(self) -> int:
        from .tasks import load_split
        n = len(self.subset) if self.subset is not None else len(load_split(self.split))
        return n * len(self.seeds)

    def __call__(self, g: Genome) -> Scored:
        self.calls += 1
        if g in self.cache:
            if self.budget is not None and self.charge_repeats:
                self.budget.charge(self.cost())
            return self.cache[g]
        if self.budget is not None:
            self.budget.charge(self.cost())
        r: EvalResult = self.ev.run(render(g), self.split, self.seeds, subset=self.subset, caller=self.caller)
        s = Scored(g, r.solved, len(r.rows), r.mean_acc, r.rows)
        self.cache[g] = s
        return s


@dataclass
class Step:
    round: int
    op: str
    target: str
    kind: str
    parent: str
    child: str
    parent_rate: float
    child_rate: float
    accepted: bool
    expected: float = 0.0
    note: str = ""

    @property
    def delta(self) -> float:
        return self.child_rate - self.parent_rate


class Trace(list):
    def accepted(self) -> List[Step]:
        return [s for s in self if s.accepted]

    def curve(self) -> List[float]:
        """Best-so-far steering rate after each step."""
        out, best = [], (self[0].parent_rate if self else 0.0)
        for s in self:
            if s.accepted:
                best = max(best, s.child_rate)
            out.append(best)
        return out


def save_json(name: str, payload) -> str:
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, name)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=_default)
    return path


def load_json(name: str):
    with open(os.path.join(RESULTS, name)) as f:
        return json.load(f)


def _default(o):
    if isinstance(o, Genome):
        return o.to_dict()
    if hasattr(o, "__dict__"):
        return o.__dict__
    if hasattr(o, "item"):
        return o.item()
    return str(o)
