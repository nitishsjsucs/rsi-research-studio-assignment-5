"""The fixed harness a solver program runs inside. Programs may change; this may not.

A solver program is ordinary Python source (see program.py). It defines
`fitness(p, ctx)` and `solve(ctx, rng)`. The harness owns three things the
program cannot touch:

  * the budget   - ctx.evaluate() counts every candidate key; past EVAL_CAP it
                   raises BudgetExhausted, so "just search longer" has a ceiling;
  * the record   - ctx keeps the best key seen *by the program's own fitness*,
                   so a program that crashes or runs out still returns something;
  * the truth    - the true key lives on the Instance; the program never sees it.
"""
from __future__ import annotations

import hashlib
import time
import types
from typing import Dict

import numpy as np

from .corpus import english_order, ngram_logp, word_table

EVAL_CAP = 20000  # candidate keys a solver may score per cipher: the "time limit"

# Names a solver program imports. Built lazily, cached once per process.
ENGLISH_ORDER = english_order()


def ngram_table(n: int, smoothing: float = 0.01) -> np.ndarray:
    """log10 P(n-gram) from the training book; `smoothing` is the add-k constant."""
    return ngram_logp(n, smoothing)


class BudgetExhausted(Exception):
    pass


def word_hits(p: np.ndarray, ctx: "Ctx", vocab: int = 3000) -> float:
    """Total letters in decrypted words that are among the `vocab` most frequent words."""
    if len(ctx.word_starts) == 0:
        return 0.0
    table = word_table(vocab)
    h = np.add.reduceat((p + 1) * ctx.word_pow, ctx.word_starts)
    pos = np.searchsorted(table, h)
    hit = (table[np.minimum(pos, len(table) - 1)] == h) & ctx.word_ok
    return float((hit * ctx.word_lens).sum())


class Ctx:
    """What a solver sees of one cipher instance."""

    def __init__(self, inst, fitness, cap: int = EVAL_CAP):
        self.cipher = inst.cipher
        self.word_starts = inst.word_starts
        self.word_lens = inst.word_lens
        self.word_pow = inst.word_pow
        self.word_ok = inst.word_ok
        self.counts = np.bincount(inst.cipher, minlength=26)
        self._fitness = fitness
        self.cap = cap
        self.used = 0
        self.best_score = -np.inf
        self.best_key = None
        self.last_improvement = 0  # eval index of the last new best: did the search stall or get cut off?

    def evaluate(self, key: np.ndarray) -> float:
        if self.used >= self.cap:
            raise BudgetExhausted
        self.used += 1
        s = self._fitness(key[self.cipher], self)
        if s > self.best_score:
            self.best_score, self.best_key = s, key.copy()
            self.last_improvement = self.used
        return s


_MODULES: Dict[str, types.ModuleType] = {}


def load_program(source: str) -> types.ModuleType:
    """Compile solver source once per process (cached by content hash)."""
    digest = hashlib.sha1(source.encode()).hexdigest()
    mod = _MODULES.get(digest)
    if mod is None:
        mod = types.ModuleType(f"solver_{digest[:10]}")
        exec(compile(source, f"<solver {digest[:10]}>", "exec"), mod.__dict__)
        _MODULES[digest] = mod
    return mod


def run_instance(source: str, inst, seed: int, cap: int = EVAL_CAP) -> dict:
    """Run one program on one cipher. Never raises: a broken program is a failed instance."""
    t0 = time.perf_counter()
    error = None
    try:
        mod = load_program(source)
        ctx = Ctx(inst, mod.fitness, cap)
        rng = np.random.default_rng(seed * 1_000_003 + int(inst.uid.rsplit("-", 1)[1]))
        try:
            mod.solve(ctx, rng)
        except BudgetExhausted:
            pass
        key = ctx.best_key if ctx.best_key is not None else np.arange(26)
        acc = float((key[inst.cipher] == inst.plain).mean())
        truth = float(mod.fitness(inst.true_key[inst.cipher], ctx))
        found = float(ctx.best_score)
        used, last = ctx.used, ctx.last_improvement
    except Exception as e:  # noqa: BLE001 - a crash is data, not a harness failure
        error = f"{type(e).__name__}: {e}"
        acc, truth, found, used, last = 0.0, float("nan"), float("nan"), 0, 0
        key = np.arange(26)
    return {
        "uid": inst.uid, "length": inst.length, "bucket": inst.bucket,
        "acc": acc, "solved": acc >= SOLVED_AT, "evals": used, "last_improvement": last,
        "hit_cap": used >= cap, "fitness_found": found, "fitness_true": truth,
        "decrypt": "".join(" " if c == " " else chr(97 + key[ord(c) - 97]) for c in inst.ciphertext),
        "seconds": time.perf_counter() - t0, "error": error,
    }


SOLVED_AT = 0.90  # a cipher counts as solved when >= 90% of its letters are right
