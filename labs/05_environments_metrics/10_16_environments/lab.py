"""Lab 10.16 · Compare environments.

The same greedy improver, with the same seed and budget, runs in three
environment styles the papers use:

    EaaS (RSIGym)        in-process services with permissions and a budget
    terminal (Terminal-RSI)  every evaluation is a shell command:
                         `python3 -m cipherlab.cli evaluate ...`, JSON on stdout
    self-play (R2Orch)   the improver chooses its own practice tasks: the length
                         bucket whose success rate p maximises p(1-p)
                         ("recursive learnability"), and evaluates edits there,
                         cheaply, before a final check on steering

We measure what each costs (wall-clock, runs) and what it returns.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

import numpy as np  # noqa: E402

from cipherlab.edits import SYMPTOM_PRIOR, sample_op  # noqa: E402
from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import Budget, Scored, Scorer, save_json  # noqa: E402
from cipherlab.methods import rsigym  # noqa: E402
from cipherlab.program import BASELINE, render  # noqa: E402
from cipherlab.tasks import load_split  # noqa: E402


def greedy(score_fn, budget: Budget, cost: int, seed: int):
    rng = np.random.default_rng(seed)
    cur = BASELINE
    cur_s = score_fn(cur)
    while budget.can_afford(cost):
        op = sample_op(cur, rng, SYMPTOM_PRIOR)
        child = op.apply(cur)
        s = score_fn(child)
        if s.beats(cur_s):
            cur, cur_s = child, s
    return cur


def eaas(ev, runs, seed):
    gym = rsigym.RSIGym(ev, "joint", runs)
    t = time.time()
    g = greedy(lambda x: gym.evaluate(x), gym.budget, 48, seed)
    return g, time.time() - t, gym.budget.spent, len(gym.calls)


def terminal(runs, seed):
    budget = Budget(runs)
    calls = []

    def score(g):
        budget.charge(48)
        t = time.time()
        out = subprocess.run([sys.executable, "-m", "cipherlab.cli", "evaluate", "--genome", json.dumps(g.to_dict()),
                              "--split", "steering", "--seeds", "0"], capture_output=True, text=True, cwd=_lab.ROOT, check=True)
        d = json.loads(out.stdout)
        calls.append((time.time() - t, d["seconds"]))
        return Scored(g, d["solved"], d["total"], d["mean_acc"])
    t = time.time()
    g = greedy(score, budget, 48, seed)
    return g, time.time() - t, budget.spent, calls


def self_play(ev, runs, seed, log=None):
    """R2Orch-style: practise on the task the current program finds most learnable."""
    rng = np.random.default_rng(seed)
    budget = Budget(runs)
    pool = load_split("probe")
    buckets = {b: [i for i, x in enumerate(pool) if x.bucket == b] for b in ("short", "medium", "long")}
    full = Scorer(ev, "probe", (0, 1), budget, caller="10.16-selfplay-profile")
    cur = BASELINE
    prof = full(cur)
    chosen, t = [], time.time()
    while budget.can_afford(full.cost()):
        rates = {b: float(np.mean([r["solved"] for r in prof.rows if r["bucket"] == b])) for b in buckets}
        learn = {b: p * (1 - p) for b, p in rates.items()}
        if max(learn.values()) == 0:  # nothing is partly solved: practise where the program is closest to working
            task = max(rates, key=lambda b: (rates[b] < 1, -["long", "medium", "short"].index(b)))
        else:
            task = max(learn, key=learn.get)
        chosen.append((task, round(learn[task], 3)))
        practice = Scorer(ev, "probe", (0, 1), budget, caller="10.16-selfplay", subset=buckets[task])
        base = practice(cur)
        for _ in range(3):  # three cheap practice attempts per profiled task
            if not budget.can_afford(practice.cost() + full.cost()):
                break
            op = sample_op(cur, rng, SYMPTOM_PRIOR)
            child = op.apply(cur)
            s = practice(child)
            if s.beats(base):
                cur, base = child, s
        prof = full(cur)
        if log:
            log(f"  practise on '{task}' (p(1-p)={learn[task]:.3f}) -> probe rate {prof.rate:.3f}  {cur.short()}")
    return cur, time.time() - t, budget.spent, chosen


def main():
    a = _lab.args(default_seeds=1, budget=24)
    runs = 48 * (8 if a.quick else a.budget)
    _lab.banner("10.16", "Compare environments", "What does each environment interface cost, and what does it let the improver do?")
    clock = _lab.Clock()
    with Evaluator() as ev:
        _lab.section(f"EaaS / RSIGym ({runs} runs)")
        g1, t1, s1, n1 = eaas(ev, runs, 0)
        print(f"  -> {g1.short()}  {t1:.1f}s, {n1} service calls")
        _lab.section(f"Terminal / Terminal-RSI ({runs} runs; one subprocess per evaluation)")
        g2, t2, s2, calls = terminal(runs, 0)
        overhead = np.mean([w - inner for w, inner in calls])
        print(f"  -> {g2.short()}  {t2:.1f}s, {len(calls)} shell commands, mean process overhead {overhead:.2f}s per evaluation")
        _lab.section(f"Self-play / R2Orch-style task choice ({runs} runs)")
        g3, t3, s3, chosen = self_play(ev, runs, 0, log=print)
        _lab.section("Same final check for all three (steering, then held-out)")
        steer = Scorer(ev, "steering", (0, 1), caller="10.16-final")
        ev.unseal()
        rows = []
        for name, g, t, s in (("EaaS", g1, t1, s1), ("terminal", g2, t2, s2), ("self-play", g3, t3, s3)):
            h = ev.run(render(g), "heldout", (0, 1), caller="10.16-final").solve_rate
            rows.append((name, s, t, steer(g).rate, h, g.short()))
        ev.seal()
    _lab.table(rows, ["environment", "runs", "seconds", "steering", "held-out", "program"],
               {"seconds": "{:.1f}", "steering": "{:.3f}", "held-out": "{:.3f}"})
    print("\n  EaaS and terminal run the same improver with the same seed: same program, different cost.")
    print("  Terminal isolation (a crash cannot take the improver down) costs a process start per evaluation.")
    print(f"  Self-play spent its budget on {len(chosen)} self-chosen practice tasks: {chosen}")
    save_json("10_16_environments.json", {"rows": rows, "self_play_tasks": chosen, "terminal_overhead_s": overhead})
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
