# Audit: Budget Rsi

| Aspect | Paper's setup | Laptop adaptation | What's preserved |
|---|---|---|---|
| Changed object | GPT-4o coding-agent scaffold (code edits) | cipher-breaker program source rendered from a genome | an edit to program text, scored from its diff |
| Feedback type | solve counts on a steering split of HumanEval+ | solve counts on 48 Sherlock ciphers | pass/fail counts per candidate |
| Evaluation protocol | 16-instance fit split for labels, 48/164 steering, rest held out | 16 fit / 48 steering / 96 held-out Frankenstein ciphers | three disjoint partitions with distinct roles |
| Compute budget | LLM calls + many full test-suite runs | <= 1,920 steering runs per arm, ~2 min on 10 CPU cores | matched budget between selectors |
| Untested assumptions | diff shape predicts edit quality on other tasks | diff shape predicts quality for template edits | tested here: the 8 coordinates are blind to edit direction (lab 10.04) |

Assumption to test next: diff shape predicts edit quality on other tasks. What would test it: run the same mechanism on a second task family with its own steering and held-out splits, matched budgets, 5+ seeds.
