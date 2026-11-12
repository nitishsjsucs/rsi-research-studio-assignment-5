"""Lab 10.06 · Run Naive RSI vs SO-RSI.

Both arms start from the same baseline program, sample edits from the same
symptom-driven prior, use the same acceptance rule and the same budget of
steering instance-runs. SO-RSI additionally watches its own trace for
anomalies, buys probes from that same budget, and lets an inquiry memory
re-weight its proposals. Held-out is unsealed once, at the end.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import so_rsi  # noqa: E402
from cipherlab.program import render  # noqa: E402


def main():
    a = _lab.args(default_seeds=3, budget=40)
    steps = 12 if a.quick else a.budget
    budget = 48 * steps
    _lab.banner("10.06", "Run the SO-RSI demo", "Does asking WHY before patching beat patching the symptom, at the same cost?")
    clock = _lab.Clock()
    res = {"naive": [], "so-rsi": []}
    with Evaluator() as ev:
        for seed in range(a.seeds):
            for arm, so in (("naive", False), ("so-rsi", True)):
                _lab.section(f"seed {seed} · {arm}")
                r = so_rsi.run(ev, budget, seed, so, log=print if (seed == 0) else None)
                res[arm].append(r)
                print(f"  -> final steering {r['final_rate']:.3f}  {r['final'].short()}")
                print(f"     rounds={r['rounds']} accepted={r['accepted']} anomalies={r['anomaly_counts']} probes={len(r['diagnoses'])} runs={r['runs_spent']}")
        _lab.section("Held-out report (unsealed once, here)")
        ev.unseal()
        for runs in res.values():
            for r in runs:
                r["heldout"] = ev.run(render(r["final"]), "heldout", (0, 1), caller="10.06-final").solve_rate
        ev.seal()
    rows = []
    for arm, runs in res.items():
        ms, ss = _lab.mean_sd(r["final_rate"] for r in runs)
        mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
        thrash = np.mean([r["anomaly_counts"].get("opposing", 0) + r["anomaly_counts"].get("recurrence", 0) for r in runs])
        wasted = np.mean([r["rounds"] - r["accepted"] for r in runs])
        rows.append((arm, f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}", thrash, wasted,
                     np.mean([len(r["diagnoses"]) for r in runs])))
    _lab.table(rows, ["arm", "steering", "held-out", "thrash anomalies", "rejected edits", "probes"],
               {"thrash anomalies": "{:.1f}", "rejected edits": "{:.1f}", "probes": "{:.1f}"})
    paired = [s["heldout"] - n["heldout"] for s, n in zip(res["so-rsi"], res["naive"])]
    print(f"\n  paired held-out difference (so-rsi - naive) per seed: {[round(x, 3) for x in paired]}")
    print(f"  mean {np.mean(paired):+.3f}. The paper reports +21.8 points on Lean 4; this is one domain, {a.seeds} seeds, {budget} runs.")
    series = []
    for i, (arm, runs) in enumerate(res.items()):
        curve = runs[0]["curve"]
        series.append((arm, [48 * (k + 2) for k in range(len(curve))], curve, [_lab.NEUTRAL, _lab.SERIES[0]][i]))
    _lab.line_chart(os.path.join(_lab.FIGURES, "10_06_so_rsi_curves.png"),
                    "Naive RSI vs SO-RSI: best steering solve rate by step (seed 0)", series, xlabel="steering runs (edits only)")
    save_json("10_06_so_rsi.json", res)
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
