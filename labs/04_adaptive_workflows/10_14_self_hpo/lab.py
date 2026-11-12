"""Lab 10.14 · Simulate Self-HPO alternation.

Three schedules from the same starting program and budget:
alternate (H,P,H,P...), harness_only, policy_only. The paper's synergy claim
is that the joint gain exceeds the sum of the separate gains; we compute both
sides of that inequality from our runs.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import self_hpo  # noqa: E402
from cipherlab.program import render  # noqa: E402


def main():
    a = _lab.args(default_seeds=3, budget=40)
    budget = 48 * (12 if a.quick else a.budget)
    _lab.banner("10.14", "Self-HPO alternation", "Is optimising harness and policy together worth more than the sum of each alone?")
    clock = _lab.Clock()
    print(f"  start program: {self_hpo.START.short()}")
    print(f"  harness edits: {', '.join(self_hpo.HARNESS_OPS)}")
    print("  policy weights: word_weight, temp0, smoothing (log-normal evolution strategy)")
    res = {s: [] for s in ("alternate", "harness_only", "policy_only")}
    with Evaluator() as ev:
        for seed in range(a.seeds):
            for sch in res:
                if seed == 0:
                    _lab.section(f"seed 0 · {sch}")
                r = self_hpo.run(ev, budget, seed, sch, log=print if seed == 0 else None)
                res[sch].append(r)
                if seed:
                    print(f"  seed {seed} {sch:12s} {r['start_rate']:.3f} -> {r['final_rate']:.3f}  {r['final'].short()}")
        ev.unseal()
        start_h = ev.run(render(self_hpo.START), "heldout", (0, 1), caller="10.14-final").solve_rate
        for runs in res.values():
            for r in runs:
                r["heldout"] = ev.run(render(r["final"]), "heldout", (0, 1), caller="10.14-final").solve_rate
        ev.seal()
    _lab.section("Results")
    rows = []
    gain = {}
    for sch, runs in res.items():
        ms, ss = _lab.mean_sd(r["final_rate"] for r in runs)
        mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
        gain[sch] = mh - start_h
        rows.append((sch, f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}", gain[sch]))
    _lab.table(rows, ["schedule", "steering", "held-out", "held-out gain"], {"held-out gain": "{:+.3f}"})
    print(f"\n  start program held-out: {start_h:.3f}")
    print(f"  synergy check: joint gain {gain['alternate']:+.3f} vs harness-only + policy-only "
          f"{gain['harness_only'] + gain['policy_only']:+.3f} -> "
          f"{'joint > sum (synergy)' if gain['alternate'] > gain['harness_only'] + gain['policy_only'] else 'no synergy at this scale'}")
    names = list(res)
    _lab.bar_chart(os.path.join(_lab.FIGURES, "10_14_self_hpo.png"), "Self-HPO schedules: held-out solve rate",
                   names, [np.mean([r["heldout"] for r in res[n]]) for n in names],
                   [np.std([r["heldout"] for r in res[n]]) for n in names],
                   colors=[_lab.SERIES[0], _lab.SERIES[1], _lab.SERIES[2]], note=f"start program held-out = {start_h:.2f}; {a.seeds} seeds")
    save_json("10_14_self_hpo.json", {"start_heldout": start_h, **res})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
