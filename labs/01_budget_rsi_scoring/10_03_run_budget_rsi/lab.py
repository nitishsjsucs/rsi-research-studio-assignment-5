"""Lab 10.03 · Run Budget RSI on real program edits.

1. Build the readout's training data: 96 scaffold edits, each parent and child
   run on the 16-cipher fit split x 4 seeds (the paper's "four evaluations of a
   16-instance fit split").
2. Fit the linear readout on [parent_score, 8 diff coordinates].
3. Run the Huxley-Godel Machine tree search three ways at one steering budget:
   readout (the method), parent_rate (the ablation), oracle (evaluate all 6
   proposals: 6x the cost per step).
4. Unseal the held-out split once, at the end, and report every arm on it.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import budget_rsi as B  # noqa: E402
from cipherlab.program import render  # noqa: E402


def main():
    a = _lab.args(default_seeds=3, budget=40)
    steps = 12 if a.quick else a.budget
    budget = 48 * steps
    _lab.banner("10.03", "Run Budget RSI", "Does scoring edits before running them buy better programs per evaluation?")
    clock = _lab.Clock()
    with Evaluator() as ev:
        _lab.section("1. Training data for the readout (96 scaffold edits)")
        ts = B.load_or_build_training(ev, 96, 0)
        print(f"  {len(ts.y)} labelled edits, {ts.runs} fit-split instance-runs (one-time cost)")
        print(f"  label = child mean letter accuracy on fit x 4 seeds: mean {ts.y.mean():.3f}, "
              f"range {ts.y.min():.3f}-{ts.y.max():.3f}; solve-rate labels > 0 for only {np.mean(ts.y_rate > 0):.0%}")
        ro = B.paper_readout(ts)
        print(f"  readout fit on {len(B.READOUT_FEATURES)} features: {', '.join(B.READOUT_FEATURES)}")

        _lab.section(f"2. Tree search at {budget} steering runs per arm ({a.seeds} seeds)")
        arms = {"readout": [], "parent_rate": [], "oracle": []}
        for seed in range(a.seeds):
            for sel in arms:
                r = B.run(ev, budget, seed, sel, ro, k=6)
                arms[sel].append(r)
                print(f"  seed {seed} {sel:12s} expansions={r['expansions']:2d} best steering={r['best_rate']:.3f}  {r['best'].short()}")
        print("\n  one expansion, shown in full (readout arm, seed 0, first 8):")
        for p in arms["readout"][0]["picks"][:8]:
            print(f"    parent #{p['parent']:<2d} ({p['parent_rate']:.3f})  --{p['op']:>14s}-->  {p['rate']:.3f}")

        _lab.section("3. Held-out report (unsealed once, here)")
        ev.unseal()
        rows = []
        for sel, runs in arms.items():
            for r in runs:
                r["heldout"] = ev.run(render(r["best"]), "heldout", (0, 1), caller="10.03-final").solve_rate
            ms, ss = _lab.mean_sd(r["best_rate"] for r in runs)
            mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
            rows.append((sel, np.mean([r["expansions"] for r in runs]), f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}",
                         np.mean([r["runs_spent"] for r in runs])))
        ev.seal()
        _lab.table(rows, ["selector", "expansions", "steering best", "held-out", "runs"], {"expansions": "{:.0f}", "runs": "{:.0f}"})

        _lab.section("4. Cost of an expansion")
        full = 6 * 48
        print(f"  evaluate all 6 proposals: {full} runs per expansion")
        print(f"  readout: rank 6 in microseconds, evaluate 1: 48 runs per expansion ({1 - 48 / full:.0%} less)")
        print(f"  one-time readout training: {ts.runs} fit runs, amortised over every expansion of every run")

        _lab.line_chart(os.path.join(_lab.FIGURES, "10_03_budget_rsi_curves.png"),
                        "Budget RSI: best steering solve rate vs runs spent (seed 0)",
                        [(sel, [48 * (k + 1) * (6 if sel == "oracle" else 1) + 48 for k in range(len(runs[0]["picks"]))],
                          list(np.maximum.accumulate([p["rate"] for p in runs[0]["picks"]])), _lab.SERIES[i])
                         for i, (sel, runs) in enumerate(arms.items())])
        save_json("10_03_budget_rsi.json", {k: [{x: r[x] for x in ("seed", "best", "best_rate", "heldout", "expansions", "runs_spent")}
                                                for r in v] for k, v in arms.items()})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
