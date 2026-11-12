"""Lab 10.09 · Compare scaling approaches: AReaL-RSI vs SwarmRSI.

Before running either at full size (10.10, 10.11), run both briefly from the
same baseline and print *who talks to whom*. The comparison table is then
filled from what the two traces actually show, not only from the papers.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.methods import areal, swarm_rsi  # noqa: E402

TABLE = [
    ("Coordination", "leader assigns orientations to specialist researchers", "peers; no one assigns work"),
    ("Memory", "conditional: replicated findings are shared, the rest stay open problems", "shared experience table: every result, weighted by recency"),
    ("Evolution", "evidence-based review revises orientation values and retires skills", "mutation + recombination + re-weighted proposal distributions"),
    ("Selection", "leader-guided (UCB over resolved evidence)", "competitive (laggards migrate to the leader)"),
    ("Pays extra for", "replication runs (a second seed) before sharing", "breadth: five evaluations per generation"),
    ("Advantage", "noise-robust: an unreplicated gain never becomes team fact", "parallel depth: many directions per sequential round"),
    ("Limitation", "replication costs 2 of every 8 evaluations (a quarter fewer edits)", "at a fixed compute budget, fewer sequential steps than one agent"),
    ("Choose it when", "evaluations are noisy and a wrong 'fact' is expensive", "wall-clock rounds are the bottleneck, compute is not"),
]


def main():
    a = _lab.args(default_seeds=1, budget=24)
    budget = 48 * (8 if a.quick else a.budget)
    _lab.banner("10.09", "Compare scaling approaches", "How do a leader-led team and a peer swarm spend the same budget?")
    clock = _lab.Clock()
    with Evaluator() as ev:
        _lab.section(f"AReaL-RSI, conditional memory ({budget} runs)")
        r1 = areal.run(ev, budget, 0, "conditional", log=print)
        print(f"  -> {r1['final_rate']:.3f} after {r1['campaigns']} campaigns; resolved={r1['resolved']} unresolved={r1['unresolved']}")
        _lab.section(f"SwarmRSI ({budget} runs)")
        r2 = swarm_rsi.run(ev, budget, 0, log=print)
        print(f"  -> {r2['best_rate']:.3f} after {len(r2['history'])} generations, leader={r2['best_agent']}")
    _lab.section("Communication pattern observed")
    print("  AReaL : leader -> {R1, R2} assignments; R* -> leader findings; leader -> replicate -> memory -> team program")
    print("  Swarm : every agent -> shared experience; improved agents -> recombination; leader -> laggards (migration)")
    _lab.section("Comparison")
    _lab.table(TABLE, ["aspect", "AReaL-RSI (leader-follower)", "SwarmRSI (peer swarm)"])
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
