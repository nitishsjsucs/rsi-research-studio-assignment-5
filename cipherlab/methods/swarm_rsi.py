"""SwarmRSI: an evolving swarm of research agents (after arXiv:2610.20431).

Five agents, each with a research *direction* (a hypothesis about why the
cipher breaker fails) and an *implementation* (its current program). One
generation does three things, every evaluation charged to one shared budget:

  1. Feedback-guided swarm mutation. Each agent proposes an edit from its own
     direction, re-weighted by the swarm's shared experience (which edits
     helped anyone, recently) and keeps it if its steering score rises.
     Agents that fall behind migrate: they adopt the leading implementation
     but keep their own direction, so the next generation tries five
     differently-motivated edits on the best program found so far.
  2. Complementary swarm recombination. When two or more agents improved
     in the same generation by changing *different* parts of the program
     (objective, search, start), their changes are merged into one program
     and evaluated once. Two half-steps found in parallel become one step;
     the merge replaces the weakest agent if it beats it.
  3. Recursive swarm evolution. Each agent's own proposal weights are
     revised by what worked for it (credit assignment), and the shared
     experience table carries every result forward: the procedure that
     generates edits is itself being edited, generation by generation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..edits import BY_NAME, OPS, applicable
from ..evaluate import Evaluator
from ..loop import Budget, Scored, Scorer
from ..program import BASELINE, Genome

DIRECTIONS: Dict[str, List[str]] = {
    "objective": ["ngram_up", "ngram_down", "add_words", "words_up", "words_down",
                  "smoothing_up", "smoothing_down", "vocab_up", "vocab_down"],
    "search": ["use_anneal", "use_hill", "temp_up", "temp_down", "iters_up", "iters_down",
               "add_polish", "remove_polish"],
    "diversify": ["restarts_up", "restarts_down", "init_frequency", "init_random", "use_anneal", "iters_down"],
    "efficiency": ["swap_ranked", "swap_uniform", "init_frequency", "iters_down", "restarts_down",
                   "remove_polish", "add_polish"],
    "explorer": [op.name for op in OPS],
}
HYPOTHESES = {
    "objective": "failures come from the scoring function: better language statistics will fix them",
    "search": "failures come from the climb: a smarter acceptance rule will escape local optima",
    "diversify": "failures are bad luck: more, better-spread starting points will fix them",
    "efficiency": "failures are wasted budget: better moves per evaluation will fix them",
    "explorer": "nobody knows yet: sample every kind of edit",
}
MODULES = {
    "objective": ("ngram", "word_weight", "smoothing", "vocab"),
    "search": ("search", "temp0", "iters", "polish"),
    "start": ("init", "restarts", "swap"),
}


@dataclass
class Agent:
    name: str
    weights: Dict[str, float]
    genome: Genome
    score: Scored
    hypothesis: str
    log: List[str] = field(default_factory=list)
    module_gain: Dict[str, float] = field(default_factory=lambda: {m: 0.0 for m in MODULES})


def module_of(op_name: str) -> str:
    t = BY_NAME[op_name].target
    return {"objective": "objective", "data": "objective", "search": "search"}.get(t, "start")


def recombine(base: Genome, donor: Genome, module: str) -> Genome:
    return base.with_(**{f: getattr(donor, f) for f in MODULES[module]})


def diversity(agents: List[Agent]) -> float:
    """Mean pairwise fraction of genome fields that differ."""
    gs = [a.genome.to_dict() for a in agents]
    pairs = [(i, j) for i in range(len(gs)) for j in range(i + 1, len(gs))]
    if not pairs:
        return 0.0
    return float(np.mean([np.mean([gs[i][k] != gs[j][k] for k in gs[i]]) for i, j in pairs]))


def run(ev: Evaluator, budget_runs: int, seed: int, recombination: bool = True,
        shared_experience: bool = True, evolve: bool = True, migrate: bool = True,
        start: Genome = BASELINE, log=None) -> dict:
    rng = np.random.default_rng(seed)
    budget = Budget(budget_runs)
    steer = Scorer(ev, "steering", (0,), budget, caller="swarm-rsi")
    s0 = steer(start)
    agents = [Agent(d, {op: 1.0 for op in ops}, start, s0, HYPOTHESES[d]) for d, ops in DIRECTIONS.items()]
    experience: Dict[str, List[float]] = {}  # op -> [gains...] across the whole swarm
    history = []
    gen = 0
    cost = steer.cost()
    while budget.can_afford(cost):
        gen += 1
        bases = {a.name: a.genome for a in agents}
        improved: List[Agent] = []
        # 1. feedback-guided mutation: every agent tries one edit from its own direction
        for a in agents:
            if not budget.can_afford(cost):
                break
            ops = [op for op in applicable(a.genome) if op.name in a.weights]
            if not ops:
                continue
            w = []
            for op in ops:
                base = a.weights[op.name]
                if shared_experience and op.name in experience:
                    recent = experience[op.name][-4:]
                    base *= 1.0 + 2.0 * float(np.mean([g > 0 for g in recent]))
                w.append(base)
            w = np.array(w) / np.sum(w)
            op = ops[int(rng.choice(len(ops), p=w))]
            child = op.apply(a.genome)
            sc = steer(child)
            gain = sc.key - a.score.key
            experience.setdefault(op.name, []).append(gain)
            kept = sc.beats(a.score)
            if evolve:  # recursive evolution of the agent's own proposal distribution
                a.weights[op.name] = float(np.clip(a.weights[op.name] * (1.6 if kept else 0.8), 0.05, 20))
            if kept:
                a.module_gain[module_of(op.name)] += sc.rate - a.score.rate
                a.genome, a.score = child, sc
                a.hypothesis = f"{HYPOTHESES[a.name]} [supported: {op.name} {gain:+.2f}]"
                improved.append(a)
            a.log.append(f"g{gen} {op.name} {'KEEP' if kept else 'drop'} {sc.rate:.3f}")
            if log:
                log(f"  g{gen} {a.name:10s} {op.name:15s} -> {sc.rate:.3f} {'KEEP' if kept else 'drop'}")
        div = diversity(agents)
        # 2. complementary recombination: merge what different agents changed, in different modules
        leader = max(agents, key=lambda x: x.score.key)
        if recombination and len(improved) >= 2 and budget.can_afford(cost):
            merged, parts = leader.genome, [leader.name]
            for a in sorted(improved, key=lambda x: -x.score.key):
                if a is leader:
                    continue
                changed = {k: v for k, v in a.genome.to_dict().items() if v != getattr(bases[a.name], k)}
                if changed and all(getattr(merged, k) == getattr(bases[a.name], k) for k in changed):
                    merged = merged.with_(**changed)  # a disjoint change: carry it over
                    parts.append(a.name)
            if len(parts) > 1:
                sc = steer(merged)
                worst = min(agents, key=lambda x: x.score.key)
                took = sc.beats(leader.score)
                if sc.beats(worst.score):
                    worst.genome, worst.score = merged, sc
                    worst.log.append(f"g{gen} recombined {'+'.join(parts)} -> {sc.rate:.3f}")
                if log:
                    log(f"  g{gen} recombine {'+'.join(parts)} -> {sc.rate:.3f} {'NEW LEADER' if took else 'kept as variant' if sc.beats(worst.score) else 'discarded'}")
        best = max(agents, key=lambda x: x.score.key)
        if migrate:  # feedback from other agents: laggards adopt the leader's implementation
            for a in agents:
                if a is not best and a.score.solved < best.score.solved:
                    a.genome, a.score = best.genome, best.score
                    a.log.append(f"g{gen} migrated to {best.name}'s program")
        history.append({"gen": gen, "best": best.score.rate, "best_agent": best.name,
                        "diversity": div, "runs": budget.spent, "improved": [a.name for a in improved],
                        "agents": {a.name: a.score.rate for a in agents}})
    best = max(agents, key=lambda x: x.score.key)
    return {"seed": seed, "recombination": recombination, "shared_experience": shared_experience,
            "evolve": evolve, "migrate": migrate, "best": best.genome, "best_rate": best.score.rate, "best_agent": best.name,
            "history": history, "runs_spent": budget.spent,
            "agents": {a.name: {"rate": a.score.rate, "genome": a.genome.short(), "hypothesis": a.hypothesis,
                                "weights_top": sorted(a.weights.items(), key=lambda kv: -kv[1])[:3]}
                       for a in agents}}
