# 10.07 · Analyse the diagnostic probes

**Group 02 · SO-RSI** · Previous: [10.06](../10_06_run_so_rsi/README.md) · Next: [10.08](../10_08_apply_to_debugging/README.md)

> **Question.** When does each anomaly fire, and do the probes recommend the edit that actually helps?

## What the code does

1. **Counts** each anomaly type in the 10.06 traces (`results/10_06_so_rsi.json`), per arm, with the
   recommendations SO-RSI's probes produced after it fired and a one-line reason each helps.
2. **Shows the objective-gap probe on one real cipher.** The weak baseline (2-gram, random start) decrypts a
   Sherlock sentence into near-English nonsense, and its *own* fitness scores that nonsense above the true
   plaintext. That is the signature of an objective problem: search harder and you converge on the wrong answer faster.
3. **Validates the probes causally.** For three programs of increasing strength: probe, then run the
   *recommended* edit and an edit the probe calls *futile* on the steering split. A probe is worth its cost
   only if its recommendation wins.

## Run it

```bash
python3 labs/02_second_order_diagnostics/10_07_analyze_probes/lab.py      # ~1 min (needs 10.06 results for part 1)
```

## Output (full run)

<!-- output lines=70 -->
```text
$ python3 labs/02_second_order_diagnostics/10_07_analyze_probes/lab.py
==============================================================================
Lab 10.07 · Analyse diagnostic probes
Question: When does each anomaly fire, and do the probes recommend the edit that actually helps?
==============================================================================

--- 1. Anomalies in the 10.06 traces ----------------------------------------
  anomaly     naive  so-rsi  typical recommendation         why it helps                                                             
  ----------  -----  ------  -----------------------------  -------------------------------------------------------------------------
  recurrence  23     15      init_frequency, restarts_down  the edit's assumption is wrong for this program; stop paying for it      
  opposing    21     17      init_frequency, restarts_down  two edits fight over one knob; the knob is not the bottleneck            
  mismatch    43     20      ngram_up, add_words            the model of the system is wrong (e.g. the cap truncates 'search longer')

  mechanisms diagnosed across SO-RSI runs: short_texts=15, cap_bound=9, objective=6, undersearched=4, local_optima=4, high_variance=3

--- 2. The objective-gap probe on one cipher --------------------------------
  program: 2-gram rand hill 1x1000
  cipher : yabgf kpn xap snf arh fkjg pgvkpjgm fogpyauj oayvgf naffshw kfsmg nog kmbgpnsfgvghn foggn 
  found  : moves art bor its own sace relarced shermofc homles tossing aside the advertiselent sheet 
  truth  : loves art for its own sake remarked sherlock holmes tossing aside the advertisement sheet 
  fitness(found) = -414.8  >=  fitness(truth) = -416.9
  The program's own objective prefers the wrong answer. Searching harder converges on it faster.

--- 3. Do the recommendations win? (probe, then test both edits on steering) 
  2-gram rand hill 1x1000
    probe: fail=48/48 obj_gap=0.33 stalled=0.04 under=0.73 cap=0.00 var=0.00 [short=0.00 medium=0.00 long=0.00]
    mechanisms: ['undersearched']
      - 73% of failures were still improving when the program stopped itself
  4-gram words×2 rand hill 2x1000
    probe: fail=44/48 obj_gap=0.00 stalled=0.50 under=0.43 cap=0.00 var=0.08 [short=0.00 medium=0.00 long=0.33]
    mechanisms: ['local_optima', 'undersearched']
      - 50% of failures stopped improving in the first half of their budget
      - 43% of failures were still improving when the program stopped itself
  3-gram words×2 freq hill 2x10000
    probe: fail=36/48 obj_gap=0.00 stalled=0.61 under=0.00 cap=0.00 var=0.08 [short=0.00 medium=0.17 long=0.83]
    mechanisms: ['local_optima', 'short_texts']
      - 61% of failures stopped improving in the first half of their budget
      - short ciphers solve 0% vs long 83%
  program                           diagnosis                   base   recommended  after  futile         after
  --------------------------------  --------------------------  -----  -----------  -----  -------------  -----
  2-gram rand hill 1x1000           undersearched               0.000  iters_up     0.021  iters_down     0.000
  4-gram words×2 rand hill 2x1000   local_optima,undersearched  0.062  use_anneal   0.042  restarts_down  0.021
  3-gram words×2 freq hill 2x10000  local_optima,short_texts    0.333  use_anneal   0.500  iters_up       0.250

  recommended edit beat the 'futile' edit in 3/3 cases.
  Remedy table the probes draw from: objective->['ngram_up', 'add_words']; local_optima->['use_anneal', 'restarts_up']; undersearched->['iters_up', 'restarts_up']; cap_bound->['init_frequency', 'restarts_down']; short_texts->['add_words', 'words_up']; high_variance->['restarts_up', 'use_anneal']

done in 45s
```
<!-- /output -->

## What the numbers say

- **SO-RSI's traces have fewer of every anomaly** than the naive loop's (recurrence 15 vs 23, opposing 17 vs 21,
  mismatch 20 vs 43, summed over 3 seeds). The commonest diagnosis is `short_texts` (15): short ciphers are the hard
  core of this task, and only prior knowledge (the dictionary) helps there.
- **The objective gap is visible on one cipher:** the 2-gram program's best decryption, *"moves art bor its own sace
  relarced shermofc homles..."*, scores −414.8 by its own objective; the true plaintext scores −416.9. Search did its
  job; the objective is wrong.
- **Probes pick the better edit 3 of 3 times**, but "better" is relative: in case 2 the recommended `use_anneal`
  (0.042) beat the futile `restarts_down` (0.021) while both scored *below* the starting program (0.062). A probe can
  rank remedies correctly and still not find one that helps.
- **The 2-gram baseline sits just under the objective threshold** (objective gap 0.33 vs 0.35 in `probes.py`), so it
  is diagnosed `undersearched` only. Thresholds are hand-set; a different threshold would recommend `ngram_up` first.

## Quiz

1. *Can several anomalies fire at once?* Yes; 10.06's logs show e.g. `['recurrence', 'mismatch']` on one step. All of them go into one finding.
2. *What if a probe finds no clear mechanism?* The finding is recorded with no recommendation and is retired as inconclusive after 8 rounds ([`retire_stale`](../../../cipherlab/methods/so_rsi.py#L115)); the proposer falls back to its prior.
3. *Why is `fitness_true` a fair signal to use?* The harness computes it for scoring the run, never shows it to the program; the improver sees only an aggregate over failures on the probe split, not any key.
