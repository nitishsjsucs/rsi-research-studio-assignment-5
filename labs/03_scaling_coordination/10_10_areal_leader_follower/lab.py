"""Lab 10.10 · Simulate leader-follower coordination (AReaL-RSI).

One leader, two researchers, conditional memory. Three variants share one
budget per seed:

    conditional   replicate before sharing (the method)
    share_all     share any gain at once (no replication)
    independent   no leader, no sharing

The interesting numbers are the final score AND how many findings each
variant turned into shared team facts: conditional pays a second-seed run
for every finding it shares; share_all pays nothing and shares everything.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import areal  # noqa: E402
from cipherlab.program import render  # noqa: E402


def main():
    a = _lab.args(default_seeds=3, budget=40)
    budget = 48 * (12 if a.quick else a.budget)
    _lab.banner("10.10", "Leader-follower coordination", "Does sharing only replicated findings beat sharing everything, or sharing nothing?")
    clock = _lab.Clock()
    res = {m: [] for m in ("conditional", "share_all", "independent")}
    with Evaluator() as ev:
        for seed in range(a.seeds):
            for mode in res:
                if seed == 0:
                    _lab.section(f"seed 0 · {mode}")
                r = areal.run(ev, budget, seed, mode, log=print if seed == 0 else None)
                res[mode].append(r)
                print(f"  seed {seed} {mode:12s} final={r['final_rate']:.3f} campaigns={r['campaigns']} "
                      f"resolved={r['resolved']} unresolved={r['unresolved']}  {r['final'].short()}")
        _lab.section("Conditional memory after seed 0")
        for e in res["conditional"][0]["memory"]:
            print(f"  c{e['campaign']} {e['researcher']}/{e['orientation']:10s} {e['status']:10s} gain={e['gain']:+.3f} via {e['ops']}")
        print(f"  orientation values: { {k: round(v, 3) for k, v in res['conditional'][0]['values'].items()} }")
        print(f"  skills retired by review: { {k: v for k, v in res['conditional'][0]['skills_retired'].items() if v} }")
        ev.unseal()
        for runs in res.values():
            for r in runs:
                r["heldout"] = ev.run(render(r["final"]), "heldout", (0, 1), caller="10.10-final").solve_rate
        ev.seal()
    _lab.section("Results")
    rows = []
    for mode, runs in res.items():
        ms, ss = _lab.mean_sd(r["final_rate"] for r in runs)
        mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
        rows.append((mode, f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}", np.mean([r["campaigns"] for r in runs]),
                     np.mean([r["resolved"] for r in runs])))
    _lab.table(rows, ["variant", "steering", "held-out", "campaigns", "shared findings"],
               {"campaigns": "{:.1f}", "shared findings": "{:.1f}"})
    names = list(res)
    _lab.bar_chart(os.path.join(_lab.FIGURES, "10_10_areal_heldout.png"), "AReaL-RSI variants: held-out solve rate",
                   names, [np.mean([r["heldout"] for r in res[n]]) for n in names],
                   [np.std([r["heldout"] for r in res[n]]) for n in names],
                   colors=[_lab.SERIES[0], _lab.SERIES[1], _lab.NEUTRAL], note=f"{a.seeds} seeds, {budget} runs each")
    save_json("10_10_areal.json", res)
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
