"""Finale · Three RSI methods, one problem, one budget.

Budget RSI, SO-RSI and SwarmRSI (plus the first-order naive loop as the
reference) each improve the same baseline cipher breaker with the same
number of steering instance-runs, over the same seeds. Held-out stays sealed
until every search has finished; the auditor then checks the evaluator's
ledger. Each final program is scored on all five RSIGym benchmarks and
summarised with the RSI-Index.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.audit import audit, print_audit  # noqa: E402
from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import budget_rsi, rsigym, so_rsi, swarm_rsi  # noqa: E402
from cipherlab.program import BASELINE, render  # noqa: E402


def main():
    a = _lab.args(default_seeds=3, budget=40)
    steps = 12 if a.quick else a.budget
    budget = 48 * steps
    _lab.banner("Finale", "Three RSI methods, one budget",
                "Under matched compute, which improvement procedure produces the best cipher breaker on unseen text?")
    clock = _lab.Clock()
    arms = {"naive (first-order)": [], "Budget RSI": [], "SO-RSI": [], "SwarmRSI": []}
    with Evaluator() as ev:
        ro = budget_rsi.paper_readout(budget_rsi.load_or_build_training(ev, 96, 0))
        for seed in range(a.seeds):
            runs = {
                "naive (first-order)": lambda: so_rsi.run(ev, budget, seed, False),
                "Budget RSI": lambda: budget_rsi.run(ev, budget, seed, "readout", ro, k=6),
                "SO-RSI": lambda: so_rsi.run(ev, budget, seed, True),
                "SwarmRSI": lambda: swarm_rsi.run(ev, budget, seed),
            }
            for name, fn in runs.items():
                r = fn()
                g = r.get("final") or r.get("best")
                rate = r.get("final_rate", r.get("best_rate"))
                arms[name].append({"seed": seed, "program": g, "steering": rate, "runs_spent": r["runs_spent"]})
                print(f"  seed {seed} {name:20s} steering={rate:.3f} runs={r['runs_spent']}  {g.short()}", flush=True)
        t_final = time.time()
        _lab.section("Held-out and five-benchmark report (unsealed once, here)")
        ev.unseal()
        gym = rsigym.RSIGym(ev, "joint", 10 ** 9)
        initial = {b: gym.evaluate(BASELINE, b, seeds=(0, 1), charge=False).rate for b in rsigym.BENCHMARKS}
        for runs in arms.values():
            for r in runs:
                r["heldout"] = ev.run(render(r["program"]), "heldout", (0, 1), caller="finale-heldout").solve_rate
                final = {b: gym.evaluate(r["program"], b, seeds=(0, 1), charge=False).rate for b in rsigym.BENCHMARKS}
                r["benchmarks"] = final
                r["rsi_index"] = rsigym.rsi_index(initial, final)
        ev.seal()
        _lab.section("Audit")
        ok = print_audit(audit(ev.ledger, arms, t_final))

    _lab.section("Results")
    rows = []
    for name, runs in arms.items():
        ms, ss = _lab.mean_sd(r["steering"] for r in runs)
        mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
        mi, si = _lab.mean_sd(r["rsi_index"] for r in runs)
        rows.append((name, f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}", f"{mi:.3f} ± {si:.3f}",
                     np.mean([r["runs_spent"] for r in runs])))
    _lab.table(rows, ["method", "steering", "held-out (Frankenstein)", "RSI-Index (5 benchmarks)", "runs"], {"runs": "{:.0f}"})
    _lab.section("Best program found, per method")
    for name, runs in arms.items():
        best = max(runs, key=lambda r: r["heldout"])
        print(f"  {name:20s} {best['heldout']:.3f}  {best['program'].short()}")
    base_h = initial["frankenstein"]
    print(f"\n  baseline program held-out: {base_h:.3f}; audit {'passed' if ok else 'FAILED'}")
    names = list(arms)
    _lab.bar_chart(os.path.join(_lab.FIGURES, "finale_heldout.png"),
                   "Held-out solve rate at matched compute (Frankenstein ciphers)",
                   names, [np.mean([r["heldout"] for r in arms[n]]) for n in names],
                   [np.std([r["heldout"] for r in arms[n]]) for n in names],
                   colors=[_lab.NEUTRAL, _lab.SERIES[0], _lab.SERIES[1], _lab.SERIES[2]],
                   note=f"{a.seeds} seeds x {budget} steering runs per method; error bars = 1 sd; baseline = {base_h:.2f}")
    save_json("finale_showdown.json", {"budget": budget, "initial": initial, "arms": arms})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
