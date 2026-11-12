# Audit: So Rsi

| Aspect | Paper's setup | Laptop adaptation | What's preserved |
|---|---|---|---|
| Changed object | the RSI workflow's edits (second order) | the proposal distribution of the improver | diagnosis changes how edits are chosen |
| Feedback type | execution traces from Lean 4 / Verus | per-cipher traces: fitness(found) vs fitness(true), stall point, cap hits | anomaly detection on the improver's own trace |
| Evaluation protocol | 24-hour search, held-out proofs | 40 steering evaluations, sealed held-out, 3+ seeds | same proposer and acceptance rule in both arms |
| Compute budget | 24 hours per comparison | probes paid from the same 1,920-run budget | probe cost counted, not free |
| Untested assumptions | probes generalise across formal systems | hand-written probes for one domain | what an LLM-written probe would find is not tested |

Assumption to test next: probes generalise across formal systems. What would test it: run the same mechanism on a second task family with its own steering and held-out splits, matched budgets, 5+ seeds.
