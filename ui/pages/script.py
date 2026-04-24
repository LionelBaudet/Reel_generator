"""
ui/pages/script.py — Viral Script Writer page (ported from tab_script).

Call render(root, gen_available, gen_import_error) from streamlit_app.py.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import yaml

from ui.components import api_error_banner, hr, page_header, section_title, step_bar


# ── Daily cache & topic blacklist ─────────────────────────────────────────────

_CACHE_FILE      = Path("output/daily_ideas_cache.json")
_USED_FILE       = Path("memory/used_topics.json")
_BLACKLIST_DAYS  = 7


def _mode_to_key(mode_label: str) -> str:
    if "complètes" in mode_label: return "trend"
    if "sociales"  in mode_label: return "social"
    if "news"      in mode_label: return "news"
    return "standard"


def _load_daily_cache(mode_key: str) -> dict | None:
    """Return today's cached pipeline result for mode_key, or None if stale/missing."""
    try:
        if not _CACHE_FILE.exists():
            return None
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        if data.get("date") != datetime.today().strftime("%Y-%m-%d"):
            return None
        return data.get(mode_key)
    except Exception:
        return None


def _save_daily_cache(mode_key: str, result: dict) -> None:
    """Persist today's result; preserves other mode entries for the same day."""
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        today = datetime.today().strftime("%Y-%m-%d")
        data: dict = {}
        if _CACHE_FILE.exists():
            try:
                existing = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                if existing.get("date") == today:
                    data = existing
            except Exception:
                pass
        data["date"] = today
        data["saved_at"] = datetime.now().strftime("%H:%M")
        data[mode_key] = result
        _CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _get_used_topics(days: int = _BLACKLIST_DAYS) -> set[str]:
    """Return lowercase set of topic/angle strings used in the last N days."""
    try:
        if not _USED_FILE.exists():
            return set()
        data = json.loads(_USED_FILE.read_text(encoding="utf-8"))
        cutoff = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        return {
            e.get("topic", "").lower()
            for e in data.get("entries", [])
            if e.get("date", "") >= cutoff
        }
    except Exception:
        return set()


def _mark_topic_used(topic: str, angle: str = "") -> None:
    """Add topic to used-topics blacklist with today's date."""
    try:
        _USED_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {"entries": []}
        if _USED_FILE.exists():
            try:
                data = json.loads(_USED_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        entries = data.get("entries", [])
        entries.append({
            "topic": topic.lower(),
            "angle": angle,
            "date":  datetime.today().strftime("%Y-%m-%d"),
        })
        # Keep only last 30 entries
        data["entries"] = entries[-30:]
        _USED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def render(root: Path, gen_available: bool, gen_import_error: str = "") -> None:
    page_header(
        eyebrow="Scripting",
        title="Script Viral",
        sub="Génère un script structuré hook → tension → shift → solution → résultat → CTA, "
            "avec optimisation automatique des hooks et plan de montage complet.",
    )

    if not gen_available:
        api_error_banner(gen_import_error)
        return

    # ── Imports backend (lazy to avoid import errors if key missing) ───────────
    try:
        from generate import (
            generate_ab_versions, generate_caption, generate_daily_ideas,
            generate_montage_plan, generate_viral_script, build_yaml_from_viral_script,
            optimize_script_hooks, FORMAT_LABELS, EMOTION_COLORS,
        )
        from utils.hook_engine import save_hook_result
        from utils.pexels import get_pexels_videos
        from utils.validation import self_check
        backend_ok = True
    except Exception as _e:
        st.error(f"Import error: {_e}")
        return

    # ── Step bar ───────────────────────────────────────────────────────────────
    _has_script   = bool(st.session_state.get("sv_result") or st.session_state.get("sv_ab_result"))
    _has_caption  = bool(st.session_state.get("sv_caption"))
    _has_montage  = bool(st.session_state.get("sv_montage"))
    step_bar(["Script", "Caption", "Montage", "Reel"],
             current=3 if _has_montage else 2 if _has_caption else 1 if _has_script else 0)

    # ── Ideas du jour — auto-load today's cache ───────────────────────────────
    _cached_mode_label = st.session_state.get("di_ideas_mode", "Tendances complètes")
    _cached_mode_key   = _mode_to_key(_cached_mode_label)
    if not st.session_state.get("trend_ideas_result") and not st.session_state.get("daily_ideas"):
        _auto = _load_daily_cache(_cached_mode_key)
        if _auto:
            st.session_state["trend_ideas_result"] = _auto

    with st.expander("💡 Ideas du jour", expanded=not _has_script):
        _di_col1, _di_col2, _di_col3, _di_col4 = st.columns([2, 2, 1, 1])
        with _di_col1:
            # Show cache freshness indicator
            _cache_meta = {}
            try:
                if _CACHE_FILE.exists():
                    _cd = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                    if _cd.get("date") == datetime.today().strftime("%Y-%m-%d"):
                        _cache_meta = _cd
            except Exception:
                pass
            _cache_label = (
                f'<span style="color:#4ade80;font-size:.75rem">● Actualisé aujourd\'hui à {_cache_meta["saved_at"]}</span>'
                if _cache_meta.get("saved_at") else
                '<span style="color:var(--text-muted);font-size:.85rem">Clique sur Générer pour analyser l\'actu du jour.</span>'
            )
            st.markdown(_cache_label, unsafe_allow_html=True)
        with _di_col2:
            _ideas_mode = st.selectbox(
                "Source",
                ["Tendances complètes", "Tendances sociales", "Flux news", "Standard (RSS)"],
                key="di_ideas_mode",
                label_visibility="collapsed",
                help=(
                    "Tendances complètes : fusion Reddit + Google Trends + flux RSS (recommandé).\n"
                    "Tendances sociales : Reddit + Google Trends uniquement.\n"
                    "Flux news : SRF, France Info, BBC, TechCrunch.\n"
                    "Standard : flux RSS + scoring local (rapide)."
                ),
            )
        with _di_col3:
            _di_clicked = st.button("Générer", type="primary",
                                    use_container_width=True, key="btn_daily_ideas")
        with _di_col4:
            _di_force = st.button("🔄", use_container_width=True, key="btn_force_refresh",
                                  help="Forcer le rechargement (ignore le cache)")

        if _di_force:
            st.session_state.pop("trend_ideas_result", None)
            st.session_state.pop("daily_ideas", None)
            st.rerun()

        if _di_clicked:
            _is_trend_mode  = "complètes" in _ideas_mode
            _is_social_mode = "sociales"  in _ideas_mode
            _is_news_mode   = "news"      in _ideas_mode
            _mode_key       = _mode_to_key(_ideas_mode)

            if _is_trend_mode or _is_social_mode or _is_news_mode:
                # Check cache first — skip API call if already done today
                _cached = _load_daily_cache(_mode_key)
                if _cached:
                    st.session_state["trend_ideas_result"] = _cached
                    st.session_state.pop("daily_ideas", None)
                    st.toast("Idées du jour chargées depuis le cache.", icon="⚡")
                else:
                    _spinner_label = (
                        "Fusion social + news — analyse des tendances du jour…" if _is_trend_mode
                        else "Analyse Reddit + Google Trends…" if _is_social_mode
                        else "Analyse des flux news RSS…"
                    )
                    with st.spinner(_spinner_label):
                        try:
                            from orchestrate import run_full_pipeline
                            _lang_for_ideas = st.session_state.get("sv_lang", "fr")
                            _trend_result = run_full_pipeline(
                                topic="",
                                trend_mode=_is_trend_mode,
                                social_mode=_is_social_mode,
                                news_mode=_is_news_mode,
                                lang=_lang_for_ideas,
                                skip_video=True,
                                ideas_only=True,
                            )
                            st.session_state["trend_ideas_result"] = _trend_result
                            st.session_state.pop("daily_ideas", None)
                            _save_daily_cache(_mode_key, _trend_result)
                        except Exception as _exc:
                            st.error(f"Erreur pipeline : {_exc}")
            else:
                _cached_std = _load_daily_cache("standard")
                if _cached_std:
                    st.session_state["daily_ideas"] = _cached_std
                    st.session_state.pop("trend_ideas_result", None)
                    st.toast("Idées du jour chargées depuis le cache.", icon="⚡")
                else:
                    with st.spinner("Analyse de l'actu et sélection des 3 meilleures idées…"):
                        try:
                            _daily = generate_daily_ideas()
                            st.session_state["daily_ideas"] = _daily
                            st.session_state.pop("trend_ideas_result", None)
                            _save_daily_cache("standard", _daily)
                        except Exception as _exc:
                            st.error(f"Erreur : {_exc}")

        _trend_result = st.session_state.get("trend_ideas_result")
        if _trend_result:
            _used = _get_used_topics()
            _render_trend_ideas(_trend_result, FORMAT_LABELS, EMOTION_COLORS, used_topics=_used)
        else:
            _daily_data = st.session_state.get("daily_ideas")
            if _daily_data:
                _render_daily_ideas(_daily_data, FORMAT_LABELS, EMOTION_COLORS)

    # ── Idea input ─────────────────────────────────────────────────────────────
    sv_idea = st.text_input(
        "💡 Ton idée",
        placeholder="ex: automatiser ses emails avec GPT, gagner 1h par jour sur Excel…",
        key="sv_idea_input",
    )

    _opt_col1, _opt_col2, _opt_col3 = st.columns([3, 2, 2])
    with _opt_col2:
        _lang_choice = st.radio("Langue", ["Français", "English"],
                                horizontal=True, key="sv_lang_radio")
    with _opt_col3:
        _mode_choice = st.radio("Mode", ["Standard", "A/B Testing"],
                                horizontal=True, key="sv_mode_radio")

    sv_lang = "en" if _lang_choice == "English" else "fr"
    sv_mode = "ab" if _mode_choice == "A/B Testing" else "standard"
    st.session_state["sv_lang"] = sv_lang

    with _opt_col1:
        sv_clicked = st.button(
            "🚀 Générer les 3 versions A/B/C" if sv_mode == "ab" else "🚀 Générer le script",
            type="primary",
            disabled=not sv_idea.strip(),
            use_container_width=True,
            key="btn_sv",
        )

    if not sv_idea.strip() and not _has_script:
        st.markdown(
            '<div class="empty-state" style="margin-top:1rem">'
            '<div class="empty-state-icon">📝</div>'
            '<div class="empty-state-title">Tape ton idée et génère le script</div>'
            '<div class="empty-state-sub">Claude structure automatiquement : '
            "hook · tension · shift · solution · résultat · CTA · "
            "caption Instagram · plan de montage avec durées.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    _reset_col, _ = st.columns([1, 5])
    with _reset_col:
        if st.button("↺ Réinitialiser", type="secondary", key="btn_sv_reset"):
            for _k in ("sv_result", "sv_ab_result", "sv_caption", "sv_montage",
                       "sv_ab_selected", "sv_pexels_paths", "sv_optimized",
                       "sv_daily_context"):
                st.session_state.pop(_k, None)
            st.rerun()

    # ── Daily context banner ───────────────────────────────────────────────────
    _sv_daily_ctx = st.session_state.get("sv_daily_context")
    try:
        if _sv_daily_ctx and isinstance(_sv_daily_ctx, dict) and sv_idea.strip():
            _render_daily_context_banner(_sv_daily_ctx, FORMAT_LABELS)
    except Exception:
        st.session_state.pop("sv_daily_context", None)

    # ── Generate (manual click OR auto-trigger from idea selection) ───────────
    _sv_auto    = st.session_state.pop("sv_auto_generate", False)
    _idea_to_use = sv_idea.strip()

    if (_sv_auto or sv_clicked) and _idea_to_use:
        if sv_mode == "ab":
            with st.spinner("Génération des 3 versions A/B/C…"):
                try:
                    ab_result = generate_ab_versions(
                        _idea_to_use, lang=sv_lang,
                        context=st.session_state.get("sv_daily_context"),
                    )
                    st.session_state["sv_ab_result"]   = ab_result
                    st.session_state["sv_idea_stored"] = _idea_to_use
                    for k in ("sv_result", "sv_caption", "sv_montage", "sv_ab_selected"):
                        st.session_state.pop(k, None)
                except Exception as exc:
                    st.error(f"Erreur : {exc}")
        else:
            with st.spinner("Génération du script viral…"):
                try:
                    sv_result = generate_viral_script(
                        _idea_to_use, lang=sv_lang,
                        context=st.session_state.get("sv_daily_context"),
                    )
                    st.session_state["sv_result"]      = sv_result
                    st.session_state["sv_idea_stored"] = _idea_to_use
                    for k in ("sv_caption", "sv_ab_result"):
                        st.session_state.pop(k, None)
                    try:
                        _opt = optimize_script_hooks(sv_result)
                        st.session_state["sv_optimized"] = _opt
                    except Exception:
                        st.session_state.pop("sv_optimized", None)
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

    # ── Display A/B result ─────────────────────────────────────────────────────
    ab_result = st.session_state.get("sv_ab_result")
    if ab_result:
        _render_ab_result(ab_result, generate_montage_plan)

    # ── Display standard script result ─────────────────────────────────────────
    sv = st.session_state.get("sv_result")
    if sv:
        _sv_lang_now = st.session_state.get("sv_lang", "fr")
        _has_cap  = bool(st.session_state.get("sv_caption"))
        _has_mont = bool(st.session_state.get("sv_montage"))

        # ── Fast-track: Caption + Montage in one shot ──────────────────────────
        if not _has_cap or not _has_mont:
            _ft_c1, _ft_c2 = st.columns([3, 2])
            with _ft_c1:
                st.markdown(
                    '<div style="font-size:.82rem;color:var(--text-muted);padding:.4rem 0">'
                    '⚡ Génère caption + montage en une seule étape pour aller plus vite.</div>',
                    unsafe_allow_html=True,
                )
            with _ft_c2:
                if st.button("⚡ Caption + Montage", type="primary",
                             use_container_width=True, key="btn_fast_track"):
                    with st.spinner("Génération caption + plan de montage…"):
                        try:
                            _cap = generate_caption(
                                sv, {},
                                st.session_state.get("sv_idea_stored", ""),
                                lang=_sv_lang_now,
                                daily_context=st.session_state.get("sv_daily_context"),
                            )
                            st.session_state["sv_caption"] = _cap
                            _plan = generate_montage_plan(
                                sv.get("script", {}),
                                lang=_sv_lang_now,
                                idea_type=sv.get("idea_type", ""),
                            )
                            st.session_state["sv_montage"] = _plan
                            st.rerun()
                        except Exception as _fte:
                            st.error(f"Erreur : {_fte}")

        # ── Shortcut: everything ready → jump to render ────────────────────────
        elif _has_cap and _has_mont:
            _montage_data = st.session_state.get("sv_montage", {})
            _reel_slug    = st.session_state.get("sv_idea_stored", "reel")
            _reel_slug    = re.sub(r"[^\w]", "_", _reel_slug.lower())[:30]
            _out_path     = root / "output" / f"{_reel_slug}.mp4"
            if not _out_path.exists():
                st.markdown(
                    '<div style="background:var(--brand-light);border:1px solid var(--brand-border);'
                    'border-radius:8px;padding:.6rem 1rem;margin:.5rem 0;font-size:.88rem">'
                    '✅ Script · Caption · Montage prêts — '
                    '<strong>descends jusqu\'à "Étape 4" pour générer le Reel.</strong></div>',
                    unsafe_allow_html=True,
                )

        _render_script_result(
            sv, root, gen_available,
            generate_caption, generate_montage_plan, build_yaml_from_viral_script,
            get_pexels_videos, save_hook_result, self_check,
            optimize_script_hooks,
        )

    # ── Transfer to generate tab ───────────────────────────────────────────────
    if _has_script:
        hr()
        if st.button("✨ Générer les 3 concepts YAML →", type="primary",
                     use_container_width=True, key="sv_to_yaml"):
            st.session_state["auto_idea_input"] = st.session_state.get("sv_idea_stored", sv_idea)
            st.info("Idée transférée → va dans l'onglet **✨ Idée → Reel** et clique sur Générer.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _render_trend_ideas(result: dict, format_labels: dict, emotion_colors: dict,
                        used_topics: set | None = None) -> None:
    """Display 3 trend-based idea cards from a run_full_pipeline() result."""
    if result.get("error"):
        st.error(f"Erreur pipeline : {result['error']}")
        return

    # ── Extract top 3 topics ───────────────────────────────────────────────────
    trends = result.get("trends") or {}
    top_topics = trends.get("top_topics", [])

    # Fallback: social trends if no fused topics
    if not top_topics:
        social = result.get("social") or {}
        raw = social.get("trends", [])
        top_topics = [
            {
                "rank": i + 1,
                "topic": t.get("title", ""),
                "angle": t.get("viral_angle", t.get("summary", "")[:100]),
                "virality_score": t.get("virality_score", 5),
                "coverage_bonus": False,
                "evidence": t.get("summary", ""),
                "region": t.get("region", ""),
                "source_mix": [t.get("source", "reddit")],
                "category": t.get("category", "social"),
            }
            for i, t in enumerate(raw[:5])
        ]

    # Fallback: news topics
    if not top_topics:
        news = result.get("news") or {}
        raw_news = news.get("topics", [])
        top_topics = [
            {
                "rank": i + 1,
                "topic": t.get("title", ""),
                "angle": t.get("ai_angle", ""),
                "virality_score": t.get("virality_score", 5),
                "coverage_bonus": False,
                "evidence": t.get("summary", ""),
                "region": t.get("region", ""),
                "source_mix": ["news"],
                "category": t.get("category", "news"),
            }
            for i, t in enumerate(raw_news[:5])
        ]

    if not top_topics:
        st.warning("Aucune tendance trouvée. Réessaie dans quelques instants.")
        return

    # ── Build hook map: topic_name → best hook ─────────────────────────────────
    trend_hooks = result.get("trend_hooks") or {}
    all_hooks = trend_hooks.get("hooks", [])
    best_hook_global = trend_hooks.get("best_hook", {})

    hook_map: dict[str, dict] = {}
    for h in all_hooks:
        topic_key = h.get("trend_topic", "").lower()
        if topic_key not in hook_map or h.get("score", 0) > hook_map[topic_key].get("score", 0):
            hook_map[topic_key] = h

    # ── AI insight for context banner ─────────────────────────────────────────
    insight = result.get("insight") or {}
    insight_text = insight.get("insight", "")
    if insight_text:
        st.markdown(
            f'<div style="font-size:.78rem;color:var(--text-muted);background:var(--surface-2);'
            f'border-radius:6px;padding:.5rem .75rem;margin-bottom:.75rem">'
            f'🤖 <strong>AI Angle :</strong> {insight_text}</div>',
            unsafe_allow_html=True,
        )

    # ── 3 trend cards ─────────────────────────────────────────────────────────
    _SOURCE_ICON = {"reddit": "📱", "news": "📰", "google_trends": "📈"}
    _CAT_COLORS  = {
        "tech": "#6366f1", "economy": "#f59e0b", "politics": "#ef4444",
        "social": "#10b981", "news": "#3b82f6",
    }
    _PATTERN_LABELS = {"fear": "😱 Peur", "curiosity": "🕵️ Curiosité", "contrast": "⚡ Contraste"}
    _used = used_topics or set()

    display_topics = top_topics[:3]
    cols = st.columns(len(display_topics))

    for idx, (col, topic) in enumerate(zip(cols, display_topics)):
        t_name     = topic.get("topic", "")
        t_angle    = topic.get("angle", "")
        t_score    = topic.get("virality_score", 5)
        t_region   = topic.get("region", "")
        t_evidence = topic.get("evidence", "")
        t_sources  = topic.get("source_mix", [])
        t_category = topic.get("category", "")
        t_coverage = topic.get("coverage_bonus", False)

        # Find best hook for this topic
        t_hook_obj  = hook_map.get(t_name.lower(), {})
        if not t_hook_obj and best_hook_global.get("trend_topic", "").lower() == t_name.lower():
            t_hook_obj = best_hook_global
        t_hook_text = t_hook_obj.get("hook", "")
        t_hook_score = t_hook_obj.get("score", 0)
        t_pattern   = _PATTERN_LABELS.get(t_hook_obj.get("pattern", ""), "")

        is_used     = t_name.lower() in _used or (t_angle or "").lower() in _used
        score_color = "#4ade80" if t_score >= 8 else "#f59e0b" if t_score >= 6 else "#f87171"
        cat_color   = _CAT_COLORS.get(t_category, "#9CA3AF")

        src_icons = " ".join(_SOURCE_ICON.get(s, "🌐") for s in t_sources)
        used_badge = (
            '<span style="font-size:.63rem;font-weight:700;background:#f1f5f9;color:#94a3b8;'
            'padding:.1rem .35rem;border-radius:3px;margin-left:4px">Déjà utilisé</span>'
            if is_used else ""
        )
        coverage_badge = (
            '<span style="font-size:.63rem;font-weight:700;background:#fef9c3;color:#b45309;'
            'padding:.1rem .35rem;border-radius:3px;margin-left:4px">Social+News</span>'
            if t_coverage else ""
        )
        cat_badge = (
            f'<span style="font-size:.63rem;font-weight:700;background:{cat_color}22;'
            f'color:{cat_color};padding:.1rem .35rem;border-radius:3px;'
            f'text-transform:uppercase">{t_category}</span>'
        ) if t_category else ""

        hook_html = (
            f'<div style="font-size:.9rem;font-weight:700;color:#1A1A2E;margin:.4rem 0;'
            f'border-left:3px solid var(--gold);padding:.25rem .5rem;'
            f'background:var(--brand-light);border-radius:0 4px 4px 0">'
            f'"{t_hook_text}"'
            f'<div style="font-size:.65rem;color:var(--text-muted);margin-top:2px">'
            f'{t_pattern}{f" · {t_hook_score}/10" if t_hook_score else ""}</div>'
            f'</div>'
        ) if t_hook_text else ""

        evidence_html = (
            f'<div style="font-size:.7rem;color:var(--text-faint);font-style:italic;margin-top:.3rem">'
            f'{t_evidence[:120]}{"…" if len(t_evidence) > 120 else ""}</div>'
        ) if t_evidence else ""

        with col:
            st.markdown(
                f'<div style="border:1px solid var(--border);border-radius:10px;padding:1rem;'
                f'background:var(--surface);height:100%">'
                # Header row
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">'
                f'<div style="display:flex;gap:.3rem;align-items:center;flex-wrap:wrap">'
                f'{cat_badge}{coverage_badge}{used_badge}'
                f'</div>'
                f'<span style="font-size:1rem;font-weight:800;color:{score_color}">{t_score}</span>'
                f'</div>'
                # Topic name
                f'<div style="font-size:.95rem;font-weight:700;color:var(--text);margin:.3rem 0">'
                f'{t_name}</div>'
                # Angle / idea
                f'<div style="font-size:.78rem;color:var(--text-muted);margin-bottom:.3rem;'
                f'font-style:italic">{t_angle}</div>'
                # Hook
                f'{hook_html}'
                # Evidence
                f'{evidence_html}'
                # Footer
                f'<div style="font-size:.68rem;color:var(--text-faint);margin-top:.4rem">'
                f'{src_icons} {t_region}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _btn_label = "✓ Utilisé" if is_used else "Utiliser cette idée →"
            _btn_type  = "secondary" if is_used else "primary"
            if st.button(_btn_label, key=f"btn_use_trend_{idx}",
                         use_container_width=True, type=_btn_type):
                # Use the verified ANGLE as the idea, not the sensationalized topic name
                idea_text = t_angle or t_name
                claim_type = topic.get("claim_type", "plausible")

                # Build why_now without mentioning upvotes or Reddit as "confirmation"
                source_label_str = " + ".join(
                    s.replace("reddit", "signal social").replace("news", "flux RSS")
                    for s in t_sources
                )
                why_now_str = f"Signal fort détecté ({source_label_str}) — score {t_score}/10"

                # best_stat = evidence only if it doesn't contain upvote/Reddit language
                evidence_clean = t_evidence[:80] if t_evidence else ""
                if any(w in evidence_clean.lower() for w in ("upvote", "reddit", "9 6", "9333")):
                    evidence_clean = ""  # strip — don't pass Reddit vote counts as stats

                _mark_topic_used(t_name, idea_text)
                st.session_state["sv_idea_input"]    = idea_text
                st.session_state["sv_auto_generate"] = True   # auto-trigger script gen
                st.session_state["sv_daily_context"] = {
                    "actu_link":    t_angle or t_name,
                    "best_stat":    evidence_clean,
                    "why_now":      why_now_str,
                    "ai_tool":      "Trend Intelligence",
                    "ai_result":    t_hook_text,
                    "context":      t_category,
                    "source_label": "Trend",
                    "source_score": t_score,
                    "emotion":      "curiosity",
                    "format":       "educational_explainer",
                    "claim_type":   claim_type,
                    "trend_sources": t_sources,
                }
                st.rerun()


def _render_daily_ideas(daily_data, format_labels, emotion_colors):
    try:
        _note    = daily_data.get("note", "") if isinstance(daily_data, dict) else ""
        _n_fetch = daily_data.get("_signals_fetched", 0) if isinstance(daily_data, dict) else 0
        _n_rel   = daily_data.get("_signals_relevant", 0) if isinstance(daily_data, dict) else 0
        _meta    = f"— {_n_rel} signaux pertinents / {_n_fetch} fetchés" if _n_fetch else ""
        if _note:
            st.markdown(
                f'<div style="font-size:.8rem;color:var(--text-muted);margin:.5rem 0 1rem;font-style:italic">'
                f'📡 {_note} <span style="color:var(--text-faint)">{_meta}</span></div>',
                unsafe_allow_html=True,
            )
        _ideas = daily_data.get("ideas", []) if isinstance(daily_data, dict) else []
        if not isinstance(_ideas, list) or not _ideas:
            st.warning("Aucune idée générée — réessaie.")
            return

        _di_cols = st.columns(len(_ideas))
        for _idx, (_col, _idea_item) in enumerate(zip(_di_cols, _ideas)):
            with _col:
                if not isinstance(_idea_item, dict):
                    continue
                _fmt   = str(_idea_item.get("format", ""))
                _emoji, _label = format_labels.get(_fmt, ("💡", _fmt))
                _emo   = str(_idea_item.get("emotion", ""))
                _emo_c = emotion_colors.get(_emo, "#9CA3AF")
                _hook  = str(_idea_item.get("hook_preview", ""))
                _idea_t = str(_idea_item.get("idea", ""))
                _why   = str(_idea_item.get("why", ""))
                _actu  = str(_idea_item.get("actu_link", ""))
                _best_stat     = str(_idea_item.get("best_stat", ""))
                _why_now       = str(_idea_item.get("why_now", ""))
                _practical_tip = str(_idea_item.get("practical_tip", ""))
                _concrete_uc   = str(_idea_item.get("concrete_use_case", ""))
                _source_title  = str(_idea_item.get("source_title", _idea_item.get("source_stat", "")))
                _source_label  = str(_idea_item.get("source_label", ""))
                _source_url    = str(_idea_item.get("source_url", ""))
                _source_score  = _idea_item.get("source_score", 0.0)
                _ai_tool    = str(_idea_item.get("ai_tool", ""))
                _ai_prompt  = str(_idea_item.get("ai_prompt_example", ""))
                _ai_result  = str(_idea_item.get("ai_result", ""))
                _ctx_type   = str(_idea_item.get("context", ""))
                _qual_warns = _idea_item.get("_quality_warnings", [])

                _ctx_colors = {"pro": "#6366f1", "perso": "#10b981", "mixte": "#f59e0b"}
                _ctx_c = _ctx_colors.get(_ctx_type.lower(), "#9CA3AF")
                _ctx_badge = (
                    f'<span style="font-size:.65rem;font-weight:700;background:{_ctx_c}22;'
                    f'color:{_ctx_c};padding:.15rem .4rem;border-radius:3px;text-transform:uppercase">'
                    f'{_ctx_type}</span>'
                ) if _ctx_type else ""

                try:
                    from utils.source_scoring import score_label as _sl
                    _score_label = _sl(float(_source_score)) if _source_score else ""
                except Exception:
                    _score_label = f"{_source_score}/10" if _source_score else ""

                _actu_html   = f'<div style="font-size:.7rem;color:#60a5fa;margin-bottom:.3rem">📡 {_actu}</div>' if _actu else ""
                _stat_html   = f'<div style="font-size:.8rem;font-weight:700;color:#f59e0b;margin:.3rem 0;background:#f59e0b11;border-left:3px solid #f59e0b;padding:.2rem .5rem;border-radius:0 4px 4px 0">💥 {_best_stat}</div>' if _best_stat else ""
                _wnow_html   = f'<div style="font-size:.7rem;color:#a5b4fc;margin:.2rem 0">⏰ {_why_now}</div>' if _why_now else ""
                _warn_html   = f'<div style="font-size:.65rem;color:#f87171;margin-top:.3rem">⚠ {"; ".join(_qual_warns)}</div>' if _qual_warns else ""

                _ai_html = ""
                if _ai_tool or _ai_prompt or _ai_result:
                    _t  = f'<strong>{_ai_tool}</strong>' if _ai_tool else ""
                    _r  = f'<div style="color:#34d399;margin-top:.2rem">✅ {_ai_result}</div>' if _ai_result else ""
                    _p  = (f'<div style="font-family:monospace;font-size:.65rem;background:#0f172a;'
                           f'border-radius:4px;padding:.3rem .5rem;margin:.3rem 0;color:#a5b4fc;white-space:pre-wrap">'
                           f'» {_ai_prompt}</div>') if _ai_prompt else ""
                    _ai_html = (f'<div style="border-top:1px solid var(--border);margin-top:.5rem;'
                                f'padding-top:.4rem;font-size:.72rem;color:var(--text-muted)">🤖 {_t}{_p}{_r}</div>')

                _tip_html = ""
                if _practical_tip or _concrete_uc:
                    _tl = f'<div style="color:#f0f0f0;margin-bottom:.2rem">💡 <strong>Astuce :</strong> {_practical_tip}</div>' if _practical_tip else ""
                    _ul = f'<div style="color:var(--text-muted);font-style:italic">🎯 {_concrete_uc}</div>' if _concrete_uc else ""
                    _tip_html = f'<div style="border-top:1px solid var(--border);margin-top:.5rem;padding-top:.4rem;font-size:.72rem">{_tl}{_ul}</div>'

                _url_line   = f'<a href="{_source_url}" target="_blank" style="color:var(--text-faint);font-size:.65rem;word-break:break-all">{_source_url}</a>' if _source_url else ""
                _score_html = f'<span style="color:#f59e0b;font-size:.68rem;margin-left:.4rem">{_score_label}</span>' if _score_label else ""
                _source_html = (
                    '<div style="font-size:.7rem;color:var(--text-muted);border-top:1px solid var(--border);margin-top:.5rem;padding-top:.4rem">'
                    f'🔗 <strong>{_source_label}</strong>{_score_html}<br>'
                    f'<em style="font-size:.67rem">{_source_title}</em><br>{_url_line}</div>'
                ) if (_source_title or _source_url) else ""

                st.markdown(
                    f'<div style="border:1px solid var(--border);border-radius:10px;padding:1rem;background:var(--surface);height:100%">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem">'
                    f'<span style="font-size:.75rem;font-weight:600;background:var(--surface-2);padding:.2rem .5rem;border-radius:4px;color:var(--text-muted)">{_emoji} {_label}</span>'
                    f'<div style="display:flex;gap:.4rem;align-items:center">{_ctx_badge}'
                    f'<span style="font-size:.7rem;font-weight:700;color:{_emo_c};text-transform:uppercase">{_emo}</span></div></div>'
                    f'<div style="font-size:.95rem;font-weight:700;color:var(--text);margin:.5rem 0">{_hook}</div>'
                    f'<div style="font-size:.78rem;color:var(--text-muted);margin-bottom:.25rem;font-style:italic">{_idea_t}</div>'
                    f'<div style="font-size:.72rem;color:var(--text-faint);margin-bottom:.3rem">{_why}</div>'
                    f'{_actu_html}{_stat_html}{_wnow_html}{_ai_html}{_tip_html}{_source_html}{_warn_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Utiliser cette idée →", key=f"btn_use_idea_{_idx}",
                             use_container_width=True):
                    st.session_state["sv_idea_input"]    = _idea_t
                    st.session_state["sv_daily_context"] = _idea_item
                    st.rerun()
    except Exception as _render_exc:
        st.error(f"Erreur d'affichage des idées : {_render_exc}")
        st.session_state.pop("daily_ideas", None)


def _render_daily_context_banner(ctx: dict, format_labels: dict) -> None:
    _ctx_actu      = str(ctx.get("actu_link", "") or "")
    _ctx_stat      = str(ctx.get("best_stat", "") or "")
    _ctx_why_now   = str(ctx.get("why_now", "") or "")
    _ctx_tip       = str(ctx.get("practical_tip", "") or "")
    _ctx_fmt       = format_labels.get(str(ctx.get("format", "") or ""), ("", ""))[1]
    _ctx_emo       = str(ctx.get("emotion", "") or "")
    _ctx_ai_tool   = str(ctx.get("ai_tool", "") or "")
    _ctx_ai_result = str(ctx.get("ai_result", "") or "")
    _ctx_type      = str(ctx.get("context", "") or "")
    _ctx_src_score = ctx.get("source_score", 0.0) or 0.0
    _ctx_src_label = str(ctx.get("source_label", "") or "")

    if not any([_ctx_actu, _ctx_fmt, _ctx_ai_tool, _ctx_stat]):
        return

    _ctx_parts = []
    if _ctx_actu:      _ctx_parts.append(f'<span>📡 <strong>Actu :</strong> {_ctx_actu}</span>')
    if _ctx_stat:      _ctx_parts.append(f'<span>💥 <strong>Stat :</strong> {_ctx_stat}</span>')
    if _ctx_why_now:   _ctx_parts.append(f'<span>⏰ <strong>Pourquoi maintenant :</strong> {_ctx_why_now}</span>')
    if _ctx_tip:       _ctx_parts.append(f'<span>💡 <strong>Astuce :</strong> {_ctx_tip}</span>')
    if _ctx_fmt:       _ctx_parts.append(f'<span>🎭 <strong>Format :</strong> {_ctx_fmt}</span>')
    if _ctx_emo:       _ctx_parts.append(f'<span>🎯 <strong>Émotion :</strong> {_ctx_emo}</span>')
    if _ctx_type:      _ctx_parts.append(f'<span>👤 <strong>Contexte :</strong> {_ctx_type}</span>')
    if _ctx_ai_tool:   _ctx_parts.append(f'<span>🤖 <strong>Outil :</strong> {_ctx_ai_tool}</span>')
    if _ctx_ai_result: _ctx_parts.append(f'<span>✅ <strong>Résultat :</strong> {_ctx_ai_result}</span>')
    if _ctx_src_label: _ctx_parts.append(f'<span>🔗 <strong>Source :</strong> {_ctx_src_label} [{_ctx_src_score}/10]</span>')

    st.markdown(
        '<div style="font-size:.78rem;color:var(--text-muted);background:var(--surface-2);'
        'border-radius:6px;padding:.6rem .75rem;margin-bottom:.5rem;display:flex;flex-direction:column;gap:.3rem">'
        + "".join(f"<div>{p}</div>" for p in _ctx_parts) + "</div>",
        unsafe_allow_html=True,
    )


def _render_ab_result(ab_result: dict, generate_montage_plan) -> None:
    hr()
    _ab_label = ab_result.get("idea_type_label", "")
    _ab_angle = ab_result.get("idea_angle", "")
    _ab_conf  = ab_result.get("idea_confidence", 0)
    if _ab_label:
        _ab_conf_pct   = int(_ab_conf * 100)
        _ab_conf_color = "#4ade80" if _ab_conf >= 0.6 else "#facc15" if _ab_conf >= 0.4 else "#94a3b8"
        st.markdown(
            f'<div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.5rem;flex-wrap:wrap">'
            f'<span style="background:#F5F5F7;border:1px solid #E0E0E8;border-radius:20px;padding:3px 10px;font-size:.72rem;font-weight:700;color:#1A1A2E">📂 {_ab_label}</span>'
            f'<span style="background:#FFF8EC;border:1px solid #E8B84B;border-radius:20px;padding:3px 10px;font-size:.72rem;font-weight:700;color:#C8972A">⚡ {_ab_angle}</span>'
            f'<span style="font-size:.68rem;color:{_ab_conf_color};font-weight:600">confiance {_ab_conf_pct}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    versions = ab_result.get("versions", [])
    selection = ab_result.get("selection", {})
    _type_colors = {"safe": "#60a5fa", "curiosity": "#facc15", "aggressive": "#f87171"}
    _type_bg     = {"safe": "#EFF6FF", "curiosity": "#FEFCE8", "aggressive": "#FFF1F2"}
    _type_labels = {"safe": "A — SAFE", "curiosity": "B — CURIOSITÉ", "aggressive": "C — AGRESSIF"}
    _script_keys = [("Hook","hook","#f87171"),("Tension","tension","#fb923c"),
                    ("Shift","shift","#facc15"),("Proof","proof","#a78bfa"),
                    ("Solution","solution","#4ade80"),("Résultat","result","#60a5fa"),
                    ("CTA","cta","#c084fc")]

    tab_a, tab_b, tab_c = st.tabs(["A — Safe", "B — Curiosité", "C — Agressif"])
    for tab, version in zip([tab_a, tab_b, tab_c], versions):
        with tab:
            vtype  = version.get("type", "")
            color  = _type_colors.get(vtype, "#aaa")
            bg     = _type_bg.get(vtype, "#F5F5F7")
            hook   = version.get("hook", {})
            sc     = hook.get("score", 0)
            st.markdown(
                f'<div style="background:{bg};border-left:4px solid {color};border-radius:0 8px 8px 0;padding:.8rem 1rem;margin-bottom:.75rem">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:4px">'
                f'<span style="font-size:.72rem;font-weight:700;color:{color}">{_type_labels.get(vtype,"")}</span>'
                f'<span style="font-size:.9rem;font-weight:800;color:{color}">Score {sc}</span></div>'
                f'<div style="font-size:1.15rem;font-weight:800;color:#1A1A2E">"{hook.get("text","")}"</div>'
                f'<div style="font-size:.75rem;color:#6B6B8A;margin-top:4px">Ton : {version.get("tone","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            script_v = version.get("script", {})
            for lbl, key, clr in _script_keys:
                txt = script_v.get(key, "")
                if txt:
                    st.markdown(
                        f'<div style="display:flex;gap:.75rem;padding:.4rem 0;border-bottom:1px solid #F0F0F5;">'
                        f'<span style="min-width:72px;font-weight:700;font-size:.8rem;color:{clr}">{lbl}</span>'
                        f'<span style="color:#1A1A2E;font-size:.9rem">{txt}</span></div>',
                        unsafe_allow_html=True,
                    )
            if version.get("overlay_lines"):
                with st.expander("Overlay texte", expanded=False):
                    for line in version["overlay_lines"]:
                        st.markdown(
                            f'<div style="background:#1A1A2E;color:#F2F0EA;font-weight:700;font-size:.95rem;padding:.35rem .7rem;border-radius:6px;margin-bottom:4px;text-align:center">{line}</div>',
                            unsafe_allow_html=True,
                        )

    if selection:
        hr()
        st.markdown("### Analyse")
        sel_cols = st.columns(3)
        for col, (label, key, icon) in zip(sel_cols, [
            ("La plus sûre", "safest", "🛡️"),
            ("La plus virale", "most_viral", "🔥"),
            ("La + convertissante", "most_likely_to_convert", "💰"),
        ]):
            with col:
                v = selection.get(key, "?")
                st.markdown(
                    f'<div style="background:#F5F5F7;border-radius:8px;padding:.6rem;text-align:center">'
                    f'<div style="font-size:.72rem;color:#6B6B8A;font-weight:700">{icon} {label}</div>'
                    f'<div style="font-size:2rem;font-weight:900;color:#E8B84B">VERSION {v}</div></div>',
                    unsafe_allow_html=True,
                )
        reco = selection.get("recommendation", "")
        if reco:
            st.markdown(
                f'<div style="background:#FFF8EC;border:1px solid #E8B84B;border-radius:8px;padding:.6rem .8rem;margin-top:.5rem;font-size:.88rem;color:#1A1A2E">'
                f'<strong>Recommandation :</strong> {reco}</div>',
                unsafe_allow_html=True,
            )

    hr()
    st.markdown("### Utiliser pour le montage")
    _ver_labels = {
        v["id"]: f'Version {v["id"]} — {v.get("type","").capitalize()} · "{v.get("hook",{}).get("text","")}"'
        for v in versions
    }
    _default_v = selection.get("most_viral", "A")
    _selected_v = st.radio(
        "Version à utiliser",
        options=[v["id"] for v in versions],
        format_func=lambda x: _ver_labels.get(x, x),
        index=["A", "B", "C"].index(_default_v) if _default_v in ["A", "B", "C"] else 0,
        key="sv_ab_version_radio",
    )
    st.session_state["sv_ab_selected"] = _selected_v

    if st.button(f"Générer plan de montage — Version {_selected_v}",
                 type="primary", use_container_width=True, key="btn_ab_montage"):
        _chosen = next((v for v in versions if v["id"] == _selected_v), versions[0])
        _sv_compat = {
            "script":    _chosen.get("script", {}),
            "best_hook": _chosen.get("hook", {}),
            "overlay_lines": _chosen.get("overlay_lines", []),
        }
        _cur_lang = st.session_state.get("sv_lang", "fr")
        with st.spinner(f"Plan de montage Version {_selected_v}…"):
            try:
                plan = generate_montage_plan(
                    _chosen.get("script", {}), lang=_cur_lang,
                    idea_type=ab_result.get("idea_type", ""),
                )
                st.session_state["sv_montage"]     = plan
                st.session_state["sv_result"]      = _sv_compat
                st.success(f"Plan de montage Version {_selected_v} prêt.")
                st.rerun()
            except Exception as _e:
                st.error(f"Erreur : {_e}")


def _render_script_result(
    sv: dict, root: Path, gen_available: bool,
    generate_caption, generate_montage_plan, build_yaml_from_viral_script,
    get_pexels_videos, save_hook_result, self_check, optimize_script_hooks,
) -> None:
    hr()
    # ── Idea type badge ────────────────────────────────────────────────────────
    _ilabel = sv.get("idea_type_label", "")
    _iangle = sv.get("idea_angle", "")
    _iconf  = sv.get("idea_confidence", 0)
    if _ilabel:
        _conf_pct   = int(_iconf * 100)
        _conf_color = "#4ade80" if _iconf >= 0.6 else "#facc15" if _iconf >= 0.4 else "#94a3b8"
        st.markdown(
            f'<div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.75rem;flex-wrap:wrap">'
            f'<span style="background:#F5F5F7;border:1px solid #E0E0E8;border-radius:20px;padding:3px 10px;font-size:.72rem;font-weight:700;color:#1A1A2E">📂 {_ilabel}</span>'
            f'<span style="background:#FFF8EC;border:1px solid #E8B84B;border-radius:20px;padding:3px 10px;font-size:.72rem;font-weight:700;color:#C8972A">⚡ {_iangle}</span>'
            f'<span style="font-size:.68rem;color:{_conf_color};font-weight:600">confiance {_conf_pct}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Best hook ──────────────────────────────────────────────────────────────
    st.markdown("### 1. Best Hook")
    best = sv.get("best_hook", {})
    best_score = best.get("score", 0)
    st.markdown(
        f'<div class="hook-winner" style="margin-bottom:.5rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
        f'<span style="font-size:.72rem;color:#C8972A;font-weight:700">BEST HOOK</span>'
        f'<span style="font-size:1rem;font-weight:800;color:#E8B84B">Score {best_score}</span></div>'
        f'<div style="font-size:1.25rem;font-weight:800;color:#1A1A2E;margin-bottom:6px">"{best.get("text","")}"</div>'
        f'<div style="font-size:.82rem;color:#6B6B8A">{best.get("reason","")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── All hooks ──────────────────────────────────────────────────────────────
    all_hooks = sv.get("hooks", [])
    if all_hooks:
        with st.expander(f"Voir les {len(all_hooks)} hooks générés", expanded=False):
            for h in sorted(all_hooks, key=lambda x: x.get("score", 0), reverse=True):
                sc  = h.get("score", 0)
                col = "#4ade80" if sc >= 8 else "#facc15" if sc >= 6 else "#f87171"
                st.markdown(
                    f'<div style="display:flex;gap:.75rem;align-items:flex-start;padding:.45rem 0;border-bottom:1px solid #F0F0F5;">'
                    f'<span style="min-width:32px;font-size:1rem;font-weight:800;color:{col}">{sc}</span>'
                    f'<div><div style="font-weight:600;color:#1A1A2E">"{h.get("text","")}"</div>'
                    f'<div style="font-size:.72rem;color:#6B6B8A">{h.get("type","").upper()} — {h.get("why","")}</div></div></div>',
                    unsafe_allow_html=True,
                )

    # ── Hook optimizer ─────────────────────────────────────────────────────────
    sv_optimized = st.session_state.get("sv_optimized")
    if sv_optimized:
        _render_hook_optimizer(sv_optimized, save_hook_result, optimize_script_hooks)

    hr()
    # ── Script ─────────────────────────────────────────────────────────────────
    st.markdown("### 2. Script")

    # Check if QC rewrote the script
    _qc = st.session_state.get("sv_qc_result", {})
    _qc_rewritten = isinstance(_qc, dict) and _qc.get("status") == "rewritten"
    if _qc_rewritten:
        _orig  = _qc.get("original_score", "?")
        _final = _qc.get("final_score", "?")
        _weak  = ", ".join(_qc.get("weak_dimensions", []))
        _flags = " · ".join(_qc.get("boring_flags", []))
        st.markdown(
            f'<div style="background:#FFF7ED;border-left:4px solid #fb923c;border-radius:0 8px 8px 0;'
            f'padding:.6rem 1rem;margin-bottom:.75rem;font-size:.82rem">'
            f'<span style="font-weight:700;color:#fb923c">🔄 QC Auto-rewrite</span> '
            f'<span style="color:#92400E">Score {_orig}/10 → <b>{_final}/10</b></span>'
            + (f'<div style="color:#B45309;margin-top:2px">Détecté : {_flags}</div>' if _flags else "")
            + f'</div>',
            unsafe_allow_html=True,
        )
        script = _qc.get("script", sv.get("script", {}))
    else:
        script = sv.get("script", {})

    _scene_keys = [
        ("Hook", "hook", "#f87171"), ("Tension", "tension", "#fb923c"),
        ("Shift", "shift", "#facc15"), ("Proof", "proof", "#a78bfa"),
        ("Solution", "solution", "#4ade80"), ("Résultat", "result", "#60a5fa"),
        ("CTA", "cta", "#c084fc"),
    ]
    for label, key, color in _scene_keys:
        text = script.get(key, "")
        if text:
            st.markdown(
                f'<div style="display:flex;gap:.75rem;align-items:flex-start;padding:.5rem 0;border-bottom:1px solid #F0F0F5;">'
                f'<span style="min-width:72px;font-weight:700;font-size:.82rem;color:{color}">{label}</span>'
                f'<span style="color:#1A1A2E;font-size:.92rem">{text}</span></div>',
                unsafe_allow_html=True,
            )

    # ── Quality score + Viral Simulator ───────────────────────────────────────
    _q_score  = sv.get("quality_score", sv.get("score", {}).get("total"))
    _vp       = sv.get("viral_prediction", sv.get("viral_scores", {}))
    _sv_status = sv.get("status", "")

    if _q_score or _vp:
        _q_color = "#4ade80" if (_q_score or 0) >= 8 else "#fb923c" if (_q_score or 0) >= 6 else "#f87171"
        _global  = _vp.get("global_score", 0) if _vp else 0
        _g_color = "#4ade80" if _global >= 8 else "#fb923c" if _global >= 6 else "#f87171"
        _status_badge = (
            '<span style="background:#dcfce7;color:#166534;font-size:.7rem;font-weight:700;'
            'padding:2px 8px;border-radius:12px">✓ validé</span>'
            if _sv_status == "validated" else
            '<span style="background:#FFF7ED;color:#92400E;font-size:.7rem;font-weight:700;'
            'padding:2px 8px;border-radius:12px">🔄 réécrit</span>'
            if _sv_status == "rewritten" else ""
        )
        _vp_items = [
            ("Stop scroll", "scroll_stop"), ("Watch time", "watch_time"),
            ("Partage",     "shareability"), ("Commentaire", "comment_trigger"),
            ("Pertinence",  "relevance"),
        ]
        _vp_html = ""
        if _vp:
            _vp_html = (
                '<div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-top:.5rem;padding-top:.5rem;'
                'border-top:1px solid #E5E5EA">'
                + "".join(
                    f'<div style="text-align:center;min-width:60px">'
                    f'<div style="font-size:1rem;font-weight:800;color:{"#4ade80" if _vp.get(k,0)>=7 else "#fb923c" if _vp.get(k,0)>=5 else "#f87171"}">'
                    f'{_vp.get(k,0)}</div>'
                    f'<div style="font-size:.65rem;color:#6B6B8A;margin-top:1px">{lbl}</div></div>'
                    for lbl, k in _vp_items
                )
                + "</div>"
            )
        st.markdown(
            f'<div style="background:#F5F5F7;border-radius:10px;padding:.6rem 1rem;margin-top:.5rem">'
            f'<div style="display:flex;align-items:center;gap:1rem">'
            f'<div><div style="font-size:.65rem;color:#6B6B8A;margin-bottom:1px">Qualité</div>'
            f'<span style="font-size:1.4rem;font-weight:900;color:{_q_color}">{_q_score}/10</span></div>'
            + (f'<div><div style="font-size:.65rem;color:#6B6B8A;margin-bottom:1px">Viral score</div>'
               f'<span style="font-size:1.4rem;font-weight:900;color:{_g_color}">{_global}/10</span></div>'
               if _global else "")
            + f'{_status_badge}</div>{_vp_html}</div>',
            unsafe_allow_html=True,
        )

    why = sv.get("why_it_performs", "")
    if why:
        st.markdown(
            f'<div class="callout callout-info" style="margin-top:.5rem">'
            f'<span style="font-weight:700">Pourquoi ça va performer :</span> {why}</div>',
            unsafe_allow_html=True,
        )

    hr()
    # ── Caption ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📣 Étape 2 — Caption Instagram</div>', unsafe_allow_html=True)
    _cap_lang   = st.session_state.get("sv_lang", "fr")
    _cap_stored = st.session_state.get("sv_caption", "")
    _cap_c1, _cap_c2 = st.columns([1, 3])
    with _cap_c1:
        if st.button("Générer le caption" if _cap_lang == "fr" else "Generate caption",
                     type="secondary", use_container_width=True, key="btn_sv_caption"):
            with st.spinner("Génération…"):
                try:
                    _cap_text = generate_caption(
                        st.session_state.get("sv_result", {}),
                        st.session_state.get("sv_montage", {}),
                        st.session_state.get("sv_idea_stored", ""),
                        lang=_cap_lang,
                        daily_context=st.session_state.get("sv_daily_context"),
                    )
                    st.session_state["sv_caption"] = _cap_text
                    _cap_stored = _cap_text
                except Exception as _ce:
                    st.error(f"Erreur : {_ce}")
    if _cap_stored:
        with _cap_c2:
            st.markdown(f'<div class="caption-box">{_cap_stored}</div>', unsafe_allow_html=True)
            st.text_area("caption_output", value=_cap_stored, height=1,
                         key="sv_caption_display", label_visibility="collapsed")
    else:
        with _cap_c2:
            st.markdown(
                '<div class="callout callout-info">Génère d\'abord le script, '
                'puis clique <strong>Générer le caption</strong>.</div>',
                unsafe_allow_html=True,
            )

    hr()
    # ── Visual details ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🎬 Détails visuels</div>', unsafe_allow_html=True)
    ov_col, info_col = st.columns(2)
    with ov_col:
        st.markdown('<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:.5rem">Overlay texte</div>', unsafe_allow_html=True)
        for line in sv.get("overlay_lines", []):
            st.markdown(f'<div class="overlay-pill">{line}</div>', unsafe_allow_html=True)
    with info_col:
        viral     = sv.get("viral_angle", {})
        emotion   = viral.get("emotion", "")
        mechanism = viral.get("mechanism", "")
        cta_opt   = sv.get("cta_optimized", "")
        st.markdown(
            f'<div style="display:flex;flex-direction:column;gap:6px">'
            f'<div style="background:var(--brand-light);border:1px solid var(--brand-border);border-radius:var(--r);padding:.55rem .75rem"><div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--brand);margin-bottom:2px">Émotion</div><div style="font-weight:600;color:var(--text);font-size:.875rem">{emotion}</div></div>'
            f'<div style="background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r);padding:.55rem .75rem"><div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:2px">Mécanisme</div><div style="color:var(--text-2);font-size:.85rem">{mechanism}</div></div>'
            f'<div style="background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r);padding:.55rem .75rem"><div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:2px">CTA optimisé</div><div style="font-weight:600;color:var(--text);font-size:.875rem">{cta_opt}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Aggressive variant ─────────────────────────────────────────────────────
    ab = sv.get("ab_variant", {})
    if ab:
        hr()
        with st.expander("⚡ Variante agressive (version C)", expanded=False):
            st.markdown(
                f'<div class="hook-rejected" style="margin-bottom:.75rem"><div style="font-size:.72rem;color:#991b1b;font-weight:700;margin-bottom:4px">HOOK AGRESSIF</div>'
                f'<div style="font-size:1.1rem;font-weight:700;color:#1A1A2E">"{ab.get("hook","")}"</div></div>',
                unsafe_allow_html=True,
            )
            ab_cols = st.columns(len(ab.get("overlay_lines", [])) or 1)
            for col, line in zip(ab_cols, ab.get("overlay_lines", [])):
                with col:
                    st.markdown(
                        f'<div style="background:#1A1A2E;color:#f87171;font-weight:700;font-size:.9rem;padding:.4rem;border-radius:6px;text-align:center">{line}</div>',
                        unsafe_allow_html=True,
                    )
            st.caption(f"Pourquoi plus agressif : {ab.get('why','')}")

    hr()
    # ── Montage plan ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🎬 Étape 3 — Plan de montage</div>', unsafe_allow_html=True)
    st.caption("Une scène = une phrase · min 2.5 s · animations sur le texte uniquement.")

    montage_col1, montage_col2 = st.columns([3, 1])
    with montage_col2:
        if st.button("Générer le montage", type="primary", use_container_width=True, key="btn_montage"):
            with st.spinner("Génération du plan de montage…"):
                try:
                    _cur_lang = st.session_state.get("sv_lang", "fr")
                    plan = generate_montage_plan(sv.get("script", {}), lang=_cur_lang,
                                                 idea_type=sv.get("idea_type", ""))
                    st.session_state["sv_montage"] = plan
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

    montage = st.session_state.get("sv_montage")
    if montage:
        _render_montage_and_render(montage, root, sv, build_yaml_from_viral_script,
                                   get_pexels_videos, self_check)


def _render_hook_optimizer(sv_optimized: dict, save_hook_result, optimize_script_hooks) -> None:
    _weak  = sv_optimized.get("weak_count", 0)
    _rewr  = sv_optimized.get("rewritten", 0)
    _best  = sv_optimized.get("best", {}) or {}
    _vars  = sv_optimized.get("variants", {})
    _hist  = sv_optimized.get("top_history", [])
    _ranked = sv_optimized.get("ranked", [])

    _badge_color = "#d1fae5" if _weak == 0 else "#fef9c3" if _weak <= 2 else "#fee2e2"
    _badge_icon  = "✅" if _weak == 0 else "⚠️"
    st.markdown(
        f'<div style="background:{_badge_color};border-radius:8px;padding:.4rem .8rem;margin:.5rem 0;font-size:.82rem">'
        f'{_badge_icon} <strong>Hook Optimizer</strong> — {_weak} hook(s) faible(s) détecté(s)'
        f'{f" · {_rewr} réécrit(s) via API" if _rewr else ""}'
        f' · Score local best : <strong>{_best.get("total_score","—")}/10</strong></div>',
        unsafe_allow_html=True,
    )

    with st.expander("🎯 Hooks optimisés — Variantes A / B / C", expanded=True):
        _v_labels = {
            "A": ("Simple", "#60a5fa", "#EFF6FF"),
            "B": ("Intrigue", "#facc15", "#FEFCE8"),
            "C": ("Interruption", "#f87171", "#FFF1F2"),
        }
        _opt_cols = st.columns(3)
        for _col, _v in zip(_opt_cols, ("A", "B", "C")):
            with _col:
                _vh = _vars.get(_v) or {}
                _vlabel, _vcolor, _vbg = _v_labels[_v]
                _sc  = _vh.get("total_score", "—")
                _bst = _vh.get("history_boost", 0)
                _wk  = _vh.get("is_weak", False)
                _rw  = _vh.get("was_rewritten", False)
                _txt = _vh.get("text", "—")
                _tag = ""
                if _rw:
                    _tag = ' <span style="font-size:.65rem;background:#d1fae5;color:#065f46;padding:1px 5px;border-radius:8px">réécrit</span>'
                elif _wk:
                    _tag = ' <span style="font-size:.65rem;background:#fee2e2;color:#991b1b;padding:1px 5px;border-radius:8px">faible</span>'
                st.markdown(
                    f'<div style="background:{_vbg};border:1px solid {_vcolor};border-radius:8px;padding:.6rem;height:100%">'
                    f'<div style="font-size:.68rem;font-weight:700;color:{_vcolor};margin-bottom:4px">VERSION {_v} — {_vlabel}</div>'
                    f'<div style="font-weight:700;color:#1A1A2E;font-size:.92rem;margin-bottom:6px">"{_txt}"{_tag}</div>'
                    f'<div style="font-size:.72rem;color:#6B6B8A">Score {_sc}/10{f" · +{_bst} hist." if _bst > 0 else ""}</div></div>',
                    unsafe_allow_html=True,
                )

        if _ranked:
            st.markdown('<div style="font-size:.78rem;font-weight:700;color:#6B6B8A;margin:.75rem 0 .3rem 0">Classement complet</div>', unsafe_allow_html=True)
            for _r in _ranked:
                _rtxt = _r.get("text", "")
                _rsc  = _r.get("total_score", 0)
                _rv   = _r.get("variant", "A")
                _rwk  = _r.get("is_weak", False)
                _rcol = "#4ade80" if _rsc >= 8 else "#facc15" if _rsc >= 6 else "#f87171"
                _rvar_color = _v_labels[_rv][1]
                _weak_mark  = " ⚠" if _rwk else ""
                st.markdown(
                    f'<div style="display:flex;gap:.6rem;align-items:center;padding:.3rem 0;border-bottom:1px solid #F5F5F7;">'
                    f'<span style="min-width:30px;font-weight:800;font-size:.9rem;color:{_rcol}">{_rsc}</span>'
                    f'<span style="min-width:18px;font-size:.7rem;font-weight:700;color:{_rvar_color}">{_rv}</span>'
                    f'<span style="color:#1A1A2E;font-size:.85rem">{_rtxt}{_weak_mark}</span></div>',
                    unsafe_allow_html=True,
                )

        if _hist:
            st.markdown('<div style="font-size:.78rem;font-weight:700;color:#C8972A;margin:.75rem 0 .3rem 0">🏆 Top performers historiques</div>', unsafe_allow_html=True)
            for _hp in _hist:
                st.markdown(
                    f'<div style="background:#FFF8EC;border-radius:6px;padding:.25rem .6rem;margin-bottom:3px;font-size:.82rem;color:#1A1A2E">"{_hp}"</div>',
                    unsafe_allow_html=True,
                )

        if _weak > 0 and _rewr == 0:
            st.markdown("")
            if st.button(f"✍️ Réécrire les {_weak} hooks faibles via Claude", type="secondary",
                         use_container_width=True, key="btn_rewrite_hooks"):
                with st.spinner("Réécriture en cours…"):
                    try:
                        _sv_cur = st.session_state.get("sv_result", {})
                        _opt2 = optimize_script_hooks(_sv_cur, use_api_rewrite=True)
                        st.session_state["sv_optimized"] = _opt2
                        st.rerun()
                    except Exception as _re:
                        st.error(f"Erreur réécriture : {_re}")

    # ── Performance saver ──────────────────────────────────────────────────────
    with st.expander("📊 Sauvegarder la performance d'un hook", expanded=False):
        st.caption("Enregistre les résultats réels pour améliorer le scoring futur.")
        _perf_hook = st.selectbox("Hook", options=[r.get("text", "") for r in _ranked], key="perf_hook_sel")
        _pc1, _pc2, _pc3 = st.columns(3)
        with _pc1:
            _perf_views    = st.number_input("Vues",         min_value=0, value=0, step=100,  key="perf_views")
        with _pc2:
            _perf_likes    = st.number_input("Likes",        min_value=0, value=0, step=10,   key="perf_likes")
        with _pc3:
            _perf_comments = st.number_input("Commentaires", min_value=0, value=0, step=1,    key="perf_comments")
        if st.button("💾 Sauvegarder", type="secondary", use_container_width=True, key="btn_save_perf"):
            if _perf_hook:
                try:
                    save_hook_result(_perf_hook, int(_perf_views), int(_perf_likes), int(_perf_comments))
                    st.success(f'Performance enregistrée pour : "{_perf_hook}"')
                except Exception as _se:
                    st.error(f"Erreur sauvegarde : {_se}")


def _render_montage_and_render(montage: dict, root: Path, sv: dict,
                                build_yaml_from_viral_script, get_pexels_videos, self_check) -> None:
    total = montage.get("total_duration", 0)
    val   = montage.get("validation", {})
    all_ok    = all(val.values()) if val else False
    val_class = "callout-success" if all_ok else "callout-warning"
    val_icon  = "✅" if all_ok else "⚠️"
    checks_parts = " · ".join(f"{'✓' if v else '✗'} {k.replace('_',' ')}" for k, v in val.items())
    st.markdown(
        f'<div class="callout {val_class}">{val_icon} <strong>{total}s</strong> &nbsp;·&nbsp; {checks_parts}</div>',
        unsafe_allow_html=True,
    )

    pexels_q = montage.get("pexels_queries", [])
    if pexels_q:
        pills = "".join(
            f'<span style="background:var(--info-bg);color:var(--info);border:1px solid var(--info-bd);border-radius:var(--r-full);padding:2px 9px;font-size:.72rem;font-weight:600">{q}</span>'
            for q in pexels_q
        )
        st.markdown(
            f'<div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:.75rem">'
            f'<span style="font-size:.72rem;font-weight:700;color:var(--text-muted);padding-top:3px">🎬 Pexels :</span>{pills}</div>',
            unsafe_allow_html=True,
        )

    # Timeline
    ANIM_ICONS = {"fade_in":"✨","slide_in":"↑","slide":"↑","slide_up":"↑","typing":"⌨️","pop":"💥","fade_out":"↓"}
    TYPE_COLORS = {"hook":"#EF4444","pain":"#F97316","twist":"#EAB308","solution":"#10B981","result":"#3B82F6","cta":"#8B5CF6"}
    scenes = montage.get("scenes", [])
    rows_html = ""
    for idx, scene in enumerate(scenes):
        stype    = scene.get("type", "")
        duration = scene.get("duration", 2.5)
        text     = scene.get("text", "")
        kw       = scene.get("keyword_highlight", "")
        anim     = scene.get("text_animation", scene.get("animation", "fade_in"))
        emphasis = scene.get("emphasis", False)
        color    = TYPE_COLORS.get(stype, "#6B7280")
        anim_icon = ANIM_ICONS.get(anim, "▶")
        display_text = text
        if kw and kw in text:
            display_text = text.replace(kw, f'<span style="color:var(--brand);font-weight:800">{kw}</span>')
        if emphasis:
            display_text = f'<strong>{display_text}</strong>'
        rows_html += (
            f'<div class="montage-row">'
            f'<div class="montage-idx">{idx+1}</div>'
            f'<div class="montage-type" style="color:{color}">{stype}</div>'
            f'<div class="montage-text">{display_text}</div>'
            f'<div class="montage-anim">{anim_icon} {anim}</div>'
            f'<div class="montage-dur">{duration}s</div>'
            f'</div>'
        )
    st.markdown(f'<div class="montage-table">{rows_html}</div>', unsafe_allow_html=True)

    hr()
    # ── Pexels download ────────────────────────────────────────────────────────
    pexels_queries = montage.get("pexels_queries", [])
    _has_pexels_key = bool(os.environ.get("PEXELS_API_KEY", ""))
    _pexels_paths = st.session_state.get("sv_pexels_paths", [])

    if pexels_queries:
        pcol1, pcol2 = st.columns([3, 1])
        with pcol1:
            if _pexels_paths:
                st.markdown(
                    f'<div style="background:#d1fae5;border-radius:8px;padding:.4rem .8rem;font-size:.82rem">'
                    f'🎬 <strong>{len(_pexels_paths)} vidéo(s) Pexels prête(s)</strong> : '
                    + " · ".join(f'`{Path(p).name}`' for p in _pexels_paths) + "</div>",
                    unsafe_allow_html=True,
                )
            elif _has_pexels_key:
                st.info(f"📥 **{len(pexels_queries)} vidéos Pexels** prêtes à télécharger — clique sur le bouton →")
            else:
                st.warning("⚠️ `PEXELS_API_KEY` non configurée — vidéos locales utilisées.")
        with pcol2:
            if _has_pexels_key:
                if st.button("📥 Télécharger Pexels", use_container_width=True, key="sv_pexels"):
                    with st.spinner("Téléchargement…"):
                        try:
                            paths = get_pexels_videos(pexels_queries, max_videos=3)
                            st.session_state["sv_pexels_paths"] = paths
                            st.success(f"{len(paths)} vidéo(s) téléchargée(s)")
                        except Exception as _pe:
                            st.error(f"Pexels : {_pe}")

    hr()
    # ── Voiceover section ──────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🎙️ Étape 3.5 — Voix-off ElevenLabs</div>', unsafe_allow_html=True)
    _render_voiceover_section(montage, sv, root)

    hr()
    # ── Generate reel ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🚀 Étape 4 — Générer le Reel</div>', unsafe_allow_html=True)
    _render_reel_generation(sv, montage, root, _pexels_paths, build_yaml_from_viral_script, self_check)


def _render_voiceover_section(montage: dict, sv: dict, root: Path) -> None:
    _vo_path_existing = st.session_state.get("sv_voiceover_path", "")
    _raw_scenes = [sc for sc in montage.get("scenes", [])
                   if sc.get("text") and sc.get("type") != "gold_outro"]

    if "sv_scene_texts" not in st.session_state or \
            len(st.session_state["sv_scene_texts"]) != len(_raw_scenes):
        st.session_state["sv_scene_texts"] = [str(sc.get("text", "")) for sc in _raw_scenes]

    with st.expander("✏️ Éditer le texte de chaque scène", expanded=False):
        _edited_scene_texts = []
        for _si, _sc in enumerate(_raw_scenes):
            _sc_type = _sc.get("type", "scene")
            _default_txt = st.session_state["sv_scene_texts"][_si]
            _new_txt = st.text_input(f"Scène {_si+1} [{_sc_type}]", value=_default_txt,
                                     key=f"sv_scene_text_{_si}")
            _edited_scene_texts.append(_new_txt)
        st.session_state["sv_scene_texts"] = _edited_scene_texts

    _vo_text_default = " ".join(st.session_state["sv_scene_texts"])

    _VOICES = {
        "Sarah — claire, pro (fr/en)": "EXAVITQu4vr4xnSDxMaL",
        "Adam — profond, autorité":    "pNInz6obpgDQGcFmaJgB",
        "Antoni — naturel, convers.":  "ErXwobaYiN019PkySvjV",
        "Laurent - Warm, friendly":    "necQJzI1X0vLpdnJteap",
    }

    _vo_col1, _vo_col2 = st.columns([3, 1])
    with _vo_col1:
        _vo_text = st.text_area("Texte complet (mode MP3 unique)", value=_vo_text_default,
                                height=100, key="sv_vo_text_area",
                                help="Concaténation des scènes. Modifiable librement.")
    with _vo_col2:
        _vo_voice_label = st.selectbox("Voix", list(_VOICES.keys()), key="sv_vo_voice")
        _vo_voice_id    = _VOICES[_vo_voice_label]
        _vo_speed       = st.slider("Vitesse", 0.7, 1.3, 1.0, 0.05, key="sv_vo_speed")
        _vo_stability   = st.slider("Stabilité", 0.2, 1.0, 0.5, 0.05, key="sv_vo_stability")

    _toggle_col1, _toggle_col2 = st.columns(2)
    with _toggle_col1:
        _vo_sync_mode = st.toggle("Mode synchronisé (une voix par scène)",
                                  value=st.session_state.get("sv_vo_sync_mode", False),
                                  key="sv_vo_sync_toggle")
        st.session_state["sv_vo_sync_mode"] = _vo_sync_mode
    with _toggle_col2:
        _bg_music_on = st.toggle("Musique de fond",
                                 value=st.session_state.get("sv_bg_music_on", False),
                                 key="sv_bg_music_toggle")
        st.session_state["sv_bg_music_on"] = _bg_music_on

    _vo_btn_col, _vo_status_col = st.columns([1, 2])
    with _vo_btn_col:
        _btn_vo = st.button("Générer la voix-off", type="primary",
                            use_container_width=True, key="btn_gen_vo")

    if _btn_vo:
        if not _vo_text.strip():
            st.warning("Le texte de la voix-off est vide.")
        else:
            _idea_slug = re.sub(r"[^\w]", "_",
                                st.session_state.get("sv_idea_stored", "reel").lower())[:30]
            _vo_out = Path("assets/voiceover") / f"{_idea_slug}.mp3"
            _vo_cfg = {
                "title": _idea_slug,
                "voiceover": {
                    "text": _vo_text, "voice_id": _vo_voice_id,
                    "speed": _vo_speed, "stability": _vo_stability,
                    "similarity_boost": 0.75, "model_id": "eleven_multilingual_v2",
                },
            }
            with st.spinner("Génération de la voix-off via ElevenLabs..."):
                try:
                    from generate_voiceover import generate_voiceover, generate_scene_voiceovers
                    _el_key = (
                        os.environ.get("ELEVENLABS_API_KEY", "")
                        or st.secrets.get("ELEVENLABS_API_KEY", "")
                    ).strip().strip('"').strip("'")
                    if not _el_key:
                        st.error("ELEVENLABS_API_KEY non configurée. Ajoute-la dans `.env` ou `st.secrets`.")
                    else:
                        if _vo_sync_mode:
                            _edited_texts = st.session_state.get("sv_scene_texts", [])
                            _scenes_for_vo = [{"text": t} for t in _edited_texts if t.strip()]
                            _vo_scene_dir  = Path("assets/voiceover") / _idea_slug
                            _scene_results = generate_scene_voiceovers(
                                _scenes_for_vo, _vo_cfg["voiceover"],
                                output_dir=_vo_scene_dir, api_key=_el_key,
                            )
                            _scene_paths = [r["path"] for r in _scene_results]
                            st.session_state["sv_scene_voiceovers"] = _scene_paths
                            st.session_state["sv_voiceover_path"]   = ""
                            st.session_state["sv_voiceover_text"]   = _vo_text
                            _valid = sum(1 for p in _scene_paths if p)
                            st.success(f"Voix-off synchronisée : {_valid}/{len(_scenes_for_vo)} scènes")
                            for _item in _scene_results:
                                if _item["path"] and Path(_item["path"]).exists():
                                    st.audio(_item["path"], format="audio/mp3")
                        else:
                            _vo_result = generate_voiceover(_vo_cfg, output_path=_vo_out, api_key=_el_key)
                            st.session_state["sv_voiceover_path"]   = str(_vo_result)
                            st.session_state["sv_voiceover_text"]   = _vo_text
                            st.session_state["sv_scene_voiceovers"] = []
                            _vo_path_existing = str(_vo_result)
                            st.success(f"Voix-off prête : `{_vo_result.name}` ({_vo_result.stat().st_size // 1024} KB)")
                except Exception as _e:
                    st.error(f"Erreur inattendue : {_e}")

    if _vo_path_existing and Path(_vo_path_existing).exists():
        with _vo_status_col:
            st.audio(_vo_path_existing, format="audio/mp3")


def _render_reel_generation(sv: dict, montage: dict, root: Path, pexels_paths: list,
                             build_yaml_from_viral_script, self_check) -> None:
    idea_for_reel = st.session_state.get("sv_idea_stored", "")
    _reel_lang = st.session_state.get("sv_lang", "fr")
    reel_yaml, reel_slug = build_yaml_from_viral_script(
        sv, montage, idea_for_reel,
        video_paths=pexels_paths or None,
        lang=_reel_lang,
        voiceover_path=st.session_state.get("sv_voiceover_path", ""),
        scene_voiceovers=st.session_state.get("sv_scene_voiceovers") or None,
        bg_music_volume=0.28 if st.session_state.get("sv_bg_music_on") else 0.0,
    )

    try:
        _cfg_check = yaml.safe_load(reel_yaml) or {}
        _checks = self_check(_cfg_check)
        _all_ok = all(_checks.values())
        _chk_color = "#d1fae5" if _all_ok else "#fef9c3"
        _chk_icon  = "✅" if _all_ok else "⚠️"
        _chk_lines = " · ".join(f"{'✓' if v else '✗'} {k}" for k, v in _checks.items())
        st.markdown(
            f'<div style="background:{_chk_color};border-radius:8px;padding:.4rem .8rem;font-size:.80rem;margin-bottom:.5rem">'
            f'{_chk_icon} <strong>Self-check</strong> : {_chk_lines}</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    # Version tracking for YAML editor refresh
    _cur_vo  = st.session_state.get("sv_voiceover_path", "")
    _cur_svo = str(st.session_state.get("sv_scene_voiceovers", ""))
    _yaml_sig = _cur_vo + "|" + _cur_svo
    if _yaml_sig and st.session_state.get("sv_reel_yaml_vo") != _yaml_sig:
        st.session_state["sv_reel_edit_val"] = reel_yaml
        st.session_state["sv_reel_edit_v"] = st.session_state.get("sv_reel_edit_v", 0) + 1
        st.session_state["sv_reel_yaml_vo"] = _yaml_sig

    with st.expander("📄 YAML reel — modifiable", expanded=False):
        _sv_edit_v   = st.session_state.get("sv_reel_edit_v", 0)
        _sv_edit_val = st.session_state.get("sv_reel_edit_val", reel_yaml)
        sv_edited_yaml = st.text_area("sv_yaml_editor", value=_sv_edit_val, height=380,
                                      key=f"sv_yaml_editor_v{_sv_edit_v}",
                                      label_visibility="collapsed")
        try:
            yaml.safe_load(sv_edited_yaml)
        except Exception as _ye:
            st.warning(f"⚠️ YAML invalide : {_ye}")

    reel_path = root / "config" / "batch" / f"{reel_slug}.yaml"
    out_path  = root / "output" / f"{reel_slug}.mp4"

    btn_c1, btn_c2, btn_c3 = st.columns(3)
    with btn_c1:
        if st.button("💾 Sauvegarder YAML", type="secondary", use_container_width=True, key="sv_save_yaml"):
            reel_path.parent.mkdir(parents=True, exist_ok=True)
            reel_path.write_text(sv_edited_yaml, encoding="utf-8")
            st.success(f"Sauvegardé → `{reel_path.name}`")

    with btn_c2:
        if st.button("🔍 Preview PNG", type="secondary", use_container_width=True, key="sv_preview"):
            reel_path.parent.mkdir(parents=True, exist_ok=True)
            reel_path.write_text(sv_edited_yaml, encoding="utf-8")
            with st.spinner("Génération des aperçus…"):
                res = subprocess.run(
                    [sys.executable, "main.py", "--config", str(reel_path),
                     "--output", "output/", "--preview"],
                    cwd=str(root), capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
            if res.returncode == 0:
                tabs_p = st.tabs(["Intro", "Hook", "Prompt", "CTA"])
                for lbl, tab in zip(["intro", "hook", "prompt", "cta"], tabs_p):
                    with tab:
                        p = root / "output" / f"preview_{lbl}.png"
                        if p.exists():
                            st.image(str(p), use_container_width=True)
            else:
                st.error("Erreur preview")
                with st.expander("Logs"):
                    st.code(res.stderr or res.stdout)

    with btn_c3:
        if st.button("🚀 Générer le Reel", type="primary", use_container_width=True, key="sv_run_reel"):
            reel_path.parent.mkdir(parents=True, exist_ok=True)
            reel_path.write_text(sv_edited_yaml, encoding="utf-8")
            _est = max(60, int(montage.get("total_duration", 18) * 8))
            _n_scenes = len(montage.get("scenes", []))
            progress = st.progress(0, text="Chargement B-roll…")

            proc = subprocess.Popen(
                [sys.executable, "main.py", "--config", str(reel_path),
                 "--output", str(out_path)],
                cwd=str(root),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
            log_lines = []
            _state = {"cur": 0, "tot": _n_scenes or 1, "broll": False, "done": False}

            def _reader():
                for line in proc.stdout:
                    log_lines.append(line.rstrip())
                    if "Scène" in line:
                        try:
                            parts = line.split("Scène")[1].strip().split("/")
                            _state["cur"] = int(parts[0])
                            _state["tot"] = int(parts[1].split()[0])
                        except Exception:
                            pass
                    elif "B-roll chargé" in line:
                        _state["broll"] = True
                _state["done"] = True

            _reader_thread = threading.Thread(target=_reader, daemon=True)
            _reader_thread.start()
            _t0 = time.time()

            with st.spinner("Génération en cours…"):
                while not _state["done"]:
                    elapsed = time.time() - _t0
                    cur = _state["cur"]
                    tot = max(1, _state["tot"])
                    if cur > 0 and cur >= tot:
                        _scene_time = _est * 0.6
                        _enc_budget = max(1.0, _est * 0.4)
                        enc_pct = min(0.99, 0.60 + (elapsed - _scene_time) / _enc_budget * 0.39)
                        progress.progress(max(0.61, enc_pct), text=f"Encodage FFmpeg… {int(elapsed)}s / ~{_est}s")
                    elif cur > 0:
                        progress.progress(min(cur / tot * 0.60, 0.59), text=f"Scène {cur}/{tot}…")
                    elif _state["broll"]:
                        progress.progress(0.10, text="B-roll chargé, rendu des scènes…")
                    else:
                        progress.progress(min(0.08, elapsed / _est * 0.08), text=f"Chargement… {int(elapsed)}s")
                    time.sleep(0.5)

            _reader_thread.join(timeout=10)
            proc.wait()
            progress.progress(1.0, text="Terminé !")
            if proc.returncode == 0 and out_path.exists():
                st.success(f"Reel prêt — {out_path.stat().st_size // 1024} KB")
                with open(out_path, "rb") as _vf:
                    st.video(_vf.read())
                with open(out_path, "rb") as _f:
                    st.download_button("⬇️ Télécharger", data=_f, file_name=out_path.name,
                                       mime="video/mp4", type="primary", key="sv_dl")
            else:
                st.error("Génération échouée.")
                with st.expander("Logs"):
                    st.code("\n".join(log_lines[-30:]))
