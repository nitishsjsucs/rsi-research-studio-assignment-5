# 10.12 · Compare workflow adaptation: RSIFlow vs Self-HPO

**Group 04 · Adaptive workflows** (arXiv:2610.21791, arXiv:2610.22791) · Previous: [10.11](../../03_scaling_coordination/10_11_swarm_rsi/README.md) · Next: [10.13](../10_13_rsiflow_meta_agent/README.md)

> **Question.** Which object does each method adapt, and on what signal?

Both papers adapt *how* improvement happens, but not the same thing. A short run of each prints what changes
between steps: RSIFlow prints `workflow:` lines when its meta-agent rewires the stages; Self-HPO prints `H`/`P`
notes as it alternates between the program's harness and its policy weights.

| | RSIFlow | Self-HPO |
|---|---|---|
| Implementation | [`methods/rsiflow.py`](../../../cipherlab/methods/rsiflow.py) | [`methods/self_hpo.py`](../../../cipherlab/methods/self_hpo.py) |
| What adapts | which stages run (PROFILE, SCREEN...) | which half of the program is optimised |

## Run it

```bash
python3 labs/04_adaptive_workflows/10_12_compare_workflows/lab.py     # ~1-2 min
```

## Output (full run)

<!-- output lines=50 -->
```text
$ python3 labs/04_adaptive_workflows/10_12_compare_workflows/lab.py
==============================================================================
Lab 10.12 · Compare workflow adaptation
Question: Which object does each method adapt, and on what signal?
==============================================================================

--- RSIFlow, adaptive (1536 runs): watch the workflow change ----------------
  step 01 workflow: PROPOSE -> EVALUATE -> INTEGRATE
    PROFILE: ['cap_bound', 'short_texts'] -> remedies ['init_frequency', 'restarts_down', 'use_anneal', 'remove_polish']
  step 27 workflow: PROFILE -> PROPOSE[7 remedies] -> SCREEN -> EVALUATE -> INTEGRATE
  step 30 workflow: PROPOSE -> SCREEN -> EVALUATE -> INTEGRATE
  -> 0.625; rules: {'screen_on_low_yield': {'enabled': True, 'activations': 1, 'usefulness': -0.0039}, 'profile_on_stall': {'enabled': True, 'activations': 1, 'usefulness': -0.0039}, 'cap_guard': {'enabled': True, 'activations': 1, 'usefulness': -0.0084}, 'drop_dead_target': {'enabled': True, 'activations': 0, 'usefulness': 0.0}}

--- Self-HPO, alternating (1536 runs): watch the object change --------------
  H1: H: init_frequency (from ['local_optima', 'short_texts']) solves 6/37 hard -> 0.229
  P2: P: 4 policy perturbations -> moved -> 0.229
  H3: H: use_anneal (from ['short_texts']) solves 6/37 hard -> 0.250
  P4: P: 4 policy perturbations -> moved -> 0.375
  H5: H: restarts_up (from ['local_optima', 'short_texts']) solves 5/30 hard -> 0.479
  P6: P: 4 policy perturbations -> stayed -> 0.479
  H7: H: iters_up (from ['local_optima', 'short_texts']) solves 7/25 hard -> 0.625
  P8: P: 4 policy perturbations -> stayed -> 0.625
  -> 0.229 -> 0.625

--- Comparison --------------------------------------------------------------
  aspect        RSIFlow                                                          Self-HPO                                                
  ------------  ---------------------------------------------------------------  --------------------------------------------------------
  What adapts   the workflow graph: which stages run, in what order              the program: harness (discrete) then policy (continuous)
  Signal        execution feedback about the improver (yield, stalls, cap hits)  the policy's own failures on hard instances             
  Who proposes  a meta-agent with rules that can be switched off                 the policy itself proposes harness candidates           
  Iteration     continuous: any step may rewire                                  alternating H-step / P-step                             
  Second order  rule usefulness scores evolve the meta-agent                     the harness search set is the policy's evolving failures
  Prefer when   the bottleneck moves during the run                              the system has a learnable part and a scaffold part     

done in 42s
```
<!-- /output -->

## What the numbers say

- RSIFlow ran unchanged for 26 steps, then rewired at step 27, when the program hit the evaluation cap and
  acceptances dried up: `PROFILE -> PROPOSE[7 remedies] -> SCREEN -> EVALUATE -> INTEGRATE`. The bottleneck it
  reacted to appeared late, so a short run would show no adaptation at all (the first version of this demo, with
  16 steps, showed none).
- Self-HPO's notes alternate between the two objects every step; its H-steps name the mechanism they target
  (`from ['local_optima', 'short_texts']`), its P-steps only report whether the weights moved.

## Quiz

1. *When is RSIFlow preferable?* When the bottleneck moves during a run (first search depth, then the objective, then the cap).
2. *When is Self-HPO preferable?* When the system has a learnable part (weights) and a scaffold part that constrain each other.
