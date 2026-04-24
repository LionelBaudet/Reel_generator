"""
reelgen/reelgen.py — Reflex UI for the Reel Generator.
Dark SaaS layout: sidebar nav + main content area.
"""
from __future__ import annotations

import reflex as rx
from reelgen.state import AppState

# ── Design tokens ──────────────────────────────────────────────────────────────

BG      = "#0A0A0F"
CARD    = "#13131F"
BORDER  = "#1E1E2E"
ACCENT  = "#7C3AED"
ACCENT2 = "#A78BFA"
TEXT    = "#F2F0EA"
MUTED   = "#6B7280"
GREEN   = "#10B981"
ORANGE  = "#F59E0B"
RED     = "#EF4444"

SCENE_COLORS = {
    "Hook":     "#EF4444",
    "Tension":  "#F97316",
    "Shift":    "#EAB308",
    "Proof":    "#A78BFA",
    "Solution": "#10B981",
    "Résultat": "#3B82F6",
    "CTA":      "#8B5CF6",
}


# ── Shared primitives ──────────────────────────────────────────────────────────

def card(*children, **props) -> rx.Component:
    return rx.box(
        *children,
        background=CARD,
        border=f"1px solid {BORDER}",
        border_radius="12px",
        padding="1.5rem",
        **props,
    )


def label(text: str, color: str = MUTED) -> rx.Component:
    return rx.text(text, font_size="0.7rem", font_weight="600",
                   color=color, text_transform="uppercase", letter_spacing="0.08em")


def score_pill(value: rx.Var, max_val: int = 10, color: str = GREEN) -> rx.Component:
    return rx.box(
        rx.text(f"{value}/{max_val}", font_size="0.85rem", font_weight="800", color=color),
        background=f"{color}15",
        border_radius="20px",
        padding="2px 10px",
    )


# ── Sidebar ────────────────────────────────────────────────────────────────────

def nav_item(icon: str, label_text: str, page: str) -> rx.Component:
    is_active = AppState.page == page
    return rx.box(
        rx.hstack(
            rx.text(icon, font_size="1.1rem"),
            rx.text(label_text, font_size="0.88rem", font_weight="600"),
            spacing="3",
            align="center",
        ),
        padding="0.65rem 1rem",
        border_radius="8px",
        cursor="pointer",
        background=rx.cond(is_active, f"{ACCENT}22", "transparent"),
        color=rx.cond(is_active, ACCENT2, MUTED),
        border_left=rx.cond(is_active, f"3px solid {ACCENT}", "3px solid transparent"),
        on_click=AppState.nav(page),
        _hover={"background": f"{ACCENT}15", "color": TEXT},
        transition="all 0.15s ease",
        width="100%",
    )


def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Logo
            rx.box(
                rx.hstack(
                    rx.text("🎬", font_size="1.4rem"),
                    rx.vstack(
                        rx.text("ReelGen", font_size="1rem", font_weight="800", color=TEXT),
                        rx.text("@ownyourtime.ai", font_size="0.65rem", color=MUTED),
                        spacing="0",
                        align="start",
                    ),
                    spacing="2",
                    align="center",
                ),
                padding="1.25rem 1rem 1.5rem",
            ),
            rx.divider(color=BORDER),
            # Nav
            rx.vstack(
                nav_item("✨", "Générateur", "generator"),
                nav_item("📊", "Résultats", "results"),
                nav_item("🧠", "Mémoire", "stats"),
                spacing="1",
                width="100%",
                padding="0.75rem 0",
            ),
            rx.spacer(),
            # Status badge
            rx.box(
                rx.hstack(
                    rx.box(width="8px", height="8px", border_radius="50%", background=GREEN),
                    rx.text("Pipeline prêt", font_size="0.72rem", color=MUTED),
                    spacing="2",
                    align="center",
                ),
                padding="0 1rem 1.5rem",
            ),
            height="100%",
            spacing="0",
            align="start",
        ),
        width="220px",
        min_height="100vh",
        background=CARD,
        border_right=f"1px solid {BORDER}",
        position="sticky",
        top="0",
        flex_shrink="0",
    )


# ── Generator page ─────────────────────────────────────────────────────────────

def mode_btn(icon: str, text: str, value: str) -> rx.Component:
    is_active = AppState.mode == value
    return rx.box(
        rx.vstack(
            rx.text(icon, font_size="1.3rem"),
            rx.text(text, font_size="0.75rem", font_weight="600"),
            spacing="1",
            align="center",
        ),
        padding="0.75rem 1rem",
        border_radius="10px",
        cursor="pointer",
        border=rx.cond(is_active, f"2px solid {ACCENT}", f"2px solid {BORDER}"),
        background=rx.cond(is_active, f"{ACCENT}18", "transparent"),
        color=rx.cond(is_active, ACCENT2, MUTED),
        on_click=AppState.set_mode(value),
        _hover={"border_color": ACCENT, "color": TEXT},
        transition="all 0.15s",
        flex="1",
        text_align="center",
    )


def generator_page() -> rx.Component:
    return rx.vstack(
        # Header
        rx.vstack(
            rx.heading("Créer un Reel", size="7", color=TEXT),
            rx.text("Pipeline IA complet : trends → hooks → script → caption",
                    color=MUTED, font_size="0.9rem"),
            spacing="1",
            align="start",
        ),

        # Error banner
        rx.cond(
            AppState.error != "",
            rx.box(
                rx.hstack(
                    rx.text("⚠", font_size="1rem"),
                    rx.text(AppState.error, font_size="0.85rem"),
                    spacing="2",
                ),
                background=f"{RED}15",
                border=f"1px solid {RED}40",
                border_radius="8px",
                padding="0.75rem 1rem",
                color=RED,
                width="100%",
            ),
        ),

        # Form card
        card(
            rx.vstack(
                # Topic
                rx.vstack(
                    label("Sujet / Topic"),
                    rx.input(
                        placeholder="Ex: IA et marché du travail, automatisation, salaires…",
                        value=AppState.topic,
                        on_change=AppState.set_topic,
                        background="#0A0A0F",
                        border=f"1px solid {BORDER}",
                        color=TEXT,
                        border_radius="8px",
                        padding="0.65rem 1rem",
                        font_size="0.9rem",
                        _placeholder={"color": MUTED},
                        _focus={"border_color": ACCENT, "outline": "none"},
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                ),

                # Language
                rx.vstack(
                    label("Langue"),
                    rx.hstack(
                        rx.box(
                            rx.text("🇫🇷  Français", font_size="0.85rem", font_weight="600"),
                            padding="0.5rem 1.25rem",
                            border_radius="8px",
                            cursor="pointer",
                            border=rx.cond(AppState.language == "fr",
                                           f"2px solid {ACCENT}", f"2px solid {BORDER}"),
                            background=rx.cond(AppState.language == "fr",
                                               f"{ACCENT}18", "transparent"),
                            color=rx.cond(AppState.language == "fr", ACCENT2, MUTED),
                            on_click=AppState.set_language("fr"),
                        ),
                        rx.box(
                            rx.text("🇬🇧  English", font_size="0.85rem", font_weight="600"),
                            padding="0.5rem 1.25rem",
                            border_radius="8px",
                            cursor="pointer",
                            border=rx.cond(AppState.language == "en",
                                           f"2px solid {ACCENT}", f"2px solid {BORDER}"),
                            background=rx.cond(AppState.language == "en",
                                               f"{ACCENT}18", "transparent"),
                            color=rx.cond(AppState.language == "en", ACCENT2, MUTED),
                            on_click=AppState.set_language("en"),
                        ),
                        spacing="3",
                    ),
                    spacing="2",
                ),

                # Mode
                rx.vstack(
                    label("Mode pipeline"),
                    rx.hstack(
                        mode_btn("🔀", "Trend", "trend"),
                        mode_btn("📱", "Social", "social"),
                        mode_btn("📰", "News", "news"),
                        mode_btn("⚡", "Standard", "standard"),
                        spacing="2",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                ),

                spacing="5",
                width="100%",
            ),
            width="100%",
        ),

        # Generate button
        rx.button(
            rx.cond(
                AppState.loading,
                rx.hstack(
                    rx.spinner(size="2", color="white"),
                    rx.text("Génération en cours…", font_weight="700"),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.text("✨", font_size="1.1rem"),
                    rx.text("Générer le Reel", font_weight="700", font_size="1rem"),
                    spacing="2",
                    align="center",
                ),
            ),
            on_click=AppState.generate,
            disabled=AppState.loading,
            background=rx.cond(AppState.loading, BORDER, ACCENT),
            color="white",
            border_radius="10px",
            padding="0.85rem 2.5rem",
            font_size="1rem",
            cursor=rx.cond(AppState.loading, "not-allowed", "pointer"),
            _hover=rx.cond(AppState.loading, {}, {"background": "#6D28D9"}),
            transition="all 0.15s",
            width="100%",
        ),

        spacing="5",
        width="100%",
        max_width="640px",
    )


# ── Results page ───────────────────────────────────────────────────────────────

def scene_row(label_text: str, value: rx.Var, color: str) -> rx.Component:
    return rx.hstack(
        rx.box(
            rx.text(label_text, font_size="0.72rem", font_weight="700",
                    color=color, text_transform="uppercase"),
            min_width="80px",
        ),
        rx.text(value, font_size="0.9rem", color=TEXT, line_height="1.5"),
        padding="0.5rem 0",
        border_bottom=f"1px solid {BORDER}",
        width="100%",
        align="start",
        spacing="4",
    )


def hook_card(hook: dict) -> rx.Component:
    type_colors = {
        "aggressive": RED,
        "medium":     ORANGE,
        "soft":       ACCENT2,
    }
    color = rx.match(
        hook["type"],
        ("aggressive", RED),
        ("medium", ORANGE),
        ACCENT2,
    )
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    hook["type"],
                    color_scheme=rx.match(
                        hook["type"],
                        ("aggressive", "red"),
                        ("medium", "orange"),
                        "violet",
                    ),
                    variant="soft",
                    radius="full",
                ),
                rx.spacer(),
            ),
            rx.text(
                hook["text"],
                font_size="1rem",
                font_weight="700",
                color=TEXT,
                line_height="1.4",
            ),
            spacing="2",
            align="start",
        ),
        background=CARD,
        border=f"1px solid {BORDER}",
        border_left=rx.match(
            hook["type"],
            ("aggressive", f"4px solid {RED}"),
            ("medium", f"4px solid {ORANGE}"),
            f"4px solid {ACCENT2}",
        ),
        border_radius="0 10px 10px 0",
        padding="1rem",
        width="100%",
    )


def viral_bar(label_text: str, value: rx.Var) -> rx.Component:
    color = rx.cond(value >= 7, GREEN, rx.cond(value >= 5, ORANGE, RED))
    return rx.vstack(
        rx.hstack(
            rx.text(label_text, font_size="0.72rem", color=MUTED),
            rx.spacer(),
            rx.text(rx.cond(value > 0, f"{value}/10", "—"),
                    font_size="0.72rem", font_weight="700", color=color),
        ),
        rx.box(
            rx.box(
                width=rx.cond(value > 0, f"{value * 10}%", "0%"),
                height="4px",
                background=color,
                border_radius="2px",
                transition="width 0.6s ease",
            ),
            background=BORDER,
            border_radius="2px",
            height="4px",
            width="100%",
            overflow="hidden",
        ),
        spacing="1",
        width="100%",
    )


def results_page() -> rx.Component:
    return rx.cond(
        AppState.has_results,
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Résultats", size="7", color=TEXT),
                    rx.text(
                        rx.cond(AppState.run_id != "", f"Run: {AppState.run_id}", ""),
                        color=MUTED, font_size="0.75rem",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.button(
                    "← Nouveau reel",
                    on_click=AppState.reset,
                    background="transparent",
                    color=MUTED,
                    border=f"1px solid {BORDER}",
                    border_radius="8px",
                    padding="0.5rem 1rem",
                    font_size="0.82rem",
                    cursor="pointer",
                    _hover={"color": TEXT, "border_color": MUTED},
                ),
                width="100%",
                align="center",
            ),

            # Best hook
            card(
                rx.vstack(
                    rx.hstack(
                        label("🏆 Meilleur hook"),
                        rx.spacer(),
                        rx.badge("Best", color_scheme="violet", variant="soft"),
                    ),
                    rx.text(
                        AppState.best_hook,
                        font_size="1.25rem",
                        font_weight="800",
                        color=TEXT,
                        line_height="1.4",
                    ),
                    spacing="3",
                    width="100%",
                ),
                border_left=f"4px solid {ACCENT}",
                width="100%",
            ),

            # Hooks grid
            rx.vstack(
                label("3 variantes de hooks"),
                rx.foreach(AppState.hooks, hook_card),
                spacing="3",
                width="100%",
            ),

            # Script
            card(
                rx.vstack(
                    label("📝 Script complet"),
                    rx.divider(color=BORDER, margin="0.5rem 0"),
                    scene_row("Hook",     AppState.script_hook,     "#EF4444"),
                    scene_row("Tension",  AppState.script_tension,  "#F97316"),
                    scene_row("Shift",    AppState.script_shift,    "#EAB308"),
                    scene_row("Proof",    AppState.script_proof,    "#A78BFA"),
                    scene_row("Solution", AppState.script_solution, "#10B981"),
                    scene_row("Résultat", AppState.script_result,   "#3B82F6"),
                    scene_row("CTA",      AppState.script_cta,      "#8B5CF6"),
                    spacing="0",
                    width="100%",
                ),
                width="100%",
            ),

            # Score + Viral
            rx.hstack(
                # Quality score
                card(
                    rx.vstack(
                        label("Score qualité"),
                        rx.text(
                            rx.cond(AppState.quality_score > 0,
                                    f"{AppState.quality_score}/10", "—"),
                            font_size="2.5rem",
                            font_weight="900",
                            color=AppState.score_color,
                            line_height="1",
                        ),
                        rx.text(
                            rx.cond(AppState.quality_score >= 8, "✓ Validé",
                            rx.cond(AppState.quality_score >= 6, "⚠ Acceptable", "✗ À réécrire")),
                            font_size="0.78rem",
                            color=AppState.score_color,
                        ),
                        spacing="2",
                        align="start",
                    ),
                    flex="1",
                ),
                # Viral prediction
                card(
                    rx.vstack(
                        label("Viral prediction"),
                        viral_bar("Stop scroll",  AppState.viral_scroll_stop),
                        viral_bar("Watch time",   AppState.viral_watch_time),
                        viral_bar("Partage",      AppState.viral_shareability),
                        viral_bar("Commentaire",  AppState.viral_comment),
                        viral_bar("Pertinence",   AppState.viral_relevance),
                        spacing="3",
                        width="100%",
                    ),
                    flex="2",
                ),
                spacing="4",
                width="100%",
                align="start",
            ),

            # Caption
            rx.cond(
                AppState.caption != "",
                card(
                    rx.vstack(
                        label("📣 Caption Instagram"),
                        rx.text(
                            AppState.caption,
                            font_size="0.88rem",
                            color=TEXT,
                            white_space="pre-wrap",
                            line_height="1.6",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),

            spacing="5",
            width="100%",
        ),
        # No results yet
        rx.vstack(
            rx.text("📊", font_size="3rem"),
            rx.heading("Aucun résultat", size="5", color=MUTED),
            rx.text("Lance une génération depuis l'onglet Générateur.",
                    color=MUTED, font_size="0.9rem"),
            rx.button(
                "← Générateur",
                on_click=AppState.nav("generator"),
                background=ACCENT,
                color="white",
                border_radius="8px",
                padding="0.6rem 1.5rem",
                cursor="pointer",
                margin_top="1rem",
            ),
            spacing="3",
            align="center",
            padding_top="4rem",
        ),
    )


# ── Stats page ─────────────────────────────────────────────────────────────────

def stats_page() -> rx.Component:
    return rx.vstack(
        rx.heading("Mémoire & Stats", size="7", color=TEXT),
        rx.text("Performances du pipeline et historique des reels.",
                color=MUTED, font_size="0.9rem"),
        card(
            rx.vstack(
                rx.text("🚧 Bientôt disponible", font_size="1rem",
                        font_weight="700", color=MUTED),
                rx.text("Les métriques de performance (scores, hooks utilisés, topics) "
                        "seront affichées ici.",
                        font_size="0.85rem", color=MUTED),
                spacing="2",
                align="center",
                padding="2rem 0",
            ),
            width="100%",
        ),
        spacing="5",
        width="100%",
    )


# ── Layout ─────────────────────────────────────────────────────────────────────

def layout(content: rx.Component) -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.box(
            content,
            flex="1",
            padding="2.5rem",
            min_height="100vh",
            overflow_y="auto",
        ),
        background=BG,
        min_height="100vh",
        spacing="0",
        align="start",
    )


def index() -> rx.Component:
    return layout(
        rx.box(
            rx.match(
                AppState.page,
                ("generator", generator_page()),
                ("results",   results_page()),
                ("stats",     stats_page()),
                generator_page(),   # default
            ),
            width="100%",
            max_width="800px",
        )
    )


# ── App ────────────────────────────────────────────────────────────────────────

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="violet",
        radius="medium",
    ),
    style={
        "font_family": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        "background": BG,
        "color": TEXT,
    },
)

app.add_page(index, route="/", title="ReelGen — @ownyourtime.ai")
