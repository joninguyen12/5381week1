#!/usr/bin/env python3
"""
Emit the validation system diagram as Markdown (Mermaid, GitHub-renderable) by default.
Optional: also write a PNG block diagram.

Default Markdown: system_design_diagram.md (repo root)
Default PNG (with --png): validation_runs/run_default/system_design_diagram.png
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

MARKDOWN_PATH_DEFAULT = Path("system_design_diagram.md")
PNG_PATH_DEFAULT = Path("validation_runs/run_default/system_design_diagram.png")

MERMAID = r"""
```mermaid
flowchart TB
  pokeapi["PokeAPI\nspecies + generation + /pokemon"]
  bundle["Retrieval bundle\nJSON ground truth\nspecies_lore · generation · pokemon_snapshot"]

  pokeapi --> bundle

  subgraph arms["Experiment: prompt arms"]
    ai["AI_POKEMON\nai_pokemon.py\nspecies JSON only"]
    rag["RAG\nfull bundle in prompt"]
    partial["RAG_PARTIAL\npartial JSON"]
    norag["NON_RAG\nname only, no JSON"]
  end

  bundle --> arms
  ai --> gen["Ollama /api/generate\nlore writer"]
  rag --> gen
  partial --> gen
  norag --> gen

  gen --> reports["Generated lore\n.txt per arm × species"]

  reports --> review["AI reviewer\nOllama /api/chat + JSON\nhallucination counts\nprecision · groundedness"]
  bundle -->|"always full bundle\nfor audit"| review

  review --> out["Outputs\nvalidation_experiment_scores.csv\nplots · ANOVA / Welch t"]

  style pokeapi fill:#d5f5e3
  style bundle fill:#fdebd0
  style arms fill:#f5eef8
  style gen fill:#d6eaf8
  style reports fill:#f9e79f
  style review fill:#fadbd8
  style out fill:#eaeded
```
"""


def markdown_document() -> str:
    return f"""# Pokédex lore validation — system design

This diagram matches the pipeline in `ai_validator_pokemon.py`: PokeAPI data is assembled into a **retrieval bundle**, each **prompt arm** generates lore via Ollama **`/api/generate`**, then an **AI reviewer** calls Ollama **`/api/chat`** with JSON mode using the **full bundle** as ground truth. Results are saved as report text files, a scores CSV, and printed statistics.

{MERMAID.strip()}

To regenerate this file and the optional PNG, run:

- `python3 diagram_validation_system.py` — updates this Markdown
- `python3 diagram_validation_system.py --png` — also writes `validation_runs/run_default/system_design_diagram.png`
"""


def write_png(path: Path) -> None:
    _mpl_cfg = Path(__file__).resolve().parent / ".mplconfig"
    _mpl_cfg.mkdir(exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cfg))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    from matplotlib import patheffects as pe

    def _box(ax, xy, w, h, text, fontsize=9, fc="#e8f4fc", ec="#2c3e50"):
        x, y = xy
        p = mpatches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02",
            linewidth=1.2,
            edgecolor=ec,
            facecolor=fc,
            mutation_aspect=0.25,
        )
        ax.add_patch(p)
        ax.text(
            x + w / 2,
            y + h / 2,
            text,
            ha="center",
            va="center",
            fontsize=fontsize,
            wrap=True,
            linespacing=1.15,
            path_effects=[pe.withStroke(linewidth=3, foreground="white")],
        )

    def _arrow(ax, x1, y1, x2, y2, label=None):
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color="#34495e", lw=1.4, shrinkA=2, shrinkB=2),
        )
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my + 0.04, label, ha="center", fontsize=7, color="#555")

    fig, ax = plt.subplots(1, 1, figsize=(11, 7.5), dpi=150)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.text(
        0.5,
        0.97,
        "Pokédex lore validation system (block diagram)",
        ha="center",
        va="top",
        fontsize=13,
        fontweight="bold",
        color="#1a1a1a",
    )

    _box(ax, (0.06, 0.78), 0.22, 0.12, "PokeAPI\n(species + generation\n+ /pokemon snapshot)", fc="#d5f5e3")
    _arrow(ax, 0.28, 0.84, 0.36, 0.84)
    _box(ax, (0.36, 0.76), 0.28, 0.16, "Retrieval bundle\n(JSON ground truth)\nspecies_lore · generation\npokemon_snapshot", fc="#fdebd0")

    _arrow(ax, 0.5, 0.76, 0.5, 0.70, "branch")
    ax.text(0.5, 0.72, "Experiment: prompt arms", ha="center", fontsize=8, style="italic", color="#555")

    y_arm = 0.52
    arms = [
        (0.05, "AI_POKEMON\n(ai_pokemon.py\nspecies JSON)"),
        (0.28, "RAG\n(full bundle)"),
        (0.51, "RAG_PARTIAL\n(partial JSON)"),
        (0.74, "NON_RAG\n(name only)"),
    ]
    for x, lab in arms:
        _box(ax, (x, y_arm), 0.20, 0.14, lab, fontsize=8, fc="#ebdef0")
        _arrow(ax, 0.5, 0.76, x + 0.10, y_arm + 0.14)

    _box(ax, (0.34, 0.34), 0.32, 0.10, "Ollama /api/generate\n(lore writer)", fc="#d6eaf8")
    for x, _ in arms:
        _arrow(ax, x + 0.10, y_arm, 0.5, 0.44)

    _arrow(ax, 0.5, 0.34, 0.5, 0.28)
    _box(ax, (0.30, 0.14), 0.40, 0.12, "Generated lore reports\n(.txt per arm × species)", fc="#f9e79f")

    _arrow(ax, 0.68, 0.84, 0.78, 0.84)
    _arrow(ax, 0.5, 0.20, 0.78, 0.26)
    _box(ax, (0.72, 0.14), 0.24, 0.20, "AI reviewer\nOllama /api/chat\nJSON: counts +\nprecision + groundedness", fc="#fadbd8")

    ax.annotate(
        "",
        xy=(0.84, 0.20),
        xytext=(0.70, 0.20),
        arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2),
    )
    ax.text(0.88, 0.22, "full bundle\nalways", ha="center", fontsize=7, color="#922b21")

    _arrow(ax, 0.84, 0.14, 0.84, 0.08)
    _box(ax, (0.62, 0.02), 0.34, 0.08, "Outputs: scores CSV · reports · stats\n(ANOVA / Welch t / optional OLS)", fontsize=8, fc="#eaeded")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-o",
        "--output-md",
        type=Path,
        default=MARKDOWN_PATH_DEFAULT,
        help="Output Markdown path (Mermaid diagram)",
    )
    ap.add_argument(
        "--png",
        action="store_true",
        help=f"Also write PNG to {PNG_PATH_DEFAULT} (or pass --output-png)",
    )
    ap.add_argument(
        "--output-png",
        type=Path,
        default=PNG_PATH_DEFAULT,
        help="PNG output path (used only with --png)",
    )
    args = ap.parse_args()

    md_path: Path = args.output_md
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown_document(), encoding="utf-8")
    print(f"Wrote {md_path.resolve()}")

    if args.png:
        write_png(args.output_png)
        print(f"Wrote {args.output_png.resolve()}")


if __name__ == "__main__":
    main()
