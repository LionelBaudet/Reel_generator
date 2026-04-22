"""ui/sidebar.py — Sidebar: brand, inputs, generate button, status, KPIs."""
from __future__ import annotations
import os
from pathlib import Path

import streamlit as st


def render_sidebar(
    root: Path,
    gen_available: bool,
) -> dict:
    """
    Render the full sidebar and return a state dict:
    {
        topic, language, mode, pipeline_mode, skip_video, show_memory,
        pexels_key, generate_clicked
    }
    """
    with st.sidebar:
        # ── Brand ─────────────────────────────────────────────────────────────
        st.markdown(
            '<div class="app-brand">'
            '<div class="app-brand-icon">🎬</div>'
            '<div>'
            '<div class="app-brand-name">Reels Generator</div>'
            '<div class="app-brand-handle">@ownyourtime.ai</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Inputs ─────────────────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section-label">Contenu</div>', unsafe_allow_html=True)

        topic = st.text_input(
            "Idée / Topic",
            placeholder="ex: automatiser reporting, gagner du temps emails…",
            key="sb_topic",
            value=st.session_state.get("sb_topic_val", ""),
        )
        # Persist value so it survives reruns when coming from Generate tab
        if topic:
            st.session_state["sb_topic_val"] = topic

        col_lang, col_mode = st.columns(2)
        with col_lang:
            language = st.selectbox(
                "Langue",
                ["FR", "EN"],
                key="sb_language",
                label_visibility="visible",
            )
        with col_mode:
            mode = st.selectbox(
                "Mode",
                ["Standard", "Parallel A/B"],
                key="sb_mode",
            )

        pipeline_mode = st.selectbox(
            "Pipeline",
            ["Standard", "News", "Social", "Trend"],
            key="sb_pipeline",
            help=(
                "Standard: génère à partir de l'idée saisie. "
                "News: enrichit avec les flux RSS. "
                "Social: enrichit avec Reddit + Google Trends. "
                "Trend: fusion complète news + social."
            ),
        )

        skip_video = st.toggle("Skip vidéo", value=False, key="sb_skip_video")
        show_memory = st.toggle("Afficher mémoire", value=False, key="sb_show_memory")

        st.markdown("")
        generate_clicked = st.button(
            "▶ Générer le Reel",
            type="primary",
            use_container_width=True,
            disabled=not (gen_available and bool(topic.strip())),
            key="sb_generate_btn",
        )

        st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

        # ── API Status ─────────────────────────────────────────────────────────
        _api_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
        _pex_ok = bool(st.session_state.get("pexels_key", "").strip())

        st.markdown(
            f'<div class="status-row">'
            f'<div class="status-dot {"ok" if _api_ok else "error"}"></div>'
            f'<span>Claude {"— connecté" if _api_ok else "— non configuré"}</span>'
            f'</div>'
            f'<div class="status-row">'
            f'<div class="status-dot {"ok" if _pex_ok else "off"}"></div>'
            f'<span>Pexels {"— actif" if _pex_ok else "— non configuré"}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

        # ── Asset KPIs ─────────────────────────────────────────────────────────
        n_videos = _count(root / "assets" / "video", "*.mp4")
        n_music  = _count(root / "assets" / "audio", "*.wav")
        n_batch  = _count(root / "config" / "batch", "reel_*.yaml")
        n_output = _count(root / "output" / "batch", "*.mp4")

        st.markdown('<div class="sidebar-section-label">Assets</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="kpi-row">'
            f'<div class="kpi-item"><div class="kpi-item-value">{n_videos}</div>'
            f'<div class="kpi-item-label">Vidéos</div></div>'
            f'<div class="kpi-item"><div class="kpi-item-value">{n_music}</div>'
            f'<div class="kpi-item-label">Musiques</div></div>'
            f'<div class="kpi-item"><div class="kpi-item-value">{n_batch}</div>'
            f'<div class="kpi-item-label">Configs</div></div>'
            f'<div class="kpi-item"><div class="kpi-item-value">{n_output}</div>'
            f'<div class="kpi-item-label">Reels</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

        # ── Pexels key ─────────────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section-label">Configuration</div>', unsafe_allow_html=True)
        pexels_key = st.text_input(
            "Clé API Pexels",
            type="password",
            value=st.session_state.get("pexels_key", ""),
            placeholder="Clé depuis pexels.com/api…",
            key="sidebar_pexels_key",
            help="Permet le téléchargement automatique de B-roll depuis Pexels.",
        )
        if pexels_key:
            st.session_state["pexels_key"] = pexels_key
        elif not _pex_ok:
            st.caption("Optionnelle — permet le B-roll automatique.")

        st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
        st.caption("v3.0 · Python · Pillow · MoviePy · FFmpeg")

    return {
        "topic":            topic.strip(),
        "language":         language.lower(),
        "mode":             "parallel" if "Parallel" in mode else "standard",
        "pipeline_mode":    pipeline_mode.lower(),
        "skip_video":       skip_video,
        "show_memory":      show_memory,
        "pexels_key":       st.session_state.get("pexels_key", ""),
        "generate_clicked": generate_clicked,
    }


def _count(directory: Path, pattern: str) -> int:
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))
