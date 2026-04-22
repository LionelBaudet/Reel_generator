"""ui/components.py — Reusable UI atoms used across all pages."""
from __future__ import annotations
import streamlit as st


def page_header(eyebrow: str, title: str, sub: str = "") -> None:
    sub_html = f'<div class="page-header-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="page-header">'
        f'<div class="page-header-eyebrow">{eyebrow}</div>'
        f'<div class="page-header-title">{title}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def hr() -> None:
    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)


def section_title(text: str) -> None:
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def badge(text: str, kind: str = "info") -> str:
    """Return badge HTML (use inside unsafe_allow_html=True block)."""
    return f'<span class="badge badge-{kind}">{text}</span>'


def callout(text: str, kind: str = "info") -> None:
    st.markdown(f'<div class="callout callout-{kind}">{text}</div>', unsafe_allow_html=True)


def kpi_dashboard(items: list[dict]) -> None:
    """
    Render a 4-up KPI row.
    Each item: {label, value, sub?, accent?}
    """
    html = '<div class="kpi-dashboard">'
    for item in items:
        accent = "accent" if item.get("accent") else ""
        sub_html = f'<div class="kpi-card-sub">{item["sub"]}</div>' if item.get("sub") else ""
        html += (
            f'<div class="kpi-card {accent}">'
            f'<div class="kpi-card-label">{item["label"]}</div>'
            f'<div class="kpi-card-value">{item["value"]}</div>'
            f'{sub_html}'
            f'</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def empty_state(icon: str, title: str, sub: str = "") -> None:
    sub_html = f'<div class="empty-state-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="empty-state">'
        f'<div class="empty-state-icon">{icon}</div>'
        f'<div class="empty-state-title">{title}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def step_bar(steps: list[str], current: int) -> None:
    """
    Render a horizontal step progress bar.
    steps: list of step names. current: 0-indexed current step.
    """
    html = '<div class="step-bar">'
    for i, name in enumerate(steps):
        if i < current:
            cls = "done"
            num = "✓"
        elif i == current:
            cls = "active"
            num = str(i + 1)
        else:
            cls = ""
            num = str(i + 1)

        html += f'<div class="step-item {cls}"><div class="step-num">{num}</div>{name}</div>'
        if i < len(steps) - 1:
            conn_cls = "done" if i < current else ""
            html += f'<div class="step-connector {conn_cls}"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def api_error_banner(import_error: str = "") -> None:
    callout(
        "🔑 <strong>ANTHROPIC_API_KEY manquante</strong> — "
        "Configure la clé dans <code>.env</code> ou dans les secrets Streamlit Cloud.",
        kind="error",
    )
    if import_error:
        with st.expander("Détail de l'erreur d'import"):
            st.code(import_error)
