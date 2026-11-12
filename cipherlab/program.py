"""Solver programs: a genome renders to real Python source, and edits are source diffs.

The object every RSI method in this repo improves is a *program*, not a
parameter vector. A Genome is the compact description an improver reasons
about; `render()` turns it into the module that actually runs, and
`diff_features()` reads the unified diff between two programs the way
Budget RSI reads a proposed patch: without running it.

Only the blocks a genome uses are emitted. Turning on the word bonus adds an
import, a constant and a function; switching to annealing rewrites the search
loop; doubling ITERATIONS changes one line. That difference in diff shape is
exactly what Budget RSI's readout learns to exploit.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass, fields, replace
from typing import Dict, List

import numpy as np

FEATURE_NAMES = [
    "lines_added", "lines_deleted", "hunks", "defs_added",
    "defs_removed", "imports_changed", "constants_changed", "control_flow_changed",
]


@dataclass(frozen=True)
class Genome:
    ngram: int = 2               # 1..4: order of the letter n-gram language model
    word_weight: float = 0.0     # 0 = no dictionary term; else weight per recognised letter
    init: str = "random"         # "random" | "frequency"
    search: str = "hill"         # "hill" | "anneal"
    swap: str = "uniform"        # "uniform" | "rank_local"
    polish: bool = False         # exhaustive pairwise-swap sweep after the search
    iters: int = 1000            # candidate swaps per restart
    restarts: int = 1
    temp0: float = 2.0           # annealing start temperature (log10 units)
    smoothing: float = 0.01      # data: add-k constant of the n-gram model
    vocab: int = 3000            # data: dictionary size for the word term

    def to_dict(self) -> Dict:
        return asdict(self)

    def short(self) -> str:
        parts = [f"{self.ngram}-gram"]
        if self.word_weight:
            parts.append(f"words×{self.word_weight:g}")
        parts += [self.init[:4], self.search]
        if self.search == "anneal":
            parts.append(f"T{self.temp0:g}")
        if self.swap != "uniform":
            parts.append("ranked")
        if self.polish:
            parts.append("polish")
        if self.smoothing != 0.01:
            parts.append(f"k={self.smoothing:g}")
        if self.word_weight and self.vocab != 3000:
            parts.append(f"vocab={self.vocab}")
        parts.append(f"{self.restarts}x{self.iters}")
        return " ".join(parts)

    def with_(self, **kw) -> "Genome":
        return replace(self, **kw)

    @staticmethod
    def from_dict(d: Dict) -> "Genome":
        names = {f.name for f in fields(Genome)}
        return Genome(**{k: v for k, v in d.items() if k in names})


BASELINE = Genome()

_NGRAM_INDEX = {
    1: "p",
    2: "p[:-1] * 26 + p[1:]",
    3: "p[:-2] * 676 + p[1:-1] * 26 + p[2:]",
    4: "p[:-3] * 17576 + p[1:-2] * 676 + p[2:-1] * 26 + p[3:]",
}


def render(g: Genome, header: str = "") -> str:
    """The solver module for a genome. Deterministic: same genome, same bytes."""
    L: List[str] = []
    add = L.append
    add('"""CipherSmith solver program.' + (f" {header}" if header else "") + '"""')
    add("import numpy as np")
    add("from cipherlab.runtime import ngram_table")
    if g.word_weight:
        add("from cipherlab.runtime import word_hits")
    if g.init == "frequency":
        add("from cipherlab.runtime import ENGLISH_ORDER")
    add("")
    add(f"NGRAM_ORDER = {g.ngram}")
    add(f"ITERATIONS = {g.iters}")
    add(f"RESTARTS = {g.restarts}")
    if g.word_weight:
        add(f"WORD_WEIGHT = {g.word_weight!r}")
    if g.search == "anneal":
        add(f"START_TEMPERATURE = {g.temp0!r}")
    add(f"SMOOTHING = {g.smoothing!r}")
    if g.word_weight:
        add(f"VOCAB = {g.vocab}")
    add("TABLE = ngram_table(NGRAM_ORDER, SMOOTHING)")
    add("")
    add("")
    add("def ngram_score(p):")
    add(f"    return float(TABLE[{_NGRAM_INDEX[g.ngram]}].sum())")
    add("")
    add("")
    if g.word_weight:
        add("def word_score(p, ctx):")
        add("    return WORD_WEIGHT * word_hits(p, ctx, VOCAB)")
        add("")
        add("")
    add("def fitness(p, ctx):")
    add("    return ngram_score(p)" + (" + word_score(p, ctx)" if g.word_weight else ""))
    add("")
    add("")
    add("def initial_key(ctx, rng):")
    if g.init == "frequency":
        add("    key = np.empty(26, dtype=np.int64)")
        add("    key[np.argsort(-ctx.counts, kind='stable')] = ENGLISH_ORDER")
        add("    for _ in range(3):  # a little jitter so restarts differ")
        add("        a, b = rng.integers(0, 26, 2)")
        add("        key[a], key[b] = key[b], key[a]")
        add("    return key")
    else:
        add("    return rng.permutation(26)")
    add("")
    add("")
    add("def swap_pairs(ctx, rng, n):")
    if g.swap == "rank_local":
        add("    order = np.argsort(-ctx.counts, kind='stable')  # cipher letters by frequency")
        add("    i = rng.integers(0, 25, n)")
        add("    j = np.minimum(i + rng.integers(1, 4, n), 25)  # swap with a near neighbour in rank")
        add("    return np.stack([order[i], order[j]], axis=1)")
    else:
        add("    pairs = rng.integers(0, 26, (n, 2))")
        add("    return pairs[pairs[:, 0] != pairs[:, 1]]")
    add("")
    add("")
    add("def climb(ctx, key, rng):")
    add("    score = ctx.evaluate(key)")
    if g.search == "anneal":
        add("    best_key, best = key.copy(), score")
        add("    pairs = swap_pairs(ctx, rng, ITERATIONS)")
        add("    coins = rng.random(len(pairs))")
        add("    for i, (a, b) in enumerate(pairs):")
        add("        t = START_TEMPERATURE * (1.0 - i / len(pairs)) + 1e-3")
        add("        key[a], key[b] = key[b], key[a]")
        add("        new = ctx.evaluate(key)")
        add("        if new >= score or coins[i] < np.exp((new - score) / t):")
        add("            score = new")
        add("            if new > best:")
        add("                best_key, best = key.copy(), new")
        add("        else:")
        add("            key[a], key[b] = key[b], key[a]")
        add("    return best_key, best")
    else:
        add("    for a, b in swap_pairs(ctx, rng, ITERATIONS):")
        add("        key[a], key[b] = key[b], key[a]")
        add("        new = ctx.evaluate(key)")
        add("        if new > score:")
        add("            score = new")
        add("        else:")
        add("            key[a], key[b] = key[b], key[a]")
        add("    return key, score")
    add("")
    add("")
    if g.polish:
        add("def polish(ctx, key, score):")
        add("    improved = True")
        add("    while improved:  # first-improvement sweep over all 325 pairs")
        add("        improved = False")
        add("        for a in range(26):")
        add("            for b in range(a + 1, 26):")
        add("                key[a], key[b] = key[b], key[a]")
        add("                new = ctx.evaluate(key)")
        add("                if new > score:")
        add("                    score, improved = new, True")
        add("                else:")
        add("                    key[a], key[b] = key[b], key[a]")
        add("    return key, score")
        add("")
        add("")
    add("def solve(ctx, rng):")
    add("    best_key, best = None, -np.inf")
    add("    for _ in range(RESTARTS):")
    add("        key, score = climb(ctx, initial_key(ctx, rng), rng)")
    add("        if score > best:")
    add("            best_key, best = key.copy(), score")
    if g.polish:
        add("    best_key, best = polish(ctx, best_key, best)")
    add("    return best_key")
    return "\n".join(L) + "\n"


def unified_diff(parent_src: str, child_src: str, n: int = 0) -> List[str]:
    return list(difflib.unified_diff(parent_src.splitlines(), child_src.splitlines(),
                                     "parent.py", "child.py", n=n, lineterm=""))


_CONST = re.compile(r"^[A-Z_]{2,}\s*=")
_FLOW = re.compile(r"^\s*(for|while|if|elif|else|try|except|return)\b")


def diff_features(parent_src: str, child_src: str) -> List[float]:
    """Budget RSI's eight diff coordinates, read from the patch alone (no execution)."""
    diff = unified_diff(parent_src, child_src)
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    deleted = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    changed = added + deleted
    return [
        float(len(added)),
        float(len(deleted)),
        float(sum(1 for l in diff if l.startswith("@@"))),
        float(sum(1 for l in added if l.startswith("def "))),
        float(sum(1 for l in deleted if l.startswith("def "))),
        float(sum(1 for l in changed if l.startswith(("import ", "from ")))),
        float(sum(1 for l in changed if _CONST.match(l))),
        float(sum(1 for l in changed if _FLOW.match(l))),
    ]


SIGNED_CONSTANTS = ["NGRAM_ORDER", "ITERATIONS", "RESTARTS", "WORD_WEIGHT",
                    "START_TEMPERATURE", "SMOOTHING", "VOCAB"]
SIGNED_NAMES = [f"dlog2_{c.lower()}" for c in SIGNED_CONSTANTS]
_ASSIGN = re.compile(r"^([A-Z_]+)\s*=\s*([0-9.eE+-]+)\s*$")


def signed_features(parent_src: str, child_src: str) -> List[float]:
    """Seven more coordinates read from the same diff: for each tunable constant,
    log2(new / old). A constant that appears (word bonus switched on) counts as
    +1, one that disappears as -1. Still no execution: only the patch text."""
    old, new = {}, {}
    for line in unified_diff(parent_src, child_src):
        if line.startswith(("+++", "---")):
            continue
        m = _ASSIGN.match(line[1:])
        if m and line[0] in "+-":
            (new if line[0] == "+" else old)[m.group(1)] = float(m.group(2))
    out = []
    for c in SIGNED_CONSTANTS:
        if c in old and c in new and old[c] > 0 and new[c] > 0:
            out.append(float(np.log2(new[c] / old[c])))
        elif c in new and c not in old:
            out.append(1.0)
        elif c in old and c not in new:
            out.append(-1.0)
        else:
            out.append(0.0)
    return out
