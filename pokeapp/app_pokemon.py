from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import shinyswatch

from api_pokemon import (
    get_generation_species,
    get_pokemon,
    get_pokemon_abilities_table_rows,
    get_pokemon_level_up_moves_table_rows,
    get_pokemon_list,
)
from shiny import reactive, render
from shiny.express import input, ui


PALETTE_RED = "#ff0000"
PALETTE_GREEN = "#00ff00"
PALETTE_BLUE = "#0000ff"
PALETTE_LIGHT = "#eeeeee"
PALETTE_DARK = "#1a1a1a"


# Shown on first load once the discovery list is available (must exist on current page / gen filter).
DEFAULT_DETAIL_POKEMON = "pikachu"
DEFAULT_BATTLE_POKEMON_A = "pikachu"
DEFAULT_BATTLE_POKEMON_B = "squirtle"

TYPE_COLORS = {
    "normal": "#A8A77A",
    "fire": "#EE8130",
    "water": "#6390F0",
    "electric": "#F7D02C",
    "grass": "#7AC74C",
    "ice": "#96D9D6",
    "fighting": "#C22E28",
    "poison": "#A33EA1",
    "ground": "#E2BF65",
    "flying": "#A98FF3",
    "psychic": "#F95587",
    "bug": "#A6B91A",
    "rock": "#B6A136",
    "ghost": "#735797",
    "dragon": "#6F35FC",
    "dark": "#705746",
    "steel": "#B7B7CE",
    "fairy": "#D685AD",
}


def _fig_html(fig: go.Figure, height_px: int = 460) -> ui.HTML:
    fig.update_layout(height=height_px, autosize=True, width=None)
    html = pio.to_html(
        fig,
        include_plotlyjs="cdn",
        full_html=False,
        config={"displayModeBar": True, "displaylogo": False, "responsive": True},
        default_width="100%",
        default_height=f"{height_px}px",
    )
    return ui.HTML(html)


def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=17, color=PALETTE_DARK),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(t=40, b=40),
    )
    return fig


def _chart_layout(fig: go.Figure, title: str) -> None:
    fig.update_layout(
        title=dict(text=title, font=dict(color=PALETTE_DARK, size=19)),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(color=PALETTE_DARK, size=14),
        xaxis=dict(
            gridcolor="rgba(26,26,26,0.12)",
            tickfont=dict(color=PALETTE_DARK, size=13),
        ),
        yaxis=dict(
            gridcolor="rgba(26,26,26,0.12)",
            tickfont=dict(color=PALETTE_DARK, size=13),
        ),
        margin=dict(t=56, b=72),
        legend=dict(font=dict(color=PALETTE_DARK, size=13)),
    )


def _id_from_url(url: str | None) -> int | None:
    if not url:
        return None
    m = re.search(r"/pokemon/(\d+)/?$", str(url).strip())
    return int(m.group(1)) if m else None


def _species_id_from_url(url: str | None) -> int | None:
    """National Dex / sprite index: use species id from pokemon-species URL (matches defaults in most cases)."""
    if not url:
        return None
    m = re.search(r"/pokemon-species/(\d+)/?$", str(url).strip())
    return int(m.group(1)) if m else None


def _sorted_results_by_id(results: list[dict], *, kind: str) -> list[dict]:
    """Sort API result rows by resource id from URL (ascending); missing ids last."""

    def _key(r: dict) -> tuple:
        url = r.get("url")
        i = _species_id_from_url(url) if kind == "species" else _id_from_url(url)
        return (i is None, i if i is not None else -1)

    return sorted(results or [], key=_key)


def _sprite_url_from_id(pid: int) -> str:
    """Front sprite URL (list endpoint has no sprites; ID comes from resource URL)."""
    return (
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
        f"{int(pid)}.png"
    )


def _badge(text: str, bg: str) -> ui.Tag:
    return ui.tags.span(
        text,
        class_="type-badge",
        style=f"background-color: {bg};",
    )


def _pokemon_sprite_card_ui(pokemon: dict[str, Any], *, title_tag: str = "h3") -> ui.Tag:
    """Details + Battle tab: name, #id, type badges, official art / sprite (GET /pokemon payload)."""
    name = (pokemon.get("name") or "—").title()
    pid = pokemon.get("id") or "—"
    sprites = pokemon.get("sprites") or {}
    img = sprites.get("official_artwork_front_default") or sprites.get("front_default")
    types = [t.get("name") for t in (pokemon.get("types") or []) if t.get("name")]
    badges = [_badge(t.title(), TYPE_COLORS.get(t, PALETTE_LIGHT)) for t in types]
    H = getattr(ui.tags, title_tag, ui.tags.h3)
    title_el = H(f"{name}  #{pid}", class_="mb-2")
    return ui.div(
        title_el,
        ui.div(*badges, class_="mb-3 d-flex justify-content-center flex-wrap gap-1"),
        ui.tags.div(
            ui.tags.img(src=img, alt=name) if img else ui.p("No sprite available.", class_="text-muted"),
            class_="sprite-panel",
        ),
        class_="detail-pokemon-card",
    )


ui.page_opts(
    title="Pokédex — Explorer",
    fillable=False,
    full_width=True,
    theme=shinyswatch.theme.flatly,
)

ui.tags.style(
    """
    /* App-wide larger type (~19px base on typical 16px browsers) */
    html {
        font-size: 118.75%;
    }
    body {
        font-size: 1rem;
    }
    .bslib-page-main .small,
    .bslib-sidebar .small,
    .sidebar .small {
        font-size: 1rem !important;
    }
    .bslib-page-main pre,
    .bslib-page-main .shiny-text-output {
        font-size: 1rem !important;
    }
    .bslib-page-main .shiny-data-grid,
    .bslib-page-main .shiny-data-grid table {
        font-size: 1rem !important;
    }
    .selectize-input,
    .selectize-dropdown {
        font-size: 1rem !important;
    }
    body { background-color: #f5f5f5 !important; }
    .bslib-page-main {
        overflow-x: auto;
        overflow-y: visible;
        padding: 0.75rem 1rem 2.5rem;
        background-color: #f5f5f5 !important;
    }
    .bslib-sidebar, .sidebar { background-color: #ececec !important; }
    .bslib-card {
        overflow: visible !important;
        min-height: unset !important;
        background-color: #ffffff !important;
        border: 1px solid #e3e3e3 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .nav-underline .nav-link {
        color: #555555 !important;
        font-weight: 500;
        font-size: 1.05rem;
    }
    .nav-underline .nav-link.active {
        color: #1a1a1a !important;
        border-bottom-color: #ff0000 !important;
        border-bottom-width: 3px !important;
        font-weight: 600;
    }
    .bslib-sidebar .form-label,
    .bslib-sidebar h5,
    .bslib-page-main h4,
    .bslib-page-main h5,
    .bslib-page-main h6 {
        font-size: 1.1rem;
    }
    .bslib-page-main h1.text-center {
        font-size: clamp(1.75rem, 4vw, 2.25rem);
    }
    .btn-primary { background-color: #ff0000 !important; border-color: #cc0000 !important; }
    .btn-primary:hover { background-color: #cc0000 !important; border-color: #990000 !important; }
    .type-badge {
        display: inline-block;
        padding: 0.25rem 0.55rem;
        border-radius: 999px;
        color: #111111;
        font-weight: 600;
        font-size: 0.95rem;
        margin-right: 0.35rem;
        border: 1px solid rgba(0,0,0,0.10);
    }
    .detail-pokemon-card {
        text-align: center;
    }
    .detail-pokemon-card .sprite-panel {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .battle-pokemon-preview-card {
        border: 1px solid #e3e3e3 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .battle-pokemon-preview-card .sprite-panel img {
        max-width: min(240px, 100%);
    }
    .sprite-panel img {
        image-rendering: pixelated;
        max-width: 280px;
        width: 100%;
        height: auto;
        display: block;
    }
    .poke-explore-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
        gap: 0.85rem;
    }
    .poke-explore-card {
        width: 100%;
        text-align: center;
        border: 1px solid #e0e0e0 !important;
        border-radius: 0.5rem;
        background: #ffffff !important;
        padding: 0.65rem 0.5rem 0.75rem;
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
        cursor: pointer;
    }
    .poke-explore-card:hover {
        border-color: #ff0000 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .poke-explore-card:focus-visible {
        outline: 2px solid #ff0000;
        outline-offset: 2px;
    }
    .poke-explore-card .poke-card-img-wrap {
        min-height: 96px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .poke-explore-card img.poke-card-sprite {
        image-rendering: pixelated;
        max-height: 96px;
        width: auto;
        max-width: 100%;
    }
    /* Abilities DataGrid: auto column widths from content (not equal columns) */
    .abilities-data-grid-wrap {
        overflow-x: auto;
        max-width: 100%;
    }
    .abilities-data-grid-wrap .shiny-data-grid {
        width: auto !important;
        max-width: 100%;
    }
    .abilities-data-grid-wrap .shiny-data-grid table {
        table-layout: auto;
        width: auto;
        max-width: 100%;
    }
    .abilities-data-grid-wrap .shiny-data-grid th,
    .abilities-data-grid-wrap .shiny-data-grid td {
        vertical-align: top;
    }
    .abilities-data-grid-wrap .shiny-data-grid th:nth-child(1),
    .abilities-data-grid-wrap .shiny-data-grid td:nth-child(1) {
        white-space: nowrap;
        width: 1%;
    }
    .abilities-data-grid-wrap .shiny-data-grid th:nth-child(2),
    .abilities-data-grid-wrap .shiny-data-grid td:nth-child(2) {
        white-space: nowrap;
    }
    .abilities-data-grid-wrap .shiny-data-grid th:nth-child(3),
    .abilities-data-grid-wrap .shiny-data-grid td:nth-child(3) {
        white-space: nowrap;
        width: 1%;
    }
    .abilities-data-grid-wrap .shiny-data-grid th:nth-child(4),
    .abilities-data-grid-wrap .shiny-data-grid td:nth-child(4) {
        white-space: normal;
        word-wrap: break-word;
        min-width: 18rem;
    }
    /* Level-up moves table: full width */
    .moves-data-grid-wrap {
        overflow-x: auto;
        max-width: 100%;
    }
    .moves-data-grid-wrap .shiny-data-grid {
        width: 100% !important;
        max-width: 100%;
    }
    .moves-data-grid-wrap .shiny-data-grid table {
        table-layout: auto;
        width: 100%;
    }
    """
)

ui.h1("Pokédex — Discovery + Analysis Dashboard", class_="text-center mb-2")
ui.p(
    "PokeAPI • list endpoint for navigation, detail endpoint for charts and comparisons",
    class_="text-center text-muted mb-3 small",
)


# -----------------------------
# Reactive state
# -----------------------------

offset = reactive.Value(0)
compare_tray = reactive.Value([])  # list[str]
_app_defaults_seeded = reactive.Value(False)


@reactive.extended_task
async def _battle_matchup_extended_task(a: str, b: str) -> str:
    """Runs PokeAPI + LLM work off the reactive thread; UI reads status + result."""
    import asyncio

    from agents_pokemon import run_battle_matchup_safe

    return await asyncio.to_thread(run_battle_matchup_safe, a, b)


@reactive.extended_task
async def _lore_summary_extended_task(name: str) -> str:
    """Lore tab: species fetch + LLM off the reactive thread."""
    import asyncio

    from ai_pokemon import summarize_pokemon_species

    return await asyncio.to_thread(summarize_pokemon_species, name)


with ui.sidebar(open="desktop"):
    ui.h5("🧬 Generation filter")
    ui.input_select(
        "generation_scope",
        "Discovery source",
        {
            "national": "National Pokédex (paginated)",
            "1": "Generation I",
            "2": "Generation II",
            "3": "Generation III",
            "4": "Generation IV",
            "5": "Generation V",
            "6": "Generation VI",
            "7": "Generation VII",
            "8": "Generation VIII",
            "9": "Generation IX",
        },
        selected="national",
    )
    ui.hr()

    ui.h5("🔎 Discover (list / page)")
    ui.input_numeric("page_limit", "Page size", value=50, min=10, max=200, step=10)
    with ui.layout_columns(col_widths=[6, 6], fill=False, fillable=False, class_="g-2"):
        ui.input_action_button("prev_page", "◀ Previous", class_="btn-outline-secondary w-100")
        ui.input_action_button("next_page", "Next ▶", class_="btn-outline-secondary w-100")
    ui.input_action_button("refresh_list", "Refresh list", class_="btn-primary w-100 mt-2")
    ui.hr()

    ui.h5("🎯 Primary control (autocomplete)")
    ui.input_selectize(
        "pokemon_pick",
        "Pokémon",
        choices={"": "Load list using Refresh list"},
        selected="",
        multiple=False,
        options={"placeholder": "Type to search (e.g., 'pi')"},
    )
    ui.input_action_button("add_to_compare", "Add to compare tray", class_="btn-outline-secondary w-100 mt-2")
    ui.hr()

    ui.h5("⭐ Compare tray (optional)")
    ui.input_selectize(
        "compare_pick",
        "Selected Pokémon",
        choices={},
        selected=[],
        multiple=True,
        options={"placeholder": "Pick multiple Pokémon"},
    )
    ui.input_action_button("clear_compare", "Clear tray", class_="btn-outline-secondary w-100")


with ui.navset_underline(id="main_tabs", selected="explore"):
    with ui.nav_panel("🧭 Explore", value="explore"):
        with ui.layout_columns(col_widths=[12], fill=False, fillable=False):
            with ui.card(full_screen=False, fill=False):
                ui.card_header("📋 Pokémon cards (this page)")
                ui.p(
                    "One card per Pokémon on the current page (page size = how many load). "
                    "Click a card to select it and open Details.",
                    class_="text-secondary small mb-2",
                )
                ui.div(
                    ui.input_text("explore_card_click", "", value=""),
                    class_="d-none",
                    **{"aria-hidden": "true"},
                )

                @render.ui
                def explore_pokemon_cards():
                    st = pokemon_list_state()
                    if not st["ok"]:
                        return ui.p(f"Could not load list: {st.get('error')}", class_="text-warning mb-0")
                    df = pokemon_list_df()
                    if df.empty:
                        return ui.p("No Pokémon on this page — try Refresh list.", class_="text-muted mb-0")
                    cards = []
                    for _, row in df.iterrows():
                        name = str(row["Name"])
                        pid = row["ID"]
                        if pid is None or (isinstance(pid, float) and pd.isna(pid)):
                            src = ""
                        else:
                            src = _sprite_url_from_id(int(pid))
                        title = name.replace("-", " ").title()
                        js_name = json.dumps(name)
                        onclick = (
                            f'Shiny.setInputValue("explore_card_click", {js_name}, '
                            '{priority: "event"}); return false;'
                        )
                        cards.append(
                            ui.tags.button(
                                ui.tags.div(f"#{int(pid)}" if pid is not None and not pd.isna(pid) else "—", class_="small text-muted mb-1"),
                                ui.tags.div(title, class_="poke-card-name fw-semibold small mb-2"),
                                ui.tags.div(
                                    ui.tags.img(
                                        src=src,
                                        alt=title,
                                        class_="poke-card-sprite",
                                    )
                                    if src
                                    else ui.span("—", class_="text-muted"),
                                    class_="poke-card-img-wrap",
                                ),
                                type="button",
                                class_="poke-explore-card",
                                onclick=onclick,
                            )
                        )
                    return ui.div(*cards, class_="poke-explore-grid")

                ui.p(
                    "Sprites use the standard repo path from National Dex ID; details still load via /pokemon/{name}.",
                    class_="text-muted small mt-3 mb-0",
                )

    with ui.nav_panel("📊 Details", value="details"):
        with ui.layout_columns(col_widths=[4, 8], fill=False, fillable=False, class_="g-3"):
            with ui.card(full_screen=False, fill=False):
                ui.card_header("🖼️ Pokémon")

                @render.ui
                def sprite_panel():
                    d = pokemon_detail()
                    if not d["ok"]:
                        return ui.p(d.get("error") or "Pick a Pokémon.", class_="text-muted mb-0")
                    return _pokemon_sprite_card_ui(d["pokemon"], title_tag="h3")

            with ui.card(full_screen=False, fill=False):
                ui.card_header("📊 Analysis + visualization (GET /pokemon/{name})")

                with ui.navset_tab(id="detail_tabs", selected="stats"):
                    with ui.nav_panel("Stats", value="stats"):
                        with ui.layout_columns(
                            col_widths=[6, 6],
                            fill=False,
                            fillable=False,
                            class_="g-3 align-items-start",
                        ):
                            @render.ui
                            def stats_bar():
                                d = pokemon_detail()
                                if not d["ok"]:
                                    return _fig_html(_empty_fig(d.get("error") or "Pick a Pokémon."), height_px=380)
                                fig = _stats_bar_fig(d["pokemon"])
                                return _fig_html(fig, height_px=420)

                            @render.ui
                            def stats_radar():
                                d = pokemon_detail()
                                if not d["ok"]:
                                    return _fig_html(_empty_fig(d.get("error") or "Pick a Pokémon."), height_px=380)
                                fig = _stats_radar_fig(d["pokemon"])
                                return _fig_html(fig, height_px=420)

                    with ui.nav_panel("Abilities", value="abilities"):
                        @render.ui
                        def abilities_notice():
                            d = pokemon_detail()
                            if not d["ok"]:
                                return ui.p(d.get("error") or "Pick a Pokémon.", class_="text-warning mb-2")
                            if not d["pokemon"].get("abilities"):
                                return ui.p("No abilities in payload.", class_="text-muted mb-2")
                            return ui.div(class_="d-none")

                        ui.p(
                            "Descriptions use GET /ability/{name} → effect_entries (English): "
                            "brief text prefers short_effect, then full effect.",
                            class_="text-secondary small mb-2",
                        )

                        with ui.div(class_="abilities-data-grid-wrap"):
                            @render.data_frame
                            def abilities_table():
                                d = pokemon_detail()
                                cols = ["No.", "Ability", "Hidden", "Description (EN)"]
                                empty = pd.DataFrame(columns=cols)
                                if not d["ok"]:
                                    return render.DataGrid(empty, width="fit-content", filters=False)
                                rows = get_pokemon_abilities_table_rows(d["pokemon"])
                                if not rows:
                                    return render.DataGrid(empty, width="fit-content", filters=False)
                                df = pd.DataFrame(rows)[cols]
                                return render.DataGrid(df, width="fit-content", filters=False)

                    with ui.nav_panel("Moves", value="moves"):
                        @render.ui
                        def moves_notice():
                            d = pokemon_detail()
                            if not d["ok"]:
                                return ui.p(d.get("error") or "Pick a Pokémon.", class_="text-warning mb-2")
                            return ui.div(class_="d-none")

                        ui.p(
                            "Level-up learnset only (move_learn_method = level-up). "
                            "Levels come from GET /pokemon/{name}; type, category, power, and accuracy from "
                            "GET /move/{name}.",
                            class_="text-secondary small mb-2",
                        )

                        with ui.div(class_="moves-data-grid-wrap"):
                            @render.data_frame
                            def moves_level_up_table():
                                d = pokemon_detail()
                                cols = ["Level", "Move", "Type", "Category", "Power", "Accuracy"]
                                empty = pd.DataFrame(columns=cols)
                                if not d["ok"]:
                                    return render.DataGrid(empty, width="100%", filters=False)
                                name = d["pokemon"].get("name")
                                if not name:
                                    return render.DataGrid(empty, width="100%", filters=False)
                                try:
                                    rows = get_pokemon_level_up_moves_table_rows(name)
                                except Exception as exc:
                                    return render.DataGrid(
                                        pd.DataFrame(
                                            [
                                                {
                                                    "Level": None,
                                                    "Move": f"Error loading moves: {exc}",
                                                    "Type": None,
                                                    "Category": None,
                                                    "Power": None,
                                                    "Accuracy": None,
                                                }
                                            ]
                                        ),
                                        width="100%",
                                        filters=False,
                                    )
                                if not rows:
                                    return render.DataGrid(empty, width="100%", filters=False)
                                df = pd.DataFrame(rows)[cols]
                                return render.DataGrid(df, width="100%", filters=False)

                    with ui.nav_panel("Lore", value="lore"):
                        ui.p(
                            "Text is grounded in GET /pokemon-species/{name} (Pokédex flavor text, habitat, evolution). "
                            "Battle stats stay on the Stats tab (GET /pokemon/{name}).",
                            class_="text-secondary small mb-2",
                        )
                        ui.input_action_button(
                            "ai_pokemon_summary_btn",
                            "Generate summary",
                            class_="btn-outline-secondary btn-sm mb-2",
                        )

                        @render.ui
                        def pokemon_ai_summary_panel():
                            if input.ai_pokemon_summary_btn() == 0:
                                return ui.p(
                                    "Click Generate summary after selecting a Pokémon. Uses Ollama.",
                                    class_="text-muted small mb-0",
                                )
                            nm = active_pokemon_name()
                            if not nm:
                                return ui.p("Select a Pokémon first.", class_="text-warning small mb-0")
                            st = _lore_summary_extended_task.status()
                            if st == "initial":
                                return ui.div(
                                    ui.span(
                                        class_="spinner-border spinner-border-sm text-primary",
                                        role="status",
                                    ),
                                    ui.span(" Starting…", class_="ms-2"),
                                    class_="d-flex align-items-center p-3 border rounded bg-light small text-muted",
                                )
                            if st == "running":
                                return ui.div(
                                    ui.span(class_="spinner-border text-primary", role="status"),
                                    ui.div(
                                        ui.p("Generating lore summary…", class_="mb-1 fw-semibold small"),
                                        ui.p(
                                            "Loading species / evolution from PokeAPI, then the AI.",
                                            class_="mb-0 small text-muted",
                                        ),
                                        class_="ms-2",
                                    ),
                                    class_="d-flex align-items-start p-3 border rounded bg-light",
                                )
                            if st == "error":
                                err = _lore_summary_extended_task.error.get()
                                return ui.p(
                                    f"Lore summary failed: {err}",
                                    class_="text-danger small mb-0",
                                )
                            if st == "success":
                                txt = _lore_summary_extended_task.value.get()
                                return ui.pre(
                                    txt,
                                    class_="small bg-light p-3 border rounded mb-0",
                                    style="white-space: pre-wrap; word-break: break-word;",
                                )
                            return ui.p("Cancelled.", class_="text-muted small mb-0")

    with ui.nav_panel("⚔️ Battle", value="battle"):
        with ui.layout_columns(col_widths=[12], fill=False, fillable=False):
            with ui.layout_columns(col_widths=[6, 6], fill=False, fillable=False, class_="g-2 mb-2"):
                ui.input_selectize(
                    "battle_pokemon_a",
                    "Pokémon A",
                    choices={"": "—"},
                    selected="",
                    multiple=False,
                    options={"placeholder": "e.g. pikachu"},
                )
                ui.input_selectize(
                    "battle_pokemon_b",
                    "Pokémon B",
                    choices={"": "—"},
                    selected="",
                    multiple=False,
                    options={"placeholder": "e.g. squirtle"},
                )
            ui.input_action_button(
                "battle_fill_tray_btn",
                "Use first two in compare tray",
                class_="btn-outline-secondary w-100 mb-3",
            )

            ui.h6("Pokémon preview", class_="mb-2")
            ui.p(
                "Same card layout as Details (GET /pokemon/{name}: types + artwork).",
                class_="text-secondary small mb-2",
            )
            with ui.layout_columns(
                col_widths=[6, 6],
                fill=False,
                fillable=False,
                class_="g-3 align-items-stretch mb-3",
            ):
                @render.ui
                def battle_pokemon_card_a():
                    slot = battle_slot_pokemon()
                    a = (input.battle_pokemon_a() or "").strip().lower()
                    if not a:
                        return ui.p(
                            "Choose Pokémon A above.",
                            class_="text-muted small border rounded p-3 mb-0 bg-white",
                        )
                    if slot.get("err_a"):
                        return ui.p(
                            f"Could not load Pokémon A: {slot['err_a']}",
                            class_="text-warning small border rounded p-3 mb-0",
                        )
                    if slot.get("a"):
                        return ui.div(
                            ui.p("Pokémon A", class_="small text-muted fw-semibold mb-2"),
                            _pokemon_sprite_card_ui(slot["a"], title_tag="h4"),
                            class_="battle-pokemon-preview-card rounded p-3 bg-white h-100",
                        )
                    return ui.p("—", class_="text-muted small")

                @render.ui
                def battle_pokemon_card_b():
                    slot = battle_slot_pokemon()
                    b = (input.battle_pokemon_b() or "").strip().lower()
                    if not b:
                        return ui.p(
                            "Choose Pokémon B above.",
                            class_="text-muted small border rounded p-3 mb-0 bg-white",
                        )
                    if slot.get("err_b"):
                        return ui.p(
                            f"Could not load Pokémon B: {slot['err_b']}",
                            class_="text-warning small border rounded p-3 mb-0",
                        )
                    if slot.get("b"):
                        return ui.div(
                            ui.p("Pokémon B", class_="small text-muted fw-semibold mb-2"),
                            _pokemon_sprite_card_ui(slot["b"], title_tag="h4"),
                            class_="battle-pokemon-preview-card rounded p-3 bg-white h-100",
                        )
                    return ui.p("—", class_="text-muted small")

            ui.h5("Stat comparison", class_="mb-2")
            ui.p(
                "Grouped bars and overlaid radar for Pokémon A vs B (GET /pokemon/{name} base stats).",
                class_="text-secondary small mb-2",
            )
            with ui.layout_columns(
                col_widths=[6, 6],
                fill=False,
                fillable=False,
                class_="g-3 align-items-stretch mb-3",
            ):
                @render.ui
                def battle_compare_bar():
                    d = battle_compare_pokes()
                    if not d["ok"]:
                        return _fig_html(_empty_fig(d.get("error") or "—"), height_px=400)
                    fig = _compare_bar_fig_from_pokes(d["pokes"] or [])
                    return _fig_html(fig, height_px=460)

                @render.ui
                def battle_compare_radar():
                    d = battle_compare_pokes()
                    if not d["ok"]:
                        return _fig_html(_empty_fig(d.get("error") or "—"), height_px=400)
                    fig = _compare_radar_fig_from_pokes(d["pokes"] or [])
                    return _fig_html(fig, height_px=460)

            with ui.card(full_screen=False, fill=False):
                ui.card_header("Battle matchup summary (multi-agent AI)")
                ui.p(
                    "Agent 1 retrieves stats, types, abilities, and level-up moves from PokeAPI (tools). "
                    "Agents 2–3 analyze and narrate using only that data (RAG). "
                    "Retrieval is parallelized and moves are capped for speed; set BATTLE_TWO_LLM_CALLS=1 "
                    "for two separate model calls (slower). "
                    "Configure Ollama (see .env.example).",
                    class_="text-secondary small mb-2",
                )
                ui.input_action_button(
                    "battle_matchup_btn",
                    "Generate battle matchup summary",
                    class_="btn-primary mb-3",
                )

                @render.ui
                def battle_matchup_summary_panel():
                    if input.battle_matchup_btn() == 0:
                        return ui.p(
                            "Pick two Pokémon and click Generate. Optional: add Pokémon to the compare tray, "
                            "then “Use first two in compare tray” to fill A and B.",
                            class_="text-muted small mb-0",
                        )
                    st = _battle_matchup_extended_task.status()
                    if st == "initial":
                        return ui.div(
                            ui.span(class_="spinner-border spinner-border-sm text-primary", role="status"),
                            ui.span(" Starting…", class_="ms-2"),
                            class_="d-flex align-items-center p-3 border rounded bg-light small text-muted",
                        )
                    if st == "running":
                        return ui.div(
                            ui.span(class_="spinner-border text-primary", role="status"),
                            ui.div(
                                ui.p("Running battle matchup…", class_="mb-1 fw-semibold small"),
                                ui.p(
                                    "Fetching PokéAPI data (stats, abilities, moves), then generating the summary.",
                                    class_="mb-0 small text-muted",
                                ),
                                class_="ms-2",
                            ),
                            class_="d-flex align-items-start p-3 border rounded bg-light",
                        )
                    if st == "error":
                        err = _battle_matchup_extended_task.error.get()
                        return ui.p(
                            f"Battle matchup failed: {err}",
                            class_="text-danger small mb-0",
                        )
                    if st == "success":
                        txt = _battle_matchup_extended_task.value.get()
                        return ui.pre(
                            txt,
                            class_="small bg-light p-3 border rounded mb-0",
                            style="white-space: pre-wrap; word-break: break-word;",
                        )
                    return ui.p("Cancelled.", class_="text-muted small mb-0")

    with ui.nav_panel("ℹ️ About", value="about"):
        ui.h4("Using this app", class_="mb-3")
        ui.p(
            "Browse and compare Pokémon in one place. In the sidebar, pick whether you are looking at "
            "the full national Pokédex (with page size and Previous/Next) or one game generation at a time, "
            "then use Refresh list if you change filters. Choose a Pokémon from the dropdown or from the "
            "Explore cards to open its full profile.",
            class_="text-secondary mb-4",
        )

        ui.h5("Explore", class_="fw-semibold mb-2")
        ui.p(
            "Skim the Pokémon on your current page as clickable cards with artwork. Use this to discover "
            "who is on this page; clicking a card selects that Pokémon and opens Details so you can dig in.",
            class_="text-secondary small mb-3",
        )

        ui.h5("Details", class_="fw-semibold mb-2")
        ui.p(
            "See the big picture for one Pokémon: picture, number, and types on the left. On the right, "
            "switch between Stats charts, a readable abilities table, level-up moves, and Lore. "
            "Use Generate summary on Lore when you want an AI-written Pokédex-style blurb (optional; "
            "needs a local model or an API key set up in your environment).",
            class_="text-secondary small mb-3",
        )

        ui.h5("Battle", class_="fw-semibold mb-2")
        ui.p(
            "Pick two Pokémon to compare side by side: preview cards, bar and radar stat charts, then "
            "Generate battle matchup summary for a written strengths-and-weaknesses style report. "
            "Defaults appear the first time the list loads so you can try it right away; use the compare "
            "tray button if you already queued Pokémon elsewhere.",
            class_="text-secondary small mb-0",
        )


# -----------------------------
# Data + calculations
# -----------------------------


@reactive.calc
def _generation_species_catalog() -> dict[str, Any]:
    """Fetch /generation/{id} once per refresh or generation change (not on every page turn)."""
    input.refresh_list()
    input.generation_scope()
    scope = str(input.generation_scope() or "national")
    if scope == "national":
        return {"kind": "national", "ok": True, "error": None}
    try:
        gen = get_generation_species(scope)
        full = _sorted_results_by_id(gen.get("results") or [], kind="species")
        return {
            "kind": "generation",
            "ok": True,
            "error": None,
            "full_results": full,
            "count": int(gen.get("count") or len(full)),
            "generation_name": gen.get("generation_name"),
            "main_region": gen.get("main_region"),
        }
    except Exception as e:
        return {
            "kind": "generation",
            "ok": False,
            "error": str(e),
            "full_results": [],
            "count": 0,
            "generation_name": None,
            "main_region": None,
        }


@reactive.calc
def pokemon_list_state() -> dict[str, Any]:
    lim = int(input.page_limit())
    off = int(offset())
    scope = str(input.generation_scope() or "national")
    cat = _generation_species_catalog()
    try:
        if scope == "national":
            payload = get_pokemon_list(limit=lim, offset=off)
            page = _sorted_results_by_id(payload.get("results") or [], kind="pokemon")
            return {
                "ok": True,
                "mode": "national",
                "count": payload.get("count"),
                "next": payload.get("next"),
                "previous": payload.get("previous"),
                "results": page,
                "generation_name": None,
                "error": None,
            }
        if not cat.get("ok"):
            return {
                "ok": False,
                "mode": "generation",
                "count": None,
                "next": None,
                "previous": None,
                "results": [],
                "generation_name": cat.get("generation_name"),
                "error": cat.get("error"),
            }
        full = cat.get("full_results") or []
        total = int(cat.get("count") or len(full))
        max_start = max(0, total - lim)
        start = min(off, max_start)
        page = full[start : start + lim]
        return {
            "ok": True,
            "mode": "generation",
            "count": total,
            "next": None,
            "previous": None,
            "results": page,
            "generation_name": cat.get("generation_name"),
            "main_region": cat.get("main_region"),
            "error": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "mode": None,
            "count": None,
            "next": None,
            "previous": None,
            "results": [],
            "generation_name": None,
            "error": str(e),
        }


@reactive.calc
def pokemon_list_df() -> pd.DataFrame:
    st = pokemon_list_state()
    if not st["ok"]:
        return pd.DataFrame(columns=["Name", "ID", "URL"])
    mode = st.get("mode") or "national"
    rows = []
    for r in st["results"]:
        url = r.get("url")
        sid = _species_id_from_url(url) if mode == "generation" else _id_from_url(url)
        rows.append(
            {
                "Name": (r.get("name") or "—"),
                "ID": sid,
                "URL": url,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Name"] = df["Name"].astype(str)
        df = df.sort_values("ID", na_position="last", kind="stable")
    return df


@reactive.calc
def active_pokemon_name() -> str | None:
    nm = (input.pokemon_pick() or "").strip().lower()
    return nm or None


@reactive.calc
def pokemon_detail() -> dict[str, Any]:
    name = active_pokemon_name()
    if not name:
        return {"ok": False, "pokemon": None, "error": "Choose a Pokémon from the sidebar or Explore cards."}
    try:
        p = get_pokemon(name)
        return {"ok": True, "pokemon": p, "error": None}
    except Exception as e:
        return {"ok": False, "pokemon": None, "error": str(e)}


@reactive.calc
def battle_compare_pokes() -> dict[str, Any]:
    """Two Pokémon payloads for Battle tab stat charts (GET /pokemon/{name})."""
    a = (input.battle_pokemon_a() or "").strip().lower()
    b = (input.battle_pokemon_b() or "").strip().lower()
    if not a or not b:
        return {"ok": False, "pokes": None, "error": "Select Pokémon A and B to compare stats."}
    if a == b:
        return {"ok": False, "pokes": None, "error": "Choose two different Pokémon to compare stats."}
    try:
        return {"ok": True, "pokes": [get_pokemon(a), get_pokemon(b)], "error": None}
    except Exception as e:
        return {"ok": False, "pokes": None, "error": str(e)}


@reactive.calc
def battle_slot_pokemon() -> dict[str, Any]:
    """Per-slot GET /pokemon payloads for Battle tab preview cards (independent of compare charts)."""
    a = (input.battle_pokemon_a() or "").strip().lower()
    b = (input.battle_pokemon_b() or "").strip().lower()
    out: dict[str, Any] = {"a": None, "b": None, "err_a": None, "err_b": None}
    if a:
        try:
            out["a"] = get_pokemon(a)
        except Exception as e:
            out["err_a"] = str(e)
    if b:
        try:
            out["b"] = get_pokemon(b)
        except Exception as e:
            out["err_b"] = str(e)
    return out


def _stats_frame(pokemon: dict) -> pd.DataFrame:
    stats = pokemon.get("stats") or []
    rows = []
    for s in stats:
        rows.append({"stat": s.get("name"), "value": s.get("base_stat")})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["stat", "value"])
    order = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
    df["stat"] = df["stat"].astype(str)
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0).astype(int)
    df["stat"] = pd.Categorical(df["stat"], categories=order, ordered=True)
    return df.sort_values("stat")


def _stats_bar_fig(pokemon: dict) -> go.Figure:
    df = _stats_frame(pokemon)
    if df.empty:
        return _empty_fig("No stats in payload.")
    fig = go.Figure(
        data=[
            go.Bar(
                x=[str(s).replace("-", " ").title() for s in df["stat"].astype(str).tolist()],
                y=df["value"].tolist(),
                marker_color=PALETTE_RED,
                hovertemplate="%{x}: %{y}<extra></extra>",
            )
        ]
    )
    _chart_layout(fig, "Base stats (bar)")
    fig.update_layout(xaxis_title="", yaxis_title="Base stat", margin=dict(t=60, b=80))
    return fig


def _stats_radar_fig(pokemon: dict) -> go.Figure:
    df = _stats_frame(pokemon)
    if df.empty:
        return _empty_fig("No stats in payload.")
    labels = [str(s).replace("-", " ").title() for s in df["stat"].astype(str).tolist()]
    values = df["value"].tolist()
    # Close the loop
    labels2 = labels + [labels[0]]
    values2 = values + [values[0]]
    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values2,
                theta=labels2,
                fill="toself",
                name=(pokemon.get("name") or "pokemon").title(),
                line=dict(color=PALETTE_BLUE),
            )
        ]
    )
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, gridcolor="rgba(26,26,26,0.12)"),
            angularaxis=dict(gridcolor="rgba(26,26,26,0.12)"),
        ),
        showlegend=False,
    )
    _chart_layout(fig, "Base stats (radar)")
    return fig


def _compare_bar_fig_from_pokes(pokes: list[dict]) -> go.Figure:
    order = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
    fig = go.Figure()
    for p in pokes:
        df = _stats_frame(p)
        if df.empty:
            continue
        df = df.set_index("stat").reindex(order).reset_index()
        df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0).astype(int)
        fig.add_trace(
            go.Bar(
                name=(p.get("name") or "—").title(),
                x=[s.replace("-", " ").title() for s in df["stat"].astype(str).tolist()],
                y=df["value"].tolist(),
            )
        )
    _chart_layout(fig, "Compare stats (grouped bars)")
    fig.update_layout(barmode="group", yaxis_title="Base stat")
    return fig


def _compare_radar_fig_from_pokes(pokes: list[dict]) -> go.Figure:
    order = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
    fig = go.Figure()
    for p in pokes:
        df = _stats_frame(p)
        if df.empty:
            continue
        df = df.set_index("stat").reindex(order).reset_index()
        df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0).astype(int)
        labels = [s.replace("-", " ").title() for s in df["stat"].astype(str).tolist()]
        values = df["value"].tolist()
        labels2 = labels + [labels[0]]
        values2 = values + [values[0]]
        fig.add_trace(
            go.Scatterpolar(
                r=values2,
                theta=labels2,
                fill="toself",
                name=(p.get("name") or "—").title(),
                opacity=0.45,
            )
        )
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, gridcolor="rgba(26,26,26,0.12)"),
            angularaxis=dict(gridcolor="rgba(26,26,26,0.12)"),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    _chart_layout(fig, "Compare stats (overlaid radar)")
    return fig


# -----------------------------
# Effects (sync UI + state)
# -----------------------------


@reactive.effect
@reactive.event(input.next_page)
def _():
    lim = int(input.page_limit())
    cur = int(offset())
    scope = str(input.generation_scope() or "national")
    if scope == "national":
        offset.set(cur + lim)
        return
    st = pokemon_list_state()
    if not st.get("ok"):
        return
    total = int(st.get("count") or 0)
    max_start = max(0, total - lim)
    offset.set(min(cur + lim, max_start))


@reactive.effect
@reactive.event(input.prev_page)
def _():
    lim = int(input.page_limit())
    offset.set(max(0, int(offset()) - lim))


@reactive.effect
@reactive.event(input.generation_scope)
def _reset_offset_on_generation_change():
    offset.set(0)


@reactive.effect(priority=5)
def _sync_dropdown_choices():
    st = pokemon_list_state()
    if not st["ok"] or not st["results"]:
        ui.update_selectize("pokemon_pick", choices={"": "Load list using Refresh list"}, selected="")
        ui.update_selectize("compare_pick", choices={}, selected=list(compare_tray()))
        ui.update_selectize("battle_pokemon_a", choices={"": "—"}, selected="")
        ui.update_selectize("battle_pokemon_b", choices={"": "—"}, selected="")
        return
    choices = {"": "—"} | {r["name"]: (r["name"] or "—").title() for r in st["results"] if r.get("name")}
    with reactive.isolate():
        cur = input.pokemon_pick()
        comp = list(compare_tray())
        ba = input.battle_pokemon_a()
        bb = input.battle_pokemon_b()
    ui.update_selectize("pokemon_pick", choices=choices, selected=cur if cur in choices else "")
    ui.update_selectize("compare_pick", choices=choices, selected=[c for c in comp if c in choices])
    ui.update_selectize("battle_pokemon_a", choices=choices, selected=ba if ba in choices else "")
    ui.update_selectize("battle_pokemon_b", choices=choices, selected=bb if bb in choices else "")


@reactive.effect(priority=4)
def _seed_app_default_pokemon():
    """First time the discovery list is ready: set Details + Battle dropdowns to defaults."""
    if _app_defaults_seeded():
        return
    st = pokemon_list_state()
    if not st.get("ok") or not st.get("results"):
        return
    names = [r["name"] for r in st["results"] if r.get("name")]
    if not names:
        return
    valid = set(names)
    choices = {"": "—"} | {r["name"]: (r["name"] or "—").title() for r in st["results"] if r.get("name")}
    with reactive.isolate():
        cur = (input.pokemon_pick() or "").strip().lower()
        ba = (input.battle_pokemon_a() or "").strip().lower()
        bb = (input.battle_pokemon_b() or "").strip().lower()
    if cur or ba or bb:
        _app_defaults_seeded.set(True)
        return
    sorted_names = sorted(valid)
    pick = DEFAULT_DETAIL_POKEMON if DEFAULT_DETAIL_POKEMON in valid else sorted_names[0]
    ba = DEFAULT_BATTLE_POKEMON_A if DEFAULT_BATTLE_POKEMON_A in valid else sorted_names[0]
    bb = DEFAULT_BATTLE_POKEMON_B if DEFAULT_BATTLE_POKEMON_B in valid else sorted_names[-1]
    if ba == bb:
        for n in sorted_names:
            if n != ba:
                bb = n
                break
    ui.update_selectize("pokemon_pick", choices=choices, selected=pick)
    ui.update_selectize("battle_pokemon_a", choices=choices, selected=ba)
    ui.update_selectize("battle_pokemon_b", choices=choices, selected=bb)
    _app_defaults_seeded.set(True)


@reactive.effect
@reactive.event(input.add_to_compare)
def _():
    nm = (active_pokemon_name() or "").strip().lower()
    if not nm:
        ui.notification_show("Pick a Pokémon first.", type="warning", duration=2)
        return
    tray = list(compare_tray())
    if nm not in tray:
        tray.append(nm)
        compare_tray.set(tray)
        ui.update_selectize("compare_pick", selected=tray)


@reactive.effect
@reactive.event(input.clear_compare)
def _():
    compare_tray.set([])
    ui.update_selectize("compare_pick", selected=[])


@reactive.effect(priority=10)
@reactive.event(input.battle_matchup_btn)
def _battle_matchup_launch():
    n = int(input.battle_matchup_btn() or 0)
    if n == 0:
        return
    a = (input.battle_pokemon_a() or "").strip().lower()
    b = (input.battle_pokemon_b() or "").strip().lower()
    _battle_matchup_extended_task.invoke(a, b)


@reactive.effect(priority=10)
@reactive.event(input.ai_pokemon_summary_btn)
def _lore_summary_launch():
    n = int(input.ai_pokemon_summary_btn() or 0)
    if n == 0:
        return
    nm = active_pokemon_name()
    if not nm:
        return
    _lore_summary_extended_task.invoke(nm)


@reactive.effect
@reactive.event(input.battle_fill_tray_btn)
def _fill_battle_from_compare_tray():
    tray = list(compare_tray())
    if len(tray) < 2:
        ui.notification_show("Add at least two Pokémon to the compare tray first.", type="warning", duration=3)
        return
    ui.update_selectize("battle_pokemon_a", selected=tray[0])
    ui.update_selectize("battle_pokemon_b", selected=tray[1])


@reactive.effect
def _sync_tray_from_input():
    # Allow manual edits to compare tray via the multi-select input
    try:
        cur = input.compare_pick()
    except Exception:
        return
    if cur is None:
        cur = []
    compare_tray.set(list(cur))


@reactive.effect
@reactive.event(input.explore_card_click)
def _open_details_from_explore_card():
    raw = (input.explore_card_click() or "").strip()
    if not raw:
        return
    key = raw.strip().lower()
    df = pokemon_list_df()
    valid = set(df["Name"].str.lower()) if not df.empty else set()
    if valid and key not in valid:
        ui.update_text("explore_card_click", value="")
        return
    ui.update_selectize("pokemon_pick", selected=key)
    ui.update_navset("main_tabs", selected="details")
    ui.update_text("explore_card_click", value="")

