"""The evaluator: runs a program on a split, in parallel, and keeps an honest ledger.

Two properties every lab relies on:

  * Cost is counted, per split, in *instance-runs* (one program on one cipher
    with one seed). Fair comparisons in this repo match that number.
  * The held-out split is sealed. While sealed, any request for it raises
    SealedSplitError, so no search procedure can select on it by accident.
    `ledger` records every access with a caller tag; lab 10.02 audits it.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

from .runtime import EVAL_CAP, run_instance
from .tasks import load_split


class SealedSplitError(RuntimeError):
    pass


def _worker(args):
    source, split, family, n, idxs, seed, cap = args
    insts = load_split(split, family, n)
    return [run_instance(source, insts[i], seed, cap) for i in idxs]


@dataclass
class EvalResult:
    split: str
    rows: List[dict]
    seeds: Sequence[int]
    seconds: float

    @property
    def solve_rate(self) -> float:
        return float(np.mean([r["solved"] for r in self.rows])) if self.rows else 0.0

    @property
    def mean_acc(self) -> float:
        return float(np.mean([r["acc"] for r in self.rows])) if self.rows else 0.0

    @property
    def solved(self) -> int:
        return int(sum(r["solved"] for r in self.rows))

    def by_bucket(self) -> Dict[str, float]:
        out = defaultdict(list)
        for r in self.rows:
            out[r["bucket"]].append(r["solved"])
        return {k: float(np.mean(v)) for k, v in sorted(out.items(), key=lambda kv: ["short", "medium", "long"].index(kv[0]))}


@dataclass
class Ledger:
    runs: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    evals: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    accesses: List[dict] = field(default_factory=list)

    def charge(self, split: str, rows: List[dict], caller: str):
        self.runs[split] += len(rows)
        self.evals[split] += sum(r["evals"] for r in rows)
        self.accesses.append({"split": split, "runs": len(rows), "caller": caller, "t": time.time()})

    def summary(self) -> str:
        return ", ".join(f"{s}: {self.runs[s]} runs" for s in sorted(self.runs))


class Evaluator:
    def __init__(self, workers: Optional[int] = None, cap: int = EVAL_CAP):
        self.workers = workers or max(1, (os.cpu_count() or 2) - 1)
        self.cap = cap
        self.pool = ProcessPoolExecutor(self.workers) if self.workers > 1 else None
        self.ledger = Ledger()
        self.sealed = {"heldout"}

    def seal(self, split: str = "heldout"):
        self.sealed.add(split)

    def unseal(self, split: str = "heldout"):
        self.sealed.discard(split)

    def run(self, source: str, split: str, seeds: Iterable[int] = (0,), family: str = "aristocrat",
            n: int = 0, subset: Optional[Sequence[int]] = None, caller: str = "?",
            cap: Optional[int] = None) -> EvalResult:
        if split in self.sealed:
            raise SealedSplitError(f"{caller} asked for the sealed '{split}' split")
        insts = load_split(split, family, n)
        idxs = list(subset) if subset is not None else list(range(len(insts)))
        seeds = list(seeds)
        t0 = time.perf_counter()
        jobs = []
        chunk = max(1, len(idxs) // (self.workers * 2) or 1)
        for seed in seeds:
            for i in range(0, len(idxs), chunk):
                jobs.append((source, split, family, n, idxs[i:i + chunk], seed, cap or self.cap))
        if self.pool:
            parts = list(self.pool.map(_worker, jobs))
        else:
            parts = [_worker(j) for j in jobs]
        rows = [r for part in parts for r in part]
        self.ledger.charge(split if family == "aristocrat" else f"{split}/{family}", rows, caller)
        return EvalResult(split, rows, seeds, time.perf_counter() - t0)

    def close(self):
        if self.pool:
            self.pool.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
