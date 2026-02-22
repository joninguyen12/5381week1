"""
app.py — Shiny for Python: Weatherstack API Dashboard

Curated weather table, AI condition summary, and training/travel advisory.
"""

import pandas as pd

from shiny import App, Inputs, Outputs, Session, reactive, render, req, ui

from ai_weather import get_ai_insights
from weather_api import DEFAULT_CITIES, fetch_weather

# Sample data when API rate limit is hit or for offline demo (check "Use sample data (skip API)").
# Same columns and types as fetch_weather() in weather_api.py. One row per default city so the user can select any subset.
SAMPLE_WEATHER = pd.DataFrame([
    {"city": "New York", "temperature_F": 42.0, "humidity": 65, "wind_mph": 12.0, "pressure": 1015, "weather": "Partly cloudy"},
    {"city": "Los Angeles", "temperature_F": 68.0, "humidity": 55, "wind_mph": 5.0, "pressure": 1012, "weather": "Clear"},
    {"city": "Chicago", "temperature_F": 35.0, "humidity": 70, "wind_mph": 15.0, "pressure": 1018, "weather": "Overcast"},
    {"city": "Houston", "temperature_F": 58.0, "humidity": 78, "wind_mph": 8.0, "pressure": 1014, "weather": "Light rain"},
    {"city": "Phoenix", "temperature_F": 75.0, "humidity": 25, "wind_mph": 6.0, "pressure": 1010, "weather": "Sunny"},
    {"city": "Philadelphia", "temperature_F": 45.0, "humidity": 62, "wind_mph": 10.0, "pressure": 1016, "weather": "Partly cloudy"},
    {"city": "Seattle", "temperature_F": 48.0, "humidity": 82, "wind_mph": 7.0, "pressure": 1013, "weather": "Light drizzle"},
    {"city": "San Diego", "temperature_F": 66.0, "humidity": 58, "wind_mph": 9.0, "pressure": 1012, "weather": "Clear"},
    {"city": "Boston", "temperature_F": 38.0, "humidity": 68, "wind_mph": 14.0, "pressure": 1017, "weather": "Partly cloudy"},
    {"city": "San Jose", "temperature_F": 62.0, "humidity": 52, "wind_mph": 4.0, "pressure": 1013, "weather": "Clear"},
])


def make_ui() -> ui.Tag:
    """Define the application UI."""
    return ui.page_sidebar(
        ui.sidebar(
            ui.head_content(
                ui.tags.style(
                    """
                    :root {
                        --weather-bg: #0f172a;
                        --weather-surface: #1e293b;
                        --weather-border: #334155;
                        --weather-primary: #38bdf8;
                        --weather-primary-dim: #0ea5e9;
                        --weather-success: #34d399;
                        --weather-danger: #f87171;
                        --weather-muted: #94a3b8;
                        --weather-text: #020617;
                    }
                    body { background: var(--weather-bg); color: var(--weather-text); }
                    .text-muted { color: #cbd5f5 !important; }
                    .text-success { color: #cbd5f5 !important; }
                    .sidebar { background: var(--weather-surface) !important; border-right: 1px solid var(--weather-border); }
                    .bslib-sidebar-layout-main { background: var(--weather-bg); }
                    .form-label { color: var(--weather-primary); font-weight: 600; }
                    .sidebar #units .form-label,
                    .sidebar #use_case .form-label,
                    .sidebar label[for="use_sample"] {
                        color: var(--weather-primary) !important;
                        font-weight: 600 !important;
                    }
                    .sidebar #cities .form-label { margin-bottom: 0.5rem; }
                    .sidebar #units .form-check:first-of-type { margin-top: 0.5rem; }
                    .sidebar .form-select,
                    .sidebar .selectize-input,
                    .sidebar .form-check-label {
                        color: var(--weather-text);
                    }
                    .sidebar .selectize-input {
                        background-color: #d1daee;
                        border-color: var(--weather-border);
                    }
                    .sidebar .form-check-input:checked {
                        background-color: var(--weather-primary);
                        border-color: var(--weather-primary);
                    }
                    .btn-primary {
                        background: var(--weather-primary);
                        border-color: var(--weather-primary);
                        color: var(--weather-bg);
                        font-weight: 600;
                    }
                    .btn-primary:hover {
                        background: var(--weather-primary-dim);
                        border-color: var(--weather-primary-dim);
                        color: white;
                    }
                    .alert-danger {
                        background: rgba(248, 113, 113, 0.15);
                        border: 1px solid var(--weather-danger);
                        color: #fca5a5;
                        border-radius: 8px;
                    }
                    .weather-hero {
                        font-size: 1.5rem;
                        font-weight: 700;
                        color: var(--weather-primary);
                        margin-bottom: 0.5rem;
                    }
                    .weather-table-container {
                        margin-bottom: 0;
                    }
                    .weather-table-container table {
                        background-color: #d1daee;
                        color: var(--weather-text);
                        overflow: hidden;
                    }
                    .weather-table-container thead th {
                        background-color: #d1daee;
                        border-bottom: 1px solid var(--weather-border);
                    }
                    .weather-table-container tbody tr:nth-child(even) {
                        background-color: #d1daee;
                    }
                    .weather-table-container tbody tr:nth-child(odd) {
                        background-color: #d1daee;
                    }
                    .weather-table-container tbody tr:hover,
                    .weather-table-container tbody tr:focus-within,
                    .weather-table-container tbody tr[aria-selected="true"] {
                        background-color: var(--weather-primary);
                        color: #d1daee;
                    }
                    .ai-card {
                        background-color: #d1daee;
                        color: var(--weather-text);
                        border: 1px solid var(--weather-border);
                        border-radius: 0;
                        padding: 0.75rem 1rem;
                        margin-bottom: 0.5rem;
                    }
                    .ai-card:last-child { margin-bottom: 0; }
                    .ai-card h4 { color: var(--weather-primary); font-size: 1rem; margin-bottom: 0.35rem; }
                    .ai-card p, .ai-card pre { color: var(--weather-text); margin: 0; white-space: pre-wrap; }
                    .status-block { margin-bottom: 0 !important; padding-bottom: 0 !important; }
                    .main-content-wrap > * { margin-top: 0 !important; margin-bottom: 0 !important; }
                    .main-content-wrap .weather-table-container { margin-top: 0 !important; padding-top: 0 !important; margin-bottom: 0; }
                    .main-content-wrap .ai-insights-wrap { margin-top: 0.5rem !important; padding-top: 0; }
                    .main-content-wrap div[data-output-id] { margin: 0 !important; }
                    .ai-loading { color: var(--weather-muted); font-style: italic; }
                    .ai-error { color: var(--weather-danger); }
                    """
                ),
                # Inline favicon to avoid /favicon.ico 404
                ui.tags.link(
                    rel="icon",
                    href=(
                        "data:image/svg+xml,"
                        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
                        "%3Crect width='100' height='100' fill='%230f172a'/%3E"
                        "%3Ctext x='50' y='68' text-anchor='middle' font-size='70' fill='%2338bdf8'%3E"
                        "W%3C/text%3E%3C/svg%3E"
                    ),
                ),
            ),
            ui.div(
                ui.span("Weather Dashboard", class_="weather-hero"),
                ui.p(
                    "Query current weather for US cities via the Weatherstack API.",
                    class_="text-muted",
                    style="font-size: 0.9rem;",
                ),
                style="margin-bottom: 1.5rem;",
            ),
            ui.div(
                ui.input_selectize(
                    "cities",
                    "Cities",
                    choices=DEFAULT_CITIES,
                    selected=DEFAULT_CITIES[:3],
                    multiple=True,
                ),
                class_="text-muted sidebar-field",
                style="font-size: 0.9rem; font-weight: bold; margin-bottom: 1rem;",
            ),
            ui.div(
                ui.input_radio_buttons(
                    "units",
                    "Units",
                    choices={
                        "f": "Fahrenheit (°F, mph)",
                        "m": "Metric (°C, km/h)",
                        "s": "Scientific",
                    },
                    selected="f",
                ),
                class_="text-muted sidebar-field",
                style="font-size: 0.9rem; font-weight: bold; margin-bottom: 1rem;",
            ),
            ui.div(
                ui.input_checkbox("use_sample", "Use sample data (skip API)", value=False),
                ui.p(
                    "Check this if you hit the API rate limit or want to try the app without the API.",
                    class_="text-muted",
                    style="font-size: 0.75rem; margin-top: 0.25rem;",
                ),
                class_="text-muted sidebar-field",
                style="font-size: 0.9rem; font-weight: bold; margin-bottom: 1rem;",
            ),
            ui.input_action_button(
                "fetch_btn",
                "Get Weather",
                class_="btn-primary",
                style="width: 100%; margin-top: 0.5rem;",
            ),
            ui.div(
                ui.input_text(
                    "use_case",
                    "Use Case",
                    placeholder="e.g. training",
                    value="",
                ),
                ui.p(
                    "Optional. Enter how you plan to use the weather (e.g. running, travel); AI will tailor the advisory.",
                    class_="text-muted",
                    style="font-size: 0.75rem; margin-top: 0.25rem;",
                ),
                class_="text-muted sidebar-field",
                style="font-size: 0.9rem; font-weight: bold; margin-bottom: 1rem;",
            ),
            ui.input_action_button(
                "ai_btn",
                "Generate AI Insights",
                class_="btn-primary",
                style="width: 100%; margin-top: 0.5rem;",
            ),
        ),
        ui.div(
            ui.output_ui("status_ui"),
            ui.div(
                ui.output_data_frame("weather_table"),
                class_="weather-table-container",
            ),
            ui.div(
                ui.output_ui("ai_insights_ui"),
                class_="ai-insights-wrap",
            ),
            class_="main-content-wrap",
            style="padding: 0.75rem 1rem; display: flex; flex-direction: column; gap: 0;",
        ),
        title="Weather Dashboard",
    )


def _concise_weather_table(df: pd.DataFrame) -> pd.DataFrame:
    """Curate a short table: City, Temp, Conditions, Wind."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df[["city", "temperature_F", "weather", "wind_mph"]].copy()
    out["temperature_F"] = out["temperature_F"].round(1)
    out["wind_mph"] = out["wind_mph"].round(1)
    out.columns = ["City", "Temp (°F)", "Conditions", "Wind (mph)"]
    return out


def server(input: Inputs, output: Outputs, session: Session) -> None:
    """Server logic: fetch weather, then optional AI summary and advisory."""

    weather_result = reactive.value(None)
    ai_result = reactive.value(None)
    ai_loading = reactive.value(False)

    @reactive.effect
    @reactive.event(input.fetch_btn)
    def _fetch_weather() -> None:
        ai_result.set(None)
        if input.use_sample():
            cities = list(input.cities())
            if not cities:
                weather_result.set({"data": None, "error": "Select at least one city.", "sample": True})
                return
            df = SAMPLE_WEATHER[SAMPLE_WEATHER["city"].isin(cities)].copy()
            df = df.set_index("city").reindex(cities).reset_index()
            weather_result.set({"data": df, "error": None, "sample": True})
            return
        cities = list(input.cities())
        units = str(input.units())
        df, err = fetch_weather(cities, units)
        if err:
            weather_result.set({"data": None, "error": err, "sample": False})
        else:
            weather_result.set({"data": df, "error": None, "sample": False})

    @reactive.effect
    @reactive.event(input.ai_btn)
    def _generate_ai() -> None:
        res = weather_result.get()
        if res is None or res.get("error") or res.get("data") is None:
            ai_result.set({"error": "Load weather first (click Get Weather)."})
            return
        ai_loading.set(True)
        ai_result.set(None)
        try:
            use_case = (input.use_case() or "").strip()
            insights = get_ai_insights(res["data"], use_case=use_case)
            ai_result.set(insights)
        finally:
            ai_loading.set(False)

    @output
    @render.ui
    def status_ui():
        res = weather_result.get()
        if res is None:
            return ui.div(
                ui.p(
                    "Select one or more cities and click ",
                    ui.strong("Get Weather"),
                    " to load current conditions.",
                ),
                class_="text-muted status-block",
                style="padding: 0.5rem 0; margin-bottom: 0;",
            )
        if res.get("error"):
            return ui.div(
                ui.p(ui.strong("Error: "), res["error"]),
                class_="alert alert-danger status-block",
                role="alert",
                style="margin-bottom: 0;",
            )
        n = len(res["data"]) if res.get("data") is not None else 0
        if res.get("sample"):
            return ui.div(
                ui.p(
                    f"Loaded sample data for {n} cities (API skipped). Use this when you hit the rate limit.",
                    class_="text-success",
                ),
                class_="status-block",
                style="margin-bottom: 0;",
            )
        return ui.div(
            ui.p(
                f"Successfully loaded the current weather report for {n} city/cities.",
                class_="text-success",
            ),
            class_="status-block",
            style="margin-bottom: 0;",
        )

    @output
    @render.data_frame
    def weather_table():
        res = weather_result.get()
        req(res is not None and res.get("data") is not None)
        return _concise_weather_table(res["data"])

    @output
    @render.ui
    def ai_insights_ui():
        loading = ai_loading.get()
        if loading:
            return ui.div(
                ui.p("Generating condition summary and advisories…", class_="ai-loading"),
                class_="ai-card",
            )
        out = ai_result.get()
        if out is None:
            return ui.div(
                ui.p(
                    "Click ",
                    ui.strong("Generate AI Insights"),
                    " after loading weather to get a condition summary and advisories. Optionally enter a use case (e.g. running, travel) to tailor the advice.",
                ),
                class_="text-muted",
                style="padding: 0.5rem 0;",
            )
        summary = out.get("summary", "").strip()
        training = out.get("training", "").strip()
        travel = out.get("travel", "").strip()
        use_case_advisory = out.get("use_case_advisory", "").strip()
        use_case_label = out.get("use_case", "").strip()
        use_cases = out.get("use_cases") or []
        advisory_legacy = out.get("advisory", "").strip()
        has_use_case_cards = bool(use_case_advisory) or bool(
            use_cases and any((u.get("advisory") or "").strip() for u in use_cases)
        )
        has_content = (
            summary or training or travel or use_case_advisory or advisory_legacy or has_use_case_cards
        )
        if not has_content and out.get("error"):
            return ui.div(
                ui.p(ui.strong("Error: "), out["error"]),
                class_="alert alert-danger status-block",
                role="alert",
                style="margin-bottom: 0;",
            )
        if not has_content:
            summary = out.get("raw", "No content.")
        def _block(text: str):
            # Strip markdown bold so "**New York:**" displays as "New York:"
            display = (text or "").replace("**", "")
            return ui.tags.pre(display, style="margin: 0; font-family: inherit; font-size: 0.95rem;")
        hint = None
        if out.get("error") and has_content:
            hint = ui.div(
                ui.p(ui.strong("Note: "), out["error"], class_="text-muted"),
                style="font-size: 0.85rem; margin-bottom: 0.5rem; padding: 0.25rem 0;",
            )
        advisory_intro = None
        if has_content:
            advisory_intro = ui.div(
                ui.p(
                    "Generated an AI advisory report for the weather conditions of the selected cities.",
                    class_="text-success",
                ),
                class_="status-block",
                style="margin-bottom: 0; padding: 0.5rem 0;",
            )
        cards = []
        if summary:
            cards.append(ui.div(ui.h4("Condition Summary"), _block(summary), class_="ai-card"))
        for uc in use_cases:
            name = uc.get("name", "").strip()
            advisory = (uc.get("advisory") or "").strip()
            if advisory:
                title = f"Advisory for {name}" if name else "Use-case Advisory"
                cards.append(ui.div(ui.h4(title), _block(advisory), class_="ai-card"))
        if use_case_advisory and not use_cases:
            title = f"Advisory for {use_case_label}" if use_case_label else "Use-case advisory"
            cards.append(ui.div(ui.h4(title), _block(use_case_advisory), class_="ai-card"))
        if training:
            cards.append(ui.div(ui.h4("(Default) Training Advisory"), _block(training), class_="ai-card"))
        if travel:
            cards.append(ui.div(ui.h4("Travel advisory"), _block(travel), class_="ai-card"))
        if advisory_legacy and not training and not travel and not use_case_advisory and not has_use_case_cards:
            cards.append(ui.div(ui.h4("Training / travel advisory"), _block(advisory_legacy), class_="ai-card"))
        parts = [p for p in (hint, advisory_intro) if p is not None]
        return ui.div(*parts, *cards)


app_ui = make_ui()
app = App(app_ui, server)
