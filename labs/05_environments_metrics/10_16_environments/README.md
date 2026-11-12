# 10.16 · Compare environments

**Group 05 · Environments and metrics** (RSIGym, Terminal-RSI, R2Orch) · Previous: [10.15](../10_15_rsi_index/README.md) · Next: [10.17](../10_17_metrics/README.md)

> **Question.** What does each environment interface cost, and what does it let the improver do?

The same greedy improver, same seed, same budget, in three environment styles:

| Style | Paper | Here (`lab.py`) |
|---|---|---|
| Everything-as-a-Service | RSIGym | `eaas()`: in-process services with permissions and one budget |
| Terminal | Terminal-RSI | `terminal()`: each evaluation is a shell command, `python3 -m cipherlab.cli evaluate ...`, JSON on stdout ([`cli.py`](../../../cipherlab/cli.py)) |
| Self-play task choice | R2Orch | `self_play()`: the improver picks the length bucket whose success rate *p* maximises *p(1-p)* ("recursive learnability"), practises there cheaply, re-profiles |

All three are scored the same way at the end: steering (2 seeds), then held-out.

## Run it

```bash
python3 labs/05_environments_metrics/10_16_environments/lab.py           # ~4-6 min (the terminal arm starts a process per evaluation)
python3 labs/05_environments_metrics/10_16_environments/lab.py --quick
```

## Output (full run)

<!-- output from="--- Self-play" lines=30 -->
```text
--- Self-play / R2Orch-style task choice (1152 runs) ------------------------
  practise on 'long' (p(1-p)=0.000) -> probe rate 0.104  3-gram rand hill 2x2000
  practise on 'long' (p(1-p)=0.243) -> probe rate 0.167  3-gram rand hill polish 2x2000
  practise on 'long' (p(1-p)=0.222) -> probe rate 0.250  3-gram rand hill polish 8x2000
  practise on 'medium' (p(1-p)=0.000) -> probe rate 0.083  4-gram rand hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.139) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.188) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.188) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.188) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.188) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.188) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.188) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000
  practise on 'medium' (p(1-p)=0.188) -> probe rate 0.250  4-gram freq hill ranked polish 8x2000

--- Same final check for all three (steering, then held-out) ----------------
  environment  runs  seconds  steering  held-out  program                              
  -----------  ----  -------  --------  --------  -------------------------------------
  EaaS         1152  16.5     0.406     0.375     4-gram rand anneal T4 polish 8x4000  
  terminal     1152  33.4     0.406     0.375     4-gram rand anneal T4 polish 8x4000  
  self-play    1164  12.5     0.292     0.297     4-gram freq hill ranked polish 8x2000

  EaaS and terminal run the same improver with the same seed: same program, different cost.
  Terminal isolation (a crash cannot take the improver down) costs a process start per evaluation.
  Self-play spent its budget on 12 self-chosen practice tasks: [('long', 0.0), ('long', 0.243), ('long', 0.222), ('medium', 0.0), ('medium', 0.139), ('medium', 0.188), ('medium', 0.188), ('medium', 0.188), ('medium', 0.188), ('medium', 0.188), ('medium', 0.188), ('medium', 0.188)]

done in 83s
```
<!-- /output -->

## What the numbers say

| Environment | Runs | Wall-clock | Steering | Held-out |
|---|---:|---:|---|---|
| EaaS (in-process services) | 1,152 | 16.5 s | 0.406 | 0.375 |
| terminal (a process per evaluation) | 1,152 | 33.4 s | 0.406 | 0.375 |
| self-play (own task choice) | 1,164 | 12.5 s | 0.292 | 0.297 |

- **Same improver, same seed, same program** for EaaS and terminal: the transport changes cost (+0.27 s of process
  start per evaluation, 2× wall-clock here) and isolation, not results.
- **Self-play was cheapest per edit and ended weakest.** Its choices are instructive: it first practised on long
  ciphers until they were nearly solved (p(1−p) fell from 0.243 to 0.222), switched to medium ones, then stayed on
  medium at p(1−p) = 0.188 for seven rounds without progress. "Most learnable" is not "most improvable": a bucket at
  p ≈ 0.25 can be stuck for a structural reason, and self-play alone does not ask why (an SO-RSI probe would).

## Quiz

1. *Why do EaaS and terminal return the same program?* Same improver, same seed, same evaluations: only the transport differs. That isolates the transport's cost.
2. *Why does self-play need a fallback task rule?* At the start nothing is partly solved, so *p(1-p)* is 0 everywhere.
