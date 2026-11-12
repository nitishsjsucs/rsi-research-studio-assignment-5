"""AReaL-RSI-style coordination: a leader, two researchers, conditional memory
(after arXiv:2610.18083).

One *campaign*: the leader assigns each researcher a research orientation;
each researcher runs a short greedy campaign from the team's current program;
the leader replicates the best finding on a second evaluation seed. Then:

  conditional memory   a finding that replicates is RESOLVED and becomes the
                       team's program; one that does not is UNRESOLVED and is
                       kept as an open problem, never shared as fact;
  evidence-based review the leader updates the value of each orientation from
                       resolved evidence only, and retires edits from a
                       researcher's skill set after repeated failure.

Variants under the same budget:
    conditional   the method above
    share_all     adopt any seed-0 gain immediately (no replication cost)
    independent   no leader, no sharing: researchers each keep a program
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from ..edits import applicable
from ..evaluate import Evaluator
from ..loop import Budget, Scorer
from ..program import BASELINE, Genome
from .swarm_rsi import DIRECTIONS

ORIENTATIONS = ["objective", "search", "diversify", "efficiency"]


@dataclass
class Entry:
    campaign: int
    researcher: str
    orientation: str
    ops: List[str]
    gain: float
    status: str  # resolved | unresolved


@dataclass
class ConditionalMemory:
    entries: List[Entry] = field(default_factory=list)

    def store(self, e: Entry):
        self.entries.append(e)

    def resolved(self) -> List[Entry]:
        return [e for e in self.entries if e.status == "resolved"]

    def unresolved(self) -> List[Entry]:
        return [e for e in self.entries if e.status == "unresolved"]

    def retrieve(self, orientation: str) -> List[Entry]:
        """What a researcher is told: only resolved findings, only for its orientation."""
        return [e for e in self.resolved() if e.orientation == orientation]


class Leader:
    def __init__(self, rng):
        self.rng = rng
        self.value = {o: 0.0 for o in ORIENTATIONS}
        self.tries = Counter()
        self.skills = {o: list(DIRECTIONS[o]) for o in ORIENTATIONS}
        self.failures = Counter()

    def select(self, k: int = 2) -> List[str]:
        """UCB over resolved evidence: exploit what replicated, still try the rest."""
        total = sum(self.tries.values()) + 1
        ucb = {o: self.value[o] + 0.08 * np.sqrt(np.log(total + 1) / (self.tries[o] + 1)) + 1e-6 * self.rng.random()
               for o in ORIENTATIONS}
        return sorted(ORIENTATIONS, key=lambda o: -ucb[o])[:k]

    def review(self, orientation: str, resolved_gain: float, tried: List[tuple]):
        """Update the orientation's value from resolved evidence, and each edit's record from its own outcome.

        Credit is per edit: an edit that was accepted inside a campaign is not a failure just because
        another researcher's campaign won. (An earlier version blamed every edit a losing campaign
        tried, and the leader retired annealing and 'search longer' from the team; see the README.)
        """
        self.tries[orientation] += 1
        n = self.tries[orientation]
        self.value[orientation] += (resolved_gain - self.value[orientation]) / n
        for op, kept in tried:
            if kept:
                self.failures[op] = 0
            else:
                self.failures[op] += 1
                if self.failures[op] >= 3 and len(self.skills[orientation]) > 2 and op in self.skills[orientation]:
                    self.skills[orientation].remove(op)  # skill revision: retire an edit that keeps failing


def _names(tried) -> List[str]:
    return [op + ("(+)" if kept else "") for op, kept in tried]


def _known(scorer: Scorer, g: Genome):
    """A program already evaluated is looked up, not re-run (and not charged)."""
    return scorer.cache[g] if g in scorer.cache else scorer(g)


def _campaign(steer: Scorer, base: Genome, ops_allowed: List[str], n: int, rng, budget: Budget):
    cur, cur_s = base, _known(steer, base)
    tried = []
    for _ in range(n):
        if not budget.can_afford(steer.cost()):
            break
        ops = [op for op in applicable(cur) if op.name in ops_allowed]
        if not ops:
            break
        op = ops[int(rng.integers(len(ops)))]
        child = op.apply(cur)
        s = steer(child)
        kept = s.beats(cur_s)
        tried.append((op.name, kept))
        if kept:
            cur, cur_s = child, s
    return cur, cur_s, tried


def run(ev: Evaluator, budget_runs: int, seed: int, mode: str = "conditional",
        start: Genome = BASELINE, edits_per_campaign: int = 3, log=None) -> dict:
    rng = np.random.default_rng(seed)
    budget = Budget(budget_runs)
    # Re-evaluating a candidate costs a run, as in every other method; looking up a known base does not (_known).
    # (With free repeats, a stuck team could loop forever without spending its budget.)
    steer = Scorer(ev, "steering", (0,), budget, caller=f"areal-{mode}")
    replicate = Scorer(ev, "steering", (1,), budget, caller=f"areal-{mode}-replicate")
    leader, memory = Leader(rng), ConditionalMemory()
    team = start
    own = {"R1": start, "R2": start}
    curve, campaign = [], 0
    _known(steer, start)
    while budget.can_afford(steer.cost() * 2) and campaign < 200:
        campaign += 1
        orients = leader.select(2) if mode != "independent" else list(rng.choice(ORIENTATIONS, 2, replace=False))
        findings = []
        for rname, o in zip(("R1", "R2"), orients):
            base = own[rname] if mode == "independent" else team
            skills = leader.skills[o] if mode == "conditional" else DIRECTIONS[o]
            g, s, tried = _campaign(steer, base, skills, edits_per_campaign, rng, budget)
            findings.append((rname, o, base, g, s, tried))
            if mode == "independent" and s.beats(_known(steer, base)):
                own[rname] = g
        if mode == "independent":
            best = max(own.values(), key=lambda g: steer.cache[g].key if g in steer.cache else -1)
            curve.append(steer.cache[best].rate)
            continue
        rname, o, base, g, s, tried = max(findings, key=lambda f: f[4].key)
        base_s = steer.cache[base]
        gain = s.rate - base_s.rate
        if g != base and s.beats(base_s):
            if mode == "conditional" and budget.can_afford(2 * replicate.cost()):
                ok = replicate(g).beats(_known(replicate, base), margin=0.0)  # does the gain survive a new seed?
                status = "resolved" if ok else "unresolved"
            else:
                status = "resolved"  # share_all: adopt without checking
            memory.store(Entry(campaign, rname, o, _names(tried), gain, status))
            if status == "resolved":
                team = g
            leader.review(o, gain if status == "resolved" else 0.0, tried)
        else:
            memory.store(Entry(campaign, rname, o, _names(tried), 0.0, "unresolved"))
            leader.review(o, 0.0, tried)
        for f in findings:
            if f[0] != rname:
                leader.review(f[1], 0.0, f[5])
        curve.append(steer.cache[team].rate)
        if log:
            log(f"  campaign {campaign}: {orients} -> best {rname}/{o} {base_s.rate:.3f}->{s.rate:.3f} "
                f"[{memory.entries[-1].status}] team={steer.cache[team].rate:.3f}")
    final = team if mode != "independent" else max(own.values(), key=lambda g: steer.cache[g].key)
    return {"mode": mode, "seed": seed, "final": final, "final_rate": steer.cache[final].rate,
            "campaigns": campaign, "runs_spent": budget.spent, "curve": curve,
            "resolved": len(memory.resolved()), "unresolved": len(memory.unresolved()),
            "values": dict(leader.value), "skills_retired": {o: sorted(set(DIRECTIONS[o]) - set(leader.skills[o])) for o in ORIENTATIONS},
            "memory": [e.__dict__ for e in memory.entries]}
