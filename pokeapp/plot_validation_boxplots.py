#!/usr/bin/env python3
"""
Build box plots from validation_experiment_scores.csv (output of ai_validator_pokemon.py).

Default input: validation_runs/run_default/validation_experiment_scores.csv
Default output: same directory / validation_boxplots.png

Metrics (by prompt_id):
- groundedness_0_100
- factual_precision_0_1
- total_hallucinations
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

# Writable config dir (sandbox/CI) + non-interactive backend for PNG export
_mpl_cfg = Path(__file__).resolve().parent / ".mplconfig"
_mpl_cfg.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cfg))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _boxplot(ax: Any, series: list[Any], labels: list[str]) -> dict[str, Any]:
    kw = dict(patch_artist=True, showmeans=True, meanline=True)
    try:
        return ax.boxplot(series, tick_labels=labels, **kw)
    except TypeError:
        return ax.boxplot(series, labels=labels, **kw)


def main() -> None:
    p = argparse.ArgumentParser(description="Box plots for validation experiment CSV")
    p.add_argument(
        "csv_path",
        type=Path,
        nargs="?",
        default=Path("validation_runs/run_default/validation_experiment_scores.csv"),
        help="Path to validation_experiment_scores.csv",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output PNG path (default: next to CSV as validation_boxplots.png)",
    )
    args = p.parse_args()

    csv_path = args.csv_path
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path.resolve()}")

    df = pd.read_csv(csv_path)
    for col in ("groundedness_0_100", "factual_precision_0_1", "total_hallucinations", "prompt_id"):
        if col not in df.columns:
            raise SystemExit(f"Missing column {col!r} in {csv_path}")

    out = args.output or (csv_path.parent / "validation_boxplots.png")

    order = sorted(df["prompt_id"].dropna().unique().tolist())
    metrics = [
        ("groundedness_0_100", "Groundedness (0–100)\nhigher is better", "Score"),
        ("factual_precision_0_1", "Factual precision (0–1)\nhigher is better", "Precision"),
        ("total_hallucinations", "Total hallucinations\nlower is better", "Count"),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(10, 10), layout="constrained")
    fig.suptitle(f"Validation summary by prompt — {csv_path.name}", fontsize=12, fontweight="bold")

    for ax, (ycol, title, ylab) in zip(axes, metrics):
        series = [df.loc[df["prompt_id"] == pid, ycol].dropna().values for pid in order]
        bp = _boxplot(ax, series, order)
        for patch in bp["boxes"]:
            patch.set_facecolor("#aed6f1")
            patch.set_edgecolor("#2c3e50")
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(ylab)
        ax.grid(True, axis="y", alpha=0.35)

    axes[-1].set_xlabel("Prompt")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
