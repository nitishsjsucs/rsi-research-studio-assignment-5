"""Lab 10.04 · Analyse the scoring mechanism.

No new search here: we open up the readout trained in 10.03.

1. Show one real diff and its 8 coordinates, so the features are concrete.
2. Rank features by standardised coefficient.
3. Cross-validate: how well does the readout rank edits it has not seen?
4. Answer the course's two questions with numbers: what if 8 features become
   4, and what if there are fewer training edits?
5. Find the blind spot: edits whose diffs have the same shape (iters_up vs
   iters_down) get the same score, whatever they do.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.edits import BY_NAME  # noqa: E402
from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import budget_rsi as B  # noqa: E402
from cipherlab.program import FEATURE_NAMES, Genome, diff_features, render, unified_diff  # noqa: E402


def cv_delta_corr(X, y, use, folds=4, n=None, seed=0):
    """Correlation between predicted and actual (child - parent) on held-out folds."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))[: n or len(y)]
    X, y = X[idx], y[idx]
    pred = np.zeros(len(y))
    fold = np.arange(len(y)) % folds
    for f in range(folds):
        te = fold == f
        m = B.LinearReadout(use=use).fit(X[~te], y[~te])
        pred[te] = m.predict(X[te])
    return float(np.corrcoef(pred - X[:, 0], y - X[:, 0])[0, 1])


def main():
    _lab.args(default_seeds=1)
    _lab.banner("10.04", "Analyse the scoring mechanism", "Which parts of a diff predict a better program, and what can a diff not see?")
    clock = _lab.Clock()
    with Evaluator() as ev:
        ts = B.load_or_build_training(ev, 96, 0)

    _lab.section("1. One real edit, read as a diff")
    p = Genome(ngram=3, iters=2000)
    c = BY_NAME["add_words"].apply(p)
    for line in unified_diff(render(p), render(c)):
        print("   " + line)
    print("  coordinates: " + ", ".join(f"{n}={v:g}" for n, v in zip(FEATURE_NAMES, diff_features(render(p), render(c)))))

    _lab.section("2. Feature importance (standardised ridge coefficients)")
    ro = B.paper_readout(ts)
    ranked = sorted(zip(B.READOUT_FEATURES, ro.coefficients), key=lambda t: -abs(t[1]))
    _lab.table([(n, w) for n, w in ranked], ["feature", "coefficient"], {"coefficient": "{:+.4f}"})

    _lab.section("3. Does it rank unseen edits? (4-fold cross-validation)")
    full = cv_delta_corr(ts.X, ts.y, range(9))
    print(f"  corr(predicted gain, actual gain) on held-out folds: {full:+.3f}")

    _lab.section("4a. 8 diff features vs 4")
    four = [0, 1, 2, 4, 6]  # parent, lines_added, lines_deleted, defs_added, imports_changed
    rows = [("parent + 8 diff coordinates", 9, full),
            ("parent + 4 (added, deleted, defs_added, imports)", 5, cv_delta_corr(ts.X, ts.y, four)),
            ("parent only (the ablation)", 1, cv_delta_corr(ts.X, ts.y, [0]))]
    _lab.table(rows, ["features", "k", "cv corr(gain)"], {"cv corr(gain)": "{:+.3f}"})

    _lab.section("4b. Fewer training edits")
    rows = []
    for n in (12, 24, 48, 96):
        vals = [cv_delta_corr(ts.X, ts.y, range(9), n=n, seed=s) for s in range(5)]
        rows.append((n, float(np.nanmean(vals)), float(np.nanstd(vals))))
    _lab.table(rows, ["edits", "cv corr(gain)", "sd over 5 draws"], {"cv corr(gain)": "{:+.3f}", "sd over 5 draws": "{:.3f}"})

    _lab.section("5. The blind spot: same diff shape, opposite meaning")
    by_op = {}
    for op, x, y in zip(ts.ops, ts.X, ts.y):
        by_op.setdefault(op, []).append((ro.predict(x[None])[0] - x[0], y - x[0]))
    rows = []
    for op in ("iters_up", "iters_down", "restarts_up", "restarts_down", "ngram_up", "ngram_down",
               "temp_up", "temp_down", "add_words", "remove_words", "use_anneal", "use_hill"):
        if op in by_op:
            pr, ac = zip(*by_op[op])
            rows.append((op, len(pr), float(np.mean(pr)), float(np.mean(ac))))
    _lab.table(rows, ["edit", "n", "predicted gain", "actual gain"], {"predicted gain": "{:+.4f}", "actual gain": "{:+.4f}"})
    g = Genome(ngram=3, iters=2000)
    up, down = BY_NAME["iters_up"].apply(g), BY_NAME["iters_down"].apply(g)
    fu, fd = diff_features(render(g), render(up)), diff_features(render(g), render(down))
    print(f"\n  iters_up   coordinates: {fu}")
    print(f"  iters_down coordinates: {fd}")
    print(f"  identical: {fu == fd}. A diff-shape readout cannot tell 'search more' from 'search less'.")
    print("  Lab 10.05 adds signed coordinates read from the same diff and tests whether that helps.")
    save_json("10_04_analysis.json", {"coefficients": ranked, "cv_corr": full})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
