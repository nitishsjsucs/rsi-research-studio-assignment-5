# 10.02 · Audit an October 2026 paper

**Group 00 · Read a frontier claim** · Previous: [10.01](../10_01_claim_vs_evidence/README.md) · Next: [10.03 Run Budget RSI](../../01_budget_rsi_scoring/10_03_run_budget_rsi/README.md)

> **Question.** What did the experiment actually measure, and can a ledger prove it?

## Why this lab exists

The course's audit template asks five questions of a paper: what object changed, what feedback connected
the parts, what evaluation protocol was used, what it cost, and what remains untested. Part A answers them
for the three papers this repo rebuilds. Part B goes one step further: it audits an *experiment in code*,
from the evaluator's own access ledger, so "we never looked at the test set" becomes a checkable fact.

## What the code does

| Part | Code | What happens |
|---|---|---|
| A | `AUDITS` + `write_audits()` in [lab.py](lab.py) | [`paper_audit_budget_rsi.md`](paper_audit_budget_rsi.md), [`paper_audit_so_rsi.md`](paper_audit_so_rsi.md), [`paper_audit_swarm_rsi.md`](paper_audit_swarm_rsi.md) |
| B1 | `greedy(..., peek_heldout=True)` | a flawed comparison: peeks at held-out (the evaluator **refuses** with `SealedSplitError`; the "author" then unseals to peek anyway, which leaves a ledger entry), gives the baseline 2× budget, uses 1 seed |
| B2 | `greedy(...)` × 3 seeds | the clean comparison: sealed, matched, 3 seeds |
| both | [`audit()`](../../../cipherlab/audit.py#L17) | four rules read from the [ledger](../../../cipherlab/evaluate.py#L63) and the run records |

Walkthrough:

1. The evaluator is created with `heldout` sealed; [`run()` raises](../../../cipherlab/evaluate.py#L94) for any sealed split.
2. Every call is [charged to the ledger](../../../cipherlab/evaluate.py#L63) with the split, the number of runs, a caller tag and a timestamp.
3. `audit()` compares held-out access times to the moment the final report began, budget spread (±5%), seeds per arm (≥ 3), and whether both steering and held-out are recorded.

## Run it

```bash
python3 labs/00_reading_frontier_research/10_02_audit_paper/lab.py      # ~1-2 min
```

## Output (full run)

<!-- output from="--- Part B1" lines=30 -->
```text
--- Part B1: the flawed comparison ------------------------------------------
    blocked: 10.02-PEEK asked for the sealed 'heldout' split
  [FAIL] sealed held-out  1 held-out access(es) before the final report
  [FAIL] matched budgets  greedy: 576-576 runs, random: 1152-1152 runs
  [FAIL] enough seeds     greedy: 1, random: 1
  [PASS] gap reported     steering and held-out recorded for every run
  verdict: claim NOT supported by this evidence

--- Part B2: the clean comparison -------------------------------------------
  [PASS] sealed held-out  held-out touched only in the final report
  [PASS] matched budgets  greedy: 576-576 runs, random: 576-576 runs
  [PASS] enough seeds     greedy: 3, random: 3
  [PASS] gap reported     steering and held-out recorded for every run
  arm     seeds  steering       held-out     
  ------  -----  -------------  -------------
  greedy  3      0.312 ± 0.091  0.330 ± 0.109
  random  3      0.153 ± 0.064  0.115 ± 0.068
  verdict: claim may be stated, with these numbers
  ledger: heldout: 576 runs, steering: 3168 runs

done in 48s
```
<!-- /output -->

## What the numbers say

- **Flawed comparison:** the evaluator refused the held-out peek; the "fix" (unsealing) left a ledger entry, so the
  audit fails *sealed held-out*; it also fails *matched budgets* (576 vs 1,152 runs) and *enough seeds* (1). Verdict: not supported.
- **Clean comparison:** all four rules pass; the greedy improver reaches **0.330 ± 0.109** held-out vs **0.115 ± 0.068**
  for random edits, over 3 seeds at 576 runs each. That claim may be stated, with those numbers.
- The same `audit()` runs at the end of the finale over every method's ledger.

## Quiz

1. *Why identify untested assumptions before implementing?* Implementation effort should go where uncertainty is largest; an untested foundational assumption deserves an ablation (lab 10.04 finds one: diff shape is blind to edit direction).
2. *Can a laptop adaptation prove a paper's headline?* No. It can show the mechanism behaves as described at small scale; scale, data and models differ.
3. *Why read a ledger rather than trust the code?* Code paths change; a ledger records what actually ran. The flawed run "fixed" the refusal by unsealing, and the ledger caught it.
