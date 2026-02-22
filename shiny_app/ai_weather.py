# ai_weather.py
# Generate condition summary and training/travel advisory from weather data using AI.
# Uses OpenAI if OPENAI_API_KEY is set, else Ollama (local or cloud).

import os
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(".env")

# Prefer OpenAI, then Ollama local, then Ollama cloud.
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OLLAMA_LOCAL_URL = "http://localhost:11434/api/generate"
OLLAMA_CLOUD_URL = "https://ollama.com/api/chat"


def _weather_to_text(df: pd.DataFrame) -> str:
    """Format weather DataFrame as concise text for the AI prompt."""
    lines = []
    for _, row in df.iterrows():
        t = row.get("temperature_F", row.get("temperature", "—"))
        w = row.get("weather", row.get("weather_descriptions", "—"))
        if isinstance(w, list):
            w = w[0] if w else "—"
        h = row.get("humidity", "—")
        wind = row.get("wind_mph", row.get("wind_speed", "—"))
        city = row.get("city", row.get("location", "—"))
        lines.append(f"  {city}: {t}°F, {w}, humidity {h}%, wind {wind} mph")
    return "\n".join(lines) if lines else "No city data."


def _get_city_list(df: pd.DataFrame) -> List[str]:
    """Return list of city names from the weather DataFrame."""
    col = "city" if "city" in df.columns else "location"
    return list(df[col].astype(str).dropna().unique()) if col in df.columns else []


def _parse_use_case_input(raw: str) -> List[str]:
    """Parse use case string into a list (comma-separated); empty or whitespace-only returns []."""
    if not raw or not raw.strip():
        return []
    return [u.strip() for u in raw.split(",") if u.strip()]


def _prompt(
    weather_text: str,
    use_case_list: List[str],
    city_list: List[str],
) -> str:
    """
    Build the AI prompt.
    use_case_list empty -> summary + training + travel.
    use_case_list of 1 -> summary + single use-case advisory (by city).
    use_case_list of 2+ -> summary + one advisory section per use case (each by city).
    """
    cities_phrase = ", ".join(city_list) if city_list else "the cities in the data"
    if not use_case_list:
        return f"""Current weather for selected cities:

{weather_text}

Respond in exactly three short sections. No other intro or outro.

**Condition summary:** Brief overview of conditions across the cities (e.g., mild vs cold, clear vs cloudy, wind). 2–4 sentences.

**Training advisory:** Practical tips for outdoor training (e.g., running, cycling). Organize your advice by city: for each of {cities_phrase}, give a subheading with the city name followed by a colon (e.g. "New York:" on its own line), then 1–3 bullet points. Do not use markdown bold for city names. Use bullet points.

**Travel advisory:** Practical tips for travel (e.g., packing, driving, layering). Organize your advice by city: for each of {cities_phrase}, give a subheading with the city name followed by a colon (e.g. "New York:" on its own line), then 1–3 bullet points. Do not use markdown bold for city names. Use bullet points."""
    if len(use_case_list) == 1:
        uc = use_case_list[0]
        return f"""Current weather for selected cities:

{weather_text}

The user's use case: {uc}

Respond in exactly two short sections. No other intro or outro.

**Condition summary:** Brief overview of conditions across the cities (e.g., mild vs cold, clear vs cloudy, wind). 2–4 sentences.

**Advisory for {uc}:** Evaluate the weather specifically for this use case. Organize your advice by city: for each of {cities_phrase}, give a subheading with the city name followed by a colon (e.g. "New York:" on its own line), then 1–3 bullet points with practical tips. Do not use markdown bold for city names. Use bullet points."""
    # Multiple use cases
    uc_enum = ", ".join(use_case_list)
    sections_instruction = "\n".join(f"- **Advisory for {u}:**" for u in use_case_list)
    return f"""Current weather for selected cities:

{weather_text}

The user's use cases: {uc_enum}

Respond with the following sections. No other intro or outro.

**Condition summary:** Brief overview of conditions across the cities (e.g., mild vs cold, clear vs cloudy, wind). 2–4 sentences.

For each use case below, provide a section with that exact header. Within each section, organize advice by city: for each of {cities_phrase}, give a subheading with the city name followed by a colon (e.g. "New York:" on its own line), then 1–3 bullet points. Do not use markdown bold for city names.

{sections_instruction}"""


def _call_openai(prompt: str, api_key: str) -> Optional[str]:
    """Call OpenAI chat/completions. Returns content or None on failure."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        r = requests.post(OPENAI_URL, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _call_ollama_local(prompt: str) -> Optional[str]:
    """Call local Ollama /api/generate. Returns response text or None."""
    body = {"model": "llama3.2", "prompt": prompt, "stream": False}
    try:
        r = requests.post(OLLAMA_LOCAL_URL, json=body, timeout=120)
        r.raise_for_status()
        return r.json().get("response")
    except Exception:
        return None


def _call_ollama_cloud(prompt: str, api_key: str) -> Optional[str]:
    """Call Ollama cloud /api/chat. Returns message content or None."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "llama3.2",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        r = requests.post(OLLAMA_CLOUD_URL, headers=headers, json=body, timeout=120)
        r.raise_for_status()
        return r.json().get("message", {}).get("content")
    except Exception:
        return None


def _sample_response(
    use_case_list: Optional[List[str]] = None,
    city_list: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return sample summary and advisories when no AI provider is available (for demo)."""
    cities = city_list or ["New York", "Los Angeles", "Chicago"]
    if use_case_list and len(use_case_list) == 1:
        uc = use_case_list[0]
        by_city = "\n\n".join(
            f"**{c}:**\n• Sample advice for {uc} here." for c in cities
        )
        return {
            "summary": "Conditions vary across the selected cities: cooler and windier in the north, milder and calmer in the south. Expect a mix of clear and partly cloudy skies.",
            "training": "",
            "travel": "",
            "use_case": uc,
            "use_case_advisory": by_city,
            "sample": True,
        }
    if use_case_list and len(use_case_list) >= 2:
        use_cases = []
        for uc in use_case_list:
            by_city = "\n\n".join(
                f"**{c}:**\n• Sample advice for {uc} here." for c in cities
            )
            use_cases.append({"name": uc, "advisory": by_city})
        return {
            "summary": "Conditions vary across the selected cities: cooler and windier in the north, milder and calmer in the south. Expect a mix of clear and partly cloudy skies.",
            "training": "",
            "travel": "",
            "use_cases": use_cases,
            "sample": True,
        }
    return {
        "summary": "Conditions vary across the selected cities: cooler and windier in the north, milder and calmer in the south. Expect a mix of clear and partly cloudy skies.",
        "training": "• Good conditions for outdoor runs in LA; light layers.\n• In Chicago, allow extra time for wind and cooler temps; consider a headwind leg first.\n• In New York, partly cloudy and mild—suitable for most outdoor training.",
        "travel": "• Layer up in colder cities (e.g., Chicago); light jacket or long sleeves for milder ones.\n• Pack for a range of temps if traveling between cities.\n• Windier in the north—allow buffer for travel time.",
        "sample": True,
    }


def _parse_three_sections(raw: str) -> Dict[str, str]:
    """Split model output into condition summary, training advisory, and travel advisory."""
    summary = ""
    training = ""
    travel = ""
    if not raw or not raw.strip():
        return {"summary": "", "training": "", "travel": ""}
    text = raw.strip()
    lower = text.lower()

    def strip_header(block: str) -> str:
        for line in block.split("\n"):
            if line.strip().startswith("**"):
                block = block.replace(line, "", 1).strip()
                break
        return block

    # Find Training advisory and Travel advisory (with ** or at line start so we don't miss them)
    i_training = lower.find("**training advisory")
    if i_training == -1:
        i_training = lower.find("**training")
    if i_training == -1:
        i_training = lower.find("\ntraining advisory")
    if i_training == -1 and lower.startswith("training advisory"):
        i_training = 0
    i_travel = lower.find("**travel advisory")
    if i_travel == -1:
        i_travel = lower.find("**travel")
    if i_travel == -1:
        i_travel = lower.find("\ntravel advisory")
    if i_travel == -1 and lower.startswith("travel advisory"):
        i_travel = 0

    if i_training >= 0 and i_travel >= 0:
        summary = text[: min(i_training, i_travel)].strip()
        summary = strip_header(summary)
        if i_training < i_travel:
            training = text[i_training:i_travel].strip()
            travel = text[i_travel:].strip()
        else:
            travel = text[i_travel:i_training].strip()
            training = text[i_training:].strip()
        training = strip_header(training)
        travel = strip_header(travel)
    else:
        # Fallback: first paragraph = summary, then try to split rest on "travel" vs "training"
        parts = text.split("\n\n", 1)
        summary = parts[0].strip() if parts else ""
        summary = strip_header(summary)
        rest = parts[1].strip() if len(parts) > 1 else ""
        if rest:
            training = rest
            travel = ""
    return {"summary": summary, "training": training, "travel": travel}


def _parse_two_sections(raw: str, use_case: str) -> Dict[str, Any]:
    """Split model output into condition summary and use-case advisory (two sections)."""
    summary = ""
    use_case_advisory = ""
    if not raw or not raw.strip():
        return {"summary": "", "training": "", "travel": "", "use_case": use_case, "use_case_advisory": ""}
    text = raw.strip()
    lower = text.lower()

    def strip_header(block: str) -> str:
        for line in block.split("\n"):
            if line.strip().startswith("**"):
                block = block.replace(line, "", 1).strip()
                break
        return block

    # Find **Advisory for {use_case}:** (header may be slightly different)
    advisory_marker = f"**advisory for"
    i_advisory = lower.find(advisory_marker)
    if i_advisory == -1:
        i_advisory = lower.find("**advisory")
    if i_advisory >= 0:
        summary = text[:i_advisory].strip()
        summary = strip_header(summary)
        use_case_advisory = text[i_advisory:].strip()
        use_case_advisory = strip_header(use_case_advisory)
    else:
        parts = text.split("\n\n", 1)
        summary = parts[0].strip() if parts else ""
        summary = strip_header(summary)
        use_case_advisory = parts[1].strip() if len(parts) > 1 else ""
        use_case_advisory = strip_header(use_case_advisory)
    return {
        "summary": summary,
        "training": "",
        "travel": "",
        "use_case": use_case,
        "use_case_advisory": use_case_advisory,
    }


def _parse_multi_use_case_sections(
    raw: str, use_case_list: List[str]
) -> Dict[str, Any]:
    """Split model output into condition summary and one advisory per use case."""
    summary = ""
    use_cases: List[Dict[str, str]] = []
    if not raw or not raw.strip():
        return {"summary": "", "training": "", "travel": "", "use_cases": []}
    text = raw.strip()
    lower = text.lower()

    def strip_header(block: str) -> str:
        for line in block.split("\n"):
            if line.strip().startswith("**"):
                block = block.replace(line, "", 1).strip()
                break
        return block

    # Everything before first "**Advisory for" is the summary
    i_first = lower.find("**advisory for")
    if i_first == -1:
        i_first = len(text)
    summary = text[:i_first].strip()
    summary = strip_header(summary)
    rest = text[i_first:].strip()
    rest_lower = rest.lower()

    pos = 0
    for uc in use_case_list:
        marker = f"**advisory for {uc.lower()}"
        start = rest_lower.find(marker, pos)
        if start == -1:
            use_cases.append({"name": uc, "advisory": ""})
            continue
        end = rest_lower.find("**advisory for", start + len(marker))
        if end == -1:
            end = len(rest)
        block = rest[start:end].strip()
        block = strip_header(block)
        use_cases.append({"name": uc, "advisory": block})
        pos = end
    return {
        "summary": summary,
        "training": "",
        "travel": "",
        "use_cases": use_cases,
    }


def get_ai_insights(df: pd.DataFrame, use_case: str = "") -> Dict[str, Any]:
    """
    Generate condition summary and advisory from weather DataFrame.

    Args:
        df: DataFrame with at least city, temperature_F (or temperature), weather,
            humidity, wind_mph (or wind_speed). Can have weather_descriptions as list.
        use_case: Optional; comma-separated use cases (e.g. "running, travel").
            Empty → training + travel advisories. One → single use-case card (by city).
            Multiple → one card per use case, each organized by city.

    Returns:
        Dict with "summary", and either "training"/"travel", or "use_case"/"use_case_advisory",
        or "use_cases" (list of {name, advisory}).
    """
    if df is None or df.empty:
        return {"error": "No weather data to analyze."}
    use_case_list = _parse_use_case_input(use_case or "")
    city_list = _get_city_list(df)
    weather_text = _weather_to_text(df)
    prompt = _prompt(weather_text, use_case_list, city_list)
    api_key_openai = (os.getenv("OPENAI_API_KEY") or "").strip()
    api_key_ollama = (os.getenv("OLLAMA_API_KEY") or "").strip()

    raw = None
    if api_key_openai:
        raw = _call_openai(prompt, api_key_openai)
    if raw is None or not raw.strip():
        raw = _call_ollama_local(prompt)
    if (raw is None or not raw.strip()) and api_key_ollama:
        raw = _call_ollama_cloud(prompt, api_key_ollama)

    if not raw or not raw.strip():
        sample = _sample_response(use_case_list=use_case_list, city_list=city_list)
        sample["error"] = (
            "No AI provider available. Showing sample output. To get real insights: "
            "add OPENAI_API_KEY to app3/.env, or run Ollama locally (ollama run llama3.2), "
            "or add OLLAMA_API_KEY for Ollama cloud."
        )
        return sample
    if len(use_case_list) == 0:
        out = _parse_three_sections(raw)
    elif len(use_case_list) == 1:
        out = _parse_two_sections(raw, use_case_list[0])
    else:
        out = _parse_multi_use_case_sections(raw, use_case_list)
    out["raw"] = raw
    out["sample"] = False
    return out
