"""Lab 10.13 · Simulate the RSIFlow meta-agent.

Static workflow (PROPOSE -> EVALUATE -> INTEGRATE) vs the adaptive workflow
whose meta-agent rewires itself from execution feedback. Same proposer, same
budget, same seeds. We print every workflow change and every rule's final
usefulness, including rules the meta-agent switched off.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import budget_rsi, rsiflow  # noqa: E402
from cipherlab.program import render  # noqa: E402


def main():
    a = _lab.args(default_seeds=3, budget=40)
    budget = 48 * (12 if a.quick else a.budget)
    _lab.banner("10.13", "RSIFlow meta-agent", "Does a workflow that rewires itself around its bottleneck beat a fixed one?")
    clock = _lab.Clock()
    res = {"static": [], "adaptive": []}
    with Evaluator() as ev:
        ro = budget_rsi.paper_readout(budget_rsi.load_or_build_training(ev, 96, 0))
        for seed in range(a.seeds):
            for name, ad in (("static", False), ("adaptive", True)):
                if seed == 0 and ad:
                    _lab.section("seed 0 · adaptive workflow changes")
                r = rsiflow.run(ev, budget, seed, ad, readout=ro, log=print if (seed == 0 and ad) else None)
                res[name].append(r)
                print(f"  seed {seed} {name:9s} final={r['final_rate']:.3f}  {r['final'].short()}")
        _lab.section("Meta-agent rules after each adaptive run")
        for r in res["adaptive"]:
            print("  " + "; ".join(f"{n}: {'on' if v['enabled'] else 'OFF'} x{v['activations']} u={v['usefulness']:+.3f}" for n, v in r["rules"].items()))
        ev.unseal()
        for runs in res.values():
            for r in runs:
                r["heldout"] = ev.run(render(r["final"]), "heldout", (0, 1), caller="10.13-final").solve_rate
        ev.seal()
    _lab.section("Results")
    rows = []
    for name, runs in res.items():
        ms, ss = _lab.mean_sd(r["final_rate"] for r in runs)
        mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
        rows.append((name, f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}", np.mean([r["steps"] for r in runs])))
    _lab.table(rows, ["workflow", "steering", "held-out", "edit steps"], {"edit steps": "{:.1f}"})
    _lab.line_chart(os.path.join(_lab.FIGURES, "10_13_rsiflow.png"), "RSIFlow (seed 0): steering solve rate by step",
                    [(n, list(range(1, len(res[n][0]["curve"]) + 1)), res[n][0]["curve"], c)
                     for n, c in (("static", _lab.NEUTRAL), ("adaptive", _lab.SERIES[0]))], xlabel="edit step")
    save_json("10_13_rsiflow.json", res)
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
