# Audit: Swarm Rsi

| Aspect | Paper's setup | Laptop adaptation | What's preserved |
|---|---|---|---|
| Changed object | hypotheses and implementations of a swarm of scientist agents | programs and proposal weights of five agents | population-level edits plus recombination |
| Feedback type | experiment results shared across agents | steering scores + a shared op->gain experience table | other agents' results steer mutation |
| Evaluation protocol | OpenProblems, NatureBench, MLE-Bench Lite | steering + sealed held-out, ablations of recombination/sharing/migration | ablations at matched compute |
| Compute budget | many agent-hours | 1,920-2,880 steering runs | every agent evaluation charged to one budget |
| Untested assumptions | swarm beats one agent at equal compute | tested here: at equal compute it does not; it wins on sequential depth | honest framing of what a swarm buys |

Assumption to test next: swarm beats one agent at equal compute. What would test it: run the same mechanism on a second task family with its own steering and held-out splits, matched budgets, 5+ seeds.
