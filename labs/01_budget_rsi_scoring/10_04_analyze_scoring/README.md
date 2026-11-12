# 10.04 · Analyse the scoring mechanism

**Group 01 · Budget RSI** · Previous: [10.03](../10_03_run_budget_rsi/README.md) · Next: [10.05](../10_05_extend_readout/README.md)

> **Question.** Which parts of a diff predict a better program, and what can a diff not see?

## What the code does

No new search: the lab opens the readout trained on the 96 cached edits from 10.03.

1. **A real diff, read as features.** `add_words` on a 3-gram program, printed as a unified diff, then its 8
   coordinates from [`diff_features()`](../../../cipherlab/program.py#L209). One import, one constant, one new
   function, one changed `return` line: that is what "adding a dictionary" looks like to the readout.
2. **Feature importance.** Standardised ridge coefficients, ranked by magnitude.
3. **Ranking unseen edits.** `cv_delta_corr()` in [lab.py](lab.py): 4-fold cross-validation, correlation
   between predicted and actual *gain* (child − parent), the quantity selection depends on.
4. **The course's two questions, answered with numbers.** 8 coordinates vs 4 vs parent-only; 12/24/48/96
   training edits (5 random draws each).
5. **The blind spot.** Mean predicted vs actual gain per edit type, and the coordinates of `iters_up` and
   `iters_down` side by side: identical.

## Run it

```bash
python3 labs/01_budget_rsi_scoring/10_04_analyze_scoring/lab.py      # seconds (uses the cached training set)
```

## Output (full run)

<!-- output lines=75 -->
```text
$ python3 labs/01_budget_rsi_scoring/10_04_analyze_scoring/lab.py
==============================================================================
Lab 10.04 · Analyse the scoring mechanism
Question: Which parts of a diff predict a better program, and what can a diff not see?
==============================================================================

--- 1. One real edit, read as a diff ----------------------------------------
   --- parent.py
   +++ child.py
   @@ -3,0 +4 @@
   +from cipherlab.runtime import word_hits
   @@ -7,0 +9 @@
   +WORD_WEIGHT = 2.0
   @@ -8,0 +11 @@
   +VOCAB = 3000
   @@ -15,0 +19,4 @@
   +def word_score(p, ctx):
   +    return WORD_WEIGHT * word_hits(p, ctx, VOCAB)
   +
   +
   @@ -17 +24 @@
   -    return ngram_score(p)
   +    return ngram_score(p) + word_score(p, ctx)
  coordinates: lines_added=8, lines_deleted=1, hunks=5, defs_added=1, defs_removed=0, imports_changed=1, constants_changed=2, control_flow_changed=3

--- 2. Feature importance (standardised ridge coefficients) -----------------
  feature               coefficient
  --------------------  -----------
  parent_score          +0.0571    
  lines_added           +0.0430    
  constants_changed     +0.0242    
  hunks                 -0.0184    
  imports_changed       +0.0153    
  defs_added            -0.0093    
  lines_deleted         +0.0087    
  control_flow_changed  -0.0074    
  defs_removed          -0.0011    

--- 3. Does it rank unseen edits? (4-fold cross-validation) -----------------
  corr(predicted gain, actual gain) on held-out folds: +0.175

--- 4a. 8 diff features vs 4 ------------------------------------------------
  features                                          k  cv corr(gain)
  ------------------------------------------------  -  -------------
  parent + 8 diff coordinates                       9  +0.175       
  parent + 4 (added, deleted, defs_added, imports)  5  +0.201       
  parent only (the ablation)                        1  -0.103       

--- 4b. Fewer training edits ------------------------------------------------
  edits  cv corr(gain)  sd over 5 draws
  -----  -------------  ---------------
  12     +0.115         0.082          
  24     +0.079         0.206          
  48     +0.198         0.100          
  96     +0.206         0.019          

--- 5. The blind spot: same diff shape, opposite meaning --------------------
  edit           n   predicted gain  actual gain
  -------------  --  --------------  -----------
  iters_up       10  +0.0105         +0.0088    
  iters_down     5   -0.0009         -0.0183    
  restarts_up    9   +0.0057         +0.0391    
  restarts_down  3   +0.0055         -0.0123    
  ngram_up       7   -0.0015         -0.0008    
  ngram_down     10  -0.0034         -0.0218    
  temp_up        1   -0.0004         -0.0853    
  temp_down      2   +0.0071         +0.0010    
  add_words      5   +0.0230         +0.0200    
  remove_words   1   +0.0203         +0.0076    
  use_anneal     5   +0.0039         +0.0059    
  use_hill       2   -0.0490         -0.0278    

  iters_up   coordinates: [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 2.0, 0.0]
  iters_down coordinates: [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 2.0, 0.0]
  identical: True. A diff-shape readout cannot tell 'search more' from 'search less'.
...
```
<!-- /output -->

## What the numbers say

- **`lines_added` is the strongest diff signal (+0.043)**, then `constants_changed` (+0.024): edits that add code
  (a dictionary term, a polishing sweep) tend to help; `hunks` is negative (scattered rewrites tend to hurt).
- **Cross-validated ranking skill is modest: r = +0.18** between predicted and actual gain on unseen edits
  (parent-only: −0.10). Modest is enough: selection only needs the top of 6 siblings to be better than a random pick, and lab 10.03 shows it is.
- **4 coordinates do as well as 8 here (+0.20 vs +0.18)**: the 8 are strongly correlated (an added function adds lines, defs and often an import).
- **More training edits mostly buy stability**: the spread over 5 random draws falls from 0.21 (24 edits) to 0.02 (96).
- **The blind spot is real**: `iters_up` and `iters_down` have identical coordinates. Their mean predictions differ
  (+0.011 vs −0.001) only because they were applied to different parents (`parent_score`); for the *same* parent
  the readout would score them identically, although on average one helps (+0.009) and the other hurts (−0.018).

## Quiz

1. *Why a linear model?* Selection needs a ranking among 6 siblings in microseconds, trained on 96 examples. A linear model is fast, data-efficient and inspectable; the point is cheap screening, not accuracy.
2. *What happens with correlated features?* Importance is split between them (e.g. `lines_added` and `defs_added`), so single coefficients are hard to read; predictive power is shared, not lost.
3. *Why can't the readout tell `iters_up` from `iters_down`?* Both change one constant on one line: same hunk count, same lines added and deleted. Diff *shape* has no sign. Lab 10.05 adds signed coordinates read from the same patch.
