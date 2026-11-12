# 10.09 · Compare scaling approaches: AReaL-RSI vs SwarmRSI

**Group 03 · Scaling RSI: coordination and swarms** (arXiv:2610.18083, arXiv:2610.20431) · Previous: [10.08](../../02_second_order_diagnostics/10_08_apply_to_debugging/README.md) · Next: [10.10](../10_10_areal_leader_follower/README.md)

> **Question.** How do a leader-led team and a peer swarm spend the same budget?

## What the code does

Before the full runs in 10.10 and 10.11, both systems run briefly (24 evaluations each) from the same baseline,
with logging on, so you can see *who talks to whom*: AReaL's leader assigns orientations, researchers report,
the leader replicates and writes the conditional memory; the swarm's agents each move, the improved ones are
merged, and laggards migrate. The comparison table (advantage, limitation, when to choose each) is printed after
the traces, and its rows are the ones the traces and the full labs actually support.

| | AReaL-RSI | SwarmRSI |
|---|---|---|
| Implementation | [`methods/areal.py`](../../../cipherlab/methods/areal.py) | [`methods/swarm_rsi.py`](../../../cipherlab/methods/swarm_rsi.py) |
| Unit of work | a *campaign*: 2 researchers × 3 edits, then replication | a *generation*: 5 agents × 1 edit, then recombination |

## Run it

```bash
python3 labs/03_scaling_coordination/10_09_compare_scaling/lab.py     # ~1 min
```

## Output (full run)

<!-- output lines=60 -->
```text
$ python3 labs/03_scaling_coordination/10_09_compare_scaling/lab.py
==============================================================================
Lab 10.09 · Compare scaling approaches
Question: How do a leader-led team and a peer swarm spend the same budget?
==============================================================================

--- AReaL-RSI, conditional memory (1152 runs) -------------------------------
  campaign 1: ['objective', 'search'] -> best R2/search 0.000->0.083 [resolved] team=0.083
  campaign 2: ['search', 'diversify'] -> best R1/search 0.083->0.083 [unresolved] team=0.083
  campaign 3: ['efficiency', 'search'] -> best R1/efficiency 0.083->0.083 [unresolved] team=0.083
  campaign 4: ['search', 'diversify'] -> best R1/search 0.083->0.083 [unresolved] team=0.083
  -> 0.083 after 4 campaigns; resolved=1 unresolved=3

--- SwarmRSI (1152 runs) ----------------------------------------------------
  g1 objective  smoothing_up    -> 0.000 KEEP
  g1 search     iters_down      -> 0.000 drop
  g1 diversify  iters_down      -> 0.000 drop
  g1 efficiency iters_down      -> 0.000 drop
  g1 explorer   smoothing_up    -> 0.000 KEEP
  g2 objective  smoothing_down  -> 0.000 drop
  g2 search     use_anneal      -> 0.000 drop
  g2 diversify  use_anneal      -> 0.000 drop
  g2 efficiency init_frequency  -> 0.000 KEEP
  g2 explorer   smoothing_up    -> 0.000 drop
  g3 objective  smoothing_up    -> 0.000 drop
  g3 search     iters_up        -> 0.021 KEEP
  g3 diversify  init_frequency  -> 0.000 KEEP
  g3 efficiency iters_down      -> 0.000 drop
  g3 explorer   swap_ranked     -> 0.000 drop
  g3 recombine search+diversify -> 0.021 NEW LEADER
  g4 objective  ngram_down      -> 0.000 drop
  g4 search     use_anneal      -> 0.125 KEEP
  g4 diversify  use_anneal      -> 0.021 drop
  g4 efficiency add_polish      -> 0.021 KEEP
  g4 explorer   use_anneal      -> 0.021 drop
  g4 recombine search+efficiency -> 0.125 NEW LEADER
  g5 objective  ngram_up        -> 0.104 drop
  -> 0.125 after 5 generations, leader=objective

--- Communication pattern observed ------------------------------------------
  AReaL : leader -> {R1, R2} assignments; R* -> leader findings; leader -> replicate -> memory -> team program
  Swarm : every agent -> shared experience; improved agents -> recombination; leader -> laggards (migration)

--- Comparison --------------------------------------------------------------
  aspect          AReaL-RSI (leader-follower)                                               SwarmRSI (peer swarm)                                           
  --------------  ------------------------------------------------------------------------  ----------------------------------------------------------------
  Coordination    leader assigns orientations to specialist researchers                     peers; no one assigns work                                      
  Memory          conditional: replicated findings are shared, the rest stay open problems  shared experience table: every result, weighted by recency      
  Evolution       evidence-based review revises orientation values and retires skills       mutation + recombination + re-weighted proposal distributions   
  Selection       leader-guided (UCB over resolved evidence)                                competitive (laggards migrate to the leader)                    
  Pays extra for  replication runs (a second seed) before sharing                           breadth: five evaluations per generation                        
  Advantage       noise-robust: an unreplicated gain never becomes team fact                parallel depth: many directions per sequential round            
  Limitation      replication costs 2 of every 8 evaluations (a quarter fewer edits)        at a fixed compute budget, fewer sequential steps than one agent
  Choose it when  evaluations are noisy and a wrong 'fact' is expensive                     wall-clock rounds are the bottleneck, compute is not            

done in 7s
```
<!-- /output -->

## What the numbers say

The short runs are traces, not results: at 24 evaluations both systems are barely past the baseline (AReaL 0.083
after 4 campaigns, swarm 0.125 after 5 generations). What they show is the *shape* of each method's spending: AReaL
spends 2 of every 8 evaluations on replication and moves the team program at most once per campaign; the swarm
spends 5 evaluations per generation and moves at most one leader per generation. Both are therefore less
sample-efficient than a single greedy chain at equal compute, which 10.10 and 10.11 measure.

## Quiz

1. *When is leader-follower better than a swarm?* When evaluations are noisy and a wrong shared "fact" is costly: the leader replicates before sharing.
2. *When is a swarm better?* When the bottleneck is sequential wall-clock rounds (e.g. slow agent calls) rather than compute: five directions advance per round.
