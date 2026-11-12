"""Lab 10.17 · Analyse metrics.

Every metric below is computed from the result files earlier labs saved in
results/, not typed in. For each: the value from our runs, what it measures,
when it is useful, and its limitation.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.loop import load_json, save_json  # noqa: E402


def get(name):
    try:
        return load_json(name)
    except FileNotFoundError:
        return None


def main():
    _lab.args(default_seeds=1)
    _lab.banner("10.17", "Analyse metrics", "What does each October 2026 metric say about our runs, and what does it hide?")
    rows = []

    gym = get("10_15_rsigym.json")
    if gym:
        v = ", ".join(f"{k}={np.mean(t['rsi_index']):.3f}" for k, t in gym["tracks"].items())
        rows.append(("RSI-Index (RSIGym)", v, "fraction of remaining gap closed, averaged over benchmarks",
                     "comparing systems across benchmarks of different difficulty", "ideal=1.0 is unreachable for short ciphers; hides which benchmark moved"))

    b = get("10_03_budget_rsi.json")
    if b:
        gaps = {k: np.mean([r["best_rate"] - r["heldout"] for r in v]) for k, v in b.items()}
        rows.append(("Steering-split solve rate (Budget RSI)", ", ".join(f"{k} steer-heldout gap={g:+.3f}" for k, g in gaps.items()),
                     "performance on the split used to select", "cheap per-candidate signal during search",
                     "inflated by selection (10.01); different text source from held-out"))

    sp = get("10_16_environments.json")
    if sp:
        tasks = sp["self_play_tasks"]
        rows.append(("Recursive learnability (R2Orch)", f"mean p(1-p) of chosen tasks = {np.mean([t[1] for t in tasks]):.3f} over {len(tasks)} choices",
                     "how informative the self-chosen task is (max 0.25 at p=0.5)", "letting an improver pick its own curriculum",
                     "0 everywhere at the start (nothing partly solved), so it needs a fallback"))

    sw = get("10_11_swarm.json")
    if sw:
        div = [np.mean([h["diversity"] for h in r["history"]]) for r in sw["variants"]["swarm (full)"]]
        nomig = [np.mean([h["diversity"] for h in r["history"]]) for r in sw["variants"]["no migration"]]
        rows.append(("Swarm diversity (SwarmRSI)", f"full={np.mean(div):.2f} vs no-migration={np.mean(nomig):.2f}",
                     "mean pairwise fraction of genome fields that differ", "detecting a swarm that has collapsed to one idea",
                     "high diversity is not high quality: no-migration is diverse and worse"))

    so = get("10_06_so_rsi.json")
    if so:
        th = {k: np.mean([(r["anomaly_counts"].get("opposing", 0) + r["anomaly_counts"].get("recurrence", 0)) / max(1, r["rounds"]) for r in v]) for k, v in so.items()}
        rows.append(("Thrash rate (SO-RSI behaviour)", ", ".join(f"{k}={x:.2f}/step" for k, x in th.items()),
                     "opposing + recurrent edits per improvement step", "spotting first-order trial-and-error",
                     "a low thrash rate can also mean the improver stopped exploring"))

    gains = []
    for name, key, final in (("10_06_so_rsi.json", "so-rsi", "final"), ("10_06_so_rsi.json", "naive", "final"),
                             ("10_10_areal.json", "conditional", "final"), ("10_13_rsiflow.json", "adaptive", "final")):
        d = get(name)
        if d and key in d:
            gains.append((key, np.mean([r["heldout"] for r in d[key]]) / (np.mean([r["runs_spent"] for r in d[key]]) / 1000)))
    if gains:
        rows.append(("Cost-normalised gain (ours)", ", ".join(f"{k}={g:.3f}" for k, g in gains),
                     "held-out solve rate per 1,000 instance-runs", "comparing methods whose budgets differ",
                     "not linear: the first runs buy more than the last"))

    for r in rows:
        print(f"\n  {r[0]}\n    our runs   : {r[1]}\n    measures   : {r[2]}\n    useful when: {r[3]}\n    limitation : {r[4]}")
    if not rows:
        print("  no results yet: run labs 10.03-10.16 first")
    save_json("10_17_metrics.json", rows)


if __name__ == "__main__":
    main()
