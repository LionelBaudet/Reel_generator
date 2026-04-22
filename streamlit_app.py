"""
Reels Generator — @ownyourtime.ai
Entry point: streamlit run streamlit_app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ── Inject API keys from st.secrets (Streamlit Cloud) or env ─────────────────

try:
    for _key in ("ANTHROPIC_API_KEY", "PEXELS_API_KEY", "ELEVENLABS_API_KEY"):
        _val = st.secrets.get(_key, "")
        if _val:
            os.environ.setdefault(_key, _val)
except Exception:
    pass

# ── Page config (must be first Streamlit call) ────────────────────────────────

st.set_page_config(
    page_title="Reels Generator — @ownyourtime.ai",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

from ui.css import inject_css
inject_css()

# ── Generative engine import ──────────────────────────────────────────────────

_GEN_IMPORT_ERROR: str = ""
_GEN_AVAILABLE: bool = False

try:
    from generate import (  # noqa: F401
        generate_variants,
        generate_viral_script,
        generate_montage_plan,
        build_yaml,
        build_yaml_from_viral_script,
        generate_caption,
        generate_ab_versions,
        optimize_script_hooks,
        BROLL_CATEGORIES,
        generate_daily_ideas,
        FORMAT_LABELS,
        EMOTION_COLORS,
    )
    from utils.hook_optimizer import analyze_hook, analyze_solution, inject_winner  # noqa: F401
    from utils.hook_engine import optimize_hooks, save_hook_result  # noqa: F401
    from utils.idea_classifier import classify_idea, CATEGORIES  # noqa: F401
    _GEN_AVAILABLE = bool(os.environ.get("ANTHROPIC_API_KEY"))
except Exception as _e:
    import traceback as _tb
    _GEN_IMPORT_ERROR = f"{type(_e).__name__}: {_e}\n{_tb.format_exc()}"

# ── Sidebar ───────────────────────────────────────────────────────────────────

from ui.sidebar import render_sidebar
sidebar = render_sidebar(root=ROOT, gen_available=_GEN_AVAILABLE)

# ── Main tabs ─────────────────────────────────────────────────────────────────

tab_idea, tab_script, tab_studio, tab_batch, tab_library = st.tabs([
    "✨ Idée → Reel",
    "📝 Script Viral",
    "🎬 Studio",
    "📦 Batch",
    "📚 Assets",
])

# ── Tab: Idée → Reel ──────────────────────────────────────────────────────────

with tab_idea:
    from ui.pages.generate import render as render_generate
    render_generate(
        sidebar=sidebar,
        root=ROOT,
        gen_available=_GEN_AVAILABLE,
        gen_import_error=_GEN_IMPORT_ERROR,
    )

# ── Tab: Script Viral ─────────────────────────────────────────────────────────

with tab_script:
    from ui.pages.script import render as render_script
    render_script(
        root=ROOT,
        gen_available=_GEN_AVAILABLE,
        gen_import_error=_GEN_IMPORT_ERROR,
    )

# ── Tab: Studio ───────────────────────────────────────────────────────────────

with tab_studio:
    from ui.pages.studio import render as render_studio
    render_studio(root=ROOT)

# ── Tab: Batch ────────────────────────────────────────────────────────────────

with tab_batch:
    from ui.pages.batch import render as render_batch
    render_batch(root=ROOT)

# ── Tab: Assets (video + music library) ──────────────────────────────────────

with tab_library:
    from ui.pages.library import render as render_library
    render_library(root=ROOT)

# ── Memory panel (collapsible, bottom of every page) ─────────────────────────

if sidebar.get("show_memory"):
    from ui.memory_panel import render_memory_panel
    render_memory_panel(root=ROOT)
