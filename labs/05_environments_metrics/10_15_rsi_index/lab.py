"""Lab 10.15 · Calculate the RSI-Index (RSIGym).

1. The worked example from the course page, computed both ways: with the
   formula as printed, (initial - final)/(ideal - initial), and corrected,
   (final - initial)/(ideal - initial).
2. A real RSIGym run: three tracks (data, harness, joint) improve the same
   baseline through permissioned services under one budget each; every final
   program is then scored on five benchmarks and the RSI-Index computed.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import rsigym  # noqa: E402
from cipherlab.program import BASELINE  # noqa: E402


def main():
    a = _lab.args(default_seeds=2, budget=30)
    budget = 48 * (10 if a.quick else a.budget)
    _lab.banner("10.15", "Calculate the RSI-Index", "What fraction of the remaining gap does each track close, across benchmarks?")
    clock = _lab.Clock()

    _lab.section("1. The course's worked example, both formulas")
    init, fin = {"b1": 0.50, "b2": 0.20}, {"b1": 0.75, "b2": 0.60}
    print(f"  as printed  (initial - final)/(ideal - initial): {rsigym.rsi_index_as_printed(init, fin):+.3f}")
    print(f"  corrected   (final - initial)/(ideal - initial): {rsigym.rsi_index(init, fin):+.3f}")
    print("  The page's own arithmetic (25/50, 40/80) uses final - initial; the printed formula has the sign flipped.")

    _lab.section(f"2. RSIGym tracks ({budget} runs each, {a.seeds} seeds)")
    for tr in ("data", "harness", "joint"):
        print(f"  {tr:8s} edits: {', '.join(rsigym.TRACK_OPS[tr][:8])}{' ...' if len(rsigym.TRACK_OPS[tr]) > 8 else ''}")
        print(f"  {'':8s} services: {sorted(rsigym.TRACK_SERVICES[tr])}")
    with Evaluator() as ev:
        try:
            rsigym.RSIGym(ev, "data", 100).rollout(BASELINE)
        except rsigym.PermissionDenied as e:
            print(f"  permission check: {e}")
        finals = {tr: [] for tr in ("data", "harness", "joint")}
        calls = {}
        for seed in range(a.seeds):
            for tr in finals:
                gym = rsigym.RSIGym(ev, tr, budget)
                g = rsigym.improve(gym, seed, log=print if seed == 0 else None)
                finals[tr].append(g)
                calls[tr] = {s: sum(1 for c in gym.calls if c.service == s) for s in ("sandbox", "train", "rollout", "evaluate")}
                print(f"  seed {seed} {tr:8s} -> {g.short()}   service calls {calls[tr]}")
        ev.unseal()
        scorer = rsigym.RSIGym(ev, "joint", 10 ** 9)
        initial = {b: scorer.evaluate(BASELINE, b, seeds=(0, 1), charge=False).rate for b in rsigym.BENCHMARKS}
        table, out = [], {}
        for tr, gs in finals.items():
            per_seed = []
            for g in gs:
                final = {b: scorer.evaluate(g, b, seeds=(0, 1), charge=False).rate for b in rsigym.BENCHMARKS}
                per_seed.append((final, rsigym.rsi_index(initial, final)))
            mean_final = {b: float(np.mean([f[b] for f, _ in per_seed])) for b in rsigym.BENCHMARKS}
            idx = [i for _, i in per_seed]
            out[tr] = {"final": mean_final, "rsi_index": idx}
            table.append((tr, *[mean_final[b] for b in rsigym.BENCHMARKS], f"{np.mean(idx):.3f} ± {np.std(idx):.3f}"))
        ev.seal()
    _lab.section("3. Scores per benchmark and RSI-Index")
    table.insert(0, ("baseline", *[initial[b] for b in rsigym.BENCHMARKS], "0"))
    headers = ["track", *rsigym.BENCHMARKS, "RSI-Index"]
    _lab.table(table, headers, {b: "{:.3f}" for b in rsigym.BENCHMARKS})
    print("\n  'frankenstein' is the sealed held-out benchmark; the other four were reachable during search only via 'sherlock'.")
    print("  short_only and patristocrat show transfer: a track that only tuned for spaced, mixed-length text may not help there.")
    names = list(out)
    _lab.bar_chart(os.path.join(_lab.FIGURES, "10_15_rsi_index.png"), "RSIGym tracks: RSI-Index over five benchmarks",
                   names, [np.mean(out[n]["rsi_index"]) for n in names], [np.std(out[n]["rsi_index"]) for n in names],
                   colors=[_lab.SERIES[2], _lab.SERIES[1], _lab.SERIES[0]], ylabel="RSI-Index (fraction of gap closed)",
                   note=f"{a.seeds} seeds, {budget} runs per track; ideal = 1.0 on every benchmark")
    save_json("10_15_rsigym.json", {"initial": initial, "tracks": out, "finals": {k: [g.to_dict() for g in v] for k, v in finals.items()}})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
