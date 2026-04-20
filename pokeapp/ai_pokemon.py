# ai_pokemon.py
# AI summary for a Pokémon using PokeAPI /pokemon-species/{name} (lore) + Ollama.
#
# Env (optional .env next to the app):
#   OLLAMA_HOST         — default http://localhost:11434
#   OLLAMA_MODEL        — default llama3.2

from __future__ import annotations

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv

from api_pokemon import get_pokemon_species

load_dotenv()

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"


def compact_species_for_prompt(species: dict[str, Any]) -> dict[str, Any]:
    """Already-compact api output; trim only if needed for token limits."""
    out = dict(species)
    fts = out.get("flavor_texts_en") or []
    if len(fts) > 16:
        out["flavor_texts_en"] = fts[:16]
        out["flavor_text_note"] = f"Truncated to 16 of {len(fts)} English entries."
    return out


def build_summary_prompt(species: dict[str, Any]) -> str:
    payload = compact_species_for_prompt(species)
    blob = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    return f"""You are a Pokédex lore assistant. The JSON below comes from the official PokeAPI `pokemon-species` resource (plus evolution-chain species names). It is your only source of factual claims about habitat, classification, and Pokédex flavor text.

{blob}

Instructions:
- Write a clear, friendly summary in 2–4 short paragraphs for a general audience.
- Ground every factual claim in the JSON. Do not invent typings, abilities, base stats, moves, or encounters — those live on other endpoints and are not provided here.
- Use the English flavor_texts_en entries for Pokédex-style lore; paraphrase faithfully and mention that descriptions vary by game version when multiple lines appear.
- If evolution_species_names is non-empty, describe the evolution family using that order as a guide (branching families may mention splits briefly).
- Mention habitat, color/shape, egg groups, and legendary/mythical/baby flags only when present in the JSON.
- If the JSON is sparse, say what is missing rather than guessing."""


def call_ollama(
    prompt: str,
    *,
    model: str | None = None,
    host: str | None = None,
    timeout: float = 120.0,
) -> str:
    base = (host or os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
    model = model or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    url = f"{base}/api/generate"
    body = {"model": model, "prompt": prompt, "stream": False}
    headers: dict[str, str] = {}
    api_key = (os.getenv("OLLAMA_API_KEY") or "").strip()
    if api_key:
        # Some hosted Ollama gateways expect an API key (Ollama itself usually doesn't).
        hdr = (os.getenv("OLLAMA_API_KEY_HEADER") or "Authorization").strip() or "Authorization"
        val = api_key
        if hdr.lower() == "authorization" and not val.lower().startswith("bearer "):
            val = f"Bearer {val}"
        headers[hdr] = val
    r = requests.post(url, json=body, headers=headers or None, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return str(data.get("response", "")).strip()


def summarize_pokemon_species(id_or_name: str | int) -> str:
    """
    Fetch /pokemon-species/{id or name} (+ evolution chain), build prompt, run LLM.
    Returns plain text or an error/help string (no bare raise).
    """
    try:
        species = get_pokemon_species(id_or_name, include_evolution_chain=True)
    except Exception as e:
        return f"Could not load species data from PokeAPI: {e}"

    prompt = build_summary_prompt(species)
    try:
        return call_ollama(prompt)
    except Exception as e:
        return (
            "Could not reach Ollama. Start the server (e.g. `ollama serve`), pull a model, "
            f"and check OLLAMA_HOST / OLLAMA_MODEL.\nDetails: {e}"
        )


if __name__ == "__main__":
    print(summarize_pokemon_species("pikachu"))
