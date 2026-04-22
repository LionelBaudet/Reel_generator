"""
ui/pages/generate.py — "Idée → Reel" generate page.

Input comes from sidebar (topic, language, mode).
Generates 3 concept variants, shows KPI dashboard, concept cards,
YAML editor, hook optimizer, solution scorer, and render controls.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

import streamlit as st
import yaml

from ui.components import (
    api_error_banner, callout, empty_state, hr, kpi_dashboard, page_header,
    section_title,
)
from ui.display import render_video_section

_ANGLE_LABELS = {
    "frustration":  ("😤", "FRUSTRATION",  "#FFF1F2", "#DC2626", "#FEE2E2"),
    "gain":         ("⚡", "GAIN DE TEMPS", "#F0FDF4", "#059669", "#DCFCE7"),
    "social_proof": ("👀", "SOCIAL PROOF",  "#EFF6FF", "#2563EB", "#DBEAFE"),
}


def render(
    sidebar: dict,
    root: Path,
    gen_available: bool,
    gen_import_error: str = "",
) -> None:
    """Entry point called from streamlit_app.py."""
    page_header(
        eyebrow="Pipeline IA",
        title="Idée → Reel",
        sub="Décris ton idée dans la sidebar — Claude génère 3 concepts complets "
            "avec hook, script, YAML et caption, optimisés pour l'algorithme Instagram.",
    )

    if not gen_available:
        api_error_banner(gen_import_error)
        return

    pipeline_mode = sidebar.get("pipeline_mode", "standard")

    # ── Non-standard pipeline modes (News / Social / Trend) ───────────────────
    if pipeline_mode != "standard":
        _render_pipeline_mode(sidebar, root, pipeline_mode)
        return

    # ── Standard mode: trigger from sidebar button ─────────────────────────────
    if sidebar["generate_clicked"] and sidebar["topic"]:
        with st.spinner(f"Génération de 3 concepts pour « {sidebar['topic']} »…"):
            try:
                from generate import generate_variants
                variants = generate_variants(sidebar["topic"])
                st.session_state["auto_variants"]     = variants
                st.session_state["auto_idea"]         = sidebar["topic"]
                st.session_state["auto_language"]     = sidebar["language"]
                st.session_state["auto_mode"]         = sidebar["mode"]
                st.session_state.pop("auto_selected_idx", None)
                st.session_state.pop("auto_yaml", None)
                st.session_state.pop("auto_slug", None)
            except Exception as exc:
                st.error(f"Erreur API : {exc}")

    # ── Reset button ───────────────────────────────────────────────────────────
    if st.session_state.get("auto_variants"):
        if st.button("↺ Réinitialiser", type="secondary", key="btn_reset_variants"):
            for k in ["auto_variants", "auto_idea", "auto_selected_idx", "auto_yaml", "auto_slug"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Empty state ────────────────────────────────────────────────────────────
    variants = st.session_state.get("auto_variants")
    if not variants:
        empty_state(
            icon="💡",
            title="Tape ton idée dans la sidebar",
            sub="Claude génère 3 angles (frustration, gain, social proof) avec hook, "
                "script complet, YAML prêt-à-générer et caption Instagram.",
        )
        return

    idea_stored = st.session_state.get("auto_idea", "")

    # ── KPI dashboard ──────────────────────────────────────────────────────────
    best_hook = max(variants, key=lambda v: len(v.get("hook_text", "")), default={})
    kpi_dashboard([
        {"label": "Concepts générés", "value": str(len(variants)), "accent": True},
        {"label": "Sujet",             "value": idea_stored[:20] + "…" if len(idea_stored) > 20 else idea_stored},
        {"label": "Langue",            "value": st.session_state.get("auto_language", "fr").upper()},
        {"label": "Mode",              "value": st.session_state.get("auto_mode", "standard").capitalize()},
    ])

    hr()
    st.markdown(
        f'<div style="font-size:.85rem;color:var(--text-muted);margin-bottom:1rem">'
        f'3 concepts générés pour <strong style="color:var(--text)">{idea_stored}</strong>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Concept cards (3 columns) ──────────────────────────────────────────────
    cols = st.columns(3)
    for i, (variant, col) in enumerate(zip(variants, cols)):
        angle_key = variant.get("angle", "frustration")
        icon, label, hdr_bg, clr, bd = _ANGLE_LABELS.get(
            angle_key, ("🎯", angle_key.upper(), "#F8F9FA", "#374151", "#E5E7EB")
        )
        hook            = variant.get("hook_text", "")
        broll           = variant.get("broll_category", "—")
        saves           = variant.get("saves_time", "—")
        caption_preview = variant.get("caption", "")[:100]
        is_selected     = (st.session_state.get("auto_selected_idx") == i)
        card_extra      = "selected" if is_selected else ""

        with col:
            st.markdown(
                f'<div class="concept-card {card_extra}">'
                f'<div class="concept-card-header" style="background:{hdr_bg};border-bottom-color:{bd};">'
                f'<span style="font-size:0.78rem;font-weight:700;color:{clr}">{icon} {label}</span>'
                f'<span style="font-size:0.72rem;color:var(--text-muted)">#{i+1}</span>'
                f'</div>'
                f'<div class="concept-card-body">'
                f'<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.07em;color:var(--text-muted);margin-bottom:3px">Hook</div>'
                f'<div class="concept-card-hook">"{hook}"</div>'
                f'<div class="concept-card-meta">'
                f'<span>📹 {broll}</span><span>⏱️ {saves}</span>'
                f'</div>'
                f'<div class="concept-card-preview">{caption_preview}…</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            btn_label = "✓ Sélectionné" if is_selected else "Choisir ce concept"
            btn_type  = "primary" if is_selected else "secondary"
            if st.button(btn_label, key=f"select_variant_{i}", type=btn_type, use_container_width=True):
                from generate import build_yaml
                st.session_state["auto_selected_idx"] = i
                st.session_state["auto_yaml"]  = build_yaml(variant, idea_stored)
                st.session_state["auto_slug"]  = variant.get("slug", f"reel_auto_v{i+1}")
                st.rerun()

    # ── Selected concept detail ────────────────────────────────────────────────
    selected_idx = st.session_state.get("auto_selected_idx")
    yaml_content = st.session_state.get("auto_yaml")

    if selected_idx is None or yaml_content is None:
        return

    variant  = variants[selected_idx]
    slug     = st.session_state.get("auto_slug", "reel_auto")
    yaml_path = root / "config" / "batch" / f"{slug}.yaml"

    hr()
    st.markdown(f"### Concept sélectionné — *{variant.get('angle','').upper()}*")

    # ── YAML editor ───────────────────────────────────────────────────────────
    st.markdown("**📄 YAML — modifiable avant génération**")
    _edit_v   = st.session_state.get(f"yaml_edit_v_{selected_idx}", 0)
    _edit_val = st.session_state.get(f"yaml_edit_val_{selected_idx}", yaml_content)
    edited_yaml = st.text_area(
        label="yaml_editor",
        value=_edit_val,
        height=420,
        key=f"yaml_editor_{selected_idx}_v{_edit_v}",
        label_visibility="collapsed",
    )
    if edited_yaml != yaml_content:
        st.caption("✏️ Modifié — la version éditée sera utilisée pour la génération.")
        try:
            yaml.safe_load(edited_yaml)
        except Exception as _e:
            st.warning(f"⚠️ YAML invalide : {_e}")

    active_yaml = edited_yaml

    # ── Hook Optimizer ─────────────────────────────────────────────────────────
    hr()
    st.markdown("### 🎯 Hook Optimizer")
    st.caption("Analyse le hook et le remplace si le score < 7.5/10.")

    try:
        from utils.hook_optimizer import analyze_hook, inject_winner
        hook_optimizer_ok = True
    except ImportError:
        hook_optimizer_ok = False

    if hook_optimizer_ok:
        opt_c1, opt_c2 = st.columns([3, 1])
        with opt_c1:
            hook_to_analyze = st.text_input(
                "Hook à analyser",
                value=variant.get("hook_text", ""),
                key=f"hook_input_{selected_idx}",
                label_visibility="collapsed",
                placeholder="Hook à analyser…",
            )
        with opt_c2:
            run_optimizer = st.button("Analyser", type="primary",
                                      use_container_width=True, key=f"btn_optimize_{selected_idx}")

        if run_optimizer and hook_to_analyze.strip():
            with st.spinner("Analyse du hook…"):
                try:
                    analysis = analyze_hook(hook_to_analyze.strip(),
                                            context=st.session_state.get("auto_idea", ""))
                    st.session_state[f"hook_analysis_{selected_idx}"] = analysis
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

        analysis = st.session_state.get(f"hook_analysis_{selected_idx}")
        if analysis:
            _render_hook_analysis(analysis, selected_idx, active_yaml, _edit_v, inject_winner)

    # ── Solution Scorer ────────────────────────────────────────────────────────
    hr()
    st.markdown("### 💡 Solution Scorer")
    st.caption("Score la réponse IA affichée. Propose une version améliorée si < 7.5/10.")

    try:
        from utils.hook_optimizer import analyze_solution
        solution_ok = True
    except ImportError:
        solution_ok = False

    if solution_ok:
        sol_c1, sol_c2 = st.columns([3, 1])
        with sol_c1:
            solution_to_score = st.text_area(
                "Solution à scorer",
                value=variant.get("prompt_output", ""),
                height=160,
                key=f"solution_input_{selected_idx}",
                label_visibility="collapsed",
                placeholder="Colle ici la réponse IA à scorer…",
            )
        with sol_c2:
            run_sol_scorer = st.button("Scorer", type="primary",
                                       use_container_width=True, key=f"btn_score_solution_{selected_idx}")

        if run_sol_scorer and solution_to_score.strip():
            with st.spinner("Analyse de la solution…"):
                try:
                    sol_analysis = analyze_solution(solution_to_score.strip(),
                                                    context=st.session_state.get("auto_idea", ""))
                    st.session_state[f"sol_analysis_{selected_idx}"] = sol_analysis
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

        sol_analysis = st.session_state.get(f"sol_analysis_{selected_idx}")
        if sol_analysis:
            _render_solution_analysis(sol_analysis, selected_idx, active_yaml, _edit_v, yaml_content)

    # ── Caption ────────────────────────────────────────────────────────────────
    with st.expander("📣 Caption Instagram", expanded=False):
        st.text(variant.get("caption", ""))

    # ── Action buttons ─────────────────────────────────────────────────────────
    hr()
    act1, act2, act3 = st.columns(3)

    with act1:
        if st.button("💾 Sauvegarder YAML", type="secondary", use_container_width=True, key="auto_save"):
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text(active_yaml, encoding="utf-8")
            st.success(f"Sauvegardé → `{yaml_path.name}`")

    with act2:
        if st.button("🔍 Preview PNG", type="secondary", use_container_width=True, key="auto_preview"):
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text(active_yaml, encoding="utf-8")
            with st.spinner("Génération des aperçus…"):
                result = subprocess.run(
                    [sys.executable, "main.py", "--config", str(yaml_path),
                     "--output", "output/", "--preview"],
                    cwd=str(root), capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
            if result.returncode == 0:
                preview_files = {
                    "Intro":  root / "output" / "preview_intro.png",
                    "Hook":   root / "output" / "preview_hook.png",
                    "Prompt": root / "output" / "preview_prompt.png",
                    "CTA":    root / "output" / "preview_cta.png",
                }
                tabs_p = st.tabs(list(preview_files.keys()))
                for (lbl, path), tab in zip(preview_files.items(), tabs_p):
                    with tab:
                        if path.exists():
                            st.image(str(path), use_container_width=True)
            else:
                st.error("Erreur preview")
                with st.expander("Logs"):
                    st.code(result.stderr or result.stdout)

    with act3:
        if st.button("🚀 Générer le Reel", type="primary", use_container_width=True, key="auto_run"):
            _run_render(root, yaml_path, active_yaml, slug)


# ── Private helpers ────────────────────────────────────────────────────────────

def _render_hook_analysis(analysis: dict, idx: int, active_yaml: str,
                          edit_v: int, inject_winner_fn) -> None:
    score    = analysis.get("original_score", {})
    avg      = score.get("average", 0)
    verdict  = score.get("verdict", "")
    winner   = analysis.get("winner", "")
    w_score  = analysis.get("winner_score", 0)
    div_cls  = "hook-accepted" if verdict == "ACCEPTED" else "hook-rejected"
    icon     = "✅" if verdict == "ACCEPTED" else "❌"

    st.markdown(
        f'<div class="{div_cls}"><strong>{icon} {verdict}</strong> — '
        f'Score moyen : <strong>{avg}/10</strong></div>',
        unsafe_allow_html=True,
    )

    with st.expander("Détail des scores", expanded=(verdict == "REJECTED")):
        labels = {"scroll_stopping": "Scroll-stop", "clarity": "Clarté",
                  "curiosity": "Curiosité", "viral_potential": "Viral", "niche_fit": "Niche fit"}
        crit_cols = st.columns(5)
        for col, (key, label) in zip(crit_cols, labels.items()):
            val = score.get(key, 0)
            color = "#4ade80" if val >= 7.5 else "#f87171"
            with col:
                st.markdown(
                    f'<div style="text-align:center">'
                    f'<div style="font-size:1.4rem;font-weight:700;color:{color}">{val}</div>'
                    f'<div style="font-size:0.7rem;color:#6B6B8A">{label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    if verdict == "REJECTED" and analysis.get("alternatives"):
        with st.expander("10 alternatives générées", expanded=True):
            for alt in analysis["alternatives"]:
                bar_color = "#4ade80" if alt["score"] >= 7.5 else "#f59e0b"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:.75rem;'
                    f'padding:.5rem 0;border-bottom:1px solid #E0E0E8;">'
                    f'<span style="font-weight:700;color:{bar_color};min-width:32px">{alt["score"]}</span>'
                    f'<span style="flex:1;font-weight:600">"{alt["hook"]}"</span>'
                    f'<span style="font-size:.75rem;color:#6B6B8A;min-width:90px">{alt["style"]}</span>'
                    f'<span style="font-size:.75rem;color:#6B6B8A">{alt["why"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown(
        f'<div class="hook-winner">'
        f'<div style="font-size:.75rem;color:#6B6B8A;margin-bottom:4px">WINNER — {w_score}/10</div>'
        f'<div style="font-size:1.1rem;font-weight:700;color:#1A1A2E">"{winner}"</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    v1, v2 = st.columns(2)
    with v1:
        st.caption(f"🔥 Agressif : *{analysis.get('aggressive', '')}*")
    with v2:
        st.caption(f"🌍 Safe : *{analysis.get('safe', '')}*")

    if st.button("Injecter le winner dans le YAML", type="primary", key=f"inject_winner_{idx}"):
        try:
            current_cfg = yaml.safe_load(active_yaml) or {}
            updated_cfg = inject_winner_fn(current_cfg, analysis)
            buf = io.StringIO()
            yaml.dump(updated_cfg, buf, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)
            st.session_state[f"yaml_edit_val_{idx}"] = buf.getvalue()
            st.session_state[f"yaml_edit_v_{idx}"]   = edit_v + 1
            st.success("Hook injecté ✓")
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur injection : {exc}")


def _render_solution_analysis(sol: dict, idx: int, active_yaml: str,
                               edit_v: int, yaml_content: str) -> None:
    sol_scores  = sol.get("scores", {})
    sol_avg     = sol_scores.get("average", 0)
    sol_verdict = sol_scores.get("verdict", "")
    div_cls     = "hook-accepted" if sol_verdict == "GOOD" else "hook-rejected"
    icon        = "✅" if sol_verdict == "GOOD" else "⚠️"

    st.markdown(
        f'<div class="{div_cls}"><strong>{icon} {sol_verdict}</strong> — '
        f'Score moyen : <strong>{sol_avg}/10</strong></div>',
        unsafe_allow_html=True,
    )

    sol_labels = {"credibility": "Crédibilité", "save_worthy": "Save-worthy",
                  "clarity": "Clarté", "wow_factor": "WOW factor", "length_fit": "Longueur"}
    scols = st.columns(5)
    for col, (key, label) in zip(scols, sol_labels.items()):
        val = sol_scores.get(key, 0)
        color = "#4ade80" if val >= 7.5 else "#f87171"
        with col:
            st.markdown(
                f'<div style="text-align:center">'
                f'<div style="font-size:1.4rem;font-weight:700;color:{color}">{val}</div>'
                f'<div style="font-size:0.7rem;color:#6B6B8A">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    for issue in sol.get("issues", []):
        st.caption(f"⚠️ {issue}")

    improved = sol.get("improved_solution", "")
    if improved:
        with st.expander("Version améliorée", expanded=True):
            st.code(improved, language=None)
            st.caption(sol.get("improvement_notes", ""))

        if st.button("Injecter la solution améliorée dans le YAML", type="primary",
                     key=f"inject_solution_{idx}"):
            try:
                current_cfg = yaml.safe_load(active_yaml) or {}
                if "prompt" in current_cfg:
                    current_cfg["prompt"]["output_preview"] = improved
                buf = io.StringIO()
                yaml.dump(current_cfg, buf, allow_unicode=True,
                          default_flow_style=False, sort_keys=False)
                st.session_state[f"yaml_edit_val_{idx}"] = buf.getvalue()
                st.session_state[f"yaml_edit_v_{idx}"]   = edit_v + 1
                st.success("Solution injectée ✓")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur injection : {exc}")


def _render_pipeline_mode(sidebar: dict, root: Path, pipeline_mode: str) -> None:
    """Display for News / Social / Trend pipeline modes."""
    mode_labels = {
        "news":   ("📰", "News Pipeline",   "Flux RSS → Claude → Hook viral"),
        "social": ("📱", "Social Pipeline",  "Reddit + Google Trends → Hook viral"),
        "trend":  ("🔥", "Trend Pipeline",   "Social + News → Fusion → Hook viral"),
    }
    icon, label, sub = mode_labels.get(pipeline_mode, ("🎬", pipeline_mode.capitalize(), ""))

    page_header(eyebrow=label, title=f"{icon} {label}", sub=sub)

    topic = sidebar["topic"]

    # ── Trigger ────────────────────────────────────────────────────────────────
    if sidebar["generate_clicked"]:
        spinner_msg = (
            f"Analyse des tendances en cours{f' pour «{topic}»' if topic else ''}…"
        )
        with st.spinner(spinner_msg):
            try:
                from orchestrate import run_full_pipeline
                result = run_full_pipeline(
                    topic=topic,
                    news_mode=(pipeline_mode == "news"),
                    social_mode=(pipeline_mode == "social"),
                    trend_mode=(pipeline_mode == "trend"),
                    lang=sidebar["language"],
                    parallel=(sidebar["mode"] == "parallel"),
                    skip_video=sidebar["skip_video"],
                )
                st.session_state["pipeline_result"] = result
                st.session_state["pipeline_topic"]  = topic or result.get("run_id", "")
                st.session_state["pipeline_mode"]   = pipeline_mode
            except Exception as exc:
                st.error(f"Erreur pipeline : {exc}")
                return

    # ── Reset button ───────────────────────────────────────────────────────────
    if st.session_state.get("pipeline_result"):
        if st.button("↺ Réinitialiser", type="secondary", key="btn_reset_pipeline"):
            st.session_state.pop("pipeline_result", None)
            st.rerun()

    # ── Empty state ────────────────────────────────────────────────────────────
    result = st.session_state.get("pipeline_result")
    if not result:
        empty_state(
            icon=icon,
            title=f"Mode {label} actif",
            sub=(
                "Clique sur « Générer le Reel » dans la sidebar pour lancer l'analyse "
                "en temps réel et générer un hook viral basé sur les tendances du jour."
            ),
        )
        return

    # ── Error banner ───────────────────────────────────────────────────────────
    if result.get("error"):
        st.error(f"Erreur pipeline : {result['error']}")
        return

    topic_stored = st.session_state.get("pipeline_topic", "")

    # ── KPI dashboard ──────────────────────────────────────────────────────────
    score = result.get("score", 0)
    n_hooks = len(result.get("hooks", []))
    kpi_dashboard([
        {"label": "Score global",  "value": f"{score:.1f}/10", "accent": True},
        {"label": "Hooks générés", "value": str(n_hooks)},
        {"label": "Langue",        "value": sidebar["language"].upper()},
        {"label": "Mode",          "value": label},
    ])

    hr()

    # ── Best hook ──────────────────────────────────────────────────────────────
    best_hook = result.get("best_hook", "")
    if best_hook:
        section_title("Hook viral sélectionné")
        st.markdown(
            f'<div class="concept-card-hook" style="font-size:1.25rem;padding:1rem 1.25rem;'
            f'border-left:4px solid var(--gold);background:var(--surface-elevated);'
            f'border-radius:8px;margin-bottom:1rem">"{best_hook}"</div>',
            unsafe_allow_html=True,
        )

    # ── Top trends (trend/social mode) ─────────────────────────────────────────
    trends = result.get("trends") or {}
    top_topics = trends.get("top_topics", [])
    social = result.get("social") or {}
    social_trends = social.get("trends", [])

    if top_topics:
        with st.expander(f"🔥 Top {len(top_topics[:5])} tendances fusionnées", expanded=True):
            for t in top_topics[:5]:
                coverage = "📡 Social + News" if t.get("coverage_bonus") else (
                    "📱 Social" if "reddit" in t.get("source_mix", []) else "📰 News"
                )
                score_color = "#4ade80" if t.get("virality_score", 0) >= 7 else "#f59e0b"
                st.markdown(
                    f'<div style="display:flex;align-items:flex-start;gap:.75rem;'
                    f'padding:.6rem 0;border-bottom:1px solid var(--border)">'
                    f'<span style="font-weight:700;color:{score_color};min-width:24px;font-size:1.1rem">'
                    f'{t.get("virality_score","?")}</span>'
                    f'<div style="flex:1">'
                    f'<div style="font-weight:600">{t.get("topic","")}</div>'
                    f'<div style="font-size:.8rem;color:var(--text-muted)">'
                    f'{t.get("angle","")} — {coverage}'
                    f'</div></div></div>',
                    unsafe_allow_html=True,
                )
    elif social_trends:
        with st.expander(f"📱 Top {len(social_trends[:5])} tendances sociales", expanded=True):
            for t in social_trends[:5]:
                score_color = "#4ade80" if t.get("virality_score", 0) >= 7 else "#f59e0b"
                st.markdown(
                    f'<div style="display:flex;align-items:flex-start;gap:.75rem;'
                    f'padding:.5rem 0;border-bottom:1px solid var(--border)">'
                    f'<span style="font-weight:700;color:{score_color};min-width:24px">'
                    f'{t.get("virality_score","?")}</span>'
                    f'<div style="flex:1">'
                    f'<div style="font-weight:600">{t.get("title","")}</div>'
                    f'<div style="font-size:.8rem;color:var(--text-muted)">'
                    f'{t.get("source","").upper()} · {t.get("region","")}'
                    f'</div></div></div>',
                    unsafe_allow_html=True,
                )

    # ── Script sections ────────────────────────────────────────────────────────
    script = result.get("script") or {}
    if script:
        hr()
        section_title("Script généré")
        scene_labels = {
            "hook": ("🪝", "Hook"),
            "pain": ("😤", "Pain Point"),
            "shift": ("⚡", "Shift"),
            "solution": ("💡", "Solution"),
            "result": ("✅", "Résultat"),
            "cta": ("📣", "CTA"),
        }
        cols = st.columns(2)
        items = list(script.items())
        for i, (scene_type, scene_data) in enumerate(items):
            icon_s, label_s = scene_labels.get(scene_type, ("🎬", scene_type.upper()))
            text = scene_data.get("text", "") if isinstance(scene_data, dict) else str(scene_data)
            with cols[i % 2]:
                st.markdown(
                    f'<div style="padding:.75rem;background:var(--surface-elevated);'
                    f'border-radius:8px;margin-bottom:.6rem;'
                    f'border-left:3px solid var(--gold)">'
                    f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.07em;color:var(--text-muted);margin-bottom:3px">'
                    f'{icon_s} {label_s}</div>'
                    f'<div style="font-weight:600">{text}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── AI Insight ─────────────────────────────────────────────────────────────
    insight_data = result.get("insight") or {}
    insight_text = insight_data.get("insight", "")
    if insight_text:
        with st.expander("🤖 AI Insight", expanded=False):
            st.markdown(f"**Angle :** {insight_data.get('angle_type','').upper()}")
            st.markdown(f"> {insight_text}")
            if insight_data.get("example"):
                st.caption(f"Exemple : {insight_data['example']}")
            if insight_data.get("cta"):
                st.caption(f"CTA suggéré : {insight_data['cta']}")

    # ── Caption ────────────────────────────────────────────────────────────────
    caption = result.get("caption", "")
    if caption:
        with st.expander("📣 Caption Instagram", expanded=False):
            st.text(caption)

    # ── All hooks ─────────────────────────────────────────────────────────────
    hooks_list = result.get("hooks", [])
    if len(hooks_list) > 1:
        with st.expander(f"📋 Tous les hooks ({len(hooks_list)})", expanded=False):
            for h in hooks_list:
                hook_text = h.get("text") or h.get("hook", "")
                hook_score = h.get("total_score") or h.get("score", 0)
                color = "#4ade80" if hook_score >= 7 else "#f59e0b"
                st.markdown(
                    f'<div style="display:flex;gap:.75rem;padding:.4rem 0;'
                    f'border-bottom:1px solid var(--border)">'
                    f'<span style="font-weight:700;color:{color};min-width:28px">{hook_score}</span>'
                    f'<span>"{hook_text}"</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Render button ──────────────────────────────────────────────────────────
    video_path = result.get("video_path")
    if video_path and Path(video_path).exists():
        hr()
        st.success(f"Reel généré — {Path(video_path).stat().st_size // 1024} KB")
        with open(video_path, "rb") as vf:
            st.video(vf.read())
        with open(video_path, "rb") as f:
            st.download_button(
                "⬇️ Télécharger", data=f, file_name=Path(video_path).name,
                mime="video/mp4", type="primary", key="pipeline_dl",
            )
    elif not sidebar["skip_video"] and script:
        hr()
        if st.button("🚀 Générer le Reel vidéo", type="primary",
                     use_container_width=True, key="pipeline_render"):
            from orchestrate import HANDOFF_DIR
            config_path = HANDOFF_DIR / "04_scene_config.yaml"
            if config_path.exists():
                slug = f"reel_pipeline_{result.get('run_id','')}"
                yaml_path = root / "config" / "batch" / f"{slug}.yaml"
                import shutil
                shutil.copy(config_path, yaml_path)
                _run_render(root, yaml_path, yaml_path.read_text(encoding="utf-8"), slug)
            else:
                st.warning("La scène YAML n'a pas encore été générée. Lance d'abord le pipeline complet.")


def _run_render(root: Path, yaml_path: Path, active_yaml: str, slug: str) -> None:
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(active_yaml, encoding="utf-8")
    out_path = root / "output" / f"{slug}.mp4"

    progress = st.progress(0, text="Initialisation…")
    with st.spinner("Rendu en cours…"):
        proc = subprocess.Popen(
            [sys.executable, "main.py", "--config", str(yaml_path), "--output", str(out_path)],
            cwd=str(root),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        log_lines = []
        for line in proc.stdout:
            log_lines.append(line.rstrip())
            if "t:" in line and "%" in line:
                try:
                    pct = int(line.split("%")[0].split("|")[-1].strip().split()[-1])
                    progress.progress(min(pct, 99) / 100, text=f"Rendu : {pct}%")
                except Exception:
                    pass
        proc.wait()

    progress.progress(1.0, text="Terminé !")
    if proc.returncode == 0 and out_path.exists():
        st.success(f"Reel prêt — {out_path.stat().st_size // 1024} KB")
        with open(out_path, "rb") as vf:
            st.video(vf.read())
        with open(out_path, "rb") as f:
            st.download_button("⬇️ Télécharger", data=f, file_name=out_path.name,
                               mime="video/mp4", type="primary", key="auto_dl")
    else:
        st.error("La génération a échoué.")
        with st.expander("Logs"):
            st.code("\n".join(log_lines[-30:]))
