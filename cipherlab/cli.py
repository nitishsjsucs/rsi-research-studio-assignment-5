"""Command-line access to the harness: the "terminal environment" of lab 10.16.

    python3 -m cipherlab.cli evaluate --genome '{"ngram": 4}' --split steering --seeds 0
    python3 -m cipherlab.cli render   --genome '{"ngram": 4, "word_weight": 2.0}'
    python3 -m cipherlab.cli solve    --genome '{"ngram": 4}' --text "attack at dawn"

`evaluate` prints one JSON object on stdout. The held-out split is refused
here as everywhere else unless --unseal is passed.
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np


def main(argv=None):
    p = argparse.ArgumentParser(prog="cipherlab")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("evaluate", "render", "solve"):
        s = sub.add_parser(name)
        s.add_argument("--genome", default="{}", help="JSON of Genome fields; {} is the baseline")
        if name == "evaluate":
            s.add_argument("--split", default="steering")
            s.add_argument("--seeds", default="0")
            s.add_argument("--workers", type=int, default=0)
            s.add_argument("--unseal", action="store_true")
        if name == "solve":
            s.add_argument("--text", required=True)
            s.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)
    from .program import Genome, render
    g = Genome.from_dict(json.loads(a.genome))
    if a.cmd == "render":
        sys.stdout.write(render(g))
        return 0
    if a.cmd == "solve":
        from .corpus import clean
        from .runtime import run_instance
        from .tasks import make_instance
        inst = make_instance("cli-000", "cli", clean(a.text), np.random.default_rng(a.seed))
        r = run_instance(render(g), inst, a.seed)
        print(json.dumps({"ciphertext": inst.ciphertext, "decrypt": r["decrypt"], "acc": r["acc"]}))
        return 0
    from .evaluate import Evaluator
    with Evaluator(workers=a.workers or None) as ev:
        if a.unseal:
            ev.unseal()
        r = ev.run(render(g), a.split, [int(x) for x in a.seeds.split(",")], caller="cli")
    print(json.dumps({"genome": g.short(), "split": a.split, "solved": r.solved, "total": len(r.rows),
                      "rate": r.solve_rate, "mean_acc": r.mean_acc, "seconds": r.seconds}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
