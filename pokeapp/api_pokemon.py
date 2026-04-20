"""
api_pokemon.py

🧠 1) Core endpoint (most important):
GET https://pokeapi.co/api/v2/pokemon/{id or name}

This endpoint includes everything needed for a dashboard:
- stats (HP, attack, defense, etc.)
- types
- abilities (with links)
- moves
- sprites (images)

📊 2) List endpoint (for dropdowns / tables):
GET https://pokeapi.co/api/v2/pokemon?limit=...&offset=...

Returns a list of Pokémon names + URLs. This is just basic info —
you’ll still call /pokemon/{name} for details.

🧬 3) Generation endpoint (species names for a generation):
GET https://pokeapi.co/api/v2/generation/{id or name}

Returns `pokemon_species` (names + species URLs). Use species **names** with
GET /pokemon/{name} for stats, sprites, and charts — same as the national list flow.

📖 4) Species / lore endpoint (for Pokédex text + evolution + habitat):
GET https://pokeapi.co/api/v2/pokemon-species/{id or name}

Flavor text, habitat, genera, evolution chain URL — feed into LLM summaries
without hallucinating (pair with /pokemon/{name} for battle stats separately).

⚡ 5) Ability endpoint (effect text for UI / tooltips):
GET https://pokeapi.co/api/v2/ability/{id or name}

Use effect_entries (language "en") for human-readable ability descriptions.

⚔️ 6) Moves (level-up table): combine Pokémon + move resources
GET https://pokeapi.co/api/v2/pokemon/{name} — version_group_details + move_learn_method
GET https://pokeapi.co/api/v2/move/{name} — type, damage_class, power, accuracy

Filter to move_learn_method.name == "level-up" for level-up learnsets only.
"""

import json
from typing import List, Optional, Tuple, Union

import requests

BASE_URL = "https://pokeapi.co/api/v2/pokemon"
GENERATION_BASE_URL = "https://pokeapi.co/api/v2/generation"
SPECIES_BASE_URL = "https://pokeapi.co/api/v2/pokemon-species"
ABILITY_BASE_URL = "https://pokeapi.co/api/v2/ability"
MOVE_BASE_URL = "https://pokeapi.co/api/v2/move"


def fetch_pokemon(id_or_name: Union[str, int], timeout: float = 30.0) -> dict:
    """GET /pokemon/{id or name} and return parsed JSON."""
    token = str(id_or_name).strip().lower()
    if not token:
        raise ValueError("id_or_name must be a non-empty string or int")
    url = f"{BASE_URL}/{token}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_pokemon_list(limit: int = 151, offset: int = 0, timeout: float = 30.0) -> dict:
    """GET /pokemon?limit=...&offset=... and return parsed JSON."""
    lim = max(1, int(limit))
    off = max(0, int(offset))
    response = requests.get(BASE_URL, params={"limit": lim, "offset": off}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def extract_pokemon_list(payload: dict) -> dict:
    """Extract a compact list of {name, url} items from the list endpoint payload."""
    results_out = []
    for r in payload.get("results") or []:
        results_out.append({"name": r.get("name"), "url": r.get("url")})
    return {
        "count": payload.get("count"),
        "next": payload.get("next"),
        "previous": payload.get("previous"),
        "results": results_out,
        "source_url": BASE_URL,
    }


def get_pokemon_list(limit: int = 151, offset: int = 0, timeout: float = 30.0) -> dict:
    """
    Convenience function for selection UIs:
    returns {count, next, previous, results:[{name,url},...]}.
    """
    return extract_pokemon_list(fetch_pokemon_list(limit=limit, offset=offset, timeout=timeout))


def fetch_generation(id_or_name: Union[str, int], timeout: float = 30.0) -> dict:
    """GET /generation/{id or name} and return parsed JSON."""
    token = str(id_or_name).strip().lower()
    if not token:
        raise ValueError("generation id_or_name must be non-empty")
    url = f"{GENERATION_BASE_URL}/{token}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def extract_generation_species(payload: dict) -> dict:
    """
    Species rows for UI lists: same {name, url} shape as the /pokemon list endpoint,
    but URLs point at pokemon-species resources (not /pokemon/).
    """
    results_out = []
    for s in payload.get("pokemon_species") or []:
        results_out.append({"name": s.get("name"), "url": s.get("url")})
    region = payload.get("main_region") or {}
    return {
        "generation_id": payload.get("id"),
        "generation_name": payload.get("name"),
        "main_region": region.get("name"),
        "count": len(results_out),
        "results": results_out,
        "source_url": f"{GENERATION_BASE_URL}/{payload.get('name') or payload.get('id')}",
    }


def get_generation_species(id_or_name: Union[str, int], timeout: float = 30.0) -> dict:
    """
    All Pokémon species introduced in a generation (names only from API).
    Paginate client-side with offset/limit; call get_pokemon(name) for details.
    """
    return extract_generation_species(fetch_generation(id_or_name=id_or_name, timeout=timeout))


def extract_pokemon(payload: dict) -> dict:
    """Extract a compact, UI-friendly shape from the PokeAPI payload."""
    # Stats for charts
    stats_out = []
    for s in payload.get("stats") or []:
        stat = s.get("stat") or {}
        stats_out.append(
            {
                "name": stat.get("name"),
                "base_stat": s.get("base_stat"),
                "effort": s.get("effort"),
            }
        )

    # Types
    types_out = []
    for t in payload.get("types") or []:
        tinfo = t.get("type") or {}
        types_out.append({"name": tinfo.get("name"), "url": tinfo.get("url")})

    # Abilities (with links)
    abilities_out = []
    for a in payload.get("abilities") or []:
        ainfo = a.get("ability") or {}
        abilities_out.append(
            {
                "name": ainfo.get("name"),
                "url": ainfo.get("url"),
                "is_hidden": a.get("is_hidden"),
                "slot": a.get("slot"),
            }
        )

    # Moves (can be long, but keeping full list is often useful for filtering/search)
    moves_out = []
    for m in payload.get("moves") or []:
        minfo = m.get("move") or {}
        moves_out.append({"name": minfo.get("name"), "url": minfo.get("url")})

    sprites = payload.get("sprites") or {}
    other = sprites.get("other") or {}
    official_artwork = (other.get("official-artwork") or {}) if isinstance(other, dict) else {}

    sprites_out = {
        # Common sprite fields
        "front_default": sprites.get("front_default"),
        "front_shiny": sprites.get("front_shiny"),
        "back_default": sprites.get("back_default"),
        "back_shiny": sprites.get("back_shiny"),
        # Higher-quality images (when present)
        "official_artwork_front_default": official_artwork.get("front_default"),
        "official_artwork_front_shiny": official_artwork.get("front_shiny"),
    }

    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "height": payload.get("height"),
        "weight": payload.get("weight"),
        "base_experience": payload.get("base_experience"),
        "stats": stats_out,
        "types": types_out,
        "abilities": abilities_out,
        "moves": moves_out,
        "sprites": sprites_out,
        "source_url": f"{BASE_URL}/{payload.get('name') or payload.get('id')}",
    }


def get_pokemon(id_or_name: Union[str, int], timeout: float = 30.0) -> dict:
    """
    Convenience function for your Shiny app:
    fetch from PokeAPI, then return extracted fields.
    """
    return extract_pokemon(fetch_pokemon(id_or_name=id_or_name, timeout=timeout))


def fetch_move(id_or_name: Union[str, int], timeout: float = 30.0) -> dict:
    """GET /move/{id or name} — type, damage_class (category), power, accuracy."""
    token = str(id_or_name).strip().lower()
    if not token:
        raise ValueError("move id_or_name must be non-empty")
    url = f"{MOVE_BASE_URL}/{token}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def extract_move_battle_fields(payload: dict) -> dict:
    """Fields for a structured moves table (physical / special / status, power, etc.)."""
    return {
        "name": payload.get("name"),
        "type": (payload.get("type") or {}).get("name"),
        "category": (payload.get("damage_class") or {}).get("name"),
        "power": payload.get("power"),
        "accuracy": payload.get("accuracy"),
    }


def level_up_moves_min_level(pokemon_raw: dict) -> List[Tuple[str, int]]:
    """
    One row per move name: minimum level_learned_at among entries where
    move_learn_method is 'level-up'. Sorted by level, then move name.
    """
    best: dict[str, int] = {}
    for m in pokemon_raw.get("moves") or []:
        minfo = m.get("move") or {}
        mname = minfo.get("name")
        if not mname:
            continue
        levels: List[int] = []
        for vgd in m.get("version_group_details") or []:
            if (vgd.get("move_learn_method") or {}).get("name") != "level-up":
                continue
            lv = vgd.get("level_learned_at")
            if lv is None:
                continue
            levels.append(int(lv))
        if not levels:
            continue
        lvl_min = min(levels)
        prev = best.get(mname)
        if prev is None or lvl_min < prev:
            best[mname] = lvl_min
    return sorted(best.items(), key=lambda x: (x[1], x[0]))


def get_pokemon_level_up_moves_table_rows(
    id_or_name: Optional[Union[str, int]] = None,
    timeout: float = 30.0,
    *,
    raw: Optional[dict] = None,
    max_moves: Optional[int] = None,
) -> List[dict]:
    """
    Level-up moves only: join /pokemon/{name} learn levels with /move/{name} stats.
    Rows: Level, Move, Type, Category, Power, Accuracy (None → shown as empty in UI).

    If ``raw`` is provided, skips an extra GET /pokemon/{name} (same payload as fetch_pokemon).
    If ``max_moves`` is set, only the first N level-up moves (by learn level, then name) are
    resolved via /move — large speed win for AI/RAG bundles.
    """
    if raw is None:
        if id_or_name is None:
            raise TypeError("id_or_name is required when raw is not provided")
        raw = fetch_pokemon(id_or_name=id_or_name, timeout=timeout)
    pairs = level_up_moves_min_level(raw)
    if max_moves is not None:
        pairs = pairs[: max(0, int(max_moves))]
    rows: List[dict] = []
    for move_slug, level in pairs:
        label = move_slug.replace("-", " ").title()
        try:
            mp = fetch_move(move_slug, timeout=timeout)
            fld = extract_move_battle_fields(mp)
        except Exception as exc:
            rows.append(
                {
                    "Level": level,
                    "Move": label,
                    "Type": f"(move API) {exc}"[:200],
                    "Category": None,
                    "Power": None,
                    "Accuracy": None,
                }
            )
            continue
        pwr = fld.get("power")
        acc = fld.get("accuracy")
        typ = fld.get("type") or ""
        cat = fld.get("category") or ""
        rows.append(
            {
                "Level": level,
                "Move": label,
                "Type": typ.replace("-", " ").title() if typ else None,
                "Category": cat.replace("-", " ").title() if cat else None,
                "Power": None if pwr is None else int(pwr),
                "Accuracy": None if acc is None else int(acc),
            }
        )
    return rows


def fetch_ability(id_or_name: Union[str, int], timeout: float = 30.0) -> dict:
    """GET /ability/{id or name} — includes effect_entries (per-language battle effect text)."""
    token = str(id_or_name).strip().lower()
    if not token:
        raise ValueError("ability id_or_name must be non-empty")
    url = f"{ABILITY_BASE_URL}/{token}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def english_effect_entries_text(payload: dict) -> str:
    """
    Prefer English effect_entries: short_effect for a brief line, else full effect text.
    """
    for e in payload.get("effect_entries") or []:
        if (e.get("language") or {}).get("name") != "en":
            continue
        short = str(e.get("short_effect") or "").strip().replace("\n", " ").replace("\f", " ")
        if short:
            return short
        long_txt = str(e.get("effect") or "").strip().replace("\n", " ").replace("\f", " ")
        if long_txt:
            return long_txt
    return ""


def get_ability_description_en(id_or_name: Union[str, int], timeout: float = 30.0) -> str:
    """Convenience: fetch ability and return English effect text only."""
    return english_effect_entries_text(fetch_ability(id_or_name=id_or_name, timeout=timeout))


def get_pokemon_abilities_table_rows(pokemon: dict, timeout: float = 30.0) -> List[dict]:
    """
    One row per ability on the Pokémon, sorted by slot.
    Fetches GET /ability/{name} for each to attach English effect_entries text.
    """
    abs_list = pokemon.get("abilities") or []
    sorted_abs = sorted(
        abs_list,
        key=lambda x: (int(x.get("slot") or 0), bool(x.get("is_hidden"))),
    )
    rows: List[dict] = []
    for i, ab in enumerate(sorted_abs, start=1):
        name = ab.get("name") or ""
        hidden = ab.get("is_hidden") or False
        label = name.replace("-", " ").title() if name else "—"
        desc = ""
        if name:
            try:
                raw = fetch_ability(name, timeout=timeout)
                desc = english_effect_entries_text(raw)
            except Exception as exc:
                desc = f"[Could not load ability: {exc}]"
        rows.append(
            {
                "No.": str(i),
                "Ability": label,
                "Hidden": "Yes" if hidden else "No",
                "Description (EN)": desc or "—",
            }
        )
    return rows


def fetch_pokemon_species(id_or_name: Union[str, int], timeout: float = 30.0) -> dict:
    """GET /pokemon-species/{id or name} — flavor text, habitat, evolution chain URL, lore fields."""
    token = str(id_or_name).strip().lower()
    if not token:
        raise ValueError("species id_or_name must be a non-empty string or int")
    url = f"{SPECIES_BASE_URL}/{token}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_url_json(url: str, timeout: float = 30.0) -> dict:
    """GET any PokeAPI JSON URL (e.g. evolution-chain)."""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _evolution_species_names(chain_node: dict) -> list[str]:
    """Depth-first names under an evolution-chain node (branches included)."""
    names: list[str] = []
    sp = (chain_node.get("species") or {}).get("name")
    if sp:
        names.append(sp)
    for ev in chain_node.get("evolves_to") or []:
        names.extend(_evolution_species_names(ev))
    return names


def extract_pokemon_species(payload: dict, evolution_chain_payload: Optional[dict] = None) -> dict:
    """
    Compact species + optional evolution chain for UI / LLM prompts.
    """
    flavor_en: list[dict] = []
    seen_text: set[str] = set()
    for ft in payload.get("flavor_text_entries") or []:
        if (ft.get("language") or {}).get("name") != "en":
            continue
        raw = ft.get("flavor_text") or ""
        text = str(raw).replace("\n", " ").replace("\f", " ").strip()
        if not text:
            continue
        key = text[:120]
        if key in seen_text:
            continue
        seen_text.add(key)
        flavor_en.append(
            {
                "version": (ft.get("version") or {}).get("name"),
                "text": text,
            }
        )
        if len(flavor_en) >= 14:
            break

    genera = ""
    for g in payload.get("genera") or []:
        if (g.get("language") or {}).get("name") == "en":
            genera = g.get("genus") or ""
            break

    ev_names: list[str] = []
    if evolution_chain_payload:
        root = evolution_chain_payload.get("chain") or {}
        ev_names = _evolution_species_names(root)
        # Deduplicate preserving order
        seen_n: set[str] = set()
        uniq: list[str] = []
        for n in ev_names:
            if n not in seen_n:
                seen_n.add(n)
                uniq.append(n)
        ev_names = uniq

    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "genus": genera,
        "color": (payload.get("color") or {}).get("name"),
        "shape": (payload.get("shape") or {}).get("name"),
        "habitat": (payload.get("habitat") or {}).get("name"),
        "capture_rate": payload.get("capture_rate"),
        "is_baby": payload.get("is_baby"),
        "is_legendary": payload.get("is_legendary"),
        "is_mythical": payload.get("is_mythical"),
        "egg_groups": [eg.get("name") for eg in payload.get("egg_groups") or []],
        "flavor_texts_en": flavor_en,
        "evolution_species_names": ev_names,
        "source_url": f"{SPECIES_BASE_URL}/{payload.get('name') or payload.get('id')}",
    }


def get_pokemon_species(id_or_name: Union[str, int], timeout: float = 30.0, include_evolution_chain: bool = True) -> dict:
    """
    Species lore bundle: flavor text (EN), habitat, tags, and optional evolution names
    from the linked evolution-chain resource.
    """
    raw = fetch_pokemon_species(id_or_name=id_or_name, timeout=timeout)
    chain_payload = None
    if include_evolution_chain:
        ec_url = (raw.get("evolution_chain") or {}).get("url")
        if ec_url:
            try:
                chain_payload = fetch_url_json(ec_url, timeout=timeout)
            except Exception:
                chain_payload = None
    return extract_pokemon_species(raw, evolution_chain_payload=chain_payload)


if __name__ == "__main__":
    print(json.dumps(get_pokemon_list(limit=10), indent=2))
    print(json.dumps(get_generation_species(1), indent=2))
    print(json.dumps(get_pokemon("pikachu"), indent=2))
    print(json.dumps(get_pokemon_species("pikachu"), indent=2))
