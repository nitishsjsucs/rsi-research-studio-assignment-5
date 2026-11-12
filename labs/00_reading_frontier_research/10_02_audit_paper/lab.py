"""Lab 10.02 · Audit an October 2026 paper.

Part A fills the course's audit template (changed object, feedback,
evaluation protocol, compute, untested assumptions) for the three papers we
rebuild and writes one paper_audit_<name>.md per paper.

Part B audits an experiment *in code*. Two versions of the same comparison
(a greedy improver vs a random-edit baseline) are run:

    flawed   peeks at the held-out split to pick its program, gives one arm
             twice the budget, and uses one seed
    clean    held-out sealed until the end, matched budgets, three seeds

The evaluator's ledger records every split access; cipherlab.audit reads that
ledger and the run records and passes or fails each rule.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.audit import audit, print_audit  # noqa: E402
from cipherlab.edits import SYMPTOM_PRIOR, UNIFORM_PRIOR, sample_op  # noqa: E402
from cipherlab.evaluate import Evaluator, SealedSplitError  # noqa: E402
from cipherlab.loop import Budget, Scorer  # noqa: E402
from cipherlab.program import BASELINE, render  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

AUDITS = {
    "budget_rsi": [
        ("Changed object", "GPT-4o coding-agent scaffold (code edits)", "cipher-breaker program source rendered from a genome", "an edit to program text, scored from its diff"),
        ("Feedback type", "solve counts on a steering split of HumanEval+", "solve counts on 48 Sherlock ciphers", "pass/fail counts per candidate"),
        ("Evaluation protocol", "16-instance fit split for labels, 48/164 steering, rest held out", "16 fit / 48 steering / 96 held-out Frankenstein ciphers", "three disjoint partitions with distinct roles"),
        ("Compute budget", "LLM calls + many full test-suite runs", "<= 1,920 steering runs per arm, ~2 min on 10 CPU cores", "matched budget between selectors"),
        ("Untested assumptions", "diff shape predicts edit quality on other tasks", "diff shape predicts quality for template edits", "tested here: the 8 coordinates are blind to edit direction (lab 10.04)"),
    ],
    "so_rsi": [
        ("Changed object", "the RSI workflow's edits (second order)", "the proposal distribution of the improver", "diagnosis changes how edits are chosen"),
        ("Feedback type", "execution traces from Lean 4 / Verus", "per-cipher traces: fitness(found) vs fitness(true), stall point, cap hits", "anomaly detection on the improver's own trace"),
        ("Evaluation protocol", "24-hour search, held-out proofs", "40 steering evaluations, sealed held-out, 3+ seeds", "same proposer and acceptance rule in both arms"),
        ("Compute budget", "24 hours per comparison", "probes paid from the same 1,920-run budget", "probe cost counted, not free"),
        ("Untested assumptions", "probes generalise across formal systems", "hand-written probes for one domain", "what an LLM-written probe would find is not tested"),
    ],
    "swarm_rsi": [
        ("Changed object", "hypotheses and implementations of a swarm of scientist agents", "programs and proposal weights of five agents", "population-level edits plus recombination"),
        ("Feedback type", "experiment results shared across agents", "steering scores + a shared op->gain experience table", "other agents' results steer mutation"),
        ("Evaluation protocol", "OpenProblems, NatureBench, MLE-Bench Lite", "steering + sealed held-out, ablations of recombination/sharing/migration", "ablations at matched compute"),
        ("Compute budget", "many agent-hours", "1,920-2,880 steering runs", "every agent evaluation charged to one budget"),
        ("Untested assumptions", "swarm beats one agent at equal compute", "tested here: at equal compute it does not; it wins on sequential depth", "honest framing of what a swarm buys"),
    ],
}


def write_audits():
    paths = []
    for name, rows in AUDITS.items():
        p = os.path.join(HERE, f"paper_audit_{name}.md")
        with open(p, "w") as f:
            f.write(f"# Audit: {name.replace('_', ' ').title()}\n\n")
            f.write("| Aspect | Paper's setup | Laptop adaptation | What's preserved |\n|---|---|---|---|\n")
            for r in rows:
                f.write("| " + " | ".join(r) + " |\n")
            f.write("\nAssumption to test next: " + rows[-1][1] + ". What would test it: run the same mechanism "
                    "on a second task family with its own steering and held-out splits, matched budgets, 5+ seeds.\n")
        paths.append(p)
    return paths


def greedy(ev, budget_runs, seed, prior, peek_heldout=False):
    rng = np.random.default_rng(seed)
    budget = Budget(budget_runs)
    steer = Scorer(ev, "steering", (0,), budget, caller="10.02-arm")
    cur, cur_s = BASELINE, steer(BASELINE)
    while budget.can_afford(48):
        op = sample_op(cur, rng, prior)
        child = op.apply(cur)
        s = steer(child)
        if peek_heldout:  # the flaw: choose using the held-out split
            try:
                ev.run(render(child), "heldout", (0,), caller="10.02-PEEK")
            except SealedSplitError as e:
                print(f"    blocked: {e}")
                peek_heldout = False  # the harness refused; record it and carry on
                ev.unseal()            # ...and an author who "fixes" it by unsealing leaves a trail
                ev.run(render(child), "heldout", (0,), caller="10.02-PEEK")
                ev.seal()
        if s.beats(cur_s):
            cur, cur_s = child, s
    return {"final": cur, "steering": cur_s.rate, "runs_spent": budget.spent}


def report(ev, runs):
    ev.unseal()
    for r in runs:
        r["heldout"] = ev.run(render(r["final"]), "heldout", (0,), caller="10.02-final").solve_rate
    ev.seal()


def main():
    a = _lab.args(default_seeds=3, budget=12)
    B = 48 * (6 if a.quick else a.budget)
    _lab.banner("10.02", "Audit an October 2026 paper", "What did the experiment actually measure, and can a ledger prove it?")
    clock = _lab.Clock()
    _lab.section("Part A: audit templates")
    for p in write_audits():
        print(f"  wrote {os.path.relpath(p, _lab.ROOT)}")
    for name, rows in AUDITS.items():
        print(f"  {name}: untested -> {rows[-1][1]}")

    with Evaluator() as ev:
        _lab.section("Part B1: the flawed comparison")
        flawed = {"greedy": [greedy(ev, B, 0, SYMPTOM_PRIOR, peek_heldout=True)],
                  "random": [greedy(ev, B * 2, 0, UNIFORM_PRIOR)]}
        t_final = time.time()
        report(ev, [r for v in flawed.values() for r in v])
        ok = print_audit(audit(ev.ledger, flawed, t_final))
        print(f"  verdict: {'claim supported' if ok else 'claim NOT supported by this evidence'}")

        _lab.section("Part B2: the clean comparison")
        ev2 = Evaluator()
        clean = {"greedy": [greedy(ev2, B, s, SYMPTOM_PRIOR) for s in range(a.seeds)],
                 "random": [greedy(ev2, B, s, UNIFORM_PRIOR) for s in range(a.seeds)]}
        t_final = time.time()
        report(ev2, [r for v in clean.values() for r in v])
        ok = print_audit(audit(ev2.ledger, clean, t_final))
        rows = []
        for k, v in clean.items():
            ms, ss = _lab.mean_sd(r["steering"] for r in v)
            mh, sh = _lab.mean_sd(r["heldout"] for r in v)
            rows.append((k, len(v), f"{ms:.3f} ± {ss:.3f}", f"{mh:.3f} ± {sh:.3f}"))
        _lab.table(rows, ["arm", "seeds", "steering", "held-out"])
        print(f"  verdict: {'claim may be stated, with these numbers' if ok else 'claim NOT supported'}")
        print("  ledger: " + ev2.ledger.summary())
        ev2.close()
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
