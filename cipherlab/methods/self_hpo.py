"""Self-HPO-style harness/policy alternation (after arXiv:2610.22791).

The paper alternates two optimisations of one coding agent:

    H-step   the current policy analyses its own failures and proposes harness
             candidates aimed at them; the best harness is selected.
    P-step   the policy is updated (RL in the paper) under the chosen harness.

Mapped onto a cipher breaker:

    harness  the scaffold around the scorer: init, search rule, polish,
             swap moves, restarts and iterations          (discrete fields)
    policy   the continuous "weights" of the scorer: word weight, annealing
             temperature, n-gram smoothing                (continuous fields)

H-step: the failing steering ciphers become the hard set; the policy's own
failure analysis (probes.diagnose_rows on those rows) ranks harness edits;
the top 3 run on the hard set only, and the winner must then beat the current
program on the full steering split. P-step: a small evolution strategy (four
log-normal perturbations of the policy weights) evaluated on steering.

Schedules compared at one budget: alternate (H,P,H,P...), harness_only,
policy_only.
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..edits import BY_NAME, applicable
from ..evaluate import Evaluator
from ..loop import Budget, Scorer
from ..probes import diagnose_rows
from ..program import Genome
from ..tasks import load_split

HARNESS_OPS = ["init_frequency", "init_random", "use_anneal", "use_hill", "add_polish", "remove_polish",
               "swap_ranked", "swap_uniform", "restarts_up", "restarts_down", "iters_up", "iters_down"]
START = Genome(ngram=3, word_weight=1.0, iters=2000, restarts=2, temp0=2.0)


def h_step(ev, steer: Scorer, cur: Genome, budget: Budget, rng, log=None):
    rows = steer(cur).rows
    insts = load_split("steering")
    uid_to_idx = {inst.uid: i for i, inst in enumerate(insts)}
    hard = sorted({uid_to_idx[r["uid"]] for r in rows if not r["solved"]})
    if not hard:
        return cur, "no failures"
    diag = diagnose_rows(cur, [r for r in rows if not r["solved"]] + [r for r in rows if r["solved"]])
    ranked = [n for n in diag.recommended() if n in HARNESS_OPS]
    ranked += [n for n in rng.permutation(HARNESS_OPS) if n not in ranked]
    cands = [BY_NAME[n] for n in ranked if BY_NAME[n].apply(cur) is not None][:3]
    hard_scorer = Scorer(ev, "steering", (0,), budget, caller="self-hpo-hard", subset=hard, charge_repeats=False)
    if not cands or not budget.can_afford(hard_scorer.cost() * (len(cands) + 1) + steer.cost()):
        return cur, "out of budget"
    base_hard = hard_scorer(cur)
    best_op, best = None, base_hard
    for op in cands:
        s = hard_scorer(op.apply(cur))
        if s.beats(best):
            best_op, best = op, s
    if best_op is None:
        return cur, f"H: none of {[c.name for c in cands]} helped on {len(hard)} hard ciphers"
    child = best_op.apply(cur)
    if steer(child).beats(steer(cur)):
        return child, f"H: {best_op.name} (from {diag.mechanisms}) solves {best.solved}/{len(hard)} hard"
    return cur, f"H: {best_op.name} won on hard set but lost on full steering"


def p_step(steer: Scorer, cur: Genome, budget: Budget, rng, sigma: float = 0.6):
    best, best_s = cur, steer(cur)
    tried = 0
    for _ in range(4):
        if not budget.can_afford(steer.cost()):
            break
        kw = {}
        if cur.word_weight:
            kw["word_weight"] = round(float(np.clip(cur.word_weight * np.exp(sigma * rng.normal()), 0.25, 16)), 3)
        if cur.search == "anneal":
            kw["temp0"] = round(float(np.clip(cur.temp0 * np.exp(sigma * rng.normal()), 0.25, 40)), 3)
        kw["smoothing"] = float(cur.smoothing * 10 ** int(rng.integers(-1, 2)))
        g = cur.with_(**kw)
        if g == cur:
            continue
        s = steer(g)
        tried += 1
        if s.beats(best_s):
            best, best_s = g, s
    return best, f"P: {tried} policy perturbations -> {'moved' if best != cur else 'stayed'}"


def run(ev: Evaluator, budget_runs: int, seed: int, schedule: str = "alternate",
        start: Genome = START, log=None) -> dict:
    rng = np.random.default_rng(seed)
    budget = Budget(budget_runs)
    # looking up a program already run is bookkeeping, not a new run: repeats are free here
    steer = Scorer(ev, "steering", (0,), budget, caller=f"self-hpo-{schedule}", charge_repeats=False)
    cur = start
    steer(cur)
    curve, notes, i = [steer(cur).rate], [], 0
    while budget.can_afford(steer.cost() * 2):
        kind = {"alternate": "HP"[i % 2], "harness_only": "H", "policy_only": "P"}[schedule]
        i += 1
        before = budget.spent
        if kind == "H":
            cur, note = h_step(ev, steer, cur, budget, rng, log)
        else:
            cur, note = p_step(steer, cur, budget, rng)
        if budget.spent == before:  # nothing affordable / nothing to try
            if kind == "H" and schedule == "harness_only":
                break
            if kind == "P" and schedule == "policy_only":
                break
        curve.append(steer(cur).rate if cur in steer.cache else curve[-1])
        notes.append(f"{kind}{i}: {note} -> {steer.cache[cur].rate:.3f}")
        if log:
            log(f"  {notes[-1]}")
    return {"schedule": schedule, "seed": seed, "start_rate": steer.cache[start].rate,
            "final": cur, "final_rate": steer.cache[cur].rate, "runs_spent": budget.spent,
            "curve": curve, "notes": notes}
