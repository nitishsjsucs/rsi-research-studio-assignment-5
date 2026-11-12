"""Shared helpers for the lab scripts: paths, flags, printing, charts.

Every lab is `python3 labs/<group>/<lab>/lab.py [--quick] [--seeds N]`.
--quick shrinks budgets and seeds so a lab finishes in well under a minute
(useful while recording a walkthrough); the committed output.txt files come
from full runs.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIGURES = os.path.join(ROOT, "docs", "figures")

# Categorical slots in fixed order (validated reference palette) + a neutral for baselines.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
NEUTRAL = "#8a8985"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"


def args(default_seeds: int = 3, **extra):
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true", help="small budgets, 1 seed: a fast demo run")
    p.add_argument("--seeds", type=int, default=default_seeds)
    for k, v in extra.items():
        p.add_argument(f"--{k}", type=type(v), default=v)
    a = p.parse_args()
    if a.quick:
        a.seeds = 1
    return a


class Clock:
    def __init__(self):
        self.t0 = time.time()

    def __str__(self):
        return f"{time.time() - self.t0:.0f}s"


def banner(lab: str, title: str, question: str):
    line = "=" * 78
    print(line)
    print(f"Lab {lab} · {title}")
    print(f"Question: {question}")
    print(line, flush=True)


def section(title: str):
    print(f"\n--- {title} " + "-" * max(0, 72 - len(title)), flush=True)


def table(rows, headers, fmt=None):
    fmt = fmt or {}
    cells = [[(fmt.get(h, "{}").format(r[i]) if r[i] is not None else "-") for i, h in enumerate(headers)] for r in rows]
    widths = [max(len(h), *(len(c[i]) for c in cells)) if cells else len(h) for i, h in enumerate(headers)]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for c in cells:
        print("  " + "  ".join(x.ljust(w) for x, w in zip(c, widths)), flush=True)


def mean_sd(xs):
    import numpy as np
    xs = list(xs)
    return float(np.mean(xs)), (float(np.std(xs, ddof=1)) if len(xs) > 1 else 0.0)


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    ax.set_xlabel(xlabel, color=INK2, fontsize=10)
    ax.set_ylabel(ylabel, color=INK2, fontsize=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def line_chart(path, title, series, xlabel="steering instance-runs spent", ylabel="best steering solve rate"):
    """series: list of (label, xs, ys, color). Lines 2px, direct end labels plus a legend."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    for label, xs, ys, color in series:
        ax.plot(xs, ys, color=color, linewidth=2, label=label, solid_capstyle="round")
        ax.annotate(f"{label} {ys[-1]:.2f}", (xs[-1], ys[-1]), xytext=(4, 0), textcoords="offset points",
                    fontsize=8, color=INK2, va="center")
    _style(ax, title, xlabel, ylabel)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def bar_chart(path, title, labels, means, sds, colors=None, ylabel="held-out solve rate", note=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 3.8), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    colors = colors or [SERIES[i % len(SERIES)] for i in range(len(labels))]
    xs = range(len(labels))
    ax.bar(xs, means, width=0.55, color=colors, edgecolor="#fcfcfb", linewidth=2)
    ax.errorbar(xs, means, yerr=sds, fmt="none", ecolor=INK2, elinewidth=1, capsize=4)
    for x, m in zip(xs, means):
        ax.annotate(f"{m:.2f}", (x, m), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(labels, fontsize=9)
    _style(ax, title, "", ylabel)
    if note:
        fig.text(0.01, 0.01, note, fontsize=7.5, color=INK2)
    ax.set_ylim(0, max(1e-3, max(m + s for m, s in zip(means, sds))) * 1.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def runs_curve(steps_rates, step_cost=48, start=48):
    """x positions for a best-so-far curve where each step cost `step_cost` runs."""
    return [start + step_cost * (i + 1) for i in range(len(steps_rates))]
