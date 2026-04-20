# agents_pokemon.py
# Multi-agent battle matchup analyzer for Homework 2 (multi-agent orchestration + RAG + tools).
#
# Architecture (see HOMEWORK2.md in dsai/08_function_calling):
#   Agent 1 — Data Retriever: calls PokeAPI tools (function-calling style) and builds a RAG bundle.
#   Agent 2 — Strategy Analyst: LLM reads ONLY that bundle; analyzes matchup.
#   Agent 3 — Battle Narrator: LLM turns analysis into a readable battle summary.
#
# Performance (env):
#   BATTLE_TWO_LLM_CALLS — set to 1/true to run Agent 2 and Agent 3 as two separate model calls
#                          (slower; default is one combined call that still contains both parts).
#
# Env: OLLAMA_HOST, OLLAMA_MODEL (see ai_pokemon.py).
#
# pip install requests python-dotenv

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from ai_pokemon import call_ollama
from api_pokemon import (
    english_effect_entries_text,
    extract_pokemon,
    fetch_ability,
    fetch_move,
    fetch_pokemon,
    get_pokemon,
    get_pokemon_level_up_moves_table_rows,
)

load_dotenv()

# Level-up moves fetched via /move (after slicing); keep small for speed + tokens.
MOVE_SAMPLE_CAP = 10


# -----------------------------------------------------------------------------
# Tool layer (explicit “function calling” surface for documentation / homework table)
# -----------------------------------------------------------------------------


def tool_fetch_pokemon(name: str, timeout: float = 30.0) -> Dict[str, Any]:
    """
    Tool: GET https://pokeapi.co/api/v2/pokemon/{name}
    Returns compact stats, types, ability names/slots (extracted shape from api_pokemon.get_pokemon).
    """
    return get_pokemon(name, timeout=timeout)


def tool_fetch_move(move_slug: str, timeout: float = 30.0) -> Dict[str, Any]:
    """
    Tool: GET https://pokeapi.co/api/v2/move/{name}
    Returns name, type, damage category, power, accuracy.
    """
    raw = fetch_move(move_slug, timeout=timeout)
    return {
        "name": raw.get("name"),
        "type": (raw.get("type") or {}).get("name"),
        "damage_class": (raw.get("damage_class") or {}).get("name"),
        "power": raw.get("power"),
        "accuracy": raw.get("accuracy"),
    }


def tool_fetch_ability_description_en(ability_slug: str, timeout: float = 30.0) -> str:
    """Tool: GET https://pokeapi.co/api/v2/ability/{name} → English effect text."""
    return english_effect_entries_text(fetch_ability(ability_slug, timeout=timeout))


def tool_sample_level_up_moves_with_stats(
    pokemon_name: str,
    *,
    raw: Optional[dict] = None,
    cap: int = MOVE_SAMPLE_CAP,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    Tool: uses /pokemon/{name} + /move/{name} (via api helper) for level-up moves with battle fields.
    Pass ``raw`` from a prior fetch to avoid duplicate GET /pokemon. ``cap`` limits /move calls.
    """
    if raw is None:
        return get_pokemon_level_up_moves_table_rows(
            str(pokemon_name).strip().lower(),
            timeout=timeout,
            max_moves=cap,
        )
    return get_pokemon_level_up_moves_table_rows(
        timeout=timeout,
        raw=raw,
        max_moves=cap,
    )


TOOLS_REGISTRY: List[Dict[str, str]] = [
    {
        "name": "tool_fetch_pokemon",
        "purpose": "Load base stats, types, and abilities for a Pokémon.",
        "parameters": "name: str — species/Pokémon slug (e.g. pikachu).",
        "returns": "dict with stats, types, abilities[], moves[] (names only in compact extract).",
    },
    {
        "name": "tool_fetch_move",
        "purpose": "Load move typing, category (physical/special/status), power, accuracy.",
        "parameters": "move_slug: str — move identifier (e.g. thunder-shock).",
        "returns": "dict with type, damage_class, power, accuracy.",
    },
    {
        "name": "tool_fetch_ability_description_en",
        "purpose": "Load English ability effect text (effect_entries, language en).",
        "parameters": "ability_slug: str (e.g. static).",
        "returns": "str — short/long English description.",
    },
    {
        "name": "tool_sample_level_up_moves_with_stats",
        "purpose": "Level-up learnset joined with move stats (same as Moves tab pipeline), truncated.",
        "parameters": "pokemon_name, optional raw payload, cap.",
        "returns": "list of row dicts: Level, Move, Type, Category, Power, Accuracy.",
    },
]

def _now_ms() -> int:
    return int(time.time() * 1000)


# -----------------------------------------------------------------------------
# Agent 1 — Data Retriever (no LLM): orchestrates tools → RAG JSON
# -----------------------------------------------------------------------------


def _ability_rows_parallel(
    pokemon_compact: Dict[str, Any],
    timeout: float,
    *,
    tool_counts: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    abs_meta = list(pokemon_compact.get("abilities") or [])
    slugs: List[str] = []
    for a in abs_meta:
        s = a.get("name") or ""
        if s:
            slugs.append(s)
    if not slugs:
        return []

    def one(slug: str) -> Tuple[str, str]:
        if tool_counts is not None:
            tool_counts["tool_fetch_ability_description_en"] = tool_counts.get("tool_fetch_ability_description_en", 0) + 1
        try:
            return slug, tool_fetch_ability_description_en(slug, timeout=timeout)
        except Exception as exc:
            return slug, f"(could not load ability: {exc})"

    texts: Dict[str, str] = {}
    workers = min(8, max(1, len(slugs)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for slug, txt in ex.map(one, slugs):
            texts[slug] = txt

    out: List[Dict[str, Any]] = []
    for a in abs_meta:
        slug = a.get("name") or ""
        if not slug:
            continue
        out.append(
            {
                "name": slug,
                "is_hidden": a.get("is_hidden"),
                "slot": a.get("slot"),
                "effect_en": texts.get(slug, ""),
            }
        )
    return out


def _stats_list_to_dict(pokemon_compact: Dict[str, Any]) -> Dict[str, int]:
    d: Dict[str, int] = {}
    for s in pokemon_compact.get("stats") or []:
        n = s.get("name")
        if n:
            d[str(n)] = int(s.get("base_stat") or 0)
    return d


def _half_rag_from_raw(raw: dict, timeout: float, *, tool_counts: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    pc = extract_pokemon(raw)
    if tool_counts is not None:
        tool_counts["tool_sample_level_up_moves_with_stats"] = tool_counts.get("tool_sample_level_up_moves_with_stats", 0) + 1
    moves = tool_sample_level_up_moves_with_stats(
        str(pc.get("name") or ""),
        raw=raw,
        cap=MOVE_SAMPLE_CAP,
        timeout=timeout,
    )
    return {
        "name": pc.get("name"),
        "id": pc.get("id"),
        "types": [t.get("name") for t in (pc.get("types") or []) if t.get("name")],
        "stats": _stats_list_to_dict(pc),
        "abilities": _ability_rows_parallel(pc, timeout=timeout, tool_counts=tool_counts),
        "level_up_moves_sample": moves,
    }


def agent_data_retriever(pokemon_a: str, pokemon_b: str, timeout: float = 45.0) -> Dict[str, Any]:
    """
    Agent 1: retrieve grounded facts only (RAG source). Uses tools above; no model calls.
    """
    a = str(pokemon_a).strip().lower()
    b = str(pokemon_b).strip().lower()
    tool_counts: Dict[str, int] = {}

    with ThreadPoolExecutor(2) as ex:
        tool_counts["tool_fetch_pokemon"] = tool_counts.get("tool_fetch_pokemon", 0) + 2
        fut_a = ex.submit(fetch_pokemon, a, timeout)
        fut_b = ex.submit(fetch_pokemon, b, timeout)
        raw_a = fut_a.result()
        raw_b = fut_b.result()

    with ThreadPoolExecutor(2) as ex:
        ha = ex.submit(_half_rag_from_raw, raw_a, timeout, tool_counts=tool_counts)
        hb = ex.submit(_half_rag_from_raw, raw_b, timeout, tool_counts=tool_counts)
        half_a = ha.result()
        half_b = hb.result()

    return {
        "pokemon_a": half_a,
        "pokemon_b": half_b,
        "meta": {
            "source": "PokeAPI via tool_fetch_* helpers",
            "note": f"Level-up moves only, first {MOVE_SAMPLE_CAP} by level-up order (see api_pokemon max_moves).",
            "tools_used": tool_counts,
        },
    }


# -----------------------------------------------------------------------------
# Agent 2 & 3 — LLM stages (grounded on RAG JSON only)
# -----------------------------------------------------------------------------

_ANTI_FABRICATION_RULES = """
STRICT GROUNDING — do not make anything up:
- Every factual claim (base stats, types, ability names, move names, move types, power, accuracy, ability text) must come directly from RAG_DATA. If you are unsure or it is not in the JSON, say "not shown in the data" — do not guess.
- Do not recommend or mention moves that are not listed under level_up_moves_sample for that Pokémon in RAG_DATA.
- Do not invent held items, EVs, IVs, levels, abilities not listed, typings not listed, or damage calculations not derivable from the numbers given.
- Type matchup claims (e.g. super-effective): only state them when the attacking move's Type and the defender's Types are both present in RAG_DATA; otherwise say the interaction cannot be confirmed from the sample.
- Win-chance language must be clearly qualitative and tied to visible stats/moves in RAG_DATA, not a precise or invented percentage.
"""

def _extract_winner_token(text: str) -> str | None:
    """
    Parse a winner token from model output.
    Expected line anywhere: "Winner: <pokemon_a|pokemon_b|unclear>"
    """
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line.lower().startswith("winner:"):
            continue
        tok = line.split(":", 1)[1].strip().lower()
        if tok in ("pokemon_a", "pokemon_b", "unclear", "tie"):
            return "unclear" if tok == "tie" else tok
    return None


def _strip_winner_markup(text: str) -> str:
    """
    Remove any Winner section/lines from model output for clean UI display.
    - Drops lines that are exactly '## Winner'
    - Drops lines that start with 'Winner:'
    """
    out_lines: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.rstrip("\n")
        s = line.strip()
        if s == "## Winner":
            continue
        if s.lower().startswith("winner:"):
            continue
        out_lines.append(line)
    # Trim extra blank lines created by removals
    cleaned = "\n".join(out_lines).strip()
    return cleaned

def _llm_route(prompt: str, timeout: float = 120.0) -> str:
    return call_ollama(prompt, timeout=timeout)


def _use_two_llm_calls() -> bool:
    return os.getenv("BATTLE_TWO_LLM_CALLS", "").strip().lower() in ("1", "true", "yes", "on")


def agent_strategy_analyst(rag: Dict[str, Any], timeout: float = 120.0) -> str:
    """Agent 2: compare stats, typings, moves; estimate matchup (grounded)."""
    blob = json.dumps(rag, indent=2, ensure_ascii=False, default=str)
    prompt = f"""You are a competitive Pokémon battle analyst. Use ONLY the JSON in RAG_DATA below.
RAG_DATA is retrieved from PokeAPI (stats, types, abilities with English effects, and level-up moves with types/categories/power/accuracy). Do not use knowledge of later generations, anime, or unreleased moves.
{_ANTI_FABRICATION_RULES}

RAG_DATA:
{blob}

TASK:
1. Compare effective offenses/defenses using ONLY the typings and stat totals shown (e.g. higher Speed, higher offensive stats, bulk).
2. Identify type-based advantages/disadvantages implied by the typings and move typings in the samples (e.g. if one side has super-effective STAB moves against the other's types, say so — only if visible in RAG_DATA).
3. Name 2–4 recommended moves per Pokémon from the level_up_moves_sample lists (prefer higher power or key coverage when visible).
4. Give a rough win-probability style judgment (e.g. "slight edge to A", "roughly even") — must be justified by RAG_DATA only.

OUTPUT FORMAT (markdown sections):
## Win probability (qualitative)
## Key advantages (stats, typings, moves from data)
## Recommended moves (Pokémon A)
## Recommended moves (Pokémon B)
## Risks / counters visible in the data
## Winner

In the Winner section, include exactly one machine-readable line:
Winner: pokemon_a | pokemon_b | unclear
"""
    return _llm_route(prompt, timeout=timeout)


def agent_battle_narrator(rag: Dict[str, Any], strategy_text: str, timeout: float = 120.0) -> str:
    """Agent 3: narrative battle summary; must stay consistent with RAG + analyst."""
    blob = json.dumps(rag, indent=2, ensure_ascii=False, default=str)
    prompt = f"""You are a sports-style battle narrator. Ground every claim in RAG_DATA or in the ANALYST section — no outside facts.
{_ANTI_FABRICATION_RULES}
Do not add new facts beyond RAG_DATA and ANALYST; do not invent dialogue, items, or moves not in the JSON.

RAG_DATA:
{blob}

ANALYST (strategy — treat as authoritative interpretation of the same data):
{strategy_text}

Write 2–4 short paragraphs:
- Who likely has the edge and why (speed, power, typings, coverage) referencing specific stats/moves from RAG_DATA.
- A punchy one-line "likely outcome" caveat that this is a simplified singles-style analysis using only the sampled moves.

End with exactly one machine-readable line:
Winner: pokemon_a | pokemon_b | unclear
"""
    return _llm_route(prompt, timeout=timeout)


def agent_combined_strategy_and_narrator(rag: Dict[str, Any], timeout: float = 120.0) -> Tuple[str, str]:
    """
    Single LLM call that produces both strategy-style and narrative sections (faster than two round-trips).
    Still grounded only on RAG JSON.
    """
    blob = json.dumps(rag, indent=2, ensure_ascii=False, default=str)
    prompt = f"""You perform two roles in ONE response. Use ONLY the JSON in RAG_DATA. No outside Pokémon knowledge.
{_ANTI_FABRICATION_RULES}

RAG_DATA:
{blob}

PART 1 — Strategy analyst (markdown). Use exactly these section headings:
## Win probability (qualitative)
## Key advantages (stats, typings, moves from data)
## Recommended moves (Pokémon A)
## Recommended moves (Pokémon B)
## Risks / counters visible in the data
## Winner

In the Winner section, include exactly one machine-readable line:
Winner: pokemon_a | pokemon_b | unclear

Then output a single line containing exactly:
---NARRATIVE---

PART 2 — Battle narrator: after that line, write 2–4 short paragraphs on who likely has the edge and why (reference stats/moves from RAG_DATA). End with one line noting this is a simplified analysis using only the sampled level-up moves.
Then end with exactly one machine-readable line:
Winner: pokemon_a | pokemon_b | unclear
"""
    text = _llm_route(prompt, timeout=timeout)
    if "---NARRATIVE---" in text:
        left, right = text.split("---NARRATIVE---", 1)
        return left.strip(), right.strip()
    return text.strip(), "(No ---NARRATIVE--- delimiter in model output.)"


def run_battle_matchup_analysis(
    pokemon_a: str,
    pokemon_b: str,
    *,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """
    Full pipeline: Agent 1 (tools) → Agent 2 + 3 (one or two LLM stages).
    Returns dict with rag, strategy, narrative, and final_markdown for UI.
    """
    rag = agent_data_retriever(pokemon_a, pokemon_b, timeout=min(timeout, 90.0))
    if _use_two_llm_calls():
        strategy = agent_strategy_analyst(rag, timeout=timeout)
        narrative = agent_battle_narrator(rag, strategy, timeout=timeout)
    else:
        strategy, narrative = agent_combined_strategy_and_narrator(rag, timeout=timeout)
    name_a = (rag.get("pokemon_a") or {}).get("name") or pokemon_a
    name_b = (rag.get("pokemon_b") or {}).get("name") or pokemon_b
    # Internal note only (not displayed in UI)
    _mode = "two LLM calls (BATTLE_TWO_LLM_CALLS)" if _use_two_llm_calls() else "single LLM call (strategy + narrative)"
    winner_tok = _extract_winner_token(narrative) or _extract_winner_token(strategy) or "unclear"
    winner_name = (
        str(name_a).title()
        if winner_tok == "pokemon_a"
        else str(name_b).title()
        if winner_tok == "pokemon_b"
        else "Unclear"
    )

    strategy_disp = _strip_winner_markup(strategy)
    narrative_disp = _strip_winner_markup(narrative)

    final_md = "\n\n".join(
        [
            f"# Battle matchup: {name_a} vs {name_b}",
            f"The winner of this battle is.... {winner_name}",
            "## Strategy analysis (Agent 2)",
            strategy_disp,
            "## Battle summary (Agent 3)",
            narrative_disp,
        ]
    )
    return {
        "rag": rag,
        "strategy": strategy,
        "narrative": narrative,
        "final_markdown": final_md,
    }


def run_battle_matchup_safe(pokemon_a: str, pokemon_b: str, *, timeout: float = 120.0) -> str:
    """Returns final markdown or a plain-text error message for Shiny UI."""
    try:
        if not str(pokemon_a).strip() or not str(pokemon_b).strip():
            return "Select both Pokémon A and Pokémon B."
        if str(pokemon_a).strip().lower() == str(pokemon_b).strip().lower():
            return "Choose two different Pokémon for a matchup."
        out = run_battle_matchup_analysis(pokemon_a, pokemon_b, timeout=timeout)
        return out["final_markdown"]
    except Exception as exc:
        return f"Battle matchup error: {exc}"


def terminal_demo(pokemon_a: str = "pikachu", pokemon_b: str = "squirtle") -> int:
    """
    Print a screenshot-friendly terminal run showing:
    - multi-agent workflow (Agent 1 → Agent 2 → Agent 3)
    - RAG bundle (retrieved JSON excerpt)
    - tool usage (tool function names + counts)
    """
    a = str(pokemon_a).strip().lower()
    b = str(pokemon_b).strip().lower()

    print()
    print("===============================================================")
    print("⚔️  agents_pokemon.py — Battle Matchup Summary (Multi-Agent + RAG)")
    print("===============================================================\n")

    print("✅ What this run demonstrates (for screenshots):")
    print("   1) Multi-agent workflow (Agent 1 → Agent 2 → Agent 3)")
    print("   2) RAG retrieval bundle (grounded JSON excerpt)")
    print("   3) Function calling / tool usage (tool_* definitions + counts)\n")

    print("🔧 Tool definitions available (function-calling surface):")
    for t in TOOLS_REGISTRY:
        print(f"   - {t.get('name')}: {t.get('purpose')}")
    print()

    print(f"🎯 Matchup request: A='{a}' vs B='{b}'\n")

    t0 = _now_ms()
    print("🤖 Agent 1 — Data Retriever (tools → RAG JSON) ...")
    rag = agent_data_retriever(a, b, timeout=45.0)
    t1 = _now_ms()
    tools_used = (rag.get("meta") or {}).get("tools_used") or {}
    print(f"   ✅ RAG bundle built in {t1 - t0} ms")
    print("   🧰 Tools used (counts):")
    for k in sorted(tools_used.keys()):
        print(f"      - {k}: {tools_used[k]}")
    print()

    print("📚 RAG_DATA excerpt (Using ONLY the data below):")
    blob = json.dumps(rag, indent=2, ensure_ascii=False, default=str)
    # Keep terminal output screenshot-friendly
    lines = blob.splitlines()
    cap = int(os.getenv("DEMO_RAG_LINES", "120") or 120)
    for ln in lines[:cap]:
        print(ln)
    if len(lines) > cap:
        print(f"... (truncated; total lines={len(lines)})")
    print()

    print("🤖 Agent 2 — Strategy Analyst (LLM; grounded to RAG_DATA) ...")
    t2 = _now_ms()
    strategy = agent_strategy_analyst(rag, timeout=120.0)
    t3 = _now_ms()
    print(f"   ✅ Agent 2 complete in {t3 - t2} ms\n")
    print("----- AGENT 2 OUTPUT (Strategy analysis) -----")
    print(strategy.strip())
    print("--------------------------------------------\n")

    print("🤖 Agent 3 — Battle Narrator (LLM; grounded to RAG_DATA + Agent 2) ...")
    t4 = _now_ms()
    narrative = agent_battle_narrator(rag, strategy, timeout=120.0)
    t5 = _now_ms()
    print(f"   ✅ Agent 3 complete in {t5 - t4} ms\n")
    print("----- AGENT 3 OUTPUT (Battle summary) -----")
    print(narrative.strip())
    print("------------------------------------------\n")

    print("✅ Done. Screenshot any of the sections above.")
    return 0


if __name__ == "__main__":
    # Usage:
    #   python agents_pokemon.py
    #   python agents_pokemon.py pikachu squirtle
    #   DEMO_RAG_LINES=200 python agents_pokemon.py pikachu bulbasaur
    args = [a for a in sys.argv[1:] if a.strip()]
    if len(args) >= 2:
        raise SystemExit(terminal_demo(args[0], args[1]))
    raise SystemExit(terminal_demo("pikachu", "squirtle"))
