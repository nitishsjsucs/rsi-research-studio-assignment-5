"""Lab 10.07 · Analyse the diagnostic probes.

1. Count each anomaly type in the 10.06 traces, per arm, with the typical
   recommendation the probes produced.
2. Show the key probe on a real cipher: the program's objective scores a
   WRONG decryption above the TRUE one. No amount of search can fix that.
3. Validate the probes causally. For three programs, probe first, then test
   the recommended edit against the edit the probe calls futile. A probe is
   only worth its cost if its recommendation wins.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import _lab  # noqa: E402

from cipherlab.edits import BY_NAME  # noqa: E402
from cipherlab.evaluate import Evaluator  # noqa: E402
from cipherlab.loop import Scorer, load_json, save_json  # noqa: E402
from cipherlab.probes import REMEDIES, probe  # noqa: E402
from cipherlab.program import Genome, render  # noqa: E402

WHY = {
    "recurrence": "the edit's assumption is wrong for this program; stop paying for it",
    "opposing": "two edits fight over one knob; the knob is not the bottleneck",
    "mismatch": "the model of the system is wrong (e.g. the cap truncates 'search longer')",
}


def main():
    a = _lab.args(default_seeds=1)
    _lab.banner("10.07", "Analyse diagnostic probes", "When does each anomaly fire, and do the probes recommend the edit that actually helps?")
    clock = _lab.Clock()

    _lab.section("1. Anomalies in the 10.06 traces")
    try:
        res = load_json("10_06_so_rsi.json")
    except FileNotFoundError:
        res = None
        print("  (run lab 10.06 first for this table)")
    if res:
        rows = []
        recs = {k: Counter() for k in WHY}
        for d in (d for r in res["so-rsi"] for d in r["diagnoses"]):
            for an in d["anomalies"]:
                for op in d["recommended"][:2]:
                    recs[an["kind"]][op] += 1
        for kind in WHY:
            n = sum(r["anomaly_counts"].get(kind, 0) for r in res["naive"])
            s = sum(r["anomaly_counts"].get(kind, 0) for r in res["so-rsi"])
            top = ", ".join(op for op, _ in recs[kind].most_common(2)) or "-"
            rows.append((kind, n, s, top, WHY[kind]))
        _lab.table(rows, ["anomaly", "naive", "so-rsi", "typical recommendation", "why it helps"])
        mech = Counter(m for r in res["so-rsi"] for d in r["diagnoses"] for m in d["mechanisms"])
        print("\n  mechanisms diagnosed across SO-RSI runs: " + ", ".join(f"{m}={n}" for m, n in mech.most_common()))

    with Evaluator() as ev:
        _lab.section("2. The objective-gap probe on one cipher")
        weak = Genome()  # 2-gram, random init, 1x1000
        r = ev.run(render(weak), "probe", (0,), caller="10.07-example")
        row = next(x for x in sorted(r.rows, key=lambda x: -x["length"]) if not x["solved"] and x["fitness_found"] >= x["fitness_true"])
        from cipherlab.tasks import load_split
        inst = next(i for i in load_split("probe") if i.uid == row["uid"])
        print(f"  program: {weak.short()}")
        print(f"  cipher : {inst.ciphertext[:90]}")
        print(f"  found  : {row['decrypt'][:90]}")
        print(f"  truth  : {inst.plaintext[:90]}")
        print(f"  fitness(found) = {row['fitness_found']:.1f}  >=  fitness(truth) = {row['fitness_true']:.1f}")
        print("  The program's own objective prefers the wrong answer. Searching harder converges on it faster.")

        _lab.section("3. Do the recommendations win? (probe, then test both edits on steering)")
        steer = Scorer(ev, "steering", (0,), caller="10.07-validate")
        cases = [Genome(), Genome(ngram=4, word_weight=2.0, iters=1000, restarts=2),
                 Genome(ngram=3, word_weight=2.0, init="frequency", iters=10000, restarts=2)]
        rows = []
        for g in cases:
            d = probe(ev, g, caller="10.07-probe")
            rec = next((n for n in d.recommended() if BY_NAME[n].apply(g) is not None), None)
            fut = next((n for n in d.futile() if BY_NAME[n].apply(g) is not None), None)
            base = steer(g).rate
            rr = steer(BY_NAME[rec].apply(g)).rate if rec else None
            fr = steer(BY_NAME[fut].apply(g)).rate if fut else None
            print(f"  {g.short()}\n    probe: {d.line()}\n    mechanisms: {d.mechanisms}")
            for ev_line in d.evidence:
                print(f"      - {ev_line}")
            rows.append((g.short()[:34], ",".join(d.mechanisms)[:30], base, rec, rr, fut, fr))
        _lab.table(rows, ["program", "diagnosis", "base", "recommended", "after", "futile", "after"],
                   {"base": "{:.3f}", "after": "{:.3f}"})
        wins = sum(1 for r in rows if r[4] is not None and r[6] is not None and r[4] > r[6])
        print(f"\n  recommended edit beat the 'futile' edit in {wins}/{len(rows)} cases.")
        print("  Remedy table the probes draw from: " + "; ".join(f"{m}->{v[0][:2]}" for m, v in REMEDIES.items()))
        save_json("10_07_probe_validation.json", rows)
    print(f"\ndone in {clock}")


if __name__ == "__main__":
    main()
