#!/usr/bin/env python3
"""
ai_validator_pokemon.py

Homework 3 (AI Report Validation System) — Pokédex lore use case.

Maps to Canvas HOMEWORK3.md requirements:

1. **Customized validation framework** — Not the LAB’s multi-item 1–5 Likert block. Here,
   measurement is **non-negative integer hallucination counts** (five categories with explicit
   benchmarks against PokeAPI retrieval), plus **factual_precision_0_1** and
   **groundedness_0_100** with operational definitions in the reviewer prompt.

2. **Qualitative content analysis** — The same LLM (Ollama chat, JSON mode) acts as a
   systematic reviewer: counts, `hallucination_instances` (quote + rationale), and
   `reviewer_notes`.

3. **Experimental design** — Default **three prompt arms** (analogous to Prompt A/B/C):
   **RAG** (full retrieval), **RAG_PARTIAL** (lore + region only; no move/ability list in
   context), **NON_RAG** (name-only, no JSON). Each species yields one scored report per arm
   (`--species-count` × 3 rows by default). Increase `--species-count` for larger n.

4. **Statistical analysis** — Welch **t-tests** (all pairwise), one-way **ANOVA** when ≥3
   groups (default), and **OLS regression** `outcome ~ C(prompt_id)` via statsmodels when
   installed (satisfies “regression” wording).

5. **Implementation** — `validate-text` audits any file; `run-experiment` generates reports,
   validates, writes CSV + `homework3_experiment_summary.json`, and prints analysis.

Env: OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_API_KEY, OLLAMA_API_KEY_HEADER (same as ai_pokemon.py).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests
from dotenv import load_dotenv
from scipy import stats

from api_pokemon import fetch_pokemon_species, fetch_url_json, get_pokemon, extract_pokemon_species

# Reuse the app’s lore prompt builder (ai_pokemon.py)
from ai_pokemon import build_summary_prompt, call_ollama, compact_species_for_prompt

load_dotenv()

# --- Hallucination rubric (for write-up / screenshots) ---------------------------------

RUBRIC_MARKDOWN = """
## Lore Accuracy — Hallucination Detector (custom criteria)

| Criterion | What counts as a hallucination | Ground-truth source |
|-----------|-------------------------------|---------------------|
| Fake evolutions | Extra/missing/wrong evolution species vs canonical chain | `species_lore.evolution_species_names` |
| Fake abilities | Any named ability not in the snapshot | `pokemon_snapshot.abilities` |
| Incorrect regions | Wrong home/main region or impossible geography vs data | `generation.main_region`, habitat in species JSON |
| Nonexistent moves | Named move not in this Pokémon’s move list | `pokemon_snapshot.move_slugs` (full API list) |
| Contradictory lore | Text contradicts flavor_texts_en, typing, tags, or chain | Species + snapshot |

**Derived metrics**

- `total_hallucinations`: sum of the five category counts (each count = discrete issues found).
- `hallucinations_per_100_summaries`: \\(100 \\times \\text{mean}(\\text{total\\_hallucinations})\\) by prompt (expected total issues per 100 generated summaries).
- `factual_precision_0_1`: reviewer-estimated share of atomic factual claims supported by retrieval (0–1); if missing, approximated from counts.
- `groundedness_0_100`: reviewer holistic 0–100 “stays inside retrieval” score.

**Difference from LAB Likert (Module 9 lab)** — The LAB uses several correlated 1–5 scales
(formality, clarity, etc.). This rubric uses **category counts + bounded continuous scores**
grounded in **retrieved API facts**, aimed specifically at **hallucination detection** for
game lore rather than generic prose quality.
"""


def build_retrieval_bundle(id_or_name: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """
    Single JSON object used as (1) RAG prompt context and (2) validator ground truth.
    """
    token = str(id_or_name).strip().lower()
    # Speed: avoid double-fetching species JSON.
    raw_sp = fetch_pokemon_species(token, timeout=timeout)
    chain_payload = None
    ec_url = (raw_sp.get("evolution_chain") or {}).get("url")
    if ec_url:
        try:
            chain_payload = fetch_url_json(str(ec_url), timeout=timeout)
        except Exception:
            chain_payload = None
    species_compact = extract_pokemon_species(raw_sp, evolution_chain_payload=chain_payload)
    species_compact = compact_species_for_prompt(species_compact)

    gen = raw_sp.get("generation") or {}
    generation_name = gen.get("name")
    main_region: str | None = None
    gen_url = gen.get("url")
    if gen_url:
        try:
            gj = fetch_url_json(str(gen_url), timeout=timeout)
            main_region = (gj.get("main_region") or {}).get("name")
        except Exception:
            main_region = None

    try:
        poke = get_pokemon(token, timeout=timeout)
    except Exception:
        poke = {"name": token, "types": [], "abilities": [], "moves": []}

    abs_slugs: list[str] = []
    for a in poke.get("abilities") or []:
        n = a.get("name")
        if n:
            abs_slugs.append(str(n))

    type_slugs: list[str] = []
    for t in poke.get("types") or []:
        n = t.get("name")
        if n:
            type_slugs.append(str(n))

    move_slugs: list[str] = []
    for m in poke.get("moves") or []:
        n = m.get("name")
        if n:
            move_slugs.append(str(n))
    move_slugs = sorted(set(move_slugs))

    return {
        "query_slug": token,
        "species_lore": species_compact,
        "generation": {
            "generation_name": generation_name,
            "main_region": main_region,
        },
        "pokemon_snapshot": {
            "types": type_slugs,
            "abilities": sorted(set(abs_slugs)),
            "move_slugs": move_slugs,
            "move_count": len(move_slugs),
        },
    }


def _ollama_chat_json(user_prompt: str, *, timeout: float = 180.0) -> str:
    base = (os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL") or "llama3.2"
    url = f"{base}/api/chat"
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": user_prompt}],
        "format": "json",
        "stream": False,
    }
    headers: dict[str, str] = {}
    api_key = (os.getenv("OLLAMA_API_KEY") or "").strip()
    if api_key:
        hdr = (os.getenv("OLLAMA_API_KEY_HEADER") or "Authorization").strip() or "Authorization"
        val = api_key
        if hdr.lower() == "authorization" and not val.lower().startswith("bearer "):
            val = f"Bearer {val}"
        headers[hdr] = val
    r = requests.post(url, json=body, headers=headers or None, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    msg = data.get("message") or {}
    return str(msg.get("content", "")).strip()


def parse_json_object(text: str) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("No JSON object found in model output")
    return json.loads(m.group(0))


HALLUCINATION_KEYS = (
    "fake_evolution",
    "fake_ability",
    "incorrect_region",
    "nonexistent_move",
    "contradictory_lore",
)


def build_validation_prompt(report_text: str, retrieval_bundle: dict[str, Any]) -> str:
    blob = json.dumps(retrieval_bundle, indent=2, ensure_ascii=False, default=str)
    return f"""You are a strict LORE ACCURACY / HALLUCINATION DETECTOR for Pokémon text.

GROUND TRUTH (retrieval bundle from PokeAPI — authoritative for this evaluation):
{blob}

REPORT TO AUDIT:
---
{report_text}
---

Task: Count discrete hallucination ISSUES (not sentences) in each category:

1) fake_evolution — evolution lines, pre-evolutions, or branch species not consistent with
   species_lore.evolution_species_names (wrong order counts; invented species counts).
2) fake_ability — names or descriptions of abilities not in pokemon_snapshot.abilities.
3) incorrect_region — claims about origin/region/routes/habitat that contradict
   generation.main_region, species habitat, or generation_name (treat vague "many regions" as 0
   unless it contradicts a specific field).
4) nonexistent_move — any specific move name the Pokémon learns/has that is NOT in
   pokemon_snapshot.move_slugs (if the report avoids naming moves, 0).
5) contradictory_lore — contradicts flavor_texts_en, types in snapshot, legendary/mythical flags,
   or other explicit JSON fields.

Also set:
- factual_precision_0_1: your estimate of (supported factual atomic claims) /
  (supported + unsupported fabricated claims), 0–1. If almost no claims, use 1.0 only if
  the text avoids risky factual assertions; else lower if it fabricates.
- groundedness_0_100: holistic 100 = perfectly retrieval-grounded; 0 = unreliable.

Return ONLY valid JSON (no markdown fences):
{{
  "hallucination_counts": {{
    "fake_evolution": <int >=0>,
    "fake_ability": <int >=0>,
    "incorrect_region": <int >=0>,
    "nonexistent_move": <int >=0>,
    "contradictory_lore": <int >=0>
  }},
  "hallucination_instances": [
    {{"category": "<one of the five keys>", "excerpt": "<short quote>", "rationale": "<why it violates GT>"}}
  ],
  "factual_precision_0_1": <float 0-1>,
  "groundedness_0_100": <float 0-100>,
  "reviewer_notes": "<80-160 words>"
}}
"""


def _coerce_counts(raw: dict[str, Any]) -> dict[str, int]:
    hc = raw.get("hallucination_counts") or {}
    out: dict[str, int] = {}
    for k in HALLUCINATION_KEYS:
        try:
            v = int(hc.get(k, 0))
        except (TypeError, ValueError):
            v = 0
        out[k] = max(0, v)
    return out


def _derive_metrics(data: dict[str, Any]) -> dict[str, Any]:
    counts = _coerce_counts(data)
    total = int(sum(counts.values()))
    data["hallucination_counts"] = counts
    data["total_hallucinations"] = total

    fp = data.get("factual_precision_0_1")
    try:
        fpf = float(fp)
        if fpf != fpf:  # NaN
            raise ValueError
        data["factual_precision_0_1"] = max(0.0, min(1.0, fpf))
    except (TypeError, ValueError):
        # Fallback: fewer hallucinations ⇒ higher precision
        data["factual_precision_0_1"] = round(1.0 / (1.0 + float(total)), 4) if total >= 0 else 1.0

    gr = data.get("groundedness_0_100")
    try:
        grf = float(gr)
        data["groundedness_0_100"] = max(0.0, min(100.0, grf))
    except (TypeError, ValueError):
        data["groundedness_0_100"] = max(0.0, min(100.0, 100.0 - 8.0 * float(total)))

    return data


def validate_report(report_text: str, retrieval_bundle: dict[str, Any]) -> dict[str, Any]:
    prompt = build_validation_prompt(report_text, retrieval_bundle)
    raw = _ollama_chat_json(prompt)
    data = parse_json_object(raw)
    data = _derive_metrics(data)
    data["_validator_raw"] = raw[:2500]
    return data


# --- Generation: RAG (full bundle) vs NON_RAG (no retrieval) -------------------------

PromptFn = Callable[[dict[str, Any]], str]


def _display_name(bundle: dict[str, Any]) -> str:
    sl = bundle.get("species_lore") or {}
    name = sl.get("name") or bundle.get("query_slug") or "unknown"
    return str(name).replace("-", " ").title()


def prompt_rag(bundle: dict[str, Any]) -> str:
    blob = json.dumps(bundle, indent=2, ensure_ascii=False, default=str)
    return f"""You are a retrieval-augmented Pokédex lore writer.

The JSON below is your ONLY source of facts (RAG context). Do not use outside knowledge
that is not implied by this JSON.

{blob}

Write 2–4 short paragraphs for a general audience. You may name abilities, types, moves,
and regions ONLY when consistent with the JSON (moves must be in pokemon_snapshot.move_slugs;
abilities in pokemon_snapshot.abilities; evolution line must match species_lore.evolution_species_names;
region claims must align with generation.main_region / habitat when you mention them).
Paraphrase flavor_texts_en faithfully. If the JSON is silent, say it is not specified — do not guess."""


def _partial_rag_writer_bundle(full: dict[str, Any]) -> dict[str, Any]:
    """Retrieval-augmented but omit battle snapshot — middle ground vs full RAG vs NON_RAG."""
    return {
        "query_slug": full.get("query_slug"),
        "species_lore": full.get("species_lore"),
        "generation": full.get("generation"),
        "writer_note": (
            "pokemon_snapshot (types, abilities, move list) is intentionally NOT provided. "
            "Do not name specific moves or abilities. You may discuss typing only if it "
            "appears explicitly in species_lore text fields; otherwise omit."
        ),
    }


def prompt_rag_partial(bundle: dict[str, Any]) -> str:
    """Prompt B: partial RAG — reduces structured battle facts in context (more hallucination risk)."""
    slim = _partial_rag_writer_bundle(bundle)
    blob = json.dumps(slim, indent=2, ensure_ascii=False, default=str)
    return f"""You are a Pokédex lore writer using PARTIAL retrieval (not the full Pokédex API bundle).

{blob}

Write 2–4 short paragraphs. Stay faithful to species_lore and generation. Because move and
ability lists were withheld from you, do NOT invent or name specific moves or abilities.
Prefer habitat, flavor/lore, evolution line, and tags from the JSON."""


def prompt_non_rag(bundle: dict[str, Any]) -> str:
    """Deliberately no structured retrieval — encourages parametric-memory hallucinations."""
    label = _display_name(bundle)
    return f"""Write a polished 2–4 paragraph Pokédex-style lore article about the Pokémon {label}.

Instructions for this condition (non-RAG):
- Rely on your general knowledge only. Do NOT ask for data or apologize for uncertainty.
- Sound authoritative: include evolution family, regions where trainers meet it, notable
  abilities, and signature moves you believe are correct for competitive flavor.
- Write vivid prose suitable for a fan magazine."""


GENERATION_PROMPTS: dict[str, PromptFn] = {
    # Uses the same lore prompt template as the app’s `ai_pokemon.py` (requested by user).
    "AI_POKEMON": lambda b: build_summary_prompt(b["species_lore"]),
    "RAG": prompt_rag,
    "RAG_PARTIAL": prompt_rag_partial,
    "NON_RAG": prompt_non_rag,
}


def generate_report(bundle: dict[str, Any], prompt_id: str) -> str:
    fn = GENERATION_PROMPTS[prompt_id]
    return call_ollama(fn(bundle))


@dataclass
class ExperimentConfig:
    species_names: list[str]
    # Three arms by default → matches HW3 “Prompt A, B, C” style and enables one-way ANOVA.
    prompts: tuple[str, ...] = ("AI_POKEMON", "RAG_PARTIAL", "NON_RAG")
    sleep_s: float = 0.10
    workers: int = 1


def run_experiment(cfg: ExperimentConfig, output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    # Cache retrieval bundles once per species (major speed win).
    bundle_cache: dict[str, dict[str, Any]] = {}
    for sp in cfg.species_names:
        try:
            bundle_cache[sp] = build_retrieval_bundle(sp)
        except Exception as e:
            print(f"[bundle] failed species={sp}: {e}", flush=True)

    def _one_job(pname: str, sp: str) -> dict[str, Any] | None:
        bundle = bundle_cache.get(sp)
        if not bundle:
            return None
        sp_key = str((bundle.get("species_lore") or {}).get("name") or sp)
        print(f"[gen] prompt={pname} species={sp_key}", flush=True)
        try:
            report = generate_report(bundle, pname)
            safe = re.sub(r"[^\w\\-]+", "_", sp_key)[:60]
            (output_dir / f"report_{pname}_{safe}.txt").write_text(report, encoding="utf-8")
        except Exception as e:
            print(f"  ! generate failed: {e}", flush=True)
            return None

        if cfg.sleep_s:
            time.sleep(cfg.sleep_s)

        try:
            v = validate_report(report, bundle)
        except Exception as e:
            print(f"  ! validate failed: {e}", flush=True)
            v = {
                "hallucination_counts": {k: 0 for k in HALLUCINATION_KEYS},
                "total_hallucinations": 0,
                "factual_precision_0_1": 0.0,
                "groundedness_0_100": 0.0,
                "reviewer_notes": f"[validator error] {e}",
                "hallucination_instances": [],
            }

        hc = v.get("hallucination_counts") or {}
        row = {
            "prompt_id": pname,
            "species": sp_key,
            "total_hallucinations": v.get("total_hallucinations"),
            "factual_precision_0_1": v.get("factual_precision_0_1"),
            "groundedness_0_100": v.get("groundedness_0_100"),
            "reviewer_notes": v.get("reviewer_notes"),
        }
        for k in HALLUCINATION_KEYS:
            row[f"halluc_{k}"] = hc.get(k, 0)
        return row

    jobs: list[tuple[str, str]] = [(pname, sp) for pname in cfg.prompts for sp in cfg.species_names]
    if int(cfg.workers) <= 1:
        for pname, sp in jobs:
            r = _one_job(pname, sp)
            if r:
                rows.append(r)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=int(cfg.workers)) as ex:
            futs = [ex.submit(_one_job, pname, sp) for pname, sp in jobs]
            for fut in as_completed(futs):
                r = fut.result()
                if r:
                    rows.append(r)

    df = pd.DataFrame(rows)
    csv_path = output_dir / "validation_experiment_scores.csv"
    df.to_csv(csv_path, index=False)
    print(f"Wrote {csv_path} ({len(df)} rows)", flush=True)

    # Compact file for HW3 doc (git link): design + sample sizes + rubric pointer.
    per_prompt = df.groupby("prompt_id").size().to_dict()
    summary = {
        "homework3_alignment": {
            "custom_rubric": "Five hallucination count dimensions + factual_precision_0_1 + groundedness_0_100 (not LAB Likert).",
            "qualitative_reviewer": "Ollama /api/chat JSON — counts, instances, reviewer_notes.",
            "prompts_compared": list(cfg.prompts),
            "scores_collected_per_prompt": per_prompt,
            "total_validation_scores": int(len(df)),
            "species_per_arm": len(cfg.species_names),
            "statistics_script_prints": "Welch t-tests, ANOVA (if >=3 arms), OLS if statsmodels installed",
            "csv": str(csv_path.name),
        }
    }
    (output_dir / "homework3_experiment_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"Wrote {output_dir / 'homework3_experiment_summary.json'}", flush=True)
    return df


def analyze_scores(df: pd.DataFrame) -> None:
    if df.empty:
        print("No rows to analyze.")
        return

    print("\n=== HOMEWORK3 — Validation criteria table (for documentation) ===\n")
    print(
        "| Dimension | Description | Scale / method | Benchmark |\n"
        "|-----------|-------------|----------------|----------|\n"
        "| fake_evolution | Wrong/missing/invented evolution vs chain | Non-negative integer count | 0 issues = matches `evolution_species_names` |\n"
        "| fake_ability | Ability names not in API list | Count | 0 = subset of `pokemon_snapshot.abilities` |\n"
        "| incorrect_region | Region/home vs generation/habitat | Count | 0 = consistent with retrieval |\n"
        "| nonexistent_move | Move names not in learnset | Count | 0 = subset of `move_slugs` |\n"
        "| contradictory_lore | Contradicts flavor/types/flags | Count | 0 = consistent with species + snapshot |\n"
        "| factual_precision_0_1 | Share of supported atomic claims | Continuous [0,1] | Higher = fewer unsupported claims |\n"
        "| groundedness_0_100 | Holistic retrieval adherence | Continuous [0,100] | Higher = better |\n"
    )

    print("\n=== Rubric: Lore Accuracy / Hallucination Detector ===\n")
    print(RUBRIC_MARKDOWN)

    print("\n=== Distribution: groundedness_0_100 (prompt × summary scores) ===\n")
    print(df.groupby("prompt_id")["groundedness_0_100"].describe().round(3).to_string())

    print("\n=== Groundedness & precision by prompt ===\n")
    g = df.groupby("prompt_id").agg(
        n=("species", "count"),
        groundedness_mean=("groundedness_0_100", "mean"),
        groundedness_std=("groundedness_0_100", "std"),
        factual_precision_mean=("factual_precision_0_1", "mean"),
        halluc_mean=("total_hallucinations", "mean"),
    )
    print(g.round(4))

    print("\n=== Hallucinations per 100 summaries (100 × mean total issues) ===\n")
    h100 = df.groupby("prompt_id")["total_hallucinations"].apply(lambda s: 100.0 * float(s.mean()))
    for pid, val in h100.items():
        print(f"  {pid}: {val:.2f}")

    prompts = sorted(df["prompt_id"].unique().tolist())
    gvals = [df.loc[df["prompt_id"] == p, "groundedness_0_100"].dropna().values for p in prompts]
    gvals = [x for x in gvals if len(x) > 0]
    hvals = [df.loc[df["prompt_id"] == p, "total_hallucinations"].dropna().values for p in prompts]
    hvals = [x for x in hvals if len(x) > 0]

    if len(gvals) >= 2:
        try:
            b_stat, b_p = stats.bartlett(*gvals)
            print("\nBartlett (groundedness, equal variances):", f"stat={b_stat:.4f}, p={b_p:.4g}")
        except Exception as e:
            print("\nBartlett skipped:", e)

        if len(gvals) >= 3:
            f_stat, p_anova = stats.f_oneway(*gvals)
            print("\nOne-way ANOVA on groundedness_0_100 (omnibus test across all prompt arms):")
            print(f"  H0: equal mean groundedness across groups;  F = {f_stat:.4f}, p = {p_anova:.4g}")
            if p_anova < 0.05:
                print("  Reject H0 at α=0.05: at least one prompt differs in mean groundedness.")
            else:
                print("  Fail to reject H0 at α=0.05: no strong evidence of mean differences.")

            h_groups = [
                df.loc[df["prompt_id"] == p, "total_hallucinations"].dropna().values for p in prompts
            ]
            h_groups = [x for x in h_groups if len(x) > 0]
            if len(h_groups) >= 3:
                fh_stat, ph_anova = stats.f_oneway(*h_groups)
                print("\nOne-way ANOVA on total_hallucinations (lower is better):")
                print(f"  H0: equal mean hallucination counts;  F = {fh_stat:.4f}, p = {ph_anova:.4g}")
        else:
            print("\n(Only two prompt groups — one-way ANOVA across 3+ groups skipped; use t-tests below.)")

        print("\nPairwise Welch t-tests — groundedness_0_100 (higher is better):")
        for i in range(len(prompts)):
            for j in range(i + 1, len(prompts)):
                a = df.loc[df["prompt_id"] == prompts[i], "groundedness_0_100"].dropna()
                b = df.loc[df["prompt_id"] == prompts[j], "groundedness_0_100"].dropna()
                if len(a) < 2 or len(b) < 2:
                    continue
                res = stats.ttest_ind(a, b, equal_var=False)
                print(
                    f"  {prompts[i]} vs {prompts[j]}: t={res.statistic:.4f}, p={res.pvalue:.4g} "
                    f"(mean G {prompts[i]}={a.mean():.3f}, {prompts[j]}={b.mean():.3f})"
                )

        print("\nPairwise Welch t-tests — total_hallucinations (lower is better):")
        for i in range(len(prompts)):
            for j in range(i + 1, len(prompts)):
                a = df.loc[df["prompt_id"] == prompts[i], "total_hallucinations"].dropna()
                b = df.loc[df["prompt_id"] == prompts[j], "total_hallucinations"].dropna()
                if len(a) < 2 or len(b) < 2:
                    continue
                res = stats.ttest_ind(a, b, equal_var=False)
                print(
                    f"  {prompts[i]} vs {prompts[j]}: t={res.statistic:.4f}, p={res.pvalue:.4g} "
                    f"(mean H {prompts[i]}={a.mean():.3f}, {prompts[j]}={b.mean():.3f})"
                )

    try:
        import statsmodels.formula.api as smf

        d = df.copy()
        if d["prompt_id"].nunique() >= 2:
            print("\nOLS: groundedness_0_100 ~ C(prompt_id)")
            print(smf.ols("groundedness_0_100 ~ C(prompt_id)", data=d).fit().summary().tables[1])
            print("\nOLS: total_hallucinations ~ C(prompt_id)")
            print(smf.ols("total_hallucinations ~ C(prompt_id)", data=d).fit().summary().tables[1])
    except Exception as e:
        # Some environments have incompatible numpy/statsmodels builds; regression is optional for HW3.
        print(
            "\n(statsmodels regression skipped — optional. "
            "Install/repair `statsmodels` + `numpy` to enable.)"
        )
        print(f"  details: {type(e).__name__}: {e}")


def default_species_list(n: int, seed: int) -> list[str]:
    pool = [
        "pikachu",
        "bulbasaur",
        "charmander",
        "squirtle",
        "eevee",
        "snorlax",
        "gengar",
        "dragonite",
        "scyther",
        "lapras",
        "mewtwo",
        "cyndaquil",
        "totodile",
        "chikorita",
        "mudkip",
        "ralts",
        "beldum",
        "garchomp",
        "lucario",
        "greninja",
    ]
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[: max(1, min(n, len(pool)))]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Hallucination-focused lore validation + RAG vs non-RAG experiment"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser(
        "run-experiment",
        help="Generate lore with multiple prompt arms (default: RAG, RAG_PARTIAL, NON_RAG) and validate",
    )
    pe.add_argument("--out", type=Path, default=Path("validation_runs") / "run_default")
    pe.add_argument(
        "--species-count",
        type=int,
        default=10,
        help="Species per prompt arm (rows ≈ count × number of prompts)",
    )
    pe.add_argument("--seed", type=int, default=42)
    pe.add_argument("--species", nargs="*", help="Explicit species slugs (overrides --species-count)")
    pe.add_argument(
        "--prompts",
        nargs="+",
        default=["AI_POKEMON", "RAG_PARTIAL", "NON_RAG"],
        choices=sorted(GENERATION_PROMPTS.keys()),
        help="Prompt arms A/B/C style (default: three-way RAG vs partial RAG vs non-RAG for HW3 ANOVA)",
    )
    pe.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel jobs for generation+validation (try 2-4 for speed if Ollama can handle it)",
    )

    pv = sub.add_parser("validate-text", help="Validate a text file against one species slug")
    pv.add_argument("species", help="Species slug, e.g. pikachu")
    pv.add_argument("report_path", type=Path)

    args = p.parse_args(argv)

    if args.cmd == "validate-text":
        text = args.report_path.read_text(encoding="utf-8")
        bundle = build_retrieval_bundle(args.species)
        out = validate_report(text, bundle)
        # Pretty-print including per-category counts
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        th = int(out.get("total_hallucinations") or 0)
        print(
            f"\n--- metrics: total_hallucinations={th}, "
            f"factual_precision_0_1={out.get('factual_precision_0_1')}, "
            f"groundedness_0_100={out.get('groundedness_0_100')} "
            f"(aggregate hallucinations_per_100_summaries = 100×mean(count) over run-experiment) ---",
            flush=True,
        )
        return 0

    if args.cmd == "run-experiment":
        names = list(args.species) if args.species else default_species_list(args.species_count, args.seed)
        cfg = ExperimentConfig(species_names=names, prompts=tuple(args.prompts), workers=int(args.workers))
        df = run_experiment(cfg, args.out)
        analyze_scores(df)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
