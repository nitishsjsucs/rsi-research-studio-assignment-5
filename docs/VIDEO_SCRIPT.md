# Recording script: one video per part

Each part is a 6-12 minute screen recording: the README section, the code, a live run, the committed full-run
output. Run labs live with `--quick` (small budgets, one seed, under a minute each), then open the committed
`output.txt` for the full numbers. Keep a terminal and an editor side by side.

Before recording anything:

```bash
python3 run_tests.py                 # 35 tests, ~1 s: show it is green
python3 -m cipherlab.cli solve --genome '{"ngram":4,"word_weight":2.0,"init":"frequency","search":"anneal","temp0":10.0,"iters":5000,"restarts":4}' --text "the detective looked at the strange marks on the door and said that the thief had come in through the window before the rain began"
```

---

## Part 0 · The problem and the harness (intro)

**Open:** `README.md` (top, "The problem"), `cipherlab/program.py`, `cipherlab/runtime.py`, `cipherlab/evaluate.py`.

1. Say the problem in one line: a program that breaks substitution ciphers, and three procedures that improve that program.
2. Run the `cli solve` command above twice: once with `--genome '{}'` (the baseline: gibberish) and once with the strong genome (English).
3. `program.py`: show `Genome`, then `render()` - a genome becomes real Python source. Run
   `python3 -m cipherlab.cli render --genome '{"word_weight":2.0}'` and point at the word-score function that appears.
4. `runtime.py`: `Ctx.evaluate` is the budget (EVAL_CAP); `run_instance` records `fitness_true` - the probe signal SO-RSI uses later.
5. `evaluate.py`: the sealed held-out split and the ledger. Say: "every number in this repo is in instance-runs, and the held-out split is locked during search".
6. `tasks.py`: three books, four splits. Pride and Prejudice trains the language model and is never encrypted.

## Part 1 · Read a frontier claim (10.01, 10.02)

```bash
python3 labs/00_reading_frontier_research/10_01_claim_vs_evidence/lab.py --quick
python3 labs/00_reading_frontier_research/10_02_audit_paper/lab.py --quick
```

- 10.01: open `claim_evidence_analysis.md`; then the winner's-curse table. Point at the headline gain vs the fresh-seed gain.
- 10.02: open one `paper_audit_*.md`; then the two audit blocks - the flawed run FAILS three rules, the clean one passes. Show `cipherlab/audit.py` reading the ledger.

## Part 2 · Budget RSI (10.03-10.05)

```bash
python3 labs/01_budget_rsi_scoring/10_03_run_budget_rsi/lab.py --quick
python3 labs/01_budget_rsi_scoring/10_04_analyze_scoring/lab.py
python3 labs/01_budget_rsi_scoring/10_05_extend_readout/lab.py --quick
```

- Code: `methods/budget_rsi.py` - `scaffold_edits`, `LinearReadout`, `HGMTree.select_parent` (Thompson sampling on clade counts), `run` (K proposals, readout picks 1).
- 10.03: the selector table; the cost section ("rank 6, run 1").
- 10.04: the printed diff of `add_words` and its 8 coordinates; the coefficient ranking; then the blind spot: `iters_up` and `iters_down` have identical coordinates.
- 10.05: `signed_features` in `program.py`; the three-selector table and `docs/figures/10_05_readout_heldout.png`; the compound-edit transfer line.

## Part 3 · SO-RSI (10.06-10.08)

```bash
python3 labs/02_second_order_diagnostics/10_06_run_so_rsi/lab.py --quick
python3 labs/02_second_order_diagnostics/10_07_analyze_probes/lab.py
python3 labs/02_second_order_diagnostics/10_08_apply_to_debugging/lab.py
```

- Code: `methods/so_rsi.py` (`AnomalyDetector.check`, `InquiryMemory.weights`, the `if second_order:` block) and `probes.py` (`diagnose_rows`, `REMEDIES`).
- 10.06: scroll the seed-0 log until the first `anomaly ... -> probe:` line; read the mechanisms aloud. Then the results table.
- 10.07: the cipher where `fitness(found) >= fitness(truth)`; the "do the recommendations win?" table.
- 10.08: the attempt table with anomalies; the contract probe; "the test was wrong".

## Part 4 · Scaling: AReaL-RSI and SwarmRSI (10.09-10.11)

```bash
python3 labs/03_scaling_coordination/10_09_compare_scaling/lab.py --quick
python3 labs/03_scaling_coordination/10_10_areal_leader_follower/lab.py --quick
python3 labs/03_scaling_coordination/10_11_swarm_rsi/lab.py --quick
```

- Code: `methods/areal.py` (`ConditionalMemory`, `Leader.select`/`review`, replication in `run`), `methods/swarm_rsi.py` (the three numbered blocks in `run`).
- 10.10: the conditional-memory dump (resolved vs unresolved), the three-variant table.
- 10.11: one generation of the full swarm log (five moves, a recombination line); the ablation table; the "equal compute vs equal rounds" table - the honest finding.

## Part 5 · Adaptive workflows: RSIFlow and Self-HPO (10.12-10.14)

```bash
python3 labs/04_adaptive_workflows/10_12_compare_workflows/lab.py --quick
python3 labs/04_adaptive_workflows/10_13_rsiflow_meta_agent/lab.py --quick
python3 labs/04_adaptive_workflows/10_14_self_hpo/lab.py --quick
```

- Code: `methods/rsiflow.py` (`MetaAgent`, the four rules, `evolve`), `methods/self_hpo.py` (`h_step` uses the policy's own failures; `p_step` is an evolution strategy).
- 10.13: the `workflow:` lines changing; the rule table with usefulness and OFF switches.
- 10.14: H/P notes; the synergy line.

## Part 6 · Environments and metrics (10.15-10.17)

```bash
python3 labs/05_environments_metrics/10_15_rsi_index/lab.py --quick
python3 labs/05_environments_metrics/10_16_environments/lab.py --quick
python3 labs/05_environments_metrics/10_17_metrics/lab.py
```

- 10.15: the two formulas on the course example (the sign); `methods/rsigym.py` services and `PermissionDenied`; the five-benchmark table.
- 10.16: the terminal overhead number; self-play's chosen tasks; the three-environment table.
- 10.17: each metric's "limitation" line.

## Part 7 · Finale: three methods, one budget

```bash
python3 labs/06_finale/three_methods_showdown/lab.py --quick
```

- Open the committed full `output.txt`: the audit block (all PASS), the results table, `docs/figures/finale_heldout.png`.
- Close with the claim, stated with its limits (README "What we can and cannot claim").
