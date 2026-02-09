"""
app.py — Shiny for Python: Weatherstack API Dashboard

Core Shiny version (no shiny.express) for maximum compatibility.
"""

from shiny import App, Inputs, Outputs, Session, reactive, render, req, ui

from weather_api import DEFAULT_CITIES, fetch_weather


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
                        color: #d1daee`;
                    }
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
                class_="text-muted",
                style="font-size: 0.9rem; font-weight: bold;",
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
                class_="text-muted",
                style="font-size: 0.9rem;",
            ),
            ui.input_action_button(
                "fetch_btn",
                "Get Weather",
                class_="btn-primary",
                style="width: 100%; margin-top: 0.5rem;",
            ),
        ),
        ui.layout_column_wrap(
            ui.output_ui("status_ui"),
            ui.div(
                ui.output_data_frame("weather_table"),
                class_="weather-table-container",
            ),
            width=1,
            style="padding: 1.5rem;",
        ),
        title="Weather Dashboard",
    )


def server(input: Inputs, output: Outputs, session: Session) -> None:
    """Server logic: run API only on button click."""

    # Reactive value: holds {"data": DataFrame | None, "error": str | None}
    weather_result = reactive.value(None)

    @reactive.effect
    @reactive.event(input.fetch_btn)
    def _fetch_weather() -> None:
        # Simpler, version-compatible pattern without Progress
        cities = list(input.cities())
        units = str(input.units())
        df, err = fetch_weather(cities, units)
        if err:
            weather_result.set({"data": None, "error": err})
        else:
            weather_result.set({"data": df, "error": None})

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
                class_="text-muted",
                style="padding: 1rem;",
            )
        if res.get("error"):
            return ui.div(
                ui.p(ui.strong("Error: "), res["error"]),
                class_="alert alert-danger",
                role="alert",
                style="margin-bottom: 1rem;",
            )
        n = len(res["data"]) if res.get("data") is not None else 0
        return ui.div(
            ui.p(
                f"Successfully loaded the current weather report for {n} city/cities.",
                class_="text-success",
            ),
            style="margin-bottom: 0.5rem;",
        )

    @output
    @render.data_frame
    def weather_table():
        res = weather_result.get()
        req(res is not None and res.get("data") is not None)
        return res["data"]


app_ui = make_ui()
app = App(app_ui, server)
