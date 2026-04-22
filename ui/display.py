"""ui/display.py — Render generated content: hooks, scripts, captions, optimization."""
from __future__ import annotations
import streamlit as st
from ui.components import hr, section_title


# ── Hooks ─────────────────────────────────────────────────────────────────────

def render_hooks(hooks: list[dict] | list[str], title: str = "Hooks générés") -> None:
    """Render a ranked list of hooks. Each item is either a str or {text, score, pattern}."""
    section_title(f"🎣 {title}")
    if not hooks:
        st.caption("Aucun hook disponible.")
        return

    for i, h in enumerate(hooks):
        if isinstance(h, str):
            text, score, pattern = h, None, None
        else:
            text    = h.get("text", h.get("hook", ""))
            score   = h.get("score") or h.get("avg_score")
            pattern = h.get("pattern")

        score_html = ""
        if score is not None:
            color = "#059669" if float(score) >= 7.5 else ("#D97706" if float(score) >= 6 else "#DC2626")
            score_html = (
                f'<span style="font-size:0.75rem;font-weight:700;color:{color};'
                f'background:rgba(0,0,0,.04);padding:1px 6px;border-radius:4px;margin-left:6px">'
                f'{score:.1f}</span>'
            )
        pattern_html = ""
        if pattern:
            pattern_html = f'<span style="font-size:0.68rem;color:var(--text-faint);margin-left:6px">{pattern}</span>'

        rank_color = "#D4A843" if i == 0 else "var(--text-faint)"
        bg = "var(--brand-light)" if i == 0 else "var(--surface)"
        border = "var(--brand-border)" if i == 0 else "var(--border)"

        st.markdown(
            f'<div style="background:{bg};border:1.5px solid {border};border-radius:8px;'
            f'padding:0.65rem 0.9rem;margin-bottom:6px;display:flex;align-items:flex-start;gap:0.6rem;">'
            f'<span style="font-size:0.7rem;font-weight:800;color:{rank_color};'
            f'padding-top:2px;flex-shrink:0;min-width:16px">#{i+1}</span>'
            f'<span style="font-size:0.9rem;font-weight:{"700" if i==0 else "500"};'
            f'color:var(--text);flex:1;line-height:1.4">{text}</span>'
            f'{score_html}{pattern_html}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Script ────────────────────────────────────────────────────────────────────

_SCENE_COLORS = {
    "hook":      "#D97706",
    "tension":   "#DC2626",
    "shift":     "#2563EB",
    "solution":  "#059669",
    "résultat":  "#059669",
    "result":    "#059669",
    "cta":       "#7C3AED",
    "caption":   "#6B7280",
}

def render_script(script: dict | str, title: str = "Script") -> None:
    """Render a structured script dict or plain string."""
    section_title(f"📄 {title}")

    if isinstance(script, str):
        st.markdown(
            f'<div class="caption-box" style="font-family:monospace;font-size:0.85rem">{script}</div>',
            unsafe_allow_html=True,
        )
        return

    if not script:
        st.caption("Aucun script disponible.")
        return

    lines_html = ""
    for key, value in script.items():
        if not value:
            continue
        label = key.upper()
        color = _SCENE_COLORS.get(key.lower(), "var(--text-muted)")
        lines_html += (
            f'<div class="script-line">'
            f'<div class="script-label" style="color:{color}">{label}</div>'
            f'<div class="script-text">{value}</div>'
            f'</div>'
        )

    if lines_html:
        st.markdown(
            f'<div class="script-block">{lines_html}</div>',
            unsafe_allow_html=True,
        )


# ── Caption ───────────────────────────────────────────────────────────────────

def render_caption(caption: str, title: str = "Caption Instagram") -> None:
    section_title(f"✍️ {title}")
    if not caption:
        st.caption("Aucune caption disponible.")
        return

    st.markdown(
        f'<div class="caption-box">{caption}</div>',
        unsafe_allow_html=True,
    )
    if st.button("📋 Copier", key="btn_copy_caption", type="secondary"):
        st.write(f"```\n{caption}\n```")
        st.toast("Caption copiée !", icon="✅")


# ── Optimization feedback ─────────────────────────────────────────────────────

def render_optimization(opt: dict, title: str = "Optimisation") -> None:
    section_title(f"⚡ {title}")
    if not opt:
        st.caption("Aucun feedback disponible.")
        return

    score = opt.get("score") or opt.get("overall_score")
    if score is not None:
        color = "#059669" if float(score) >= 7.5 else ("#D97706" if float(score) >= 6 else "#DC2626")
        st.markdown(
            f'<div style="font-size:2rem;font-weight:800;color:{color};line-height:1;margin-bottom:4px">'
            f'{score}<span style="font-size:1rem;color:var(--text-muted)">/10</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    feedback = opt.get("feedback") or opt.get("improvements") or opt.get("notes")
    if feedback:
        if isinstance(feedback, list):
            for item in feedback:
                st.markdown(f"- {item}")
        else:
            st.markdown(
                f'<div class="caption-box">{feedback}</div>',
                unsafe_allow_html=True,
            )

    strengths = opt.get("strengths")
    if strengths:
        st.markdown('<div style="margin-top:.5rem;font-size:.8rem;font-weight:700;color:var(--success)">Forces</div>', unsafe_allow_html=True)
        if isinstance(strengths, list):
            for s in strengths:
                st.markdown(f"- {s}")
        else:
            st.caption(str(strengths))


# ── Montage plan ──────────────────────────────────────────────────────────────

def render_montage(montage: list[dict], title: str = "Plan de montage") -> None:
    section_title(f"🎬 {title}")
    if not montage:
        st.caption("Aucun plan de montage disponible.")
        return

    rows_html = ""
    for i, scene in enumerate(montage):
        scene_type = scene.get("type", scene.get("scene_type", "scene")).upper()
        text = scene.get("text", scene.get("description", scene.get("content", "")))
        dur  = scene.get("duration", scene.get("dur", ""))
        anim = scene.get("animation", scene.get("transition", ""))

        dur_html  = f'<div class="montage-dur">{dur}s</div>'  if dur  else ""
        anim_html = f'<div class="montage-anim">{anim}</div>' if anim else ""
        rows_html += (
            f'<div class="montage-row">'
            f'<div class="montage-idx">{i+1}</div>'
            f'<div class="montage-type">{scene_type}</div>'
            f'<div class="montage-text">{text}</div>'
            f'{dur_html}{anim_html}'
            f'</div>'
        )

    st.markdown(
        f'<div class="montage-table">{rows_html}</div>',
        unsafe_allow_html=True,
    )


# ── Video preview ─────────────────────────────────────────────────────────────

def render_video_section(video_path: str | None, download_name: str = "reel.mp4") -> None:
    section_title("🎥 Vidéo finale")
    if not video_path:
        from pathlib import Path
        import streamlit as st
        st.caption("Aucune vidéo générée pour l'instant.")
        return

    from pathlib import Path as _P
    p = _P(video_path)
    if p.exists() and p.stat().st_size > 0:
        st.video(str(p))
        with open(p, "rb") as f:
            st.download_button(
                "⬇️ Télécharger",
                data=f,
                file_name=download_name,
                mime="video/mp4",
                type="primary",
                key=f"dl_video_{p.name}",
            )
    else:
        st.caption(f"Vidéo introuvable : `{video_path}`")
