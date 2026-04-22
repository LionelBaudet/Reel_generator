"""ui/memory_panel.py — Collapsible memory section (reel history + best hooks)."""
from __future__ import annotations
import json
from pathlib import Path

import streamlit as st
from ui.components import section_title


def render_memory_panel(root: Path) -> None:
    """Render the collapsible memory panel at the bottom of any page."""
    mem_dir = root / "memory"
    if not mem_dir.exists():
        return

    with st.expander("📊 Mémoire — Historique & meilleurs hooks", expanded=False):
        tab_hist, tab_hooks, tab_strat = st.tabs(["Historique reels", "Meilleurs hooks", "Stratégie"])

        # ── Reel score history ─────────────────────────────────────────────────
        with tab_hist:
            scores_file = mem_dir / "reel_scores.json"
            if scores_file.exists():
                try:
                    data = json.loads(scores_file.read_text(encoding="utf-8"))
                    runs = data.get("runs", [])
                    if runs:
                        import pandas as pd
                        rows = []
                        for r in runs[-20:]:  # last 20
                            rows.append({
                                "Run":    r.get("run_id", "—")[:16],
                                "Idea":   r.get("idea", "—")[:40],
                                "Score":  r.get("overall_score", "—"),
                                "Mode":   r.get("strategy_mode", "—"),
                                "Type":   r.get("idea_type", "—"),
                            })
                        st.dataframe(pd.DataFrame(rows), use_container_width=True)
                    else:
                        st.caption("Aucun run enregistré pour l'instant.")
                except Exception as e:
                    st.caption(f"Erreur lecture : {e}")
            else:
                st.caption("Fichier reel_scores.json introuvable.")

        # ── Best hooks ────────────────────────────────────────────────────────
        with tab_hooks:
            hooks_file = mem_dir / "best_hooks.json"
            if hooks_file.exists():
                try:
                    data = json.loads(hooks_file.read_text(encoding="utf-8"))
                    top = data.get("top_hooks", [])
                    if top:
                        for i, h in enumerate(top[:10]):
                            score = h.get("avg_score", 0)
                            color = "#059669" if score >= 7.5 else "#D97706"
                            st.markdown(
                                f'<div style="padding:0.5rem 0;border-bottom:1px solid var(--border);">'
                                f'<span style="font-weight:700;color:{color};min-width:36px;display:inline-block">#{i+1} {score:.1f}</span> '
                                f'<span style="font-size:0.875rem">{h.get("text","")}</span>'
                                f'<span style="font-size:0.72rem;color:var(--text-faint);margin-left:8px">{h.get("pattern","")}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("Aucun hook enregistré pour l'instant.")
                except Exception as e:
                    st.caption(f"Erreur lecture : {e}")
            else:
                st.caption("Fichier best_hooks.json introuvable.")

        # ── Strategy log ─────────────────────────────────────────────────────
        with tab_strat:
            strat_file = mem_dir / "strategy_log.json"
            if strat_file.exists():
                try:
                    data = json.loads(strat_file.read_text(encoding="utf-8"))
                    entries = data.get("log", [])
                    if entries:
                        for entry in entries[-5:]:
                            run_id = entry.get("run_id", "—")
                            mode   = entry.get("strategy_mode", "—")
                            reason = entry.get("reasoning", "")[:120]
                            st.markdown(
                                f'<div style="padding:0.5rem 0;border-bottom:1px solid var(--border);font-size:0.82rem">'
                                f'<strong>{run_id}</strong> — <code>{mode}</code><br>'
                                f'<span style="color:var(--text-muted)">{reason}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("Aucune décision stratégique enregistrée.")
                except Exception as e:
                    st.caption(f"Erreur lecture : {e}")
            else:
                st.caption("Fichier strategy_log.json introuvable.")
