# weather_api.py
# Helper module for Weatherstack API queries.
# Used by the Shiny weather app and can be reused by other scripts.

import os
import time
from typing import Any, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(".env")

BASE_URL = "http://api.weatherstack.com/current"
DEFAULT_CITIES: List[str] = [
    "New York",
    "Los Angeles",
    "Chicago",
    "Houston",
    "Phoenix",
    "Philadelphia",
    "Seattle",
    "San Diego",
    "Boston",
    "San Jose",
]


def get_api_key() -> Optional[str]:
    """Return the Weatherstack API key from environment, or None if missing."""
    return os.getenv("WEATHER_API_KEY")


def fetch_weather(
    cities: List[str],
    units: str = "f",
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Query Weatherstack current weather API for the given cities.

    Args:
        cities: List of location names (e.g., city names).
        units: 'm' = metric, 'f' = Fahrenheit, 's' = scientific.

    Returns:
        (DataFrame, None) on success; (None, error_message) on failure.
    """
    api_key = get_api_key()
    if not api_key or not api_key.strip():
        return None, "API key not found. Add WEATHER_API_KEY to a .env file in the app directory."

    if not cities:
        return None, "Please select at least one city."

    results = []
    last_status = None
    last_error = None

    for i, city in enumerate(cities):
        params = {
            "access_key": api_key,
            "query": city.strip(),
            "units": units,
        }
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            last_status = response.status_code
            data = response.json()
        except requests.RequestException as e:
            last_error = str(e)
            continue
        except (ValueError, KeyError) as e:
            last_error = str(e)
            continue

        if response.status_code != 200:
            err_msg = data.get("error", {}).get("info", response.text) or response.reason
            last_error = err_msg
            continue

        if "current" not in data:
            err_msg = data.get("error", {}).get("info", "No current weather in response.")
            last_error = err_msg
            continue

        cur = data["current"]
        descs = cur.get("weather_descriptions") or []
        results.append({
            "city": city.strip(),
            "temperature_F": cur.get("temperature"),
            "humidity": cur.get("humidity"),
            "wind_mph": cur.get("wind_speed"),
            "pressure": cur.get("pressure"),
            "weather": descs[0] if descs else "",
        })

        if i < len(cities) - 1:
            time.sleep(1)

    if not results:
        msg = last_error or (f"HTTP {last_status}" if last_status else "No data returned.")
        return None, f"Could not load weather for any city. {msg}"

    return pd.DataFrame(results), None
