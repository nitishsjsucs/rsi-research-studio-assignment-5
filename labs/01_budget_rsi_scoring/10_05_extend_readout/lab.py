"""Lab 10.05 · Extend the readout to your own edits.

Two extensions, both still "score before running":

A. Readout+: seven signed coordinates read from the same diff text, the
   log2 ratio of each tunable constant (ITERATIONS 1000 -> 2000 is +1).
   This targets the blind spot found in 10.04. Compared at one budget:
   paper readout vs readout+ vs parent-rate ablation, held-out at the end.

B. A new edit type: compound edits (two operators applied at once, the shape
   an LLM patch often has). Train on single edits only, then ask: does the
   readout still rank 24 unseen compound edits? (Each compound edit is
   labelled on the fit split x 4 seeds, exactly like the training edits.)

C. The training distribution. The same paper readout, trained on 96 edits of
   SHALLOW parents (random walks of <= 5 edits instead of <= 8), run through
   the same tree search. A readout is only as good as the match between the
   edits it was trained on and the edits it is asked to rank.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.edits import UNIFORM_PRIOR, applicable, random_genome  # noqa: E402
from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import Scorer, save_json  # noqa: E402
from cipherlab.methods import budget_rsi as B  # noqa: E402
from cipherlab.program import render  # noqa: E402


def compound_edits(ev, n, seed=99):
    rng = np.random.default_rng(seed)
    fit = Scorer(ev, "fit", B.FIT_SEEDS, caller="10.05-compound", charge_repeats=False)
    X, y, names = [], [], []
    while len(X) < n:
        parent = random_genome(rng, int(rng.integers(0, 6)))
        ops = [op for op in applicable(parent) if UNIFORM_PRIOR[op.name]]
        if len(ops) < 2:
            continue
        i, j = rng.choice(len(ops), 2, replace=False)
        mid = ops[i].apply(parent)
        second = ops[j].apply(mid) if ops[j].apply(mid) is not None else None
        if second is None:
            continue
        X.append(B.edit_row(parent, fit(parent).mean_acc, second))
        y.append(fit(second).mean_acc)
        names.append(f"{ops[i].name}+{ops[j].name}")
    return np.array(X), np.array(y), names


def main():
    a = _lab.args(default_seeds=3, budget=40, compound=24)
    steps = 12 if a.quick else a.budget
    n_comp = 8 if a.quick else a.compound
    _lab.banner("10.05", "Extend the readout", "Do signed coordinates fix the blind spot, and does the readout transfer to compound edits?")
    clock = _lab.Clock()
    with Evaluator() as ev:
        ts = B.load_or_build_training(ev, 96, 0)
        paper, plus = B.paper_readout(ts), B.extended_readout(ts)

        _lab.section("A1. Readout+ coefficients on the signed coordinates")
        _lab.table([(n, w) for n, w in zip(B.EXTENDED_FEATURES[9:], plus.coefficients[9:])],
                   ["signed coordinate", "coefficient"], {"coefficient": "{:+.4f}"})

        _lab.section(f"A2. Tree search with each readout ({48 * steps} runs per arm, {a.seeds} seeds)")
        arms = {"paper readout": (paper, "readout"), "readout+": (plus, "readout"), "parent_rate": (None, "parent_rate")}
        res = {k: [] for k in arms}
        for seed in range(a.seeds):
            for name, (model, sel) in arms.items():
                r = B.run(ev, 48 * steps, seed, sel, model, k=6)
                res[name].append(r)
                print(f"  seed {seed} {name:14s} best steering={r['best_rate']:.3f}  {r['best'].short()}")
        ev.unseal()
        rows = []
        for name, runs in res.items():
            for r in runs:
                r["heldout"] = ev.run(render(r["best"]), "heldout", (0, 1), caller="10.05-final").solve_rate
            ms, ss = _lab.mean_sd(r["best_rate"] for r in runs)
            mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
            rows.append((name, f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}"))
        ev.seal()
        _lab.table(rows, ["selector", "steering best", "held-out"])
        names = list(res)
        _lab.bar_chart(os.path.join(_lab.FIGURES, "10_05_readout_heldout.png"),
                       "Budget RSI selectors: held-out solve rate of the best program",
                       names, [np.mean([r["heldout"] for r in res[n]]) for n in names],
                       [np.std([r["heldout"] for r in res[n]]) for n in names],
                       colors=[_lab.SERIES[0], _lab.SERIES[2], _lab.NEUTRAL],
                       note=f"{a.seeds} seeds, {48 * steps} steering runs per arm; error bars = 1 sd")

        _lab.section(f"B. Transfer to {n_comp} compound (two-operator) edits")
        Xc, yc, cn = compound_edits(ev, n_comp)
        for label, m in (("paper readout", paper), ("readout+", plus)):
            pred = m.predict(Xc)
            corr = float(np.corrcoef(pred - Xc[:, 0], yc - Xc[:, 0])[0, 1])
            top = np.argsort(-pred)[: max(1, n_comp // 4)]
            print(f"  {label:14s} corr(pred gain, gain) = {corr:+.3f};  mean gain of its top quarter = "
                  f"{np.mean(yc[top] - Xc[top, 0]):+.4f} vs all = {np.mean(yc - Xc[:, 0]):+.4f}")
        best = int(np.argmax(yc - Xc[:, 0]))
        print(f"  best compound edit in the sample: {cn[best]} ({yc[best] - Xc[best, 0]:+.4f})")
        _lab.section("C. Training distribution: parents from shallow walks (<= 5 edits) vs deep (<= 8)")
        shallow_ts = B.load_or_build_training(ev, 96, 0, walk=5)
        shallow = B.paper_readout(shallow_ts)
        names9 = B.READOUT_FEATURES
        print("  coefficient on defs_added: deep-walk readout "
              f"{paper.coefficients[names9.index('defs_added')]:+.4f}, shallow-walk readout "
              f"{shallow.coefficients[names9.index('defs_added')]:+.4f}")
        res["readout (shallow training)"] = [B.run(ev, 48 * steps, seed, "readout", shallow, k=6) for seed in range(a.seeds)]
        ev.unseal()  # searches are done; held-out opens for the report only
        for seed, r in enumerate(res["readout (shallow training)"]):
            r["heldout"] = ev.run(render(r["best"]), "heldout", (0, 1), caller="10.05-final").solve_rate
            print(f"  seed {seed} shallow-trained readout best steering={r['best_rate']:.3f} held-out={r['heldout']:.3f}  {r['best'].short()}")
        ev.seal()
        rows = []
        for name in ("paper readout", "readout (shallow training)", "parent_rate"):
            mh, sh = _lab.mean_sd(r["heldout"] for r in res[name])
            rows.append((name, f"{mh:.3f} ± {sh:.3f}"))
        _lab.table(rows, ["selector", "held-out"])
        save_json("10_05_extend.json", {k: [{x: r[x] for x in ("seed", "best", "best_rate", "heldout")} for r in v] for k, v in res.items()})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
