# 10.17 · Analyse metrics

**Group 05 · Environments and metrics** · Previous: [10.16](../10_16_environments/README.md) · Next: [Finale](../../06_finale/three_methods_showdown/README.md)

> **Question.** What does each October 2026 metric say about *our* runs, and what does it hide?

Every value is computed from the JSON files earlier labs saved in [`results/`](../../../results), not typed in:
RSI-Index (10.15), the steering vs held-out gap (10.03), recursive learnability of self-chosen tasks (10.16),
swarm diversity with and without migration (10.11), thrash rate (10.06), and a cost-normalised gain (held-out
solve rate per 1,000 instance-runs). For each: our value, what it measures, when it is useful, its limitation.

## Run it

```bash
python3 labs/05_environments_metrics/10_17_metrics/lab.py     # instant; run labs 10.03-10.16 first
```

## Output (full run)

<!-- output lines=60 -->
```text
$ python3 labs/05_environments_metrics/10_17_metrics/lab.py
==============================================================================
Lab 10.17 · Analyse metrics
Question: What does each October 2026 metric say about our runs, and what does it hide?
==============================================================================

  RSI-Index (RSIGym)
    our runs   : data=0.006, harness=0.132, joint=0.262
    measures   : fraction of remaining gap closed, averaged over benchmarks
    useful when: comparing systems across benchmarks of different difficulty
    limitation : ideal=1.0 is unreachable for short ciphers; hides which benchmark moved

  Steering-split solve rate (Budget RSI)
    our runs   : readout steer-heldout gap=+0.056, parent_rate steer-heldout gap=+0.069, oracle steer-heldout gap=+0.024
    measures   : performance on the split used to select
    useful when: cheap per-candidate signal during search
    limitation : inflated by selection (10.01); different text source from held-out

  Recursive learnability (R2Orch)
    our runs   : mean p(1-p) of chosen tasks = 0.160 over 12 choices
    measures   : how informative the self-chosen task is (max 0.25 at p=0.5)
    useful when: letting an improver pick its own curriculum
    limitation : 0 everywhere at the start (nothing partly solved), so it needs a fallback

  Swarm diversity (SwarmRSI)
    our runs   : full=0.06 vs no-migration=0.20
    measures   : mean pairwise fraction of genome fields that differ
    useful when: detecting a swarm that has collapsed to one idea
    limitation : high diversity is not high quality: no-migration is diverse and worse

  Thrash rate (SO-RSI behaviour)
    our runs   : naive=0.38/step, so-rsi=0.33/step
    measures   : opposing + recurrent edits per improvement step
    useful when: spotting first-order trial-and-error
    limitation : a low thrash rate can also mean the improver stopped exploring

  Cost-normalised gain (ours)
    our runs   : so-rsi=0.248, naive=0.288, conditional=0.107, adaptive=0.299
    measures   : held-out solve rate per 1,000 instance-runs
    useful when: comparing methods whose budgets differ
    limitation : not linear: the first runs buy more than the last
```
<!-- /output -->

## What the numbers say

| Metric | Our value | The catch |
|---|---|---|
| RSI-Index (10.15) | data 0.006 · harness 0.132 · joint 0.262 | an average over benchmarks; short_only barely moves for any track |
| steering − held-out gap (10.03) | +0.056 readout · +0.069 ablation · +0.024 oracle | selection inflates every steering score; fewer expansions (oracle) inflate less |
| recursive learnability (10.16) | mean p(1−p) = 0.160 over 12 self-chosen tasks | high learnability did not mean progress: 7 rounds stuck at 0.188 |
| swarm diversity (10.11) | 0.06 with migration · 0.20 without | the diverse variant is not the better one |
| thrash rate (10.06) | 0.38 per step naive · 0.33 SO-RSI | SO-RSI's lower thrash did not buy a better held-out score |
| held-out per 1,000 runs | naive 0.288 · RSIFlow 0.299 · SO-RSI 0.248 · AReaL 0.107 | nonlinear in budget; only comparable at equal budgets, which these are |

No single metric ranks the methods the way held-out does; each explains one part of *why* held-out moved.

## Quiz

1. *Why so many metrics?* Each RSI system changes a different object (program, workflow, swarm, environment); no single number covers all of them.
2. *Which metric would you report first?* Held-out solve rate at a stated budget, with seeds; the others explain *why* it moved.
