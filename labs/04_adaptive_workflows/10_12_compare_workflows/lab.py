"""Lab 10.12 · Compare workflow adaptation: RSIFlow vs Self-HPO.

Both adapt *how* improvement happens, but they adapt different objects.
A short run of each prints what changed between steps: RSIFlow rewires the
stages of the workflow; Self-HPO alternates which half of the program
(harness or policy) is being optimised.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.methods import budget_rsi, rsiflow, self_hpo  # noqa: E402

TABLE = [
    ("What adapts", "the workflow graph: which stages run, in what order", "the program: harness (discrete) then policy (continuous)"),
    ("Signal", "execution feedback about the improver (yield, stalls, cap hits)", "the policy's own failures on hard instances"),
    ("Who proposes", "a meta-agent with rules that can be switched off", "the policy itself proposes harness candidates"),
    ("Iteration", "continuous: any step may rewire", "alternating H-step / P-step"),
    ("Second order", "rule usefulness scores evolve the meta-agent", "the harness search set is the policy's evolving failures"),
    ("Prefer when", "the bottleneck moves during the run", "the system has a learnable part and a scaffold part"),
]


def main():
    a = _lab.args(default_seeds=1, budget=32)
    budget = 48 * (10 if a.quick else a.budget)
    _lab.banner("10.12", "Compare workflow adaptation", "Which object does each method adapt, and on what signal?")
    clock = _lab.Clock()
    with Evaluator() as ev:
        ro = budget_rsi.paper_readout(budget_rsi.load_or_build_training(ev, 96, 0))
        _lab.section(f"RSIFlow, adaptive ({budget} runs): watch the workflow change")
        r = rsiflow.run(ev, budget, 0, True, readout=ro, log=print)
        print(f"  -> {r['final_rate']:.3f}; rules: {r['rules']}")
        _lab.section(f"Self-HPO, alternating ({budget} runs): watch the object change")
        r = self_hpo.run(ev, budget, 0, "alternate", log=print)
        print(f"  -> {r['start_rate']:.3f} -> {r['final_rate']:.3f}")
    _lab.section("Comparison")
    _lab.table(TABLE, ["aspect", "RSIFlow", "Self-HPO"])
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
