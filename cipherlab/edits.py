"""The edit vocabulary every improver draws from.

An EditOp turns one Genome into another (and therefore one program source
into another). Each op is labelled with what it changes, which op undoes it,
and what a symptom-driven proposer *expects* it to do. Those labels are not
used by the evaluator; they are what the improvers reason with:

    kind     structural | parametric | data
    target   objective  | search | init | efficiency | data
    inverse  the op that undoes it   (SO-RSI's "opposing edit" detector)
    expect   prior expected gain     (SO-RSI's "expectation mismatch" detector)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from .program import Genome

MAX_ITERS, MIN_ITERS = 40000, 250
MAX_RESTARTS = 32


@dataclass(frozen=True)
class EditOp:
    name: str
    kind: str
    target: str
    inverse: str
    expect: float
    fn: Callable[[Genome], Optional[Genome]]

    def apply(self, g: Genome) -> Optional[Genome]:
        out = self.fn(g)
        return None if out is None or out == g else out


def _if(cond, make):
    return lambda g: make(g) if cond(g) else None


OPS: List[EditOp] = [
    # objective: what the program believes English looks like
    EditOp("ngram_up", "structural", "objective", "ngram_down", 0.06,
           _if(lambda g: g.ngram < 4, lambda g: g.with_(ngram=g.ngram + 1))),
    EditOp("ngram_down", "structural", "objective", "ngram_up", 0.00,
           _if(lambda g: g.ngram > 1, lambda g: g.with_(ngram=g.ngram - 1))),
    EditOp("add_words", "structural", "objective", "remove_words", 0.05,
           _if(lambda g: not g.word_weight, lambda g: g.with_(word_weight=2.0))),
    EditOp("remove_words", "structural", "objective", "add_words", 0.00,
           _if(lambda g: g.word_weight, lambda g: g.with_(word_weight=0.0))),
    EditOp("words_up", "parametric", "objective", "words_down", 0.02,
           _if(lambda g: 0 < g.word_weight < 8, lambda g: g.with_(word_weight=g.word_weight * 2))),
    EditOp("words_down", "parametric", "objective", "words_up", 0.01,
           _if(lambda g: g.word_weight > 0.5, lambda g: g.with_(word_weight=g.word_weight / 2))),
    # search: how hard and how cleverly the program looks
    EditOp("iters_up", "parametric", "search", "iters_down", 0.05,
           _if(lambda g: g.iters < MAX_ITERS, lambda g: g.with_(iters=min(MAX_ITERS, g.iters * 2)))),
    EditOp("iters_down", "parametric", "search", "iters_up", 0.00,
           _if(lambda g: g.iters > MIN_ITERS, lambda g: g.with_(iters=max(MIN_ITERS, g.iters // 2)))),
    EditOp("restarts_up", "parametric", "search", "restarts_down", 0.04,
           _if(lambda g: g.restarts < MAX_RESTARTS, lambda g: g.with_(restarts=min(MAX_RESTARTS, g.restarts * 2)))),
    EditOp("restarts_down", "parametric", "search", "restarts_up", 0.00,
           _if(lambda g: g.restarts > 1, lambda g: g.with_(restarts=max(1, g.restarts // 2)))),
    EditOp("use_anneal", "structural", "search", "use_hill", 0.04,
           _if(lambda g: g.search != "anneal", lambda g: g.with_(search="anneal"))),
    EditOp("use_hill", "structural", "search", "use_anneal", 0.00,
           _if(lambda g: g.search != "hill", lambda g: g.with_(search="hill"))),
    EditOp("temp_up", "parametric", "search", "temp_down", 0.02,
           _if(lambda g: g.search == "anneal" and g.temp0 < 40, lambda g: g.with_(temp0=g.temp0 * 2))),
    EditOp("temp_down", "parametric", "search", "temp_up", 0.02,
           _if(lambda g: g.search == "anneal" and g.temp0 > 0.25, lambda g: g.with_(temp0=g.temp0 / 2))),
    EditOp("add_polish", "structural", "search", "remove_polish", 0.02,
           _if(lambda g: not g.polish, lambda g: g.with_(polish=True))),
    EditOp("remove_polish", "structural", "search", "add_polish", 0.00,
           _if(lambda g: g.polish, lambda g: g.with_(polish=False))),
    # init and efficiency: where the search starts, which moves it tries
    EditOp("init_frequency", "structural", "init", "init_random", 0.03,
           _if(lambda g: g.init != "frequency", lambda g: g.with_(init="frequency"))),
    EditOp("init_random", "structural", "init", "init_frequency", 0.00,
           _if(lambda g: g.init != "random", lambda g: g.with_(init="random"))),
    EditOp("swap_ranked", "structural", "efficiency", "swap_uniform", 0.02,
           _if(lambda g: g.swap != "rank_local", lambda g: g.with_(swap="rank_local"))),
    EditOp("swap_uniform", "structural", "efficiency", "swap_ranked", 0.00,
           _if(lambda g: g.swap != "uniform", lambda g: g.with_(swap="uniform"))),
    # data: the statistics the objective is built from
    EditOp("smoothing_up", "data", "data", "smoothing_down", 0.01,
           _if(lambda g: g.smoothing < 1.0, lambda g: g.with_(smoothing=round(g.smoothing * 10, 6)))),
    EditOp("smoothing_down", "data", "data", "smoothing_up", 0.01,
           _if(lambda g: g.smoothing > 1e-4, lambda g: g.with_(smoothing=round(g.smoothing / 10, 6)))),
    EditOp("vocab_up", "data", "data", "vocab_down", 0.01,
           _if(lambda g: g.word_weight and g.vocab < 10000, lambda g: g.with_(vocab={1000: 3000, 3000: 10000}.get(g.vocab, 10000)))),
    EditOp("vocab_down", "data", "data", "vocab_up", 0.00,
           _if(lambda g: g.word_weight and g.vocab > 1000, lambda g: g.with_(vocab={10000: 3000, 3000: 1000}.get(g.vocab, 1000)))),
]
BY_NAME: Dict[str, EditOp] = {op.name: op for op in OPS}

# What a symptom-driven proposer reaches for when a score is low: mostly "search
# harder", sometimes a structural change. This mirrors the first-order habit the
# SO-RSI paper describes (patch the surface parameter that looks responsible).
SYMPTOM_PRIOR: Dict[str, float] = {
    "iters_up": 0.16, "restarts_up": 0.11, "temp_up": 0.06, "temp_down": 0.06,
    "iters_down": 0.04, "restarts_down": 0.04, "words_up": 0.03, "words_down": 0.02,
    "ngram_up": 0.05, "ngram_down": 0.02, "add_words": 0.04, "remove_words": 0.02,
    "use_anneal": 0.05, "use_hill": 0.02, "add_polish": 0.04, "remove_polish": 0.02,
    "init_frequency": 0.04, "init_random": 0.02, "swap_ranked": 0.03, "swap_uniform": 0.02,
    "smoothing_up": 0.02, "smoothing_down": 0.02, "vocab_up": 0.02, "vocab_down": 0.01,
}
UNIFORM_PRIOR: Dict[str, float] = {op.name: 1.0 for op in OPS}


def applicable(g: Genome, names: Optional[Sequence[str]] = None) -> List[EditOp]:
    ops = OPS if names is None else [BY_NAME[n] for n in names]
    return [op for op in ops if op.apply(g) is not None]


def sample_op(g: Genome, rng: np.random.Generator, weights: Dict[str, float],
              exclude: Sequence[str] = ()) -> Optional[EditOp]:
    ops = [op for op in applicable(g) if op.name not in exclude and weights.get(op.name, 0) > 0]
    if not ops:
        return None
    w = np.array([weights[op.name] for op in ops], dtype=float)
    return ops[int(rng.choice(len(ops), p=w / w.sum()))]


def random_genome(rng: np.random.Generator, steps: int = 4, start: Genome = Genome()) -> Genome:
    """A random walk of `steps` uniform edits: used to make scaffold parents."""
    g = start
    for _ in range(steps):
        op = sample_op(g, rng, UNIFORM_PRIOR)
        if op:
            g = op.apply(g)
    return g
