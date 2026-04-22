"""ui/css.py — Design System CSS. Call inject_css() once at app startup."""
import streamlit as st

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
  --brand:        #D4A843;
  --brand-dark:   #B8901E;
  --brand-deeper: #966F0A;
  --brand-light:  #FEF9ED;
  --brand-border: #F0D080;
  --bg:           #F7F8FA;
  --surface:      #FFFFFF;
  --surface-2:    #F3F4F6;
  --surface-3:    #EAECF0;
  --border:       #E5E7EB;
  --border-dark:  #D1D5DB;
  --text:         #111827;
  --text-2:       #374151;
  --text-muted:   #6B7280;
  --text-faint:   #9CA3AF;
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
  --r-xs:   3px;  --r-sm:   6px;  --r:      8px;
  --r-md:   10px; --r-lg:   14px; --r-xl:   20px; --r-full: 9999px;
  --shadow-xs: 0 1px 2px rgba(0,0,0,.06);
  --shadow-sm: 0 1px 3px rgba(0,0,0,.1), 0 1px 2px rgba(0,0,0,.06);
  --shadow:    0 4px 8px rgba(0,0,0,.08), 0 2px 4px rgba(0,0,0,.05);
  --shadow-md: 0 10px 18px rgba(0,0,0,.1), 0 4px 6px rgba(0,0,0,.05);
  --gold: var(--brand); --gold-dark: var(--brand-dark);
  --gold-light: var(--brand-light); --gold-border: var(--brand-border);
}

*, *::before, *::after { box-sizing: border-box; }
html, body, .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  background: var(--bg) !important;
  -webkit-font-smoothing: antialiased;
}
footer, #MainMenu, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stStatusWidget"] {
  display: none !important; visibility: hidden !important;
}
.main .block-container {
  padding-top: 1.75rem !important;
  padding-left: 2.25rem !important;
  padding-right: 2.25rem !important;
  max-width: 1280px !important;
}
section[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

h1 { font-size:1.5rem !important; font-weight:800 !important; color:var(--text) !important;
     letter-spacing:-0.025em !important; line-height:1.25 !important; margin-bottom:0.25rem !important; }
h2 { font-size:1.2rem !important; font-weight:700 !important; color:var(--text) !important;
     letter-spacing:-0.02em !important; margin-bottom:0.2rem !important; }
h3 { font-size:0.975rem !important; font-weight:600 !important; color:var(--text) !important; }
p, .stMarkdown p { color:var(--text-2) !important; font-size:0.9rem !important; line-height:1.55 !important; }
.stCaption, small { color:var(--text-muted) !important; font-size:0.8rem !important; }

.stTextArea textarea, .stTextInput input {
  background:var(--surface) !important; color:var(--text) !important;
  border:1.5px solid var(--border) !important; border-radius:var(--r) !important;
  font-size:0.9rem !important; font-family:'Inter',sans-serif !important;
  transition:border-color .15s ease, box-shadow .15s ease;
}
.stTextArea textarea:focus, .stTextInput input:focus {
  border-color:var(--brand) !important;
  box-shadow:0 0 0 3px rgba(212,168,67,.18) !important;
}
.stSelectbox [data-baseweb="select"] > div:first-child {
  background:var(--surface) !important; border:1.5px solid var(--border) !important;
  border-radius:var(--r) !important;
}
.stNumberInput input { border:1.5px solid var(--border) !important; border-radius:var(--r) !important; }
label, .stWidgetLabel p {
  font-size:0.82rem !important; font-weight:600 !important;
  color:var(--text-2) !important; letter-spacing:0.01em !important;
}

.stButton > button {
  height:40px !important; font-size:0.875rem !important; font-weight:600 !important;
  border-radius:var(--r) !important; transition:all .15s ease !important;
  letter-spacing:0.01em !important; font-family:'Inter',sans-serif !important;
}
.stButton > button[kind="primary"] {
  background:var(--brand) !important; color:#fff !important;
  border:1.5px solid var(--brand-dark) !important;
  box-shadow:var(--shadow-xs),inset 0 1px 0 rgba(255,255,255,.12) !important;
}
.stButton > button[kind="primary"]:hover {
  background:var(--brand-dark) !important; border-color:var(--brand-deeper) !important;
  box-shadow:var(--shadow-sm) !important; transform:translateY(-1px) !important;
}
.stButton > button[kind="primary"]:active { transform:translateY(0) !important; }
.stButton > button[kind="secondary"] {
  background:var(--surface) !important; border:1.5px solid var(--border) !important;
  color:var(--text-2) !important; box-shadow:var(--shadow-xs) !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color:var(--brand-border) !important; color:var(--brand-dark) !important;
  background:var(--brand-light) !important; box-shadow:var(--shadow-sm) !important;
}

.stTabs [data-baseweb="tab-list"] {
  gap:2px !important; background:var(--surface-2) !important;
  border-radius:var(--r-md) !important; padding:3px !important;
  border-bottom:none !important; width:fit-content !important;
  max-width:100% !important; margin-bottom:1.5rem !important;
}
.stTabs [data-baseweb="tab"] {
  color:var(--text-muted) !important; font-weight:500 !important;
  font-size:0.825rem !important; padding:0.38rem 0.85rem !important;
  border-radius:var(--r-sm) !important; transition:all .12s ease !important;
  border:none !important; background:transparent !important; white-space:nowrap !important;
}
.stTabs [data-baseweb="tab"]:hover { color:var(--text) !important; background:rgba(0,0,0,.04) !important; }
.stTabs [aria-selected="true"] {
  background:var(--surface) !important; color:var(--text) !important;
  font-weight:700 !important; box-shadow:var(--shadow-xs) !important; border:none !important;
}

.stProgress > div > div { background:var(--surface-3) !important; border-radius:var(--r-full) !important; height:5px !important; }
.stProgress > div > div > div { background:linear-gradient(90deg,var(--brand),var(--brand-dark)) !important; border-radius:var(--r-full) !important; }

[data-testid="metric-container"] {
  background:var(--surface) !important; border:1px solid var(--border) !important;
  border-radius:var(--r-md) !important; padding:1rem 1.2rem !important;
  box-shadow:var(--shadow-xs) !important;
}
[data-testid="stMetricLabel"] { font-size:0.72rem !important; font-weight:700 !important; color:var(--text-muted) !important; text-transform:uppercase !important; letter-spacing:0.07em !important; }
[data-testid="stMetricValue"] { font-size:1.65rem !important; font-weight:800 !important; color:var(--text) !important; letter-spacing:-0.03em !important; }

.streamlit-expanderHeader {
  background:var(--surface) !important; border:1px solid var(--border) !important;
  border-radius:var(--r) !important; font-weight:600 !important;
  font-size:0.875rem !important; color:var(--text) !important; padding:0.65rem 1rem !important;
}
.streamlit-expanderHeader:hover { background:var(--surface-2) !important; }
.streamlit-expanderContent {
  border:1px solid var(--border) !important; border-top:none !important;
  border-radius:0 0 var(--r) var(--r) !important; padding:1rem !important;
}

.stDataFrame { border:1px solid var(--border) !important; border-radius:var(--r-md) !important; overflow:hidden !important; box-shadow:var(--shadow-xs) !important; }

/* ── Custom Components ── */
.page-header { padding-bottom:1.4rem; border-bottom:1px solid var(--border); margin-bottom:1.75rem; }
.page-header-eyebrow { font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:var(--brand); margin-bottom:4px; }
.page-header-title { font-size:1.45rem; font-weight:800; color:var(--text); letter-spacing:-0.025em; line-height:1.2; margin:0 0 6px 0; }
.page-header-sub { font-size:0.875rem; color:var(--text-muted); margin:0; line-height:1.5; }

.app-brand { display:flex; align-items:center; gap:10px; padding:1.1rem 1rem 0.9rem; border-bottom:1px solid var(--border); }
.app-brand-icon { width:34px; height:34px; background:var(--brand); border-radius:var(--r); display:flex; align-items:center; justify-content:center; font-size:1rem; flex-shrink:0; box-shadow:0 2px 6px rgba(212,168,67,.35); }
.app-brand-name { font-size:0.9rem; font-weight:800; color:var(--text); line-height:1.1; }
.app-brand-handle { font-size:0.7rem; color:var(--text-muted); font-weight:500; }

.status-row { display:flex; align-items:center; gap:7px; padding:0.3rem 1rem; font-size:0.78rem; color:var(--text-2); }
.status-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
.status-dot.ok    { background:var(--success); box-shadow:0 0 5px rgba(5,150,105,.5); }
.status-dot.warn  { background:var(--warning); }
.status-dot.error { background:var(--error); }
.status-dot.off   { background:var(--text-faint); }

.sidebar-section-label { font-size:0.65rem; font-weight:700; text-transform:uppercase; letter-spacing:0.09em; color:var(--text-faint); padding:0.65rem 1rem 0.2rem; }
.kpi-row { display:grid; grid-template-columns:1fr 1fr; gap:6px; padding:0 0.8rem 0.75rem; }
.kpi-item { background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r); padding:0.55rem 0.6rem; text-align:center; }
.kpi-item:hover { border-color:var(--brand-border); }
.kpi-item-value { font-size:1.05rem; font-weight:800; color:var(--text); letter-spacing:-0.02em; }
.kpi-item-label { font-size:0.65rem; color:var(--text-muted); font-weight:500; margin-top:1px; }

.gold-hr, hr.section-hr { border:none; border-top:1px solid var(--border); margin:1.4rem 0; }

.section-title { font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.09em; color:var(--text-muted); margin:1.5rem 0 0.6rem; display:flex; align-items:center; gap:0.5rem; }
.section-title::after { content:''; flex:1; height:1px; background:var(--border); }

.step-bar { display:flex; align-items:center; background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-xl); padding:0.45rem 1rem; margin:0 0 1.75rem 0; gap:0; }
.step-item { display:flex; align-items:center; gap:0.4rem; flex:1; font-size:0.73rem; font-weight:600; color:var(--text-muted); white-space:nowrap; }
.step-item .step-num { width:22px; height:22px; border-radius:50%; flex-shrink:0; background:var(--surface); border:1.5px solid var(--border); color:var(--text-muted); font-size:0.68rem; font-weight:700; display:flex; align-items:center; justify-content:center; }
.step-item.done .step-num  { background:var(--success-bg); border-color:var(--success-bd); color:var(--success); }
.step-item.active .step-num { background:var(--brand-light); border-color:var(--brand-border); color:var(--brand); box-shadow:0 0 0 3px rgba(212,168,67,.15); }
.step-item.active { color:var(--brand); font-weight:700; }
.step-item.done   { color:var(--success); }
.step-connector { flex:1; height:1.5px; background:var(--border); margin:0 0.35rem; max-width:40px; border-radius:1px; }
.step-connector.done { background:var(--success-bd); }

.callout { border-radius:var(--r); padding:0.7rem 1rem; margin:0.5rem 0; font-size:0.85rem; line-height:1.55; border-left:4px solid; }
.callout-info    { background:var(--info-bg);    border-color:var(--info);    color:#1e40af; }
.callout-success { background:var(--success-bg); border-color:var(--success); color:#065f46; }
.callout-warning { background:var(--warning-bg); border-color:var(--warning); color:#92400e; }
.callout-error   { background:var(--error-bg);   border-color:var(--error);   color:#991b1b; }

.badge { display:inline-flex; align-items:center; gap:4px; padding:2px 9px; border-radius:var(--r-full); font-size:0.72rem; font-weight:700; border:1.5px solid transparent; }
.badge-ok    { background:var(--success-bg); color:var(--success); border-color:var(--success-bd); }
.badge-miss  { background:var(--error-bg);   color:var(--error);   border-color:var(--error-bd); }
.badge-warn  { background:var(--warning-bg); color:var(--warning); border-color:var(--warning-bd); }
.badge-info  { background:var(--info-bg);    color:var(--info);    border-color:var(--info-bd); }
.badge-gold  { background:var(--brand-light); color:var(--brand);  border-color:var(--brand-border); }
.badge-gen   { background:var(--warning-bg); color:var(--warning); border-color:var(--warning-bd); }

.concept-card { background:var(--surface); border:1.5px solid var(--border); border-radius:var(--r-lg); overflow:hidden; transition:border-color .15s,box-shadow .15s,transform .15s; height:100%; }
.concept-card:hover { border-color:var(--brand-border); box-shadow:var(--shadow); transform:translateY(-2px); }
.concept-card.selected { border-color:var(--brand); box-shadow:0 0 0 3px rgba(212,168,67,.15); }
.concept-card-header { padding:0.65rem 0.9rem; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; }
.concept-card-body { padding:0.85rem 0.9rem; }
.concept-card-hook { background:var(--brand-light); border-left:3px solid var(--brand); border-radius:0 var(--r-sm) var(--r-sm) 0; padding:0.55rem 0.75rem; margin:0.5rem 0 0.65rem; font-size:0.9rem; font-weight:700; color:var(--text); line-height:1.35; font-style:italic; }
.concept-card-meta { font-size:0.77rem; color:var(--text-muted); line-height:1.4; display:flex; gap:0.75rem; flex-wrap:wrap; margin-bottom:0.5rem; }
.concept-card-preview { font-size:0.8rem; color:var(--text-muted); line-height:1.45; font-style:italic; margin-top:0.4rem; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }

.script-block { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md); overflow:hidden; margin-bottom:0.75rem; }
.script-line { display:flex; gap:0.8rem; align-items:flex-start; padding:0.65rem 1rem; border-bottom:1px solid var(--surface-2); transition:background .1s; }
.script-line:last-child { border-bottom:none; }
.script-line:hover { background:var(--surface-2); }
.script-label { min-width:70px; font-weight:700; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.06em; padding-top:2px; flex-shrink:0; }
.script-text { color:var(--text); font-size:0.9rem; line-height:1.5; flex:1; }

.hook-winner  { background:var(--brand-light); border:2px solid var(--brand-border); border-radius:var(--r-lg); padding:1rem 1.25rem; margin:0.75rem 0; box-shadow:var(--shadow-sm); }
.hook-accepted { background:var(--success-bg); border:1px solid var(--success-bd); border-radius:var(--r); padding:0.75rem 1rem; margin-bottom:0.75rem; color:#065f46; }
.hook-rejected { background:var(--error-bg);   border:1px solid var(--error-bd);   border-radius:var(--r); padding:0.75rem 1rem; margin-bottom:0.75rem; color:#991b1b; }

.score-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:6px; margin:0.75rem 0; }
.score-cell { text-align:center; padding:0.55rem 0.3rem; background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r); }
.score-cell-value { font-size:1.25rem; font-weight:800; line-height:1; }
.score-cell-label { font-size:0.63rem; color:var(--text-muted); margin-top:2px; font-weight:500; }

.montage-table { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md); overflow:hidden; margin:0.75rem 0; }
.montage-row { display:flex; align-items:center; gap:0.7rem; padding:0.6rem 0.9rem; border-bottom:1px solid var(--surface-2); font-size:0.875rem; transition:background .1s; }
.montage-row:last-child { border-bottom:none; }
.montage-row:hover { background:var(--surface-2); }
.montage-idx { width:20px; height:20px; background:var(--surface-2); border-radius:var(--r-xs); display:flex; align-items:center; justify-content:center; font-size:0.65rem; font-weight:700; color:var(--text-muted); flex-shrink:0; }
.montage-type { min-width:62px; font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; }
.montage-text { flex:1; color:var(--text); line-height:1.4; }
.montage-dur { font-size:0.75rem; color:var(--text-muted); font-weight:600; background:var(--surface-2); padding:2px 8px; border-radius:var(--r-full); flex-shrink:0; }
.montage-anim { font-size:0.7rem; color:var(--text-faint); min-width:60px; text-align:right; }

.caption-box { background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-md); padding:1rem 1.1rem; font-size:0.875rem; line-height:1.65; color:var(--text-2); white-space:pre-wrap; font-family:'Inter',sans-serif; }

.reel-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md); padding:0.85rem 1rem; margin-bottom:6px; display:flex; align-items:center; gap:0.75rem; transition:border-color .15s,box-shadow .15s; }
.reel-card:hover { border-color:var(--brand-border); box-shadow:var(--shadow-sm); }

.empty-state { text-align:center; padding:3.5rem 2rem; color:var(--text-muted); background:var(--surface); border:1.5px dashed var(--border); border-radius:var(--r-lg); margin:1rem 0; }
.empty-state-icon { font-size:2.25rem; margin-bottom:0.65rem; opacity:.55; }
.empty-state-title { font-size:0.975rem; font-weight:700; color:var(--text-2); margin-bottom:0.35rem; }
.empty-state-sub { font-size:0.84rem; color:var(--text-muted); }

.overlay-pill { display:inline-block; background:#111827; color:#F2F0EA; font-weight:700; font-size:0.875rem; padding:0.3rem 0.75rem; border-radius:var(--r); margin:3px; letter-spacing:0.01em; }

/* KPI dashboard row */
.kpi-dashboard { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:1.75rem; }
.kpi-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md); padding:1rem 1.2rem; box-shadow:var(--shadow-xs); }
.kpi-card-label { font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-muted); margin-bottom:6px; }
.kpi-card-value { font-size:1.8rem; font-weight:800; color:var(--text); letter-spacing:-0.03em; line-height:1; }
.kpi-card-sub   { font-size:0.75rem; color:var(--text-muted); margin-top:4px; }
.kpi-card.accent { border-color:var(--brand-border); background:var(--brand-light); }
.kpi-card.accent .kpi-card-value { color:var(--brand-dark); }

@media (max-width:768px) {
  .main .block-container { padding-left:1rem !important; padding-right:1rem !important; }
  [data-testid="column"] { width:100% !important; flex:1 1 100% !important; min-width:100% !important; }
  h1 { font-size:1.2rem !important; }
  .kpi-dashboard { grid-template-columns:1fr 1fr; }
  .step-bar { flex-wrap:wrap; gap:0.3rem; border-radius:var(--r); }
  .step-connector { display:none; }
  .kpi-row { padding:0 0.5rem 0.5rem; }
  .stTabs [data-baseweb="tab-list"] { overflow-x:auto !important; flex-wrap:nowrap !important; width:100% !important; }
}
"""


def inject_css() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
