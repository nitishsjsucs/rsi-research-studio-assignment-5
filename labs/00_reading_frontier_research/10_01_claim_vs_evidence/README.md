# 10.01 · Distinguish claim from evidence

**Group 00 · Read a frontier claim** · [Course map §10](../../../README.md#the-17-codelabs) · Next: [10.02 Audit a paper](../10_02_audit_paper/README.md)

> **Question.** Does the best score *after selection* survive re-measurement?

## Why this lab exists

Every RSI paper reports a headline number, and nearly every headline is the score of the best candidate
*after a search chose it*. The search itself inflates that number: among many noisy candidates, the
winner is partly the luckiest. Before rebuilding any October 2026 method, this lab makes the difference
between a claim and its evidence concrete twice: once on paper (claim cards) and once in an experiment.

## What the code does

| Part | Code | What happens |
|---|---|---|
| A | `CARDS` and `write_cards()` in [lab.py](lab.py) | three claim cards (Budget RSI, SO-RSI, SwarmRSI): claim · evidence as summarised · untested · what our laptop adaptation preserves and changes → [`claim_evidence_analysis.md`](claim_evidence_analysis.md) |
| B | `main()` in [lab.py](lab.py) | one mid-strength program (`3-gram words×2 freq hill 4x2000`) gets 16 random single edits; each runs on the **steering** split (seed 0); the best is the "headline" |
| B | `fresh` / `unseen` scorers in `main()` | the winner and its parent are re-run on **fresh seeds of the same ciphers** and on **unseen probe ciphers** |

Walkthrough:

1. [`Scorer`](../../../cipherlab/loop.py#L65) wraps the evaluator: one call = one program on one split, cost counted in instance-runs.
2. [`applicable()`](../../../cipherlab/edits.py#L114) lists the edits that change this program; the lab samples 16 without replacement.
3. Each edit is [rendered to real source](../../../cipherlab/program.py#L83) and run by the [harness](../../../cipherlab/runtime.py#L92); `steer(...)` returns solved counts.
4. The table sorts by steering score; the top row is the headline. The second table re-measures it.

## Run it

```bash
python3 labs/00_reading_frontier_research/10_01_claim_vs_evidence/lab.py           # ~1 min
python3 labs/00_reading_frontier_research/10_01_claim_vs_evidence/lab.py --quick   # 8 edits
```

## Output (full run, captured by `run_all.py`)

<!-- output from="--- Part B" lines=40 -->
```text
--- Part B: the winner's curse on 16 candidate edits ------------------------
  parent: 3-gram words×2 freq hill 4x2000  steering(seed 0) = 0.312
  edit            steering  gain  
  --------------  --------  ------
  iters_up        0.479     +0.167
  add_polish      0.458     +0.146
  restarts_up     0.438     +0.125
  vocab_down      0.354     +0.042
  words_down      0.354     +0.042
  ngram_down      0.333     +0.021
  smoothing_up    0.312     +0.000
  words_up        0.312     +0.000
  ngram_up        0.292     -0.021
  smoothing_down  0.292     -0.021
  init_random     0.292     -0.021
  vocab_up        0.271     -0.042
  restarts_down   0.208     -0.104
  remove_words    0.188     -0.125
  iters_down      0.167     -0.146
  swap_ranked     0.042     -0.271

--- Headline vs evidence ----------------------------------------------------
  measurement                        parent  winner (iters_up)  gain  
  ---------------------------------  ------  -----------------  ------
  steering, seed 0 (used to SELECT)  0.312   0.479              +0.167
  steering, fresh seeds 1-2          0.365   0.375              +0.010
  unseen probe ciphers, seeds 0-1    0.312   0.312              +0.000

  6/16 edits 'beat' the parent on the selection split.
  The headline gain +0.167 shrinks by +0.156 on fresh seeds of the SAME ciphers.
  Claim: 'edit X improves the solver by the headline amount'.
  Evidence: only the re-measured gains, with their spread, support a claim.

done in 40s
```
<!-- /output -->

## What the numbers say

- 6 of 16 edits "beat" the parent on the selection split. The winner, `iters_up`, scores **+0.167** there (0.312 → 0.479).
- On fresh seeds of the *same* 48 ciphers its gain is **+0.010**; on 24 unseen ciphers it is **+0.000**.
- So 94% of the headline gain was the selection picking up seed-0 luck. "Doubling iterations adds 17 points" is a
  claim; "+0.01 ± noise on re-measurement" is the evidence. Every later lab therefore selects on steering and
  reports held-out, with seeds.

## Quiz

1. *Can the Budget RSI paper claim its readout works for every code-editing task?* No. It measured HumanEval+ and Polyglot with GPT-4o; our card lists what remains untested.
2. *Why does the headline shrink on fresh seeds of the same ciphers?* The winner was chosen *because* it scored well on seed 0; part of that score is seed-0 luck that does not repeat (regression to the mean).
3. *What would make a gain claim credible?* The gain measured on data the selection never saw, over several seeds, with its spread, next to the selection-time number.
