"""Lab 10.11 · Simulate swarm evolution (SwarmRSI).

Five agents (objective, search, diversify, efficiency, explorer). We run the
full swarm and three ablations at one compute budget, then ask the question
the papers leave open: what does a swarm buy at EQUAL compute versus at EQUAL
sequential rounds? The single-agent reference is the naive greedy loop from
10.06 (same proposer prior), measured both ways.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import save_json  # noqa: E402
from cipherlab.methods import so_rsi, swarm_rsi  # noqa: E402
from cipherlab.program import render  # noqa: E402

VARIANTS = {
    "swarm (full)": {},
    "no recombination": {"recombination": False},
    "no shared experience": {"shared_experience": False},
    "no migration": {"migrate": False},
}


def main():
    a = _lab.args(default_seeds=3, budget=40)
    steps = 12 if a.quick else a.budget
    budget = 48 * steps
    _lab.banner("10.11", "Swarm evolution", "What do mutation, recombination and shared experience each contribute?")
    clock = _lab.Clock()
    res = {k: [] for k in VARIANTS}
    single_equal_compute, single_equal_rounds = [], []
    with Evaluator() as ev:
        for seed in range(a.seeds):
            for name, kw in VARIANTS.items():
                if seed == 0 and name == "swarm (full)":
                    _lab.section("seed 0 · full swarm, every agent's move")
                r = swarm_rsi.run(ev, budget, seed, log=print if (seed == 0 and name == "swarm (full)") else None, **kw)
                res[name].append(r)
                print(f"  seed {seed} {name:22s} best={r['best_rate']:.3f} by {r['best_agent']:10s} gens={len(r['history'])}  {r['best'].short()}")
            gens = len(res["swarm (full)"][-1]["history"])
            single_equal_compute.append(so_rsi.run(ev, budget, seed, False))
            single_equal_rounds.append(so_rsi.run(ev, 48 * (gens + 1), seed, False))
        _lab.section("Agents after seed 0")
        for n, ag in res["swarm (full)"][0]["agents"].items():
            print(f"  {n:10s} {ag['rate']:.3f}  top proposal weights {[(o, round(w, 2)) for o, w in ag['weights_top']]}")
            print(f"             hypothesis: {ag['hypothesis']}")
        ev.unseal()
        for runs in list(res.values()) + [single_equal_compute, single_equal_rounds]:
            for r in runs:
                g = r.get("best") or r.get("final")
                r["heldout"] = ev.run(render(g), "heldout", (0, 1), caller="10.11-final").solve_rate
        ev.seal()
    _lab.section("Ablations at equal compute")
    rows = []
    for name, runs in res.items():
        ms, ss = _lab.mean_sd(r["best_rate"] for r in runs)
        mh, sh = _lab.mean_sd(r["heldout"] for r in runs)
        rows.append((name, f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}", np.mean([len(r["history"]) for r in runs]),
                     np.mean([np.mean([h["diversity"] for h in r["history"]]) for r in runs])))
    _lab.table(rows, ["variant", "steering", "held-out", "sequential rounds", "mean diversity"],
               {"sequential rounds": "{:.1f}", "mean diversity": "{:.2f}"})
    _lab.section("What a swarm buys: equal compute vs equal sequential rounds")
    gens = np.mean([len(r["history"]) for r in res["swarm (full)"]])
    rows = [("swarm (full)", budget, f"{gens:.0f}", np.mean([r["heldout"] for r in res["swarm (full)"]])),
            ("single agent, equal compute", budget, f"{steps}", np.mean([r["heldout"] for r in single_equal_compute])),
            ("single agent, equal rounds", f"~{int(48 * (gens + 1))}", f"{gens:.0f}", np.mean([r["heldout"] for r in single_equal_rounds]))]
    _lab.table(rows, ["arm", "runs", "sequential rounds", "held-out"], {"held-out": "{:.3f}"})
    h = res["swarm (full)"][0]["history"]
    _lab.line_chart(os.path.join(_lab.FIGURES, "10_11_swarm.png"), "SwarmRSI (seed 0): best agent and swarm diversity by generation",
                    [("best steering", [x["gen"] for x in h], [x["best"] for x in h], _lab.SERIES[0]),
                     ("diversity", [x["gen"] for x in h], [x["diversity"] for x in h], _lab.SERIES[1])],
                    xlabel="generation", ylabel="rate / fraction of genome fields differing")
    save_json("10_11_swarm.json", {"variants": res, "single_equal_compute": single_equal_compute,
                                   "single_equal_rounds": single_equal_rounds})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
