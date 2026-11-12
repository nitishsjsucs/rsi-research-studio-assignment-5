"""An auditor for comparisons: does the evidence support the claim being made?

`audit()` checks a finished comparison against four rules every lab follows:

  1. sealed held-out   no held-out access happened before the final report
                       (read from the evaluator's ledger, not from promises);
  2. matched budgets   every compared arm spent the same steering runs (+-5%);
  3. enough seeds      at least 3 seeds per arm;
  4. gap reported      steering and held-out numbers are both present, so a
                       selection-inflated steering score cannot pass as the result.
"""
from __future__ import annotations

from typing import Dict, List


def audit(ledger, arms: Dict[str, List[dict]], final_report_time: float = None) -> List[tuple]:
    out = []
    held = [a for a in ledger.accesses if a["split"].startswith("heldout")]
    early = [a for a in held if final_report_time is None or a["t"] < final_report_time]
    out.append(("sealed held-out", not early,
                f"{len(early)} held-out access(es) before the final report" if early else "held-out touched only in the final report"))
    spent = {k: [r.get("runs_spent", 0) for r in v] for k, v in arms.items()}
    flat = [x for v in spent.values() for x in v]
    ok = bool(flat) and max(flat) <= 1.05 * min(flat)
    out.append(("matched budgets", ok, ", ".join(f"{k}: {min(v)}-{max(v)} runs" for k, v in spent.items())))
    seeds = {k: len(v) for k, v in arms.items()}
    out.append(("enough seeds", all(n >= 3 for n in seeds.values()), ", ".join(f"{k}: {n}" for k, n in seeds.items())))
    gap = all("heldout" in r and "steering" in r for v in arms.values() for r in v)
    out.append(("gap reported", gap, "steering and held-out recorded for every run" if gap else "a run lacks steering or held-out"))
    return out


def print_audit(rows):
    for name, ok, why in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:16s} {why}")
    return all(ok for _, ok, _ in rows)
