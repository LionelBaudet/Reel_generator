"""
Interface web — Reels Generator @ownyourtime.ai
Lancez avec : streamlit run app.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import streamlit as st
import yaml

# Injecter les clés API depuis st.secrets (Streamlit Cloud) ou .env (local)
import os as _os
try:
    import streamlit as _st_tmp
    for _secret_key in ("ANTHROPIC_API_KEY", "PEXELS_API_KEY", "ELEVENLABS_API_KEY"):
        _val = _st_tmp.secrets.get(_secret_key, "")
        if _val:
            _os.environ.setdefault(_secret_key, _val)
except Exception:
    pass

# Import du moteur génératif (nécessite ANTHROPIC_API_KEY)
_GEN_IMPORT_ERROR: str = ""
try:
    from generate import generate_variants, generate_viral_script, generate_montage_plan, build_yaml, build_yaml_from_viral_script, generate_caption, generate_ab_versions, optimize_script_hooks, BROLL_CATEGORIES
    from utils.hook_optimizer import analyze_hook, analyze_solution, inject_winner
    from utils.hook_engine import optimize_hooks, save_hook_result
    from utils.idea_classifier import classify_idea, CATEGORIES
    from utils.pexels import get_pexels_videos, _api_key as _pexels_key_fn
    from utils.validation import validate_config, self_check
    _GEN_AVAILABLE = bool(_os.environ.get("ANTHROPIC_API_KEY"))
except Exception as _e:
    import traceback as _tb
    _GEN_AVAILABLE = False
    _GEN_IMPORT_ERROR = f"{type(_e).__name__}: {_e}\n{_tb.format_exc()}"

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)   # les chemins relatifs (assets/, config/) fonctionnent depuis ROOT

# ─────────────────────────────────────────────────────────────────────────────
# Configuration de la page
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Reels Generator — @ownyourtime.ai",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS — palette de la marque
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   REELS GENERATOR — Design System v3
   Premium SaaS · Clean · Professional · Production-ready
   ═══════════════════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Design Tokens ──────────────────────────────────────────────────────────── */
:root {
  /* Brand */
  --brand:        #D4A843;
  --brand-dark:   #B8901E;
  --brand-deeper: #966F0A;
  --brand-light:  #FEF9ED;
  --brand-border: #F0D080;

  /* Neutrals */
  --bg:           #F7F8FA;
  --surface:      #FFFFFF;
  --surface-2:    #F3F4F6;
  --surface-3:    #EAECF0;
  --border:       #E5E7EB;
  --border-dark:  #D1D5DB;

  /* Text */
  --text:         #111827;
  --text-2:       #374151;
  --text-muted:   #6B7280;
  --text-faint:   #9CA3AF;

  /* Status */
  --success:      #059669;
  --success-bg:   #ECFDF5;
  --success-bd:   #A7F3D0;
  --warning:      #D97706;
  --warning-bg:   #FFFBEB;
  --warning-bd:   #FDE68A;
  --error:        #DC2626;
  --error-bg:     #FEF2F2;
  --error-bd:     #FECACA;
  --info:         #2563EB;
  --info-bg:      #EFF6FF;
  --info-bd:      #BFDBFE;

  /* Radius */
  --r-xs:   3px;
  --r-sm:   6px;
  --r:      8px;
  --r-md:   10px;
  --r-lg:   14px;
  --r-xl:   20px;
  --r-full: 9999px;

  /* Shadows */
  --shadow-xs: 0 1px 2px rgba(0,0,0,.06);
  --shadow-sm: 0 1px 3px rgba(0,0,0,.1), 0 1px 2px rgba(0,0,0,.06);
  --shadow:    0 4px 8px rgba(0,0,0,.08), 0 2px 4px rgba(0,0,0,.05);
  --shadow-md: 0 10px 18px rgba(0,0,0,.1), 0 4px 6px rgba(0,0,0,.05);

  /* Legacy compat */
  --gold:        var(--brand);
  --gold-dark:   var(--brand-dark);
  --gold-light:  var(--brand-light);
  --gold-border: var(--brand-border);
}

/* ── Reset & Base ───────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  background: var(--bg) !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Clean up Streamlit chrome */
footer, #MainMenu, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stStatusWidget"] {
  display: none !important;
  visibility: hidden !important;
}

/* Main area */
.main .block-container {
  padding-top: 1.75rem !important;
  padding-left: 2.25rem !important;
  padding-right: 2.25rem !important;
  max-width: 1280px !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

/* ── Typography ─────────────────────────────────────────────────────────────── */
h1 {
  font-size: 1.5rem !important; font-weight: 800 !important;
  color: var(--text) !important; letter-spacing: -0.025em !important;
  line-height: 1.25 !important; margin-bottom: 0.25rem !important;
}
h2 {
  font-size: 1.2rem !important; font-weight: 700 !important;
  color: var(--text) !important; letter-spacing: -0.02em !important;
  margin-bottom: 0.2rem !important;
}
h3 {
  font-size: 0.975rem !important; font-weight: 600 !important;
  color: var(--text) !important;
}
p, .stMarkdown p { color: var(--text-2) !important; font-size: 0.9rem !important; line-height: 1.55 !important; }
.stCaption, small { color: var(--text-muted) !important; font-size: 0.8rem !important; }

/* ── Inputs ─────────────────────────────────────────────────────────────────── */
.stTextArea textarea, .stTextInput input {
  background: var(--surface) !important;
  color: var(--text) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--r) !important;
  font-size: 0.9rem !important;
  font-family: 'Inter', sans-serif !important;
  transition: border-color .15s ease, box-shadow .15s ease;
}
.stTextArea textarea:focus, .stTextInput input:focus {
  border-color: var(--brand) !important;
  box-shadow: 0 0 0 3px rgba(212,168,67,.18) !important;
  outline: none !important;
}
.stSelectbox [data-baseweb="select"] > div:first-child {
  background: var(--surface) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--r) !important;
}
.stNumberInput input {
  border: 1.5px solid var(--border) !important;
  border-radius: var(--r) !important;
}
label, .stWidgetLabel p {
  font-size: 0.82rem !important;
  font-weight: 600 !important;
  color: var(--text-2) !important;
  letter-spacing: 0.01em !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────────── */
.stButton > button {
  height: 40px !important;
  font-size: 0.875rem !important;
  font-weight: 600 !important;
  border-radius: var(--r) !important;
  transition: all .15s ease !important;
  letter-spacing: 0.01em !important;
  font-family: 'Inter', sans-serif !important;
}
.stButton > button[kind="primary"] {
  background: var(--brand) !important;
  color: #fff !important;
  border: 1.5px solid var(--brand-dark) !important;
  box-shadow: var(--shadow-xs), inset 0 1px 0 rgba(255,255,255,.12) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--brand-dark) !important;
  border-color: var(--brand-deeper) !important;
  box-shadow: var(--shadow-sm) !important;
  transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"]:active { transform: translateY(0) !important; }
.stButton > button[kind="secondary"] {
  background: var(--surface) !important;
  border: 1.5px solid var(--border) !important;
  color: var(--text-2) !important;
  box-shadow: var(--shadow-xs) !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color: var(--brand-border) !important;
  color: var(--brand-dark) !important;
  background: var(--brand-light) !important;
  box-shadow: var(--shadow-sm) !important;
}

/* ── Tabs — Pill Style ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 2px !important;
  background: var(--surface-2) !important;
  border-radius: var(--r-md) !important;
  padding: 3px !important;
  border-bottom: none !important;
  width: fit-content !important;
  max-width: 100% !important;
  margin-bottom: 1.5rem !important;
}
.stTabs [data-baseweb="tab"] {
  color: var(--text-muted) !important;
  font-weight: 500 !important;
  font-size: 0.825rem !important;
  padding: 0.38rem 0.85rem !important;
  border-radius: var(--r-sm) !important;
  transition: all .12s ease !important;
  border: none !important;
  background: transparent !important;
  white-space: nowrap !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text) !important; background: rgba(0,0,0,.04) !important; }
.stTabs [aria-selected="true"] {
  background: var(--surface) !important;
  color: var(--text) !important;
  font-weight: 700 !important;
  box-shadow: var(--shadow-xs) !important;
  border: none !important;
}

/* ── Progress ───────────────────────────────────────────────────────────────── */
.stProgress > div > div {
  background: var(--surface-3) !important;
  border-radius: var(--r-full) !important;
  height: 5px !important;
}
.stProgress > div > div > div {
  background: linear-gradient(90deg, var(--brand), var(--brand-dark)) !important;
  border-radius: var(--r-full) !important;
}

/* ── Metrics ────────────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 1rem 1.2rem !important;
  box-shadow: var(--shadow-xs) !important;
}
[data-testid="stMetricLabel"] {
  font-size: 0.72rem !important; font-weight: 700 !important;
  color: var(--text-muted) !important; text-transform: uppercase !important;
  letter-spacing: 0.07em !important;
}
[data-testid="stMetricValue"] {
  font-size: 1.65rem !important; font-weight: 800 !important;
  color: var(--text) !important; letter-spacing: -0.03em !important;
}

/* ── Expanders ──────────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  font-weight: 600 !important;
  font-size: 0.875rem !important;
  color: var(--text) !important;
  padding: 0.65rem 1rem !important;
  transition: background .12s ease;
}
.streamlit-expanderHeader:hover { background: var(--surface-2) !important; }
.streamlit-expanderContent {
  border: 1px solid var(--border) !important;
  border-top: none !important;
  border-radius: 0 0 var(--r) var(--r) !important;
  padding: 1rem !important;
}

/* ── DataFrames ─────────────────────────────────────────────────────────────── */
.stDataFrame {
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  overflow: hidden !important;
  box-shadow: var(--shadow-xs) !important;
}

/* ─────────────────────────────────────────────────────────────────────────────
   CUSTOM COMPONENTS
   ───────────────────────────────────────────────────────────────────────────── */

/* ── Page Header ────────────────────────────────────────────────────────────── */
.page-header {
  padding-bottom: 1.4rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.75rem;
}
.page-header-eyebrow {
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--brand); margin-bottom: 4px;
}
.page-header-title {
  font-size: 1.45rem; font-weight: 800; color: var(--text);
  letter-spacing: -0.025em; line-height: 1.2; margin: 0 0 6px 0;
}
.page-header-sub {
  font-size: 0.875rem; color: var(--text-muted); margin: 0; line-height: 1.5;
}

/* ── App Brand (sidebar) ────────────────────────────────────────────────────── */
.app-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 1.1rem 1rem 0.9rem;
  border-bottom: 1px solid var(--border);
}
.app-brand-icon {
  width: 34px; height: 34px;
  background: var(--brand);
  border-radius: var(--r);
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem; flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(212,168,67,.35);
}
.app-brand-name { font-size: 0.9rem; font-weight: 800; color: var(--text); line-height: 1.1; }
.app-brand-handle { font-size: 0.7rem; color: var(--text-muted); font-weight: 500; }

/* ── Status Indicators ──────────────────────────────────────────────────────── */
.status-row {
  display: flex; align-items: center; gap: 7px;
  padding: 0.3rem 1rem; font-size: 0.78rem; color: var(--text-2);
}
.status-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.status-dot.ok    { background: var(--success); box-shadow: 0 0 5px rgba(5,150,105,.5); }
.status-dot.warn  { background: var(--warning); }
.status-dot.error { background: var(--error); }
.status-dot.off   { background: var(--text-faint); }

/* ── Sidebar KPI Grid ───────────────────────────────────────────────────────── */
.sidebar-section-label {
  font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.09em; color: var(--text-faint); padding: 0.65rem 1rem 0.2rem;
}
.kpi-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px; padding: 0 0.8rem 0.75rem;
}
.kpi-item {
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--r); padding: 0.55rem 0.6rem; text-align: center;
  transition: border-color .12s;
}
.kpi-item:hover { border-color: var(--brand-border); }
.kpi-item-value { font-size: 1.05rem; font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.kpi-item-label { font-size: 0.65rem; color: var(--text-muted); font-weight: 500; margin-top: 1px; }

/* ── Divider ────────────────────────────────────────────────────────────────── */
.gold-hr, hr.section-hr {
  border: none; border-top: 1px solid var(--border); margin: 1.4rem 0;
}

/* ── Section Label ──────────────────────────────────────────────────────────── */
.section-title {
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.09em; color: var(--text-muted); margin: 1.5rem 0 0.6rem;
  display: flex; align-items: center; gap: 0.5rem;
}
.section-title::after {
  content: ''; flex: 1; height: 1px; background: var(--border);
}

/* ── Step Indicator ─────────────────────────────────────────────────────────── */
.step-bar {
  display: flex; align-items: center;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--r-xl); padding: 0.45rem 1rem;
  margin: 0 0 1.75rem 0; gap: 0;
}
.step-item {
  display: flex; align-items: center; gap: 0.4rem; flex: 1;
  font-size: 0.73rem; font-weight: 600; color: var(--text-muted); white-space: nowrap;
}
.step-item .step-num {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  background: var(--surface); border: 1.5px solid var(--border);
  color: var(--text-muted); font-size: 0.68rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s ease;
}
.step-item.done .step-num  { background: var(--success-bg); border-color: var(--success-bd); color: var(--success); }
.step-item.active .step-num {
  background: var(--brand-light); border-color: var(--brand-border);
  color: var(--brand); box-shadow: 0 0 0 3px rgba(212,168,67,.15);
}
.step-item.active { color: var(--brand); font-weight: 700; }
.step-item.done   { color: var(--success); }
.step-connector {
  flex: 1; height: 1.5px; background: var(--border);
  margin: 0 0.35rem; max-width: 40px; border-radius: 1px;
}
.step-connector.done { background: var(--success-bd); }

/* ── Callouts ───────────────────────────────────────────────────────────────── */
.callout {
  border-radius: var(--r); padding: 0.7rem 1rem; margin: 0.5rem 0;
  font-size: 0.85rem; line-height: 1.55; border-left: 4px solid;
}
.callout-info    { background: var(--info-bg);    border-color: var(--info);    color: #1e40af; }
.callout-success { background: var(--success-bg); border-color: var(--success); color: #065f46; }
.callout-warning { background: var(--warning-bg); border-color: var(--warning); color: #92400e; }
.callout-error   { background: var(--error-bg);   border-color: var(--error);   color: #991b1b; }

/* ── Badges ─────────────────────────────────────────────────────────────────── */
.badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 9px; border-radius: var(--r-full);
  font-size: 0.72rem; font-weight: 700; border: 1.5px solid transparent;
}
.badge-ok    { background: var(--success-bg); color: var(--success); border-color: var(--success-bd); }
.badge-miss  { background: var(--error-bg);   color: var(--error);   border-color: var(--error-bd); }
.badge-warn  { background: var(--warning-bg); color: var(--warning); border-color: var(--warning-bd); }
.badge-info  { background: var(--info-bg);    color: var(--info);    border-color: var(--info-bd); }
.badge-gold  { background: var(--brand-light); color: var(--brand);  border-color: var(--brand-border); }
.badge-gen   { background: var(--warning-bg); color: var(--warning); border-color: var(--warning-bd); }

/* ── Concept Card (Tab 0 variants) ─────────────────────────────────────────── */
.concept-card {
  background: var(--surface); border: 1.5px solid var(--border);
  border-radius: var(--r-lg); overflow: hidden;
  transition: border-color .15s, box-shadow .15s, transform .15s;
  height: 100%;
}
.concept-card:hover {
  border-color: var(--brand-border); box-shadow: var(--shadow);
  transform: translateY(-2px);
}
.concept-card.selected {
  border-color: var(--brand); box-shadow: 0 0 0 3px rgba(212,168,67,.15);
}
.concept-card-header {
  padding: 0.65rem 0.9rem; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.concept-card-body { padding: 0.85rem 0.9rem; }
.concept-card-hook {
  background: var(--brand-light); border-left: 3px solid var(--brand);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  padding: 0.55rem 0.75rem; margin: 0.5rem 0 0.65rem;
  font-size: 0.9rem; font-weight: 700; color: var(--text);
  line-height: 1.35; font-style: italic;
}
.concept-card-meta {
  font-size: 0.77rem; color: var(--text-muted); line-height: 1.4;
  display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.5rem;
}
.concept-card-preview {
  font-size: 0.8rem; color: var(--text-muted);
  line-height: 1.45; font-style: italic; margin-top: 0.4rem;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Script Display ─────────────────────────────────────────────────────────── */
.script-block {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-md); overflow: hidden; margin-bottom: 0.75rem;
}
.script-line {
  display: flex; gap: 0.8rem; align-items: flex-start;
  padding: 0.65rem 1rem; border-bottom: 1px solid var(--surface-2);
  transition: background .1s;
}
.script-line:last-child { border-bottom: none; }
.script-line:hover { background: var(--surface-2); }
.script-label {
  min-width: 70px; font-weight: 700; font-size: 0.7rem;
  text-transform: uppercase; letter-spacing: 0.06em; padding-top: 2px; flex-shrink: 0;
}
.script-text { color: var(--text); font-size: 0.9rem; line-height: 1.5; flex: 1; }

/* ── Hook Cards ─────────────────────────────────────────────────────────────── */
.hook-winner {
  background: var(--brand-light); border: 2px solid var(--brand-border);
  border-radius: var(--r-lg); padding: 1rem 1.25rem; margin: 0.75rem 0;
  box-shadow: var(--shadow-sm);
}
.hook-accepted {
  background: var(--success-bg); border: 1px solid var(--success-bd);
  border-radius: var(--r); padding: 0.75rem 1rem; margin-bottom: 0.75rem; color: #065f46;
}
.hook-rejected {
  background: var(--error-bg); border: 1px solid var(--error-bd);
  border-radius: var(--r); padding: 0.75rem 1rem; margin-bottom: 0.75rem; color: #991b1b;
}

/* ── Score Grid ─────────────────────────────────────────────────────────────── */
.score-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin: 0.75rem 0;
}
.score-cell {
  text-align: center; padding: 0.55rem 0.3rem;
  background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r);
}
.score-cell-value { font-size: 1.25rem; font-weight: 800; line-height: 1; }
.score-cell-label { font-size: 0.63rem; color: var(--text-muted); margin-top: 2px; font-weight: 500; }

/* ── Montage Rows ───────────────────────────────────────────────────────────── */
.montage-table {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-md); overflow: hidden; margin: 0.75rem 0;
}
.montage-row {
  display: flex; align-items: center; gap: 0.7rem;
  padding: 0.6rem 0.9rem; border-bottom: 1px solid var(--surface-2);
  font-size: 0.875rem; transition: background .1s;
}
.montage-row:last-child { border-bottom: none; }
.montage-row:hover { background: var(--surface-2); }
.montage-idx {
  width: 20px; height: 20px; background: var(--surface-2);
  border-radius: var(--r-xs); display: flex; align-items: center; justify-content: center;
  font-size: 0.65rem; font-weight: 700; color: var(--text-muted); flex-shrink: 0;
}
.montage-type {
  min-width: 62px; font-size: 0.68rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.montage-text { flex: 1; color: var(--text); line-height: 1.4; }
.montage-dur {
  font-size: 0.75rem; color: var(--text-muted); font-weight: 600;
  background: var(--surface-2); padding: 2px 8px; border-radius: var(--r-full); flex-shrink: 0;
}
.montage-anim {
  font-size: 0.7rem; color: var(--text-faint); min-width: 60px; text-align: right;
}

/* ── Caption Box ────────────────────────────────────────────────────────────── */
.caption-box {
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--r-md); padding: 1rem 1.1rem;
  font-size: 0.875rem; line-height: 1.65; color: var(--text-2);
  white-space: pre-wrap; font-family: 'Inter', sans-serif;
}

/* ── Reel Card ──────────────────────────────────────────────────────────────── */
.reel-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-md); padding: 0.85rem 1rem;
  margin-bottom: 6px; display: flex; align-items: center; gap: 0.75rem;
  transition: border-color .15s, box-shadow .15s;
}
.reel-card:hover { border-color: var(--brand-border); box-shadow: var(--shadow-sm); }

/* ── Empty State ────────────────────────────────────────────────────────────── */
.empty-state {
  text-align: center; padding: 3.5rem 2rem; color: var(--text-muted);
  background: var(--surface); border: 1.5px dashed var(--border);
  border-radius: var(--r-lg); margin: 1rem 0;
}
.empty-state-icon { font-size: 2.25rem; margin-bottom: 0.65rem; opacity: .55; }
.empty-state-title { font-size: 0.975rem; font-weight: 700; color: var(--text-2); margin-bottom: 0.35rem; }
.empty-state-sub { font-size: 0.84rem; color: var(--text-muted); }

/* ── Overlay pill ───────────────────────────────────────────────────────────── */
.overlay-pill {
  display: inline-block; background: #111827; color: #F2F0EA;
  font-weight: 700; font-size: 0.875rem; padding: 0.3rem 0.75rem;
  border-radius: var(--r); margin: 3px; letter-spacing: 0.01em;
}

/* ── Mobile ─────────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
  [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; }
  h1 { font-size: 1.2rem !important; }
  .page-header { flex-direction: column; gap: 0.75rem; }
  .step-bar { flex-wrap: wrap; gap: 0.3rem; border-radius: var(--r); }
  .step-connector { display: none; }
  .kpi-row { padding: 0 0.5rem 0.5rem; }
  .stTabs [data-baseweb="tab-list"] { overflow-x: auto !important; flex-wrap: nowrap !important; width: 100% !important; }
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list, cwd: str = str(ROOT)) -> subprocess.CompletedProcess:
    """Lance une commande et retourne le résultat."""
    return subprocess.run(
        cmd, cwd=cwd,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def _available_videos() -> dict[str, Path]:
    """Retourne {nom_affichage: path} pour toutes les vidéos disponibles."""
    vid_dir = ROOT / "assets" / "video"
    return {p.name: p for p in sorted(vid_dir.glob("*.mp4"))} if vid_dir.exists() else {}


def _available_music() -> dict[str, Path]:
    """Retourne {nom: path} pour tous les fichiers audio disponibles."""
    aud_dir = ROOT / "assets" / "audio"
    if not aud_dir.exists():
        return {}
    return {p.name: p for p in sorted(aud_dir.glob("*.wav")) if p.stat().st_size > 10_000}


def _batch_configs() -> list[Path]:
    """Liste les YAMLs dans config/batch/ qui commencent par 'reel_'."""
    d = ROOT / "config" / "batch"
    return sorted(d.glob("reel_*.yaml")) if d.exists() else []


# ── Helpers Pexels ────────────────────────────────────────────────────────────

def _pexels_search_videos(query: str, api_key: str, per_page: int = 9) -> list:
    """Cherche des vidéos sur Pexels. Retourne la liste brute des vidéos."""
    import urllib.request, urllib.parse, json
    url = (
        "https://api.pexels.com/videos/search"
        f"?query={urllib.parse.quote(query)}&per_page={per_page}&orientation=landscape"
    )
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/2.0)",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("videos", []), data.get("total_results", 0)
    except Exception as e:
        return [], str(e)


def _pexels_best_file(video: dict) -> dict | None:
    """Retourne le meilleur fichier téléchargeable d'une vidéo Pexels."""
    files = video.get("video_files", [])
    # Préférer MP4, prendre le plus large en résolution
    mp4 = [f for f in files if f.get("file_type") == "video/mp4"]
    pool = mp4 if mp4 else files
    pool.sort(key=lambda f: f.get("width", 0), reverse=True)
    return pool[0] if pool else None


def _download_to_file(url: str, dest: Path) -> bool:
    """Télécharge une URL vers dest. Retourne True si succès."""
    import urllib.request
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/2.0)",
        "Accept":     "video/mp4,video/*;q=0.9,*/*;q=0.8",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        return dest.stat().st_size > 10_000
    except Exception:
        if dest.exists():
            dest.unlink()
        return False


def _slugify(text: str) -> str:
    """Convertit un texte en nom de fichier valide."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:40]


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _config_to_form(cfg: dict) -> dict:
    """Extrait les champs éditables d'un config dict."""
    return {
        "intro_text":     cfg.get("intro", {}).get("text", ""),
        "intro_subtext":  cfg.get("intro", {}).get("subtext", ""),
        "intro_video":    cfg.get("intro", {}).get("video", ""),
        "intro_duration": cfg.get("intro", {}).get("duration", 3),
        "hook_text":      cfg.get("hook", {}).get("text", ""),
        "hook_highlight": cfg.get("hook", {}).get("highlight", ""),
        "hook_duration":  cfg.get("hook", {}).get("duration", 3),
        "prompt_text":    cfg.get("prompt", {}).get("text", ""),
        "prompt_output":  cfg.get("prompt", {}).get("output_preview", ""),
        "prompt_saves":   cfg.get("prompt", {}).get("saves", ""),
        "prompt_duration":cfg.get("prompt", {}).get("duration", 14),
        "cta_headline":   cfg.get("cta", {}).get("headline", "Save THIS."),
        "cta_subtext":    cfg.get("cta", {}).get("subtext", ""),
        "cta_duration":   cfg.get("cta", {}).get("duration", 3),
        "audio_music":    cfg.get("audio", {}).get("background_music", ""),
        "audio_volume":   cfg.get("audio", {}).get("volume", 0.28),
    }


def _form_to_config(f: dict, base: dict | None = None) -> dict:
    """Reconstruit un config dict depuis les champs du formulaire."""
    cfg = base.copy() if base else {}
    cfg["reel"] = cfg.get("reel", {"template": "prompt_reveal", "fps": 30, "width": 1080, "height": 1920})
    intro_dur  = f["intro_duration"]
    hook_dur   = f["hook_duration"]
    prompt_dur = f["prompt_duration"]
    cta_dur    = f["cta_duration"]
    cfg["reel"]["duration"] = intro_dur + hook_dur + prompt_dur + cta_dur

    cfg["intro"] = {
        "video":           f["intro_video"],
        "duration":        intro_dur,
        "start_at":        cfg.get("intro", {}).get("start_at", 0),
        "text":            f["intro_text"],
        "subtext":         f["intro_subtext"],
        "fade_in":         0.4,
        "fade_out":        0.5,
        "overlay_opacity": 0.50,
    }
    cfg["hook"] = {
        "text":      f["hook_text"],
        "highlight": f["hook_highlight"],
        "duration":  hook_dur,
    }
    cfg["prompt"] = {
        "title":          "AI Prompt",
        "text":           f["prompt_text"],
        "output_preview": f["prompt_output"],
        "saves":          f["prompt_saves"],
        "duration":       prompt_dur,
    }
    cfg["cta"] = {
        "headline": f["cta_headline"],
        "subtext":  f["cta_subtext"],
        "handle":   "@ownyourtime.ai",
        "duration": cta_dur,
    }
    cfg["audio"] = {
        "background_music": f["audio_music"],
        "volume":           f["audio_volume"],
    }
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    # ── Brand ─────────────────────────────────────────────────────────────────
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

    # ── API Status ─────────────────────────────────────────────────────────────
    _api_ok = bool(_os.environ.get("ANTHROPIC_API_KEY"))
    _pex_ok = bool(st.session_state.get("pexels_key"))
    st.markdown(
        f'<div class="status-row">'
        f'<div class="status-dot {"ok" if _api_ok else "error"}"></div>'
        f'<span>Claude API {"— connecté" if _api_ok else "— non configurée"}</span>'
        f'</div>'
        f'<div class="status-row">'
        f'<div class="status-dot {"ok" if _pex_ok else "off"}"></div>'
        f'<span>Pexels {"— actif" if _pex_ok else "— non configuré"}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ── Assets KPIs ───────────────────────────────────────────────────────────
    n_videos = len(_available_videos())
    n_music  = len(_available_music())
    n_batch  = len(_batch_configs())
    n_output = len(list((ROOT / "output" / "batch").glob("*.mp4"))) if (ROOT / "output" / "batch").exists() else 0

    st.markdown('<div class="sidebar-section-label">Assets</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="kpi-row">'
        f'<div class="kpi-item"><div class="kpi-item-value">{n_videos}</div><div class="kpi-item-label">Vidéos</div></div>'
        f'<div class="kpi-item"><div class="kpi-item-value">{n_music}</div><div class="kpi-item-label">Musiques</div></div>'
        f'<div class="kpi-item"><div class="kpi-item-value">{n_batch}</div><div class="kpi-item-label">Configs</div></div>'
        f'<div class="kpi-item"><div class="kpi-item-value">{n_output}</div><div class="kpi-item-label">Reels</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ── Clé Pexels ────────────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section-label">Configuration</div>', unsafe_allow_html=True)
    pexels_key = st.text_input(
        "Clé API Pexels",
        type="password",
        value=st.session_state.get("pexels_key", ""),
        placeholder="Clé depuis pexels.com/api…",
        key="sidebar_pexels_key",
        help="Permet le téléchargement automatique de B-roll depuis Pexels (gratuit).",
    )
    if pexels_key:
        st.session_state["pexels_key"] = pexels_key
    elif not _pex_ok:
        st.caption("Optionnelle — permet le B-roll automatique.")

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
    st.caption("v2.1 · Python · Pillow · MoviePy · FFmpeg")


# ─────────────────────────────────────────────────────────────────────────────
# Onglets principaux
# ─────────────────────────────────────────────────────────────────────────────

tab_auto, tab_script, tab_gen, tab_batch, tab_video, tab_music = st.tabs([
    "✨ Idée → Reel",
    "📝 Script Viral",
    "🎬 Générer",
    "📦 Batch",
    "📹 Vidéos",
    "🎵 Musique",
])


# ═════════════════════════════════════════════════════════════════════════════
# ONGLET 0 — IDÉE → REEL (FULL AUTONOME)
# ═════════════════════════════════════════════════════════════════════════════

_ANGLE_LABELS = {
    "frustration":  ("😤", "FRUSTRATION",  "#3a1a1a", "#f87171"),
    "gain":         ("⚡", "GAIN DE TEMPS", "#1a2e1a", "#4ade80"),
    "social_proof": ("👀", "SOCIAL PROOF",  "#1a1a3a", "#818cf8"),
}

with tab_auto:
    st.markdown(
        '<div class="page-header">'
        '<div class="page-header-eyebrow">Pipeline IA</div>'
        '<div class="page-header-title">Idée → Reel</div>'
        '<div class="page-header-sub">'
        'Décris ton idée en quelques mots — Claude génère 3 concepts complets avec hook, '
        'script, YAML et caption, optimisés pour l\'algorithme Instagram.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not _GEN_AVAILABLE:
        st.markdown(
            '<div class="callout callout-error">🔑 <strong>ANTHROPIC_API_KEY manquante</strong> — '
            'Configure la clé dans <code>.env</code> ou dans les secrets Streamlit Cloud.</div>',
            unsafe_allow_html=True,
        )
        if _GEN_IMPORT_ERROR:
            with st.expander("Détail de l'erreur d'import"):
                st.code(_GEN_IMPORT_ERROR)
    else:
        # ── Input ─────────────────────────────────────────────────────────────
        idea_input = st.text_input(
            "Ton idée en quelques mots",
            placeholder="ex: automatiser reporting, gagner du temps emails, préparer réunion client...",
            key="auto_idea_input",
        )

        col_btn, col_reset = st.columns([2, 1])
        with col_btn:
            gen_clicked = st.button(
                "Générer 3 concepts",
                type="primary",
                disabled=not idea_input.strip(),
                use_container_width=True,
                key="btn_gen_variants",
            )
        with col_reset:
            if st.button("Réinitialiser", type="secondary", use_container_width=True, key="btn_reset_variants"):
                for k in ["auto_variants", "auto_idea", "auto_selected_idx", "auto_yaml", "auto_slug"]:
                    st.session_state.pop(k, None)
                st.rerun()

        # ── Génération ────────────────────────────────────────────────────────
        if gen_clicked and idea_input.strip():
            with st.spinner(f"Génération de 3 concepts pour « {idea_input} »…"):
                try:
                    variants = generate_variants(idea_input.strip())
                    st.session_state["auto_variants"] = variants
                    st.session_state["auto_idea"] = idea_input.strip()
                    st.session_state.pop("auto_selected_idx", None)
                    st.session_state.pop("auto_yaml", None)
                    st.session_state.pop("auto_slug", None)
                except Exception as exc:
                    st.error(f"Erreur API : {exc}")

        # ── Affichage des 3 cartes ────────────────────────────────────────────
        variants = st.session_state.get("auto_variants")
        if not variants and not idea_input.strip():
            st.markdown(
                '<div class="empty-state">'
                '<div class="empty-state-icon">💡</div>'
                '<div class="empty-state-title">Tape ton idée ci-dessus</div>'
                '<div class="empty-state-sub">Claude génère 3 angles différents (frustration, gain, social proof) '
                'avec hook, script complet, YAML prêt à générer et caption Instagram.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        if variants:
            idea_stored = st.session_state.get("auto_idea", "")
            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:.85rem;color:var(--text-muted);margin-bottom:1rem">'
                f'3 concepts générés pour <strong style="color:var(--text)">{idea_stored}</strong>'
                f'</div>',
                unsafe_allow_html=True,
            )

            _ANGLE_STYLE = {
                "frustration":  ("#FFF1F2", "#DC2626", "#FEE2E2"),
                "gain":         ("#F0FDF4", "#059669", "#DCFCE7"),
                "social_proof": ("#EFF6FF", "#2563EB", "#DBEAFE"),
            }

            cols = st.columns(3)
            for i, (variant, col) in enumerate(zip(variants, cols)):
                angle_key = variant.get("angle", "frustration")
                icon, label, _bg_legacy, _c_legacy = _ANGLE_LABELS.get(
                    angle_key, ("🎯", angle_key.upper(), "#1e1e32", "#f2f0ea")
                )
                _card_hdr_bg, _card_clr, _card_bd = _ANGLE_STYLE.get(
                    angle_key, ("#F8F9FA", "#374151", "#E5E7EB")
                )
                broll           = variant.get("broll_category", "—")
                saves           = variant.get("saves_time", "—")
                hook            = variant.get("hook_text", "")
                caption_preview = variant.get("caption", "")[:100]
                is_selected     = (st.session_state.get("auto_selected_idx") == i)
                card_extra      = "selected" if is_selected else ""

                with col:
                    st.markdown(
                        f'<div class="concept-card {card_extra}">'
                        f'<div class="concept-card-header" style="background:{_card_hdr_bg};border-bottom-color:{_card_bd};">'
                        f'<span style="font-size:0.78rem;font-weight:700;color:{_card_clr}">{icon} {label}</span>'
                        f'<span style="font-size:0.72rem;color:var(--text-muted)">#{i+1}</span>'
                        f'</div>'
                        f'<div class="concept-card-body">'
                        f'<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;'
                        f'letter-spacing:.07em;color:var(--text-muted);margin-bottom:3px">Hook</div>'
                        f'<div class="concept-card-hook">"{hook}"</div>'
                        f'<div class="concept-card-meta">'
                        f'<span>📹 {broll}</span>'
                        f'<span>⏱️ {saves}</span>'
                        f'</div>'
                        f'<div class="concept-card-preview">{caption_preview}…</div>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    btn_label = "✓ Sélectionné" if is_selected else "Choisir ce concept"
                    btn_type  = "primary" if is_selected else "secondary"

                    if st.button(btn_label, key=f"select_variant_{i}", type=btn_type, use_container_width=True):
                        st.session_state["auto_selected_idx"] = i
                        yaml_content = build_yaml(variant, idea_stored)
                        st.session_state["auto_yaml"]  = yaml_content
                        st.session_state["auto_slug"]  = variant.get("slug", f"reel_auto_v{i+1}")
                        st.rerun()

            # ── Concept sélectionné → actions ─────────────────────────────────
            selected_idx = st.session_state.get("auto_selected_idx")
            yaml_content = st.session_state.get("auto_yaml")

            if selected_idx is not None and yaml_content:
                variant   = variants[selected_idx]
                slug      = st.session_state.get("auto_slug", "reel_auto")
                yaml_path = ROOT / "config" / "batch" / f"{slug}.yaml"

                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                st.markdown(f"### Concept sélectionné — *{variant.get('angle','').upper()}*")

                st.markdown("**📄 YAML — modifiable avant génération**")
                # Chaque injection incrémente le compteur → nouvelle key → widget rechargé avec la bonne valeur
                _edit_v = st.session_state.get(f"yaml_edit_v_{selected_idx}", 0)
                _edit_val = st.session_state.get(f"yaml_edit_val_{selected_idx}", yaml_content)
                edited_yaml = st.text_area(
                    label="yaml_editor",
                    value=_edit_val,
                    height=420,
                    key=f"yaml_editor_{selected_idx}_v{_edit_v}",
                    label_visibility="collapsed",
                )
                # Détecter les modifications
                if edited_yaml != yaml_content:
                    st.caption("✏️ Modifié — la version éditée sera utilisée pour la génération.")
                    # Valider que c'est du YAML parseable
                    try:
                        import yaml as _yaml
                        _yaml.safe_load(edited_yaml)
                    except Exception as _e:
                        st.warning(f"⚠️ YAML invalide : {_e}")

                # La version active = ce qui est dans l'éditeur
                active_yaml = edited_yaml

                # ── Hook Optimizer ────────────────────────────────────────────
                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                st.markdown("### 🎯 Hook Optimizer")
                st.caption("Analyse le hook et le remplace automatiquement si le score est < 7.5/10.")

                opt_col1, opt_col2 = st.columns([3, 1])
                with opt_col1:
                    hook_to_analyze = st.text_input(
                        "Hook à analyser",
                        value=variant.get("hook_text", ""),
                        key=f"hook_input_{selected_idx}",
                        label_visibility="collapsed",
                        placeholder="Hook à analyser…",
                    )
                with opt_col2:
                    run_optimizer = st.button(
                        "Analyser",
                        type="primary",
                        use_container_width=True,
                        key=f"btn_optimize_{selected_idx}",
                    )

                if run_optimizer and hook_to_analyze.strip():
                    with st.spinner("Analyse du hook en cours…"):
                        try:
                            analysis = analyze_hook(
                                hook_to_analyze.strip(),
                                context=st.session_state.get("auto_idea", ""),
                            )
                            st.session_state[f"hook_analysis_{selected_idx}"] = analysis
                        except Exception as exc:
                            st.error(f"Erreur : {exc}")

                analysis = st.session_state.get(f"hook_analysis_{selected_idx}")
                if analysis:
                    score     = analysis.get("original_score", {})
                    avg       = score.get("average", 0)
                    verdict   = score.get("verdict", "")
                    winner    = analysis.get("winner", "")
                    w_score   = analysis.get("winner_score", 0)
                    div_class = "hook-accepted" if verdict == "ACCEPTED" else "hook-rejected"
                    verdict_icon = "✅" if verdict == "ACCEPTED" else "❌"

                    # Score card
                    st.markdown(
                        f'<div class="{div_class}">'
                        f'<strong>{verdict_icon} {verdict}</strong> — Score moyen : '
                        f'<strong>{avg}/10</strong>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Détail des 5 critères
                    with st.expander("Détail des scores", expanded=verdict == "REJECTED"):
                        crit_cols = st.columns(5)
                        labels = {
                            "scroll_stopping": "Scroll-stop",
                            "clarity": "Clarté",
                            "curiosity": "Curiosité",
                            "viral_potential": "Viral",
                            "niche_fit": "Niche fit",
                        }
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

                    # Alternatives si rejected
                    if verdict == "REJECTED" and analysis.get("alternatives"):
                        with st.expander("10 alternatives générées", expanded=True):
                            for alt in analysis["alternatives"]:
                                bar_color = "#4ade80" if alt["score"] >= 7.5 else "#f59e0b"
                                st.markdown(
                                    f'<div style="display:flex;align-items:center;gap:0.75rem;'
                                    f'padding:0.5rem 0;border-bottom:1px solid #E0E0E8;">'
                                    f'<span style="font-weight:700;color:{bar_color};min-width:32px">'
                                    f'{alt["score"]}</span>'
                                    f'<span style="flex:1;font-weight:600">"{alt["hook"]}"</span>'
                                    f'<span style="font-size:0.75rem;color:#6B6B8A;min-width:90px">'
                                    f'{alt["style"]}</span>'
                                    f'<span style="font-size:0.75rem;color:#6B6B8A">{alt["why"]}</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                    # Winner + variantes
                    st.markdown(
                        f'<div class="hook-winner">'
                        f'<div style="font-size:0.75rem;color:#6B6B8A;margin-bottom:4px">WINNER — {w_score}/10</div>'
                        f'<div style="font-size:1.1rem;font-weight:700;color:#1A1A2E">"{winner}"</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    var_c1, var_c2 = st.columns(2)
                    with var_c1:
                        st.caption(f"🔥 Agressif : *{analysis.get('aggressive', '')}*")
                    with var_c2:
                        st.caption(f"🌍 Safe : *{analysis.get('safe', '')}*")

                    # Bouton d'injection dans le YAML
                    if st.button(
                        "Injecter le winner dans le YAML",
                        type="primary",
                        key=f"inject_winner_{selected_idx}",
                    ):
                        try:
                            current_cfg = yaml.safe_load(active_yaml) or {}
                            updated_cfg = inject_winner(current_cfg, analysis)
                            import io as _io
                            buf = _io.StringIO()
                            yaml.dump(updated_cfg, buf, allow_unicode=True,
                                      default_flow_style=False, sort_keys=False)
                            new_yaml = buf.getvalue()
                            # Changer la version force Streamlit à recréer le widget avec la nouvelle valeur
                            st.session_state[f"yaml_edit_val_{selected_idx}"] = new_yaml
                            st.session_state[f"yaml_edit_v_{selected_idx}"] = _edit_v + 1
                            st.success("Hook injecté ✓")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erreur injection : {exc}")

                # ── Solution Scorer ───────────────────────────────────────────
                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                st.markdown("### 💡 Solution Scorer")
                st.caption("Score la réponse IA affichée dans le reel. Propose une version améliorée si < 7.5/10.")

                sol_col1, sol_col2 = st.columns([3, 1])
                with sol_col1:
                    solution_to_score = st.text_area(
                        "Solution à scorer",
                        value=variant.get("prompt_output", ""),
                        height=160,
                        key=f"solution_input_{selected_idx}",
                        label_visibility="collapsed",
                        placeholder="Colle ici la réponse IA à scorer…",
                    )
                with sol_col2:
                    run_solution_scorer = st.button(
                        "Scorer",
                        type="primary",
                        use_container_width=True,
                        key=f"btn_score_solution_{selected_idx}",
                    )

                if run_solution_scorer and solution_to_score.strip():
                    with st.spinner("Analyse de la solution…"):
                        try:
                            sol_analysis = analyze_solution(
                                solution_to_score.strip(),
                                context=st.session_state.get("auto_idea", ""),
                            )
                            st.session_state[f"sol_analysis_{selected_idx}"] = sol_analysis
                        except Exception as exc:
                            st.error(f"Erreur : {exc}")

                sol_analysis = st.session_state.get(f"sol_analysis_{selected_idx}")
                if sol_analysis:
                    sol_scores  = sol_analysis.get("scores", {})
                    sol_avg     = sol_scores.get("average", 0)
                    sol_verdict = sol_scores.get("verdict", "")
                    sol_div     = "hook-accepted" if sol_verdict == "GOOD" else "hook-rejected"
                    sol_icon    = "✅" if sol_verdict == "GOOD" else "⚠️"

                    st.markdown(
                        f'<div class="{sol_div}">'
                        f'<strong>{sol_icon} {sol_verdict}</strong> — Score moyen : '
                        f'<strong>{sol_avg}/10</strong>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    sol_labels = {
                        "credibility": "Crédibilité",
                        "save_worthy": "Save-worthy",
                        "clarity":     "Clarté",
                        "wow_factor":  "WOW factor",
                        "length_fit":  "Longueur",
                    }
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

                    issues = sol_analysis.get("issues", [])
                    if issues:
                        for issue in issues:
                            st.caption(f"⚠️ {issue}")

                    improved = sol_analysis.get("improved_solution", "")
                    if improved:
                        with st.expander("Version améliorée", expanded=True):
                            st.code(improved, language=None)
                            st.caption(sol_analysis.get("improvement_notes", ""))

                        if st.button(
                            "Injecter la solution améliorée dans le YAML",
                            type="primary",
                            key=f"inject_solution_{selected_idx}",
                        ):
                            try:
                                current_cfg = yaml.safe_load(active_yaml) or {}
                                if "prompt" in current_cfg:
                                    current_cfg["prompt"]["output_preview"] = improved
                                import io as _io2
                                buf2 = _io2.StringIO()
                                yaml.dump(current_cfg, buf2, allow_unicode=True,
                                          default_flow_style=False, sort_keys=False)
                                st.session_state[f"yaml_edit_val_{selected_idx}"] = buf2.getvalue()
                                st.session_state[f"yaml_edit_v_{selected_idx}"] = _edit_v + 1
                                st.success("Solution injectée ✓")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Erreur injection : {exc}")

                with st.expander("📣 Caption Instagram", expanded=False):
                    st.text(variant.get("caption", ""))

                # Boutons d'action
                act1, act2, act3 = st.columns(3)

                with act1:
                    if st.button("💾 Sauvegarder le YAML", type="secondary", use_container_width=True, key="auto_save"):
                        yaml_path.parent.mkdir(parents=True, exist_ok=True)
                        yaml_path.write_text(active_yaml, encoding="utf-8")
                        st.success(f"Sauvegardé → `{yaml_path.name}`")

                with act2:
                    if st.button("🔍 Preview PNG", type="secondary", use_container_width=True, key="auto_preview"):
                        yaml_path.parent.mkdir(parents=True, exist_ok=True)
                        yaml_path.write_text(active_yaml, encoding="utf-8")
                        with st.spinner("Génération des aperçus…"):
                            result = _run([
                                sys.executable, "main.py",
                                "--config", str(yaml_path),
                                "--output", "output/",
                                "--preview",
                            ])
                        if result.returncode == 0:
                            preview_files = {
                                "Intro":  ROOT / "output" / "preview_intro.png",
                                "Hook":   ROOT / "output" / "preview_hook.png",
                                "Prompt": ROOT / "output" / "preview_prompt.png",
                                "CTA":    ROOT / "output" / "preview_cta.png",
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
                        yaml_path.parent.mkdir(parents=True, exist_ok=True)
                        yaml_path.write_text(active_yaml, encoding="utf-8")
                        out_path = ROOT / "output" / f"{slug}.mp4"

                        progress = st.progress(0, text="Initialisation…")
                        with st.spinner("Rendu en cours…"):
                            proc = subprocess.Popen(
                                [sys.executable, "main.py",
                                 "--config", str(yaml_path),
                                 "--output", str(out_path)],
                                cwd=str(ROOT),
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
                            with open(out_path, "rb") as _vf:
                                st.video(_vf.read())
                            with open(out_path, "rb") as f:
                                st.download_button(
                                    "⬇️ Télécharger",
                                    data=f,
                                    file_name=out_path.name,
                                    mime="video/mp4",
                                    type="primary",
                                    key="auto_dl",
                                )
                        else:
                            st.error("La génération a échoué.")
                            with st.expander("Logs"):
                                st.code("\n".join(log_lines[-30:]))


# ═════════════════════════════════════════════════════════════════════════════
# ONGLET 1 — SCRIPT VIRAL
# ═════════════════════════════════════════════════════════════════════════════

with tab_script:
    st.markdown(
        '<div class="page-header">'
        '<div class="page-header-eyebrow">Scripting</div>'
        '<div class="page-header-title">Script Viral</div>'
        '<div class="page-header-sub">'
        'Génère un script structuré hook → tension → shift → solution → résultat → CTA, '
        'avec optimisation automatique des hooks et plan de montage complet.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not _GEN_AVAILABLE:
        st.markdown(
            '<div class="callout callout-error">🔑 <strong>ANTHROPIC_API_KEY manquante</strong> — '
            'Configure la clé dans <code>.env</code> ou dans les secrets Streamlit Cloud.</div>',
            unsafe_allow_html=True,
        )
        if _GEN_IMPORT_ERROR:
            with st.expander("Détail de l'erreur d'import"):
                st.code(_GEN_IMPORT_ERROR)
    else:
        # ── Étape en cours ───────────────────────────────────────────────────
        _has_script   = bool(st.session_state.get("sv_result") or st.session_state.get("sv_ab_result"))
        _has_caption  = bool(st.session_state.get("sv_caption"))
        _has_montage  = bool(st.session_state.get("sv_montage"))
        _s1 = "done" if _has_script else "active"
        _s2 = "done" if _has_caption else ("active" if _has_script else "")
        _s3 = "done" if _has_montage else ("active" if _has_caption else "")
        _s4 = "active" if _has_montage else ""
        st.markdown(
            f'<div class="step-bar">'
            f'<div class="step-item {_s1}"><div class="step-num">{"✓" if _s1=="done" else "1"}</div>Script</div>'
            f'<div class="step-connector {_s1}"></div>'
            f'<div class="step-item {_s2}"><div class="step-num">{"✓" if _s2=="done" else "2"}</div>Caption</div>'
            f'<div class="step-connector {"done" if _has_caption else ""}"></div>'
            f'<div class="step-item {_s3}"><div class="step-num">{"✓" if _s3=="done" else "3"}</div>Montage</div>'
            f'<div class="step-connector {"done" if _has_montage else ""}"></div>'
            f'<div class="step-item {_s4}"><div class="step-num">4</div>Reel</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Saisie idée ──────────────────────────────────────────────────────
        sv_idea = st.text_input(
            "💡 Ton idée",
            placeholder="ex: automatiser ses emails avec GPT, gagner 1h par jour sur Excel…",
            key="sv_idea_input",
        )

        _opt_col1, _opt_col2, _opt_col3 = st.columns([3, 2, 2])
        with _opt_col2:
            _lang_choice = st.radio(
                "Langue",
                ["Français", "English"],
                horizontal=True,
                key="sv_lang_radio",
            )
        with _opt_col3:
            _mode_choice = st.radio(
                "Mode",
                ["Standard", "A/B Testing"],
                horizontal=True,
                key="sv_mode_radio",
            )
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
                'hook · tension · shift · solution · résultat · CTA · '
                'caption Instagram · plan de montage avec durées.</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        _reset_col, _ = st.columns([1, 5])
        with _reset_col:
            if st.button("↺ Réinitialiser", type="secondary", key="btn_sv_reset"):
                for _k in ("sv_result", "sv_ab_result", "sv_caption", "sv_montage",
                           "sv_ab_selected", "sv_pexels_paths", "sv_optimized"):
                    st.session_state.pop(_k, None)
                st.rerun()

        if sv_clicked and sv_idea.strip():
            if sv_mode == "ab":
                with st.spinner("Génération des 3 versions A/B/C…"):
                    try:
                        ab_result = generate_ab_versions(sv_idea.strip(), lang=sv_lang)
                        st.session_state["sv_ab_result"]   = ab_result
                        st.session_state["sv_idea_stored"] = sv_idea.strip()
                        st.session_state.pop("sv_result",  None)
                        st.session_state.pop("sv_caption", None)
                        st.session_state.pop("sv_montage", None)
                        st.session_state.pop("sv_ab_selected", None)
                    except Exception as exc:
                        st.error(f"Erreur : {exc}")
            else:
                with st.spinner("Génération du script viral…"):
                    try:
                        sv_result = generate_viral_script(sv_idea.strip(), lang=sv_lang)
                        st.session_state["sv_result"] = sv_result
                        st.session_state["sv_idea_stored"] = sv_idea.strip()
                        st.session_state.pop("sv_caption",   None)
                        st.session_state.pop("sv_ab_result", None)
                        # Optimisation locale automatique (sans appel API)
                        try:
                            _opt = optimize_script_hooks(sv_result)
                            st.session_state["sv_optimized"] = _opt
                        except Exception:
                            st.session_state.pop("sv_optimized", None)
                    except Exception as exc:
                        st.error(f"Erreur : {exc}")

        # ── Mode A/B ─────────────────────────────────────────────────────────
        ab_result = st.session_state.get("sv_ab_result")
        if ab_result:
            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
            # Badge type d'idée
            _ab_label = ab_result.get("idea_type_label", "")
            _ab_angle = ab_result.get("idea_angle", "")
            _ab_conf  = ab_result.get("idea_confidence", 0)
            if _ab_label:
                _ab_conf_pct   = int(_ab_conf * 100)
                _ab_conf_color = "#4ade80" if _ab_conf >= 0.6 else "#facc15" if _ab_conf >= 0.4 else "#94a3b8"
                st.markdown(
                    f'<div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;flex-wrap:wrap">'
                    f'<span style="background:#F5F5F7;border:1px solid #E0E0E8;border-radius:20px;'
                    f'padding:3px 10px;font-size:0.72rem;font-weight:700;color:#1A1A2E">📂 {_ab_label}</span>'
                    f'<span style="background:#FFF8EC;border:1px solid #E8B84B;border-radius:20px;'
                    f'padding:3px 10px;font-size:0.72rem;font-weight:700;color:#C8972A">⚡ {_ab_angle}</span>'
                    f'<span style="font-size:0.68rem;color:{_ab_conf_color};font-weight:600">confiance {_ab_conf_pct}%</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            versions   = ab_result.get("versions", [])
            selection  = ab_result.get("selection", {})

            _type_labels = {"safe": "A — SAFE", "curiosity": "B — CURIOSITÉ", "aggressive": "C — AGRESSIF"}
            _type_colors = {"safe": "#60a5fa", "curiosity": "#facc15", "aggressive": "#f87171"}
            _type_bg     = {"safe": "#EFF6FF", "curiosity": "#FEFCE8", "aggressive": "#FFF1F2"}

            tab_a, tab_b, tab_c = st.tabs(["A — Safe", "B — Curiosité", "C — Agressif"])
            _script_keys = [("Hook","hook","#f87171"),("Tension","pain","#fb923c"),
                            ("Shift","shift","#facc15"),("Solution","solution","#4ade80"),
                            ("Résultat","result","#60a5fa"),("CTA","cta","#c084fc")]

            for tab, version in zip([tab_a, tab_b, tab_c], versions):
                with tab:
                    vtype  = version.get("type", "")
                    color  = _type_colors.get(vtype, "#aaa")
                    bg     = _type_bg.get(vtype, "#F5F5F7")
                    hook   = version.get("hook", {})
                    sc     = hook.get("score", 0)

                    # Hook
                    st.markdown(
                        f'<div style="background:{bg};border-left:4px solid {color};'
                        f'border-radius:0 8px 8px 0;padding:0.8rem 1rem;margin-bottom:0.75rem">'
                        f'<div style="display:flex;justify-content:space-between;margin-bottom:4px">'
                        f'<span style="font-size:0.72rem;font-weight:700;color:{color}">'
                        f'{_type_labels.get(vtype,"")}</span>'
                        f'<span style="font-size:0.9rem;font-weight:800;color:{color}">Score {sc}</span>'
                        f'</div>'
                        f'<div style="font-size:1.15rem;font-weight:800;color:#1A1A2E">'
                        f'"{hook.get("text","")}"</div>'
                        f'<div style="font-size:0.75rem;color:#6B6B8A;margin-top:4px">'
                        f'Ton : {version.get("tone","")}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Script
                    script_v = version.get("script", {})
                    for lbl, key, clr in _script_keys:
                        txt = script_v.get(key, "")
                        if txt:
                            st.markdown(
                                f'<div style="display:flex;gap:0.75rem;padding:0.4rem 0;'
                                f'border-bottom:1px solid #F0F0F5;">'
                                f'<span style="min-width:72px;font-weight:700;font-size:0.8rem;color:{clr}">{lbl}</span>'
                                f'<span style="color:#1A1A2E;font-size:0.9rem">{txt}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    # Overlay lines
                    if version.get("overlay_lines"):
                        with st.expander("Overlay texte", expanded=False):
                            for line in version["overlay_lines"]:
                                st.markdown(
                                    f'<div style="background:#1A1A2E;color:#F2F0EA;font-weight:700;'
                                    f'font-size:0.95rem;padding:0.35rem 0.7rem;border-radius:6px;'
                                    f'margin-bottom:4px;text-align:center">{line}</div>',
                                    unsafe_allow_html=True,
                                )

            # ── Self-selection ───────────────────────────────────────────────
            if selection:
                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                st.markdown("### Analyse")
                sel_cols = st.columns(3)
                for col, (label, key, icon) in zip(sel_cols, [
                    ("La plus sûre",       "safest",                 "🛡️"),
                    ("La plus virale",      "most_viral",             "🔥"),
                    ("La + convertissante", "most_likely_to_convert", "💰"),
                ]):
                    with col:
                        v = selection.get(key, "?")
                        st.markdown(
                            f'<div style="background:#F5F5F7;border-radius:8px;padding:0.6rem;text-align:center">'
                            f'<div style="font-size:0.72rem;color:#6B6B8A;font-weight:700">{icon} {label}</div>'
                            f'<div style="font-size:2rem;font-weight:900;color:#E8B84B">VERSION {v}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                reco = selection.get("recommendation", "")
                if reco:
                    st.markdown(
                        f'<div style="background:#FFF8EC;border:1px solid #E8B84B;border-radius:8px;'
                        f'padding:0.6rem 0.8rem;margin-top:0.5rem;font-size:0.88rem;color:#1A1A2E">'
                        f'<strong>Recommandation :</strong> {reco}</div>',
                        unsafe_allow_html=True,
                    )

            # ── Choisir la version pour le montage ───────────────────────────
            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
            st.markdown("### Utiliser pour le montage")
            _ver_labels = {v["id"]: f"Version {v['id']} — {v.get('type','').capitalize()} · \"{v.get('hook',{}).get('text','')}\"" for v in versions}
            _default_v  = selection.get("most_viral", "A")
            _selected_v = st.radio(
                "Version à utiliser",
                options=[v["id"] for v in versions],
                format_func=lambda x: _ver_labels.get(x, x),
                index=["A","B","C"].index(_default_v) if _default_v in ["A","B","C"] else 0,
                key="sv_ab_version_radio",
            )
            st.session_state["sv_ab_selected"] = _selected_v

            _ab_montage_btn = st.button(
                f"Générer plan de montage — Version {_selected_v}",
                type="primary", use_container_width=True, key="btn_ab_montage",
            )
            if _ab_montage_btn:
                _chosen = next((v for v in versions if v["id"] == _selected_v), versions[0])
                # Construire un sv compatible avec generate_montage_plan
                _sv_compat = {
                    "script":    _chosen.get("script", {}),
                    "best_hook": _chosen.get("hook", {}),
                    "overlay_lines": _chosen.get("overlay_lines", []),
                }
                _cur_lang = st.session_state.get("sv_lang", "fr")
                with st.spinner(f"Plan de montage Version {_selected_v}…"):
                    try:
                        plan = generate_montage_plan(_chosen.get("script", {}), lang=_cur_lang, idea_type=ab_result.get("idea_type", ""))
                        st.session_state["sv_montage"]      = plan
                        st.session_state["sv_result"]       = _sv_compat
                        st.session_state["sv_idea_stored"]  = st.session_state.get("sv_idea_stored", "")
                        st.success(f"Plan de montage Version {_selected_v} prêt.")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Erreur : {_e}")

        sv = st.session_state.get("sv_result")
        if sv:
            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # ── Type d'idée détecté ─────────────────────────────────────────
            _itype = sv.get("idea_type", "")
            _ilabel = sv.get("idea_type_label", "")
            _iangle = sv.get("idea_angle", "")
            _iconf  = sv.get("idea_confidence", 0)
            if _ilabel:
                _conf_pct = int(_iconf * 100)
                _conf_color = "#4ade80" if _iconf >= 0.6 else "#facc15" if _iconf >= 0.4 else "#94a3b8"
                st.markdown(
                    f'<div style="display:flex;gap:0.5rem;align-items:center;'
                    f'margin-bottom:0.75rem;flex-wrap:wrap">'
                    f'<span style="background:#F5F5F7;border:1px solid #E0E0E8;border-radius:20px;'
                    f'padding:3px 10px;font-size:0.72rem;font-weight:700;color:#1A1A2E">'
                    f'📂 {_ilabel}</span>'
                    f'<span style="background:#FFF8EC;border:1px solid #E8B84B;border-radius:20px;'
                    f'padding:3px 10px;font-size:0.72rem;font-weight:700;color:#C8972A">'
                    f'⚡ {_iangle}</span>'
                    f'<span style="font-size:0.68rem;color:{_conf_color};font-weight:600">'
                    f'confiance {_conf_pct}%</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Best hook ────────────────────────────────────────────────────
            st.markdown("### 1. Best Hook")
            best = sv.get("best_hook", {})
            best_score = best.get("score", 0)
            st.markdown(
                f'<div class="hook-winner" style="margin-bottom:0.5rem">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
                f'<span style="font-size:0.72rem;color:#C8972A;font-weight:700">BEST HOOK</span>'
                f'<span style="font-size:1rem;font-weight:800;color:#E8B84B">Score {best_score}</span>'
                f'</div>'
                f'<div style="font-size:1.25rem;font-weight:800;color:#1A1A2E;margin-bottom:6px">"{best.get("text","")}"</div>'
                f'<div style="font-size:0.82rem;color:#6B6B8A">{best.get("reason","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── 10 hooks (expander) ──────────────────────────────────────────
            all_hooks = sv.get("hooks", [])
            if all_hooks:
                with st.expander(f"Voir les {len(all_hooks)} hooks générés", expanded=False):
                    for h in sorted(all_hooks, key=lambda x: x.get("score", 0), reverse=True):
                        sc  = h.get("score", 0)
                        col = "#4ade80" if sc >= 8 else "#facc15" if sc >= 6 else "#f87171"
                        st.markdown(
                            f'<div style="display:flex;gap:0.75rem;align-items:flex-start;'
                            f'padding:0.45rem 0;border-bottom:1px solid #F0F0F5;">'
                            f'<span style="min-width:32px;font-size:1rem;font-weight:800;color:{col}">{sc}</span>'
                            f'<div>'
                            f'<div style="font-weight:600;color:#1A1A2E">"{h.get("text","")}"</div>'
                            f'<div style="font-size:0.72rem;color:#6B6B8A">{h.get("type","").upper()} — {h.get("why","")}</div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

            # ── Hook Optimizer ────────────────────────────────────────────────
            sv_optimized = st.session_state.get("sv_optimized")
            if sv_optimized:
                _weak  = sv_optimized.get("weak_count", 0)
                _rewr  = sv_optimized.get("rewritten", 0)
                _best  = sv_optimized.get("best", {}) or {}
                _vars  = sv_optimized.get("variants", {})
                _hist  = sv_optimized.get("top_history", [])
                _ranked = sv_optimized.get("ranked", [])

                # Badge résumé
                _badge_color = "#d1fae5" if _weak == 0 else "#fef9c3" if _weak <= 2 else "#fee2e2"
                _badge_icon  = "✅" if _weak == 0 else "⚠️"
                st.markdown(
                    f'<div style="background:{_badge_color};border-radius:8px;'
                    f'padding:0.4rem 0.8rem;margin:0.5rem 0;font-size:0.82rem">'
                    f'{_badge_icon} <strong>Hook Optimizer</strong> — '
                    f'{_weak} hook(s) faible(s) détecté(s)'
                    f'{f" · {_rewr} réécrit(s) via API" if _rewr else ""}'
                    f' · Score local best : <strong>{_best.get("total_score", "—")}/10</strong>'
                    f'</div>',
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
                                _tag = ' <span style="font-size:0.65rem;background:#d1fae5;color:#065f46;padding:1px 5px;border-radius:8px">réécrit</span>'
                            elif _wk:
                                _tag = ' <span style="font-size:0.65rem;background:#fee2e2;color:#991b1b;padding:1px 5px;border-radius:8px">faible</span>'
                            st.markdown(
                                f'<div style="background:{_vbg};border:1px solid {_vcolor};'
                                f'border-radius:8px;padding:0.6rem;height:100%">'
                                f'<div style="font-size:0.68rem;font-weight:700;color:{_vcolor};margin-bottom:4px">'
                                f'VERSION {_v} — {_vlabel}</div>'
                                f'<div style="font-weight:700;color:#1A1A2E;font-size:0.92rem;margin-bottom:6px">'
                                f'"{_txt}"{_tag}</div>'
                                f'<div style="font-size:0.72rem;color:#6B6B8A">'
                                f'Score {_sc}/10'
                                f'{f" · +{_bst} hist." if _bst > 0 else ""}'
                                f'</div></div>',
                                unsafe_allow_html=True,
                            )

                    # Top hooks classés
                    if _ranked:
                        st.markdown(
                            '<div style="font-size:0.78rem;font-weight:700;color:#6B6B8A;'
                            'margin:0.75rem 0 0.3rem 0">Classement complet</div>',
                            unsafe_allow_html=True,
                        )
                        for _r in _ranked:
                            _rtxt = _r.get("text", "")
                            _rsc  = _r.get("total_score", 0)
                            _rv   = _r.get("variant", "A")
                            _rwk  = _r.get("is_weak", False)
                            _rcol = "#4ade80" if _rsc >= 8 else "#facc15" if _rsc >= 6 else "#f87171"
                            _rvar_color = _v_labels[_rv][1]
                            _weak_mark  = " ⚠" if _rwk else ""
                            st.markdown(
                                f'<div style="display:flex;gap:0.6rem;align-items:center;'
                                f'padding:0.3rem 0;border-bottom:1px solid #F5F5F7;">'
                                f'<span style="min-width:30px;font-weight:800;font-size:0.9rem;color:{_rcol}">{_rsc}</span>'
                                f'<span style="min-width:18px;font-size:0.7rem;font-weight:700;color:{_rvar_color}">{_rv}</span>'
                                f'<span style="color:#1A1A2E;font-size:0.85rem">{_rtxt}{_weak_mark}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    # Patterns historiques
                    if _hist:
                        st.markdown(
                            '<div style="font-size:0.78rem;font-weight:700;color:#C8972A;'
                            'margin:0.75rem 0 0.3rem 0">🏆 Top performers historiques</div>',
                            unsafe_allow_html=True,
                        )
                        for _hp in _hist:
                            st.markdown(
                                f'<div style="background:#FFF8EC;border-radius:6px;'
                                f'padding:0.25rem 0.6rem;margin-bottom:3px;'
                                f'font-size:0.82rem;color:#1A1A2E">"{_hp}"</div>',
                                unsafe_allow_html=True,
                            )

                    # Bouton réécriture API
                    if _weak > 0 and _rewr == 0:
                        st.markdown("")
                        if st.button(
                            f"✍️ Réécrire les {_weak} hooks faibles via Claude",
                            type="secondary",
                            use_container_width=True,
                            key="btn_rewrite_hooks",
                        ):
                            with st.spinner("Réécriture en cours…"):
                                try:
                                    _sv_cur = st.session_state.get("sv_result", {})
                                    _opt2 = optimize_script_hooks(_sv_cur, use_api_rewrite=True)
                                    st.session_state["sv_optimized"] = _opt2
                                    st.rerun()
                                except Exception as _re:
                                    st.error(f"Erreur réécriture : {_re}")

                # Sauvegarder la performance
                with st.expander("📊 Sauvegarder la performance d'un hook", expanded=False):
                    st.caption("Enregistre les résultats réels pour améliorer le scoring futur.")
                    _perf_hook = st.selectbox(
                        "Hook",
                        options=[r.get("text", "") for r in _ranked],
                        key="perf_hook_sel",
                    )
                    _pc1, _pc2, _pc3 = st.columns(3)
                    with _pc1:
                        _perf_views = st.number_input("Vues", min_value=0, value=0, step=100, key="perf_views")
                    with _pc2:
                        _perf_likes = st.number_input("Likes", min_value=0, value=0, step=10, key="perf_likes")
                    with _pc3:
                        _perf_comments = st.number_input("Commentaires", min_value=0, value=0, step=1, key="perf_comments")
                    if st.button("💾 Sauvegarder", type="secondary", use_container_width=True, key="btn_save_perf"):
                        if _perf_hook:
                            try:
                                save_hook_result(_perf_hook, int(_perf_views), int(_perf_likes), int(_perf_comments))
                                st.success(f"Performance enregistrée pour : \"{_perf_hook}\"")
                            except Exception as _se:
                                st.error(f"Erreur sauvegarde : {_se}")

            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # ── Script structuré ─────────────────────────────────────────────
            st.markdown("### 2. Script")
            script = sv.get("script", {})
            script_steps = [
                ("Hook",     "hook",     "#f87171"),
                ("Tension",  "pain",     "#fb923c"),
                ("Shift",    "shift",    "#facc15"),
                ("Solution", "solution", "#4ade80"),
                ("Résultat", "result",   "#60a5fa"),
                ("CTA",      "cta",      "#c084fc"),
            ]
            for label, key, color in script_steps:
                text = script.get(key, "")
                if text:
                    st.markdown(
                        f'<div style="display:flex;gap:0.75rem;align-items:flex-start;'
                        f'padding:0.5rem 0;border-bottom:1px solid #F0F0F5;">'
                        f'<span style="min-width:72px;font-weight:700;font-size:0.82rem;color:{color}">{label}</span>'
                        f'<span style="color:#1A1A2E;font-size:0.92rem">{text}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # why it performs
            why = sv.get("why_it_performs", "")
            if why:
                st.markdown(
                    f'<div class="callout callout-info" style="margin-top:0.5rem">'
                    f'<span style="font-weight:700">Pourquoi ça va performer :</span> {why}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # ── Caption Instagram (après le script, avant le montage) ─────────
            st.markdown('<div class="section-title">📣 Étape 2 — Caption Instagram</div>', unsafe_allow_html=True)
            _cap_lang   = st.session_state.get("sv_lang", "fr")
            _cap_stored = st.session_state.get("sv_caption", "")
            _cap_col1, _cap_col2 = st.columns([1, 3])
            with _cap_col1:
                if st.button(
                    "Générer le caption" if _cap_lang == "fr" else "Generate caption",
                    type="secondary",
                    use_container_width=True,
                    key="btn_sv_caption",
                ):
                    with st.spinner("Génération…"):
                        try:
                            _cap_text = generate_caption(
                                st.session_state.get("sv_result", {}),
                                st.session_state.get("sv_montage", {}),
                                st.session_state.get("sv_idea_stored", ""),
                                lang=_cap_lang,
                            )
                            st.session_state["sv_caption"] = _cap_text
                            _cap_stored = _cap_text
                        except Exception as _ce:
                            st.error(f"Erreur : {_ce}")
            if _cap_stored:
                with _cap_col2:
                    st.markdown(
                        f'<div class="caption-box">{_cap_stored}</div>',
                        unsafe_allow_html=True,
                    )
                    st.text_area(
                        "caption_output",
                        value=_cap_stored,
                        height=1,
                        key="sv_caption_display",
                        label_visibility="collapsed",
                    )
            else:
                with _cap_col2:
                    st.markdown(
                        '<div class="callout callout-info">'
                        'Génère d\'abord le script, puis clique <strong>Générer le caption</strong>.</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # ── Overlay + Angle viral + CTA ───────────────────────────────────
            st.markdown('<div class="section-title">🎬 Détails visuels</div>', unsafe_allow_html=True)
            ov_col, info_col = st.columns([1, 1])

            with ov_col:
                st.markdown(
                    '<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;'
                    'letter-spacing:.07em;color:var(--text-muted);margin-bottom:.5rem">'
                    'Overlay texte</div>',
                    unsafe_allow_html=True,
                )
                for line in sv.get("overlay_lines", []):
                    st.markdown(
                        f'<div class="overlay-pill">{line}</div>',
                        unsafe_allow_html=True,
                    )

            with info_col:
                viral = sv.get("viral_angle", {})
                emotion   = viral.get("emotion", "")
                mechanism = viral.get("mechanism", "")
                cta_opt   = sv.get("cta_optimized", "")
                st.markdown(
                    f'<div style="display:flex;flex-direction:column;gap:6px">'
                    f'<div style="background:var(--brand-light);border:1px solid var(--brand-border);'
                    f'border-radius:var(--r);padding:.55rem .75rem">'
                    f'<div style="font-size:.68rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.07em;color:var(--brand);margin-bottom:2px">Émotion</div>'
                    f'<div style="font-weight:600;color:var(--text);font-size:.875rem">{emotion}</div>'
                    f'</div>'
                    f'<div style="background:var(--surface-2);border:1px solid var(--border);'
                    f'border-radius:var(--r);padding:.55rem .75rem">'
                    f'<div style="font-size:.68rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.07em;color:var(--text-muted);margin-bottom:2px">Mécanisme</div>'
                    f'<div style="color:var(--text-2);font-size:.85rem">{mechanism}</div>'
                    f'</div>'
                    f'<div style="background:var(--surface-2);border:1px solid var(--border);'
                    f'border-radius:var(--r);padding:.55rem .75rem">'
                    f'<div style="font-size:.68rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.07em;color:var(--text-muted);margin-bottom:2px">CTA optimisé</div>'
                    f'<div style="font-weight:600;color:var(--text);font-size:.875rem">{cta_opt}</div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Variante A/B agressive ────────────────────────────────────────
            ab = sv.get("ab_variant", {})
            if ab:
                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                with st.expander("⚡ Variante agressive (version C)", expanded=False):
                    st.markdown(
                        f'<div class="hook-rejected" style="margin-bottom:0.75rem">'
                        f'<div style="font-size:0.72rem;color:#991b1b;font-weight:700;margin-bottom:4px">HOOK AGRESSIF</div>'
                        f'<div style="font-size:1.1rem;font-weight:700;color:#1A1A2E">"{ab.get("hook","")}"</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    ab_cols = st.columns(len(ab.get("overlay_lines", [])) or 1)
                    for col, line in zip(ab_cols, ab.get("overlay_lines", [])):
                        with col:
                            st.markdown(
                                f'<div style="background:#1A1A2E;color:#f87171;font-weight:700;'
                                f'font-size:0.9rem;padding:0.4rem;border-radius:6px;text-align:center">'
                                f'{line}</div>',
                                unsafe_allow_html=True,
                            )
                    st.caption(f"Pourquoi plus agressif : {ab.get('why','')}")

            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # ── Plan de montage ───────────────────────────────────────────────
            st.markdown('<div class="section-title">🎬 Étape 3 — Plan de montage</div>', unsafe_allow_html=True)
            st.caption("Une scène = une phrase · min 2.5 s · animations sur le texte uniquement.")

            montage_col1, montage_col2 = st.columns([3, 1])
            with montage_col2:
                if st.button("Générer le montage", type="primary",
                             use_container_width=True, key="btn_montage"):
                    with st.spinner("Génération du plan de montage…"):
                        try:
                            _cur_lang = st.session_state.get("sv_lang", "fr")
                            plan = generate_montage_plan(sv.get("script", {}), lang=_cur_lang, idea_type=sv.get("idea_type", ""))
                            st.session_state["sv_montage"] = plan
                        except Exception as exc:
                            st.error(f"Erreur : {exc}")

            montage = st.session_state.get("sv_montage")
            if montage:
                total = montage.get("total_duration", 0)
                val   = montage.get("validation", {})

                # ── Bandeau validation ────────────────────────────────────────
                all_ok    = all(val.values()) if val else False
                val_class = "callout-success" if all_ok else "callout-warning"
                val_icon  = "✅" if all_ok else "⚠️"
                checks_parts = " · ".join(
                    f"{'✓' if v else '✗'} {k.replace('_', ' ')}"
                    for k, v in val.items()
                )
                st.markdown(
                    f'<div class="callout {val_class}">'
                    f'{val_icon} <strong>{total}s</strong> &nbsp;·&nbsp; {checks_parts}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Pexels suggérés ───────────────────────────────────────────
                pexels_q = montage.get("pexels_queries", [])
                if pexels_q:
                    pills = "".join(
                        f'<span style="background:var(--info-bg);color:var(--info);'
                        f'border:1px solid var(--info-bd);border-radius:var(--r-full);'
                        f'padding:2px 9px;font-size:.72rem;font-weight:600">{q}</span>'
                        for q in pexels_q
                    )
                    st.markdown(
                        f'<div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:.75rem">'
                        f'<span style="font-size:.72rem;font-weight:700;color:var(--text-muted);'
                        f'padding-top:3px">🎬 Pexels :</span>{pills}</div>',
                        unsafe_allow_html=True,
                    )

                # ── Timeline scène par scène ──────────────────────────────────
                ANIM_ICONS = {
                    "fade_in": "✨", "slide_in": "↑", "slide": "↑",
                    "slide_up": "↑", "typing": "⌨️", "pop": "💥", "fade_out": "↓",
                }
                TYPE_COLORS = {
                    "hook":     "#EF4444",
                    "pain":     "#F97316",
                    "twist":    "#EAB308",
                    "solution": "#10B981",
                    "result":   "#3B82F6",
                    "cta":      "#8B5CF6",
                }
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
                        display_text = text.replace(
                            kw,
                            f'<span style="color:var(--brand);font-weight:800">{kw}</span>'
                        )
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
                st.markdown(
                    f'<div class="montage-table">{rows_html}</div>',
                    unsafe_allow_html=True,
                )

                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

                # ── Pexels : téléchargement des vidéos de fond ────────────────
                pexels_queries = montage.get("pexels_queries", [])
                _has_pexels_key = bool(_os.environ.get("PEXELS_API_KEY", ""))
                _pexels_paths = st.session_state.get("sv_pexels_paths", [])

                if pexels_queries:
                    pcol1, pcol2 = st.columns([3, 1])
                    with pcol1:
                        if _pexels_paths:
                            st.markdown(
                                '<div style="background:#d1fae5;border-radius:8px;'
                                'padding:0.4rem 0.8rem;font-size:0.82rem">'
                                f'🎬 <strong>{len(_pexels_paths)} vidéo(s) Pexels prête(s)</strong> : '
                                + " · ".join(f'`{Path(p).name}`' for p in _pexels_paths)
                                + "</div>",
                                unsafe_allow_html=True,
                            )
                        elif _has_pexels_key:
                            st.info(
                                f"📥 **{len(pexels_queries)} vidéos Pexels** prêtes à télécharger "
                                f"— clique sur le bouton →"
                            )
                        else:
                            st.warning(
                                "⚠️ `PEXELS_API_KEY` non configurée — vidéos locales utilisées. "
                                "Ajoute la clé dans `.env` ou `st.secrets`."
                            )
                    with pcol2:
                        if _has_pexels_key:
                            if st.button("📥 Télécharger Pexels",
                                         use_container_width=True, key="sv_pexels"):
                                with st.spinner("Téléchargement des vidéos Pexels…"):
                                    try:
                                        paths = get_pexels_videos(pexels_queries, max_videos=3)
                                        st.session_state["sv_pexels_paths"] = paths
                                        _pexels_paths = paths
                                        st.success(f"{len(paths)} vidéo(s) téléchargée(s)")
                                    except Exception as _pe:
                                        st.error(f"Pexels : {_pe}")

                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

                # ── Étape 3.5 — Voix-off ElevenLabs ─────────────────────────
                st.markdown('<div class="section-title">🎙️ Étape 3.5 — Voix-off ElevenLabs</div>',
                            unsafe_allow_html=True)

                _vo_path_existing = st.session_state.get("sv_voiceover_path", "")

                # Derive default voiceover text from scene texts
                _scenes_text = " ".join(
                    str(sc.get("text", ""))
                    for sc in montage.get("scenes", [])
                    if sc.get("text")
                )
                _vo_text_default = st.session_state.get("sv_voiceover_text") or _scenes_text

                _vo_col1, _vo_col2 = st.columns([3, 1])
                with _vo_col1:
                    _vo_text = st.text_area(
                        "Texte de la voix-off",
                        value=_vo_text_default,
                        height=120,
                        key="sv_vo_text_area",
                        help="Texte que lira ElevenLabs. Dérive automatiquement des scènes du montage.",
                    )
                with _vo_col2:
                    _VOICES = {
                        "Sarah — claire, pro (fr/en)": "EXAVITQu4vr4xnSDxMaL",
                        "Adam — profond, autorité":    "pNInz6obpgDQGcFmaJgB",
                        "Antoni — naturel, convers.":  "ErXwobaYiN019PkySvjV",
                    }
                    _vo_voice_label = st.selectbox(
                        "Voix", list(_VOICES.keys()), key="sv_vo_voice"
                    )
                    _vo_voice_id = _VOICES[_vo_voice_label]
                    _vo_speed = st.slider(
                        "Vitesse", 0.7, 1.3, 1.0, 0.05, key="sv_vo_speed"
                    )
                    _vo_stability = st.slider(
                        "Stabilité", 0.2, 1.0, 0.5, 0.05, key="sv_vo_stability"
                    )

                _vo_btn_col, _vo_status_col = st.columns([1, 2])
                with _vo_btn_col:
                    _btn_vo = st.button(
                        "Générer la voix-off",
                        type="primary", use_container_width=True, key="btn_gen_vo",
                    )

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
                                "text":             _vo_text,
                                "voice_id":         _vo_voice_id,
                                "speed":            _vo_speed,
                                "stability":        _vo_stability,
                                "similarity_boost": 0.75,
                                "model_id":         "eleven_multilingual_v2",
                            },
                        }
                        with st.spinner("Génération de la voix-off via ElevenLabs..."):
                            try:
                                from generate_voiceover import generate_voiceover
                                _el_key = (
                                    _os.environ.get("ELEVENLABS_API_KEY", "")
                                    or st.secrets.get("ELEVENLABS_API_KEY", "")
                                ).strip().strip('"').strip("'")
                                if not _el_key:
                                    st.error("ELEVENLABS_API_KEY non configurée. Ajoute-la dans `.env` ou `st.secrets`.")
                                    st.stop()
                                st.caption(f"Clé ElevenLabs : `{_el_key[:8]}...{_el_key[-4:]}` ({len(_el_key)} cars)")
                                # Quick pre-flight test to surface exact API error
                                import requests as _req
                                _test_r = _req.post(
                                    f"https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL",
                                    headers={"xi-api-key": _el_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
                                    json={"text": "test", "model_id": "eleven_multilingual_v2",
                                          "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                                    timeout=15,
                                )
                                if not _test_r.ok:
                                    st.error(f"ElevenLabs pré-test {_test_r.status_code} : `{_test_r.text[:300]}`")
                                    st.stop()
                                _vo_result = generate_voiceover(_vo_cfg, output_path=_vo_out, api_key=_el_key)
                                st.session_state["sv_voiceover_path"] = str(_vo_result)
                                st.session_state["sv_voiceover_text"] = _vo_text
                                _vo_path_existing = str(_vo_result)
                                st.success(f"Voix-off prête : `{_vo_result.name}` ({_vo_result.stat().st_size // 1024} KB)")
                            except SystemExit as _e:
                                st.error(f"Erreur ElevenLabs : {_e}")
                            except Exception as _e:
                                st.error(f"Erreur inattendue : {_e}")

                if _vo_path_existing and Path(_vo_path_existing).exists():
                    with _vo_status_col:
                        st.audio(_vo_path_existing, format="audio/mp3")

                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">🚀 Étape 4 — Générer le Reel</div>', unsafe_allow_html=True)

                idea_for_reel = st.session_state.get("sv_idea_stored", "")
                _reel_lang = st.session_state.get("sv_lang", "fr")
                reel_yaml, reel_slug = build_yaml_from_viral_script(
                    sv, montage, idea_for_reel,
                    video_paths=_pexels_paths or None,
                    lang=_reel_lang,
                    voiceover_path=st.session_state.get("sv_voiceover_path", ""),
                )

                # ── Self-check validation ──────────────────────────────────────
                try:
                    _cfg_check = yaml.safe_load(reel_yaml) or {}
                    _checks = self_check(_cfg_check)
                    _all_ok = all(_checks.values())
                    _chk_color = "#d1fae5" if _all_ok else "#fef9c3"
                    _chk_icon  = "✅" if _all_ok else "⚠️"
                    _chk_lines = " · ".join(
                        f"{'✓' if v else '✗'} {k}" for k, v in _checks.items()
                    )
                    st.markdown(
                        f'<div style="background:{_chk_color};border-radius:8px;'
                        f'padding:0.4rem 0.8rem;font-size:0.80rem;margin-bottom:0.5rem">'
                        f'{_chk_icon} <strong>Self-check</strong> : {_chk_lines}</div>',
                        unsafe_allow_html=True,
                    )
                except Exception:
                    pass

                # If voiceover path changed since last YAML build, refresh the editor
                _cur_vo = st.session_state.get("sv_voiceover_path", "")
                if _cur_vo and st.session_state.get("sv_reel_yaml_vo") != _cur_vo:
                    st.session_state["sv_reel_edit_val"] = reel_yaml
                    st.session_state["sv_reel_edit_v"] = st.session_state.get("sv_reel_edit_v", 0) + 1
                    st.session_state["sv_reel_yaml_vo"] = _cur_vo

                with st.expander("📄 YAML reel — modifiable", expanded=False):
                    _sv_edit_v = st.session_state.get("sv_reel_edit_v", 0)
                    _sv_edit_val = st.session_state.get("sv_reel_edit_val", reel_yaml)
                    sv_edited_yaml = st.text_area(
                        "sv_yaml_editor",
                        value=_sv_edit_val,
                        height=380,
                        key=f"sv_yaml_editor_v{_sv_edit_v}",
                        label_visibility="collapsed",
                    )
                    try:
                        yaml.safe_load(sv_edited_yaml)
                    except Exception as _ye:
                        st.warning(f"⚠️ YAML invalide : {_ye}")

                reel_path = ROOT / "config" / "batch" / f"{reel_slug}.yaml"
                out_path  = ROOT / "output" / f"{reel_slug}.mp4"

                btn_c1, btn_c2, btn_c3 = st.columns(3)

                with btn_c1:
                    if st.button("💾 Sauvegarder YAML", type="secondary",
                                 use_container_width=True, key="sv_save_yaml"):
                        reel_path.parent.mkdir(parents=True, exist_ok=True)
                        reel_path.write_text(sv_edited_yaml, encoding="utf-8")
                        st.success(f"Sauvegardé → `{reel_path.name}`")

                with btn_c2:
                    if st.button("🔍 Preview PNG", type="secondary",
                                 use_container_width=True, key="sv_preview"):
                        reel_path.parent.mkdir(parents=True, exist_ok=True)
                        reel_path.write_text(sv_edited_yaml, encoding="utf-8")
                        with st.spinner("Génération des aperçus…"):
                            res = _run([sys.executable, "main.py",
                                        "--config", str(reel_path),
                                        "--output", "output/", "--preview"])
                        if res.returncode == 0:
                            tabs_p = st.tabs(["Intro", "Hook", "Prompt", "CTA"])
                            for lbl, tab in zip(["intro", "hook", "prompt", "cta"], tabs_p):
                                with tab:
                                    p = ROOT / "output" / f"preview_{lbl}.png"
                                    if p.exists():
                                        st.image(str(p), use_container_width=True)
                        else:
                            st.error("Erreur preview")
                            with st.expander("Logs"):
                                st.code(res.stderr or res.stdout)

                with btn_c3:
                    if st.button("🚀 Générer le Reel", type="primary",
                                 use_container_width=True, key="sv_run_reel"):
                        reel_path.parent.mkdir(parents=True, exist_ok=True)
                        reel_path.write_text(sv_edited_yaml, encoding="utf-8")
                        # ~8s de rendu par seconde de vidéo (scènes + encodage FFmpeg)
                        _est = max(60, int(montage.get("total_duration", 18) * 8))
                        _n_scenes = len(montage.get("scenes", []))
                        progress = st.progress(0, text="Chargement B-roll…")

                        proc = subprocess.Popen(
                            [sys.executable, "main.py",
                             "--config", str(reel_path),
                             "--output", str(out_path)],
                            cwd=str(ROOT),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                        )
                        log_lines = []
                        # État partagé entre le thread lecteur et le thread principal
                        _state = {"cur": 0, "tot": _n_scenes or 1,
                                  "broll": False, "done": False}

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
                                    # Toutes les scènes rendues → encodage FFmpeg
                                    # Les scènes ≈ 60% du temps, l'encodage ≈ 40%
                                    _scene_time = _est * 0.6
                                    _enc_budget = max(1.0, _est * 0.4)
                                    enc_pct = min(0.99, 0.60 + (elapsed - _scene_time) / _enc_budget * 0.39)
                                    progress.progress(max(0.61, enc_pct),
                                                      text=f"Encodage FFmpeg… {int(elapsed)}s / ~{_est}s")
                                elif cur > 0:
                                    progress.progress(
                                        min(cur / tot * 0.60, 0.59),
                                        text=f"Scène {cur}/{tot}…",
                                    )
                                elif _state["broll"]:
                                    progress.progress(0.10, text="B-roll chargé, rendu des scènes…")
                                else:
                                    progress.progress(
                                        min(0.08, elapsed / _est * 0.08),
                                        text=f"Chargement… {int(elapsed)}s",
                                    )
                                time.sleep(0.5)

                        _reader_thread.join(timeout=10)
                        proc.wait()
                        progress.progress(1.0, text="Terminé !")
                        if proc.returncode == 0 and out_path.exists():
                            st.success(f"Reel prêt — {out_path.stat().st_size // 1024} KB")
                            with open(out_path, "rb") as _vf:
                                st.video(_vf.read())
                            with open(out_path, "rb") as _f:
                                st.download_button("⬇️ Télécharger", data=_f,
                                                   file_name=out_path.name,
                                                   mime="video/mp4", type="primary",
                                                   key="sv_dl")
                        else:
                            st.error("Génération échouée.")
                            with st.expander("Logs"):
                                st.code("\n".join(log_lines[-30:]))

            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # ── Bouton → générer les 3 concepts YAML ─────────────────────────
            if st.button(
                "✨ Générer les 3 concepts YAML →",
                type="primary",
                use_container_width=True,
                key="sv_to_yaml",
            ):
                st.session_state["auto_idea_input"] = st.session_state.get("sv_idea_stored", sv_idea)
                st.info("Idée transférée → va dans l'onglet **✨ Idée → Reel** et clique sur Générer.")


# ═════════════════════════════════════════════════════════════════════════════
# ONGLET 2 — GÉNÉRER
# ═════════════════════════════════════════════════════════════════════════════

with tab_gen:
    st.markdown(
        '<div class="page-header">'
        '<div class="page-header-eyebrow">Studio</div>'
        '<div class="page-header-title">Créer un Reel</div>'
        '<div class="page-header-sub">'
        'Configure manuellement chaque section du reel — intro, hook, prompt, CTA — '
        'prévisualise les frames clés et génère la vidéo finale.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Charger une config existante ─────────────────────────────────────────
    all_configs = [ROOT / "config" / "reel_config.yaml"] + _batch_configs()
    config_names = {p.stem: p for p in all_configs}

    col_load, col_save = st.columns([2, 2])
    with col_load:
        selected_cfg_name = st.selectbox(
            "Charger une config",
            options=["(nouveau)"] + list(config_names.keys()),
            key="cfg_selector",
        )
    with col_save:
        new_cfg_name = st.text_input(
            "Nom de la config (pour sauvegarder)",
            value=selected_cfg_name if selected_cfg_name != "(nouveau)" else "reel_nouveau",
            key="cfg_new_name",
        )

    # Charger les valeurs par défaut
    if selected_cfg_name != "(nouveau)" and selected_cfg_name in config_names:
        base_cfg  = _load_yaml(config_names[selected_cfg_name])
        form_vals = _config_to_form(base_cfg)
    else:
        base_cfg  = {}
        form_vals = _config_to_form({})

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ── Formulaire (2 colonnes) ───────────────────────────────────────────────
    left, right = st.columns([3, 2])

    # Pré-remplissage depuis la Vidéothèque (session state)
    prefill = st.session_state.pop("gen_prefill", None)
    if prefill:
        form_vals["intro_video"] = prefill.get("intro_video", form_vals["intro_video"])
        st.info(f"✨ Vidéo pré-sélectionnée depuis la Vidéothèque : "
                f"`{Path(form_vals['intro_video']).name}`")

    with left:
        # Section Intro
        with st.expander("📽️ Intro — Vidéo d'accroche", expanded=bool(prefill)):
            videos = _available_videos()
            video_options = ["(aucune)"] + list(videos.keys())
            current_video = Path(form_vals["intro_video"]).name if form_vals["intro_video"] else "(aucune)"
            intro_video_sel = st.selectbox("Vidéo stock", video_options,
                index=video_options.index(current_video) if current_video in video_options else 0,
                key="intro_video_sel")
            intro_video = str(videos[intro_video_sel]) if intro_video_sel != "(aucune)" else ""

            fi_text    = st.text_input("Texte principal",  value=form_vals["intro_text"],    key="intro_text")
            fi_subtext = st.text_input("Sous-texte",        value=form_vals["intro_subtext"], key="intro_subtext")
            fi_dur     = st.slider("Durée (s)", 2, 6, int(form_vals["intro_duration"]),       key="intro_dur")

        # Section Hook
        with st.expander("⚡ Hook — Phrase d'accroche", expanded=True):
            fh_text = st.text_input("Texte du hook", value=form_vals["hook_text"], key="hook_text")
            fh_hl   = st.text_input("Mots à souligner (or)",
                                    value=form_vals["hook_highlight"],
                                    help="Sous-ensemble exact du texte du hook",
                                    key="hook_highlight")
            fh_dur  = st.slider("Durée (s)", 2, 5, int(form_vals["hook_duration"]), key="hook_dur")

        # Section Prompt (coeur du reel)
        with st.expander("💬 Prompt ChatGPT — Le moment WOW", expanded=True):
            st.caption("✍️ Prompt utilisateur — court et casual (2–3 lignes)")
            fp_text = st.text_area("Prompt (affiché dans la bulle utilisateur)",
                                   value=form_vals["prompt_text"], height=90, key="prompt_text")

            st.caption("🤖 Réponse ChatGPT — longue et impressionnante")
            fp_out  = st.text_area("Réponse (streamée mot par mot)",
                                   value=form_vals["prompt_output"], height=220, key="prompt_output")

            fp_saves = st.text_input("Badge 'saves' (ex: 20 min/day)",
                                     value=form_vals["prompt_saves"], key="prompt_saves")
            fp_dur   = st.slider("Durée (s)", 8, 20, int(form_vals["prompt_duration"]), key="prompt_dur")

        # Section CTA
        with st.expander("📣 CTA — Call to Action", expanded=False):
            fc_head = st.text_input("Titre CTA",  value=form_vals["cta_headline"], key="cta_headline")
            fc_sub  = st.text_input("Sous-texte CTA", value=form_vals["cta_subtext"], key="cta_subtext")
            fc_dur  = st.slider("Durée (s)", 2, 5, int(form_vals["cta_duration"]),   key="cta_dur")

        # Section Audio
        with st.expander("🎵 Audio", expanded=False):
            music_files = _available_music()
            music_opts  = ["(aucune)"] + list(music_files.keys())
            cur_music   = Path(form_vals["audio_music"]).name if form_vals["audio_music"] else "(aucune)"
            music_sel   = st.selectbox("Musique de fond", music_opts,
                index=music_opts.index(cur_music) if cur_music in music_opts else 0,
                key="audio_music_sel")
            audio_path  = str(music_files[music_sel]) if music_sel != "(aucune)" else ""
            audio_vol   = st.slider("Volume", 0.0, 1.0, float(form_vals["audio_volume"]), 0.01, key="audio_vol")

    # Construire le config dict depuis le formulaire
    form_data = {
        "intro_text": fi_text, "intro_subtext": fi_subtext,
        "intro_video": intro_video, "intro_duration": fi_dur,
        "hook_text": fh_text, "hook_highlight": fh_hl, "hook_duration": fh_dur,
        "prompt_text": fp_text, "prompt_output": fp_out,
        "prompt_saves": fp_saves, "prompt_duration": fp_dur,
        "cta_headline": fc_head, "cta_subtext": fc_sub, "cta_duration": fc_dur,
        "audio_music": audio_path, "audio_volume": audio_vol,
    }
    live_cfg = _form_to_config(form_data, base_cfg)

    with right:
        st.markdown("### 👁️ Prévisualisation")
        st.caption("Aperçu des frames clés de votre reel (PNG rapide)")

        if st.button("🔍 Générer l'aperçu", type="primary", key="btn_preview"):
            # Sauvegarder le config dans un fichier temporaire
            tmp_cfg = ROOT / "output" / "_preview_tmp.yaml"
            _save_yaml(tmp_cfg, live_cfg)

            with st.spinner("Génération des aperçus..."):
                result = _run([
                    sys.executable, "main.py",
                    "--config", str(tmp_cfg),
                    "--output", "output/",
                    "--preview",
                ])

            if result.returncode == 0:
                preview_files = {
                    "Intro":  ROOT / "output" / "preview_intro.png",
                    "Hook":   ROOT / "output" / "preview_hook.png",
                    "Prompt": ROOT / "output" / "preview_prompt.png",
                    "CTA":    ROOT / "output" / "preview_cta.png",
                }
                tabs_prev = st.tabs(list(preview_files.keys()))
                for (label, path), tab in zip(preview_files.items(), tabs_prev):
                    with tab:
                        if path.exists():
                            st.image(str(path), use_container_width=True)
                        else:
                            st.warning("Aperçu non disponible")
            else:
                st.error("Erreur lors de la prévisualisation")
                with st.expander("Logs d'erreur"):
                    st.code(result.stderr or result.stdout)

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ── Boutons d'action ──────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns([2, 2, 3])

    with col_a:
        output_name = st.text_input("Nom du fichier de sortie", value=f"{new_cfg_name}.mp4", key="output_filename")

    with col_b:
        save_col, _ = st.columns([1, 1])
        with save_col:
            if st.button("💾 Sauvegarder config", type="secondary"):
                save_path = ROOT / "config" / "batch" / f"{new_cfg_name}.yaml"
                if not new_cfg_name.startswith("reel_"):
                    save_path = ROOT / "config" / "batch" / f"reel_{new_cfg_name}.yaml"
                _save_yaml(save_path, live_cfg)
                st.success(f"Config sauvegardée : {save_path.name}")

    with col_c:
        if st.button("🚀 Générer le Reel", type="primary", use_container_width=True, key="btn_gen"):
            tmp_cfg = ROOT / "output" / "_gen_tmp.yaml"
            _save_yaml(tmp_cfg, live_cfg)
            out_path = ROOT / "output" / output_name

            progress = st.progress(0, text="Initialisation...")
            log_area = st.empty()
            start_t  = time.time()

            with st.spinner(f"Génération en cours ({live_cfg['reel']['duration']}s de vidéo)..."):
                proc = subprocess.Popen(
                    [sys.executable, "main.py", "--config", str(tmp_cfg), "--output", str(out_path)],
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                )
                log_lines = []
                for line in proc.stdout:
                    log_lines.append(line.rstrip())
                    # Estimer la progression depuis les logs MoviePy
                    if "t:" in line and "%" in line:
                        try:
                            pct = int(line.split("%")[0].split("|")[-1].strip().split()[-1])
                            progress.progress(min(pct, 99) / 100, text=f"Rendu vidéo : {pct}%")
                        except Exception:
                            pass
                    elif "Writing audio" in line:
                        progress.progress(0.05, text="Export audio...")
                    elif "Writing video" in line:
                        progress.progress(0.10, text="Rendu des frames...")
                proc.wait()

            elapsed = time.time() - start_t
            progress.progress(1.0, text="Terminé !")

            if proc.returncode == 0 and out_path.exists():
                st.success(f"Reel généré en {elapsed:.0f}s — {out_path.stat().st_size // 1024} KB")
                with open(out_path, "rb") as _vf:
                    st.video(_vf.read())
                with open(out_path, "rb") as f:
                    st.download_button(
                        "⬇️ Télécharger le Reel",
                        data=f,
                        file_name=output_name,
                        mime="video/mp4",
                        type="primary",
                    )
            else:
                st.error("La génération a échoué.")
                with st.expander("Logs"):
                    st.code("\n".join(log_lines[-30:]))


# ═════════════════════════════════════════════════════════════════════════════
# ONGLET 2 — BATCH
# ═════════════════════════════════════════════════════════════════════════════

with tab_batch:
    st.markdown(
        '<div class="page-header">'
        '<div class="page-header-eyebrow">Production</div>'
        '<div class="page-header-title">Génération Batch</div>'
        '<div class="page-header-sub">'
        'Gérez plusieurs configs YAML simultanément — générez en série, '
        'suivez la progression et téléchargez les reels produits.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    configs = _batch_configs()
    out_batch = ROOT / "output" / "batch"
    out_batch.mkdir(parents=True, exist_ok=True)

    if not configs:
        st.info("Aucun fichier reel_*.yaml dans config/batch/. Créez-en un depuis l'onglet Générer.")
    else:
        # ── Tableau des configs ───────────────────────────────────────────────
        st.markdown(f"**{len(configs)} config(s) disponible(s)**")

        for cfg_path in configs:
            cfg       = _load_yaml(cfg_path)
            stem      = cfg_path.stem
            out_mp4   = out_batch / f"{stem}.mp4"
            has_video = out_mp4.exists()

            with st.container():
                st.markdown(f'<div class="reel-card">', unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])

                with c1:
                    hook_text = cfg.get("hook", {}).get("text", stem)
                    prompt_short = cfg.get("prompt", {}).get("text", "")[:60].replace("\n", " ")
                    st.markdown(f"**{stem}**")
                    st.caption(f"🎣 {hook_text[:50]}")
                    st.caption(f"💬 {prompt_short}...")

                with c2:
                    dur = cfg.get("reel", {}).get("duration", "?")
                    music = Path(cfg.get("audio", {}).get("background_music", "")).stem or "—"
                    st.caption(f"⏱️ {dur}s")
                    st.caption(f"🎵 {music}")

                with c3:
                    if has_video:
                        size_kb = out_mp4.stat().st_size // 1024
                        st.markdown(f'<span class="badge-ok">✓ {size_kb} KB</span>', unsafe_allow_html=True)
                        with open(out_mp4, "rb") as f:
                            st.download_button("⬇️", data=f, file_name=out_mp4.name,
                                               mime="video/mp4", key=f"dl_{stem}")
                    else:
                        st.markdown('<span class="badge-miss">Non généré</span>', unsafe_allow_html=True)

                with c4:
                    if st.button("▶ Générer", key=f"run_{stem}", type="secondary"):
                        with st.spinner(f"Génération de {stem}..."):
                            result = _run([
                                sys.executable, "main.py",
                                "--config", str(cfg_path),
                                "--output", str(out_batch / f"{stem}.mp4"),
                            ])
                        if result.returncode == 0:
                            st.success("✓ Généré !")
                            st.rerun()
                        else:
                            st.error("Échec")
                            st.code(result.stderr[-500:] if result.stderr else "")

                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # ── Générer tous ──────────────────────────────────────────────────────
        col_all1, col_all2 = st.columns([1, 3])
        with col_all1:
            if st.button("🚀 Générer TOUS les reels", type="primary", use_container_width=True):
                total = len(configs)
                prog  = st.progress(0, text="Batch en cours...")
                errors = []
                for i, cfg_path in enumerate(configs):
                    stem     = cfg_path.stem
                    out_mp4  = out_batch / f"{stem}.mp4"
                    prog.progress(i / total, text=f"[{i+1}/{total}] {stem}...")
                    result = _run([
                        sys.executable, "main.py",
                        "--config", str(cfg_path),
                        "--output", str(out_mp4),
                    ])
                    if result.returncode != 0:
                        errors.append(stem)
                prog.progress(1.0, text="Batch terminé !")
                if errors:
                    st.warning(f"{total - len(errors)}/{total} générés. Échecs : {', '.join(errors)}")
                else:
                    st.success(f"✓ {total} reels générés dans output/batch/")
                st.rerun()

        # ── Aperçu des vidéos générées ────────────────────────────────────────
        generated = sorted(out_batch.glob("reel_*.mp4"))
        if generated:
            st.markdown(f"### 🎬 {len(generated)} reel(s) généré(s)")
            cols = st.columns(min(len(generated), 3))
            for i, mp4 in enumerate(generated):
                with cols[i % 3]:
                    st.caption(f"**{mp4.stem}** — {mp4.stat().st_size // 1024} KB")
                    st.video(str(mp4))
                    with open(mp4, "rb") as f:
                        st.download_button(
                            f"⬇️ {mp4.name}", data=f,
                            file_name=mp4.name, mime="video/mp4",
                            key=f"gallery_{mp4.stem}",
                        )


# ═════════════════════════════════════════════════════════════════════════════
# ONGLET 3 — VIDÉOS
# ═════════════════════════════════════════════════════════════════════════════

with tab_video:
    st.markdown(
        '<div class="page-header">'
        '<div class="page-header-eyebrow">Assets</div>'
        '<div class="page-header-title">Vidéothèque B-Roll</div>'
        '<div class="page-header-sub">'
        'Recherche et téléchargement de B-roll via Pexels, gestion de la bibliothèque locale '
        'et thèmes prédéfinis CC0 sans clé API.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    vid_dir = ROOT / "assets" / "video"
    vid_dir.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — RECHERCHE PEXELS PAR MOT-CLÉ
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🔍 Rechercher des vidéos par mot-clé")

    has_key = bool(st.session_state.get("pexels_key", "").strip())
    if not has_key:
        st.info("💡 Entrez votre clé API Pexels dans la sidebar pour activer la recherche. "
                "Clé gratuite sur **pexels.com/api**")
    else:
        # ── Barre de recherche ────────────────────────────────────────────────
        col_q, col_n, col_orient, col_btn = st.columns([4, 1, 1, 1])
        with col_q:
            query = st.text_input(
                "Mot-clé ou phrase",
                placeholder="stats, meeting, laptop, data analysis, coffee...",
                key="pexels_query",
                label_visibility="collapsed",
            )
        with col_n:
            n_results = st.selectbox("Résultats", [6, 9, 15, 20], index=1, key="pexels_n")
        with col_orient:
            orient = st.selectbox("Format", ["landscape", "portrait", "square"], key="pexels_orient")
        with col_btn:
            search_btn = st.button("🔍 Rechercher", type="primary",
                                   use_container_width=True, key="btn_pexels_search")

        # ── Lancer la recherche ───────────────────────────────────────────────
        if search_btn:
            if not query.strip():
                st.warning("Entrez un mot-clé avant de rechercher.")
            else:
                with st.spinner(f"Recherche « {query} » sur Pexels..."):
                    import urllib.request, urllib.parse, json as _json
                    url = (
                        "https://api.pexels.com/videos/search"
                        f"?query={urllib.parse.quote(query.strip())}"
                        f"&per_page={n_results}&orientation={orient}"
                    )
                    headers = {
                        "Authorization": st.session_state["pexels_key"],
                        "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/2.0)",
                    }
                    try:
                        req = urllib.request.Request(url, headers=headers)
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            data = _json.loads(resp.read())
                        st.session_state["pexels_results"]    = data.get("videos", [])
                        st.session_state["pexels_total"]      = data.get("total_results", 0)
                        st.session_state["pexels_last_query"] = query.strip()
                        st.session_state["pexels_error"]      = None
                    except Exception as e:
                        st.session_state["pexels_results"] = []
                        st.session_state["pexels_error"]   = str(e)

        # ── Afficher les résultats ────────────────────────────────────────────
        err     = st.session_state.get("pexels_error")
        results = st.session_state.get("pexels_results", [])
        last_q  = st.session_state.get("pexels_last_query", "")
        total   = st.session_state.get("pexels_total", 0)

        if err:
            st.error(f"Erreur Pexels : {err}")

        elif results:
            st.caption(f"**{total} vidéos** trouvées pour « {last_q} » — {len(results)} affichées")
            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # Afficher les résultats ligne par ligne (3 cartes par ligne)
            for row_start in range(0, len(results), 3):
                row_videos = results[row_start:row_start + 3]
                cols = st.columns(3)

                for col_idx, video in enumerate(row_videos):
                    # Chercher le meilleur fichier (critères élargis)
                    files = video.get("video_files", [])
                    mp4_files = [f for f in files if f.get("file_type") == "video/mp4"]
                    if not mp4_files:
                        mp4_files = files   # fallback : prendre n'importe quel format
                    mp4_files.sort(key=lambda f: f.get("width", 0), reverse=True)
                    best = mp4_files[0] if mp4_files else None
                    if not best:
                        continue

                    thumb    = video.get("image", "")
                    duration = video.get("duration", 0)
                    author   = video.get("user", {}).get("name", "")
                    pex_url  = video.get("url", "")
                    vid_w    = best.get("width", 0)
                    vid_h    = best.get("height", 0)
                    dl_url   = best.get("link", "")
                    quality  = best.get("quality", "mp4").upper()
                    i        = row_start + col_idx

                    with cols[col_idx]:
                        # ── Thumbnail via <img> HTML (fonctionne mieux que st.image pour les URLs externes)
                        if thumb:
                            st.markdown(
                                f'<img src="{thumb}" '
                                f'style="width:100%;border-radius:10px;margin-bottom:6px;" />',
                                unsafe_allow_html=True,
                            )

                        # ── Métadonnées en une ligne
                        quality_color = "#4ade80" if quality in ("HD", "UHD") else "#facc15"
                        st.markdown(
                            f'<span style="background:#1a3a2a;color:{quality_color};'
                            f'padding:1px 8px;border-radius:10px;font-size:.75rem;'
                            f'font-weight:700">{quality}</span> '
                            f'<span style="color:#b0b0c0;font-size:.8rem">'
                            f'&nbsp;{vid_w}×{vid_h} · {duration}s</span>',
                            unsafe_allow_html=True,
                        )
                        st.caption(f"📸 {author}")

                        # ── Lien Pexels
                        if pex_url:
                            st.markdown(
                                f'<a href="{pex_url}" target="_blank" '
                                f'style="font-size:.75rem;color:#E8B84B;text-decoration:none;">'
                                f'Voir sur Pexels ↗</a>',
                                unsafe_allow_html=True,
                            )

                        # ── Nom du fichier (input natif Streamlit — pas dans un <div>)
                        default_name = f"{_slugify(last_q)}_{i+1:02d}.mp4"
                        fname = st.text_input(
                            "Nom",
                            value=default_name,
                            key=f"pex_fname_{i}",
                            label_visibility="collapsed",
                        )

                        # ── Bouton télécharger
                        if st.button(
                            "💾 Télécharger",
                            key=f"pex_dl_{i}",
                            type="primary",
                            use_container_width=True,
                        ):
                            dest = vid_dir / fname
                            prog = st.progress(0, text="Connexion...")
                            import urllib.request as _ur
                            _hdrs = {
                                "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/2.0)",
                                "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                            }
                            try:
                                req = _ur.Request(dl_url, headers=_hdrs)
                                with _ur.urlopen(req, timeout=120) as resp:
                                    total_bytes = int(resp.headers.get("Content-Length", 0))
                                    downloaded  = 0
                                    with open(dest, "wb") as f:
                                        while True:
                                            chunk = resp.read(65536)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                            downloaded += len(chunk)
                                            if total_bytes:
                                                prog.progress(
                                                    downloaded / total_bytes,
                                                    text=f"{downloaded // 1024} / {total_bytes // 1024} KB",
                                                )
                                prog.progress(1.0, text="Terminé !")
                                size_mb = dest.stat().st_size / (1024 * 1024)
                                st.success(f"✅ {fname} ({size_mb:.1f} MB)")
                                st.session_state["prefill_video"] = fname
                                st.session_state["prefill_query"] = last_q
                            except Exception as e:
                                st.error(f"Échec : {e}")
                                if dest.exists():
                                    dest.unlink()
                            st.rerun()

                        st.markdown("---")

            # ── CTA : créer un reel avec la dernière vidéo téléchargée ────────
            if st.session_state.get("prefill_video"):
                vname = st.session_state["prefill_video"]
                qname = st.session_state.get("prefill_query", "")
                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="reel-card" style="border-color:#E8B84B">'
                    f'<b>✨ Vidéo téléchargée : <code>{vname}</code></b><br>'
                    f'<span style="color:#8e8ea0">Allez dans <b>🎬 Générer</b> '
                    f'→ section Intro → sélectionnez <code>{vname}</code> '
                    f'pour créer votre reel.</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # Suggestion de contenu basée sur le mot-clé
                if st.button("✨ Pré-remplir un Reel avec ce thème", type="primary",
                             key="btn_prefill_reel"):
                    st.session_state["gen_prefill"] = {
                        "intro_video": str(vid_dir / vname),
                        "query": qname,
                    }
                    st.info(f"Allez dans l'onglet **🎬 Générer** — la vidéo est pré-sélectionnée.")

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — THÈMES PRÉDÉFINIS (Mixkit fallback)
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("📦 Télécharger les thèmes prédéfinis (Mixkit CC0 — sans clé API)", expanded=False):
        try:
            from scripts.download_batch_videos import THEMES, download_theme, DEST_DIR
            theme_cols = st.columns(len(THEMES))
            for i, (theme_key, theme) in enumerate(THEMES.items()):
                with theme_cols[i]:
                    dest    = DEST_DIR / theme["filename"]
                    has_it  = dest.exists() and dest.stat().st_size > 100_000
                    icon    = "✅" if has_it else "❌"
                    st.markdown(f"{icon} **{theme_key}**")
                    st.caption(theme["description"])
                    if has_it:
                        st.caption(f"{dest.stat().st_size // 1024} KB")
                    if st.button(
                        "Re-DL" if has_it else "Télécharger",
                        key=f"theme_dl_{theme_key}", type="secondary",
                    ):
                        api = st.session_state.get("pexels_key") or None
                        with st.spinner(f"Téléchargement {theme_key}..."):
                            ok = download_theme(theme_key, api_key=api, force=True)
                        if ok:
                            st.success("OK !")
                            st.rerun()
                        else:
                            st.error("Échec.")
        except ImportError:
            st.warning("Module download_batch_videos non disponible.")

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — BIBLIOTHÈQUE LOCALE
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🗂️ Bibliothèque locale")
    existing = sorted(vid_dir.glob("*.mp4"))
    if existing:
        st.caption(f"{len(existing)} vidéo(s) disponible(s) dans assets/video/")
        lib_cols = st.columns(3)
        for i, vid in enumerate(existing):
            with lib_cols[i % 3]:
                size_mb = vid.stat().st_size / (1024 * 1024)
                # Badge si cette vidéo vient d'être téléchargée
                is_new  = (st.session_state.get("prefill_video") == vid.name)
                label   = f"{'🆕 ' if is_new else ''}**{vid.name}** — {size_mb:.1f} MB"
                st.caption(label)
                st.video(str(vid))
                if st.button("🗑️ Supprimer", key=f"del_vid_{vid.stem}", type="secondary"):
                    vid.unlink()
                    st.rerun()
    else:
        st.info("Aucune vidéo dans la bibliothèque. Utilisez la recherche ci-dessus.")

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — UPLOAD MANUEL
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("📤 Ajouter une vidéo depuis mon ordinateur", expanded=False):
        st.caption("Uploadez votre propre vidéo (MP4 / MOV — redimensionnée automatiquement).")
        uploaded = st.file_uploader("Choisir un fichier", type=["mp4", "mov", "avi"],
                                    key="vid_uploader")
        if uploaded:
            target_name = st.text_input("Nom du fichier vidéo", value=uploaded.name,
                                        key="upload_video_name")
            if st.button("💾 Sauvegarder dans assets/video/", type="primary"):
                dest = vid_dir / target_name
                with open(dest, "wb") as f:
                    f.write(uploaded.read())
                st.success(f"Vidéo sauvegardée : {dest.name}")
                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# ONGLET 4 — MUSIQUE
# ═════════════════════════════════════════════════════════════════════════════

with tab_music:
    st.markdown(
        '<div class="page-header">'
        '<div class="page-header-eyebrow">Assets</div>'
        '<div class="page-header-title">Bibliothèque Musicale</div>'
        '<div class="page-header-sub">'
        'Beats lo-fi synthétiques générés localement — aucune dépendance externe, '
        'gestion des pistes et aperçu audio intégré.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    try:
        from utils.audio_gen import CHORD_PROGRESSIONS, ensure_lofi_beat
        audio_gen_ok = True
    except ImportError:
        audio_gen_ok = False
        st.warning("Module audio_gen non disponible.")

    if audio_gen_ok:
        MUSIC_INFO = {
            "dm": {"label": "Dm — Chaud & classique",  "emoji": "🌅", "desc": "Dm - Am - Bb - F"},
            "am": {"label": "Am — Mélancolique",        "emoji": "🌙", "desc": "Am - F - C - G"},
            "em": {"label": "Em — Lumineux & énergique","emoji": "⚡", "desc": "Em - C - G - D"},
            "gm": {"label": "Gm — Sombre & introspectif","emoji": "🌑","desc": "Gm - Eb - Bb - F"},
        }

        # ── Générer toutes les musiques manquantes ────────────────────────────
        any_missing = any(
            not (ROOT / f"assets/audio/lofi_beat_{k}.wav").exists()
            for k in CHORD_PROGRESSIONS
        )
        if any_missing:
            if st.button("⚡ Générer toutes les musiques manquantes", type="primary"):
                with st.spinner("Génération des beats lo-fi..."):
                    for key, (bpm, _) in CHORD_PROGRESSIONS.items():
                        path = f"assets/audio/lofi_beat_{key}.wav"
                        ensure_lofi_beat(path, duration=35.0, key=key)
                st.success("Tous les beats générés !")
                st.rerun()

        st.markdown("---")

        # ── Grille des 4 tonalités ────────────────────────────────────────────
        cols = st.columns(2)
        for i, (key, (bpm, chords)) in enumerate(CHORD_PROGRESSIONS.items()):
            info  = MUSIC_INFO[key]
            path  = ROOT / f"assets/audio/lofi_beat_{key}.wav"
            exists = path.exists() and path.stat().st_size > 10_000

            with cols[i % 2]:
                st.markdown(f'<div class="reel-card">', unsafe_allow_html=True)
                st.markdown(f"### {info['emoji']} {info['label']}")
                st.caption(f"**{bpm} BPM** — Progression : {info['desc']}")

                if exists:
                    size_kb = path.stat().st_size // 1024
                    st.caption(f"📁 lofi_beat_{key}.wav — {size_kb} KB")
                    st.audio(str(path), format="audio/wav")

                    # Quels reels utilisent cette musique ?
                    users = [
                        c.stem for c in _batch_configs()
                        if f"lofi_beat_{key}" in _load_yaml(c).get("audio", {}).get("background_music", "")
                    ]
                    if users:
                        st.caption(f"Utilisée par : {', '.join(users)}")

                    col_regen, _ = st.columns([1, 2])
                    with col_regen:
                        if st.button("🔄 Régénérer", key=f"regen_{key}", type="secondary"):
                            with st.spinner(f"Génération {key}..."):
                                path.unlink()
                                ensure_lofi_beat(str(path), duration=35.0, key=key)
                            st.success("Régénéré !")
                            st.rerun()
                else:
                    st.markdown('<span class="badge-miss">Non généré</span>', unsafe_allow_html=True)
                    if st.button(f"▶ Générer ({bpm} BPM)", key=f"gen_{key}", type="primary"):
                        with st.spinner(f"Génération {key} @ {bpm} BPM..."):
                            ensure_lofi_beat(str(path), duration=35.0, key=key)
                        st.success(f"lofi_beat_{key}.wav généré !")
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # ── Upload custom ─────────────────────────────────────────────────────────
    st.markdown("### 🎵 Ajouter une musique personnalisée")
    st.caption("Uploadez un fichier MP3 ou WAV à utiliser comme fond musical.")
    uploaded_music = st.file_uploader("Choisir un fichier audio", type=["mp3", "wav", "ogg"])
    if uploaded_music:
        music_name = st.text_input("Nom du fichier audio", value=uploaded_music.name, key="upload_music_name")
        if st.button("💾 Sauvegarder dans assets/audio/", type="primary"):
            dest = ROOT / "assets" / "audio" / music_name
            with open(dest, "wb") as f:
                f.write(uploaded_music.read())
            st.success(f"Musique sauvegardée : {dest.name}")
            st.rerun()
