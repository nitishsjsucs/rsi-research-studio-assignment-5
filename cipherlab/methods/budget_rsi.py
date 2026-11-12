"""Budget RSI: score code edits before they run (after arXiv:2610.29121).

The expensive step in a self-improving coding agent is evaluating a proposed
edit. Budget RSI spends that money only on the edit a cheap *linear readout*
predicts will do best:

    score(edit) = w . [parent_fit_rate, 8 diff coordinates]          (readout)

The readout is fit once per run on 96 "scaffold" edits, each labelled by four
evaluations (seeds) of a 16-cipher fit split. Search is a Huxley-Godel
Machine style tree: a parent is chosen by Thompson sampling on its *clade's*
steering counts (the node plus every descendant, a proxy for how productive
that line of programs has been), K candidate edits are proposed, the readout
picks one, and only that one is run on the steering split.

Selectors compared under the SAME steering budget:
    readout      the paper's method
    parent_rate  ablation: the readout sees only parent_rate, which is the same
                 for every sibling, so the pick among K is uniform at random
    oracle       evaluates all K and keeps the best (K times the cost per step)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..edits import UNIFORM_PRIOR, applicable, random_genome
from ..evaluate import Evaluator
from ..loop import Budget, Scorer
from ..program import BASELINE, FEATURE_NAMES, SIGNED_NAMES, Genome, diff_features, render, signed_features

FIT_SEEDS = (0, 1, 2, 3)
READOUT_FEATURES = ["parent_score"] + FEATURE_NAMES            # the paper's 1 + 8
EXTENDED_FEATURES = READOUT_FEATURES + SIGNED_NAMES                # lab 10.05: + 7 signed


class LinearReadout:
    """Ridge regression on standardised features. Fits in microseconds, scores in nanoseconds."""

    def __init__(self, ridge: float = 1.0, use: Optional[Sequence[int]] = None):
        self.ridge = ridge
        self.use = list(use) if use is not None else None  # feature subset (for ablations)

    def _x(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return X[:, self.use] if self.use is not None else X

    def fit(self, X, y) -> "LinearReadout":
        X = self._x(X)
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd < 1e-9] = 1.0  # a feature that never varied in training contributes nothing
        Z = (X - self.mu) / self.sd
        self.b = float(np.mean(y))
        with np.errstate(all="ignore"):  # numpy 2.0 + macOS Accelerate emits spurious matmul warnings
            A = Z.T @ Z + self.ridge * np.eye(Z.shape[1])
            self.w = np.linalg.solve(A, Z.T @ (np.asarray(y) - self.b))
        return self

    def predict(self, X) -> np.ndarray:
        Z = (self._x(X) - self.mu) / self.sd
        with np.errstate(all="ignore"):
            return Z @ self.w + self.b

    @property
    def coefficients(self) -> np.ndarray:
        """Weights in standard-deviation units: comparable across features."""
        return self.w


def edit_row(parent: Genome, parent_score: float, child: Genome) -> List[float]:
    """[parent_score, 8 diff coordinates, 7 signed coordinates]. The paper's readout
    uses the first 9 (LinearReadout(use=range(9))); lab 10.05 uses all 16."""
    ps, cs = render(parent), render(child)
    return [parent_score] + diff_features(ps, cs) + signed_features(ps, cs)


@dataclass
class TrainingSet:
    X: np.ndarray
    y: np.ndarray            # child mean letter accuracy on fit x 4 seeds (the label)
    y_rate: np.ndarray       # child solve rate on the same runs (reported, not fit)
    ops: List[str]
    parents: List[Genome]
    children: List[Genome]
    runs: int


def scaffold_edits(ev: Evaluator, n: int = 96, seed: int = 0, walk: int = 8,
                   ops: Optional[Sequence[str]] = None) -> TrainingSet:
    """n random (parent, edit) pairs, parent and child each run on fit x 4 seeds.

    The paper labels edits by solve rate. Our scaffold parents are random
    programs and most solve nothing on 16 ciphers, so solve rate is zero for
    most labels; we fit the readout to mean letter accuracy (partial credit)
    and keep the solve rate alongside for reporting.

    Parents are random walks of 0..`walk` edits from the baseline. The walk
    depth should match how far the search actually travels (~8-10 accepted
    edits at our budgets): lab 10.05 shows a readout trained on shallow walks
    (<= 5) learns that adding a function hurts, and then loses to the ablation.
    """
    rng = np.random.default_rng(10_000 + seed)
    fit = Scorer(ev, "fit", FIT_SEEDS, caller="budget-rsi-train", charge_repeats=False)
    X, y, yr, names, parents, children = [], [], [], [], [], []
    while len(X) < n:
        parent = random_genome(rng, int(rng.integers(0, walk + 1)))
        cands = applicable(parent, ops)
        if not cands:
            continue
        op = cands[int(rng.integers(len(cands)))]
        child = op.apply(parent)
        pa = fit(parent).mean_acc
        X.append(edit_row(parent, pa, child))
        c = fit(child)
        y.append(c.mean_acc)
        yr.append(c.rate)
        names.append(op.name)
        parents.append(parent)
        children.append(child)
    runs = len(fit.cache) * fit.cost()
    return TrainingSet(np.array(X), np.array(y), np.array(yr), names, parents, children, runs)


@dataclass
class Node:
    genome: Genome
    parent: Optional[int]
    solved: int
    total: int
    mean_acc: float
    op: str = "root"
    children: List[int] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.solved / self.total


class HGMTree:
    def __init__(self):
        self.nodes: List[Node] = []

    def add(self, node: Node) -> int:
        self.nodes.append(node)
        i = len(self.nodes) - 1
        if node.parent is not None:
            self.nodes[node.parent].children.append(i)
        return i

    def clade(self, i: int) -> List[int]:
        out, stack = [], [i]
        while stack:
            j = stack.pop()
            out.append(j)
            stack.extend(self.nodes[j].children)
        return out

    def select_parent(self, rng: np.random.Generator) -> int:
        """Thompson sampling on clade-level steering successes and failures."""
        best, best_theta = 0, -1.0
        for i in range(len(self.nodes)):
            cl = self.clade(i)
            s = sum(self.nodes[j].solved for j in cl)
            f = sum(self.nodes[j].total - self.nodes[j].solved for j in cl)
            theta = rng.beta(1 + s, 1 + f)  # clade metaproductivity: pooled counts of the node and its descendants
            if theta > best_theta:
                best, best_theta = i, theta
        return best

    def best(self) -> Node:
        return max(self.nodes, key=lambda n: (n.solved, n.mean_acc))


def run(ev: Evaluator, budget_runs: int, seed: int, selector: str = "readout",
        readout: Optional[LinearReadout] = None, k: int = 6, start: Genome = BASELINE, log=None) -> dict:
    rng = np.random.default_rng(seed)
    budget = Budget(budget_runs)
    steer = Scorer(ev, "steering", (0,), budget, caller=f"budget-rsi-{selector}")
    tree = HGMTree()
    s0 = steer(start)
    tree.add(Node(start, None, s0.solved, s0.total, s0.mean_acc))
    expansions, picks = 0, []
    step_cost = steer.cost() * (k if selector == "oracle" else 1)
    while budget.can_afford(step_cost):
        pi = tree.select_parent(rng)
        parent = tree.nodes[pi]
        cands = [op for op in applicable(parent.genome) if UNIFORM_PRIOR.get(op.name)]
        if not cands:
            continue
        chosen = rng.choice(len(cands), size=min(k, len(cands)), replace=False)
        props = [(cands[j].name, cands[j].apply(parent.genome)) for j in chosen]
        if selector == "readout":
            X = [edit_row(parent.genome, parent.mean_acc, g) for _, g in props]
            pred = readout.predict(np.array(X))
            order = [int(np.argmax(pred))]
        elif selector == "oracle":
            order = list(range(len(props)))
        else:  # parent_rate ablation: every sibling has the same score
            order = [int(rng.integers(len(props)))]
        results = [(props[j][0], props[j][1], steer(props[j][1])) for j in order]
        name, g, sc = max(results, key=lambda t: t[2].key)
        tree.add(Node(g, pi, sc.solved, sc.total, sc.mean_acc, op=name))
        picks.append({"parent": pi, "op": name, "rate": sc.rate, "parent_rate": parent.rate})
        expansions += 1
        if log:
            log(f"  x{expansions:02d} parent#{pi:<2d} ({parent.rate:.3f}) --{name:>14s}--> {sc.rate:.3f}")
    best = tree.best()
    return {"selector": selector, "seed": seed, "expansions": expansions, "runs_spent": budget.spent,
            "best": best.genome, "best_rate": best.rate, "picks": picks,
            "tree": [{"genome": n.genome.short(), "parent": n.parent, "rate": n.rate, "op": n.op} for n in tree.nodes]}


def load_or_build_training(ev: Evaluator, n: int = 96, seed: int = 0, walk: int = 8) -> TrainingSet:
    """The scaffold training set, cached in results/ so later labs reuse the same 96 edits."""
    import json
    import os

    from ..loop import RESULTS
    path = os.path.join(RESULTS, f"budget_training_n{n}_s{seed}_w{walk}.json")
    if os.path.exists(path):
        with open(path) as f:
            d = json.load(f)
        return TrainingSet(np.array(d["X"]), np.array(d["y"]), np.array(d["y_rate"]), d["ops"],
                           [Genome.from_dict(g) for g in d["parents"]],
                           [Genome.from_dict(g) for g in d["children"]], d["runs"])
    ts = scaffold_edits(ev, n, seed, walk)
    os.makedirs(RESULTS, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"X": ts.X.tolist(), "y": ts.y.tolist(), "y_rate": ts.y_rate.tolist(), "ops": ts.ops,
                   "parents": [g.to_dict() for g in ts.parents], "children": [g.to_dict() for g in ts.children],
                   "runs": ts.runs}, f)
    return ts


def paper_readout(ts: TrainingSet) -> LinearReadout:
    return LinearReadout(use=range(len(READOUT_FEATURES))).fit(ts.X, ts.y)


def extended_readout(ts: TrainingSet) -> LinearReadout:
    return LinearReadout(use=range(len(EXTENDED_FEATURES))).fit(ts.X, ts.y)
