"""
Interface web — Reels Generator @ownyourtime.ai
Lancez avec : streamlit run app.py
"""
from __future__ import annotations

import os
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
    for _secret_key in ("ANTHROPIC_API_KEY", "PEXELS_API_KEY"):
        _val = _st_tmp.secrets.get(_secret_key, "")
        if _val:
            _os.environ.setdefault(_secret_key, _val)
except Exception:
    pass

# Import du moteur génératif (nécessite ANTHROPIC_API_KEY)
try:
    from generate import generate_variants, generate_viral_script, generate_montage_plan, build_yaml, build_yaml_from_viral_script, generate_caption, generate_ab_versions, optimize_script_hooks, BROLL_CATEGORIES
    from utils.hook_optimizer import analyze_hook, analyze_solution, inject_winner
    from utils.hook_engine import optimize_hooks, save_hook_result
    from utils.idea_classifier import classify_idea, CATEGORIES
    from utils.pexels import get_pexels_videos, _api_key as _pexels_key_fn
    from utils.validation import validate_config, self_check
    _GEN_AVAILABLE = bool(_os.environ.get("ANTHROPIC_API_KEY"))
except Exception:
    _GEN_AVAILABLE = False

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
/* Palette */
:root {
  --midnight:  #FFFFFF;
  --deep-ink:  #F5F5F7;
  --gold:      #C8972A;
  --ivory:     #1A1A2E;
  --muted:     #6B6B8A;
}

/* Fond général */
.stApp { background-color: #FFFFFF; }
section[data-testid="stSidebar"] { background-color: #F5F5F7; border-right: 1px solid #E0E0E8; }

/* Titres */
h1, h2, h3 { color: #1A1A2E !important; }

/* Texte général */
p, label, .stMarkdown, .stCaption { color: #1A1A2E !important; }

/* Bouton primaire gold */
.stButton > button[kind="primary"] {
  background: var(--gold);
  color: #FFFFFF;
  font-weight: 700;
  border: none;
  border-radius: 8px;
  padding: 0.5rem 1.5rem;
}
.stButton > button[kind="primary"]:hover {
  background: #b5841f;
  color: #FFFFFF;
}

/* Bouton secondaire */
.stButton > button[kind="secondary"] {
  background: #FFFFFF;
  border: 1px solid #C8C8D8;
  color: #1A1A2E;
  border-radius: 8px;
}
.stButton > button[kind="secondary"]:hover {
  border-color: var(--gold);
  color: var(--gold);
}

/* Cartes / blocs */
.reel-card {
  background: #F5F5F7;
  border: 1px solid #E0E0E8;
  border-radius: 12px;
  padding: 1rem 1.2rem;
  margin-bottom: 0.75rem;
}
.reel-card:hover { border-color: var(--gold); }

/* Badge statut */
.badge-ok   { background:#d1fae5; color:#065f46; padding:2px 10px;
              border-radius:20px; font-size:0.8rem; font-weight:600; }
.badge-miss { background:#fee2e2; color:#991b1b; padding:2px 10px;
              border-radius:20px; font-size:0.8rem; font-weight:600; }
.badge-gen  { background:#fef9c3; color:#854d0e; padding:2px 10px;
              border-radius:20px; font-size:0.8rem; font-weight:600; }

/* Séparateur gold */
.gold-hr { border: none; border-top: 2px solid var(--gold);
           opacity: 0.4; margin: 1rem 0; }

/* Zone texte / inputs */
.stTextArea textarea, .stTextInput input {
  background: #FFFFFF !important;
  color: #1A1A2E !important;
  border: 1px solid #C8C8D8 !important;
  border-radius: 8px !important;
}

/* Slider */
.stSlider > div { color: #1A1A2E; }

/* Onglets */
.stTabs [data-baseweb="tab"] {
  color: #6B6B8A;
  font-weight: 600;
}
.stTabs [aria-selected="true"] {
  color: var(--gold) !important;
  border-bottom: 2px solid var(--gold) !important;
}

/* Logo sidebar */
.sidebar-logo {
  text-align: center;
  padding: 1rem 0 1.5rem 0;
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--gold);
  letter-spacing: 1px;
}
.sidebar-sub {
  text-align: center;
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: -1.2rem;
  margin-bottom: 1rem;
}

/* ── Hook score card ──────────────────────────────────────── */
.hook-score-bar { height: 8px; border-radius: 4px; margin: 4px 0 10px 0; }
.hook-accepted  { background:#d1fae5; border:1px solid #6ee7b7;
                  border-radius:10px; padding:1rem; margin-bottom:1rem; }
.hook-rejected  { background:#fee2e2; border:1px solid #fca5a5;
                  border-radius:10px; padding:1rem; margin-bottom:1rem; }
.hook-winner    { background:#FFF8EC; border:2px solid #C8972A;
                  border-radius:10px; padding:1rem; margin:0.75rem 0; }

/* ── Responsive mobile ────────────────────────────────────── */
/* Tous les boutons : hauteur min 48px (touch target) */
.stButton > button {
  min-height: 48px !important;
  font-size: 0.95rem !important;
}

/* Cards 3 colonnes → 1 colonne sur mobile */
@media (max-width: 768px) {
  /* Colonnes Streamlit empilées */
  [data-testid="column"] {
    width: 100% !important;
    flex: 1 1 100% !important;
    min-width: 100% !important;
  }
  /* Sidebar réduite */
  section[data-testid="stSidebar"] {
    min-width: 0 !important;
    width: 100% !important;
  }
  /* Titres plus petits */
  h1 { font-size: 1.4rem !important; }
  h2 { font-size: 1.2rem !important; }
  h3 { font-size: 1.05rem !important; }
  /* Inputs pleine largeur */
  .stTextInput input, .stTextArea textarea {
    font-size: 1rem !important;
  }
  /* Métriques sidebar côte à côte */
  [data-testid="metric-container"] {
    padding: 0.3rem !important;
  }
  /* Tabs scrollables horizontalement */
  .stTabs [data-baseweb="tab-list"] {
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
  }
  .stTabs [data-baseweb="tab"] {
    white-space: nowrap !important;
    font-size: 0.82rem !important;
    padding: 0.4rem 0.6rem !important;
  }
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
    st.markdown('<div class="sidebar-logo">🎬 REELS GEN</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">@ownyourtime.ai</div>', unsafe_allow_html=True)
    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # Stats rapides
    n_videos = len(_available_videos())
    n_music  = len(_available_music())
    n_batch  = len(_batch_configs())
    n_output = len(list((ROOT / "output" / "batch").glob("*.mp4"))) if (ROOT / "output" / "batch").exists() else 0

    col1, col2 = st.columns(2)
    col1.metric("Vidéos", n_videos)
    col2.metric("Musiques", n_music)
    col1.metric("Configs", n_batch)
    col2.metric("Reels", n_output)

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

    # Clé API Pexels (persistée en session)
    st.markdown("**🔑 Pexels API Key**")
    pexels_key = st.text_input(
        "Clé API", type="password",
        value=st.session_state.get("pexels_key", ""),
        help="Gratuite sur pexels.com/api",
        label_visibility="collapsed",
        key="sidebar_pexels_key",
    )
    if pexels_key:
        st.session_state["pexels_key"] = pexels_key
        st.success("Clé enregistrée", icon="✅")

    st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
    st.caption("v2.0 — Python + Pillow + MoviePy")


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
    st.markdown("## ✨ Idée → Reel en 1 clic")
    st.caption("Tape quelques mots. Claude génère 3 concepts. Tu choisis. C'est parti.")

    if not _GEN_AVAILABLE:
        st.error("Module `generate.py` non disponible. Vérifie que `ANTHROPIC_API_KEY` est définie dans `.env`.")
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
        if variants:
            idea_stored = st.session_state.get("auto_idea", "")
            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
            st.markdown(f"### 3 concepts pour « {idea_stored} »")

            cols = st.columns(3)
            for i, (variant, col) in enumerate(zip(variants, cols)):
                angle_key = variant.get("angle", "frustration")
                icon, label, bg, color = _ANGLE_LABELS.get(
                    angle_key, ("🎯", angle_key.upper(), "#1e1e32", "#f2f0ea")
                )
                broll = variant.get("broll_category", "—")
                saves = variant.get("saves_time", "—")
                hook  = variant.get("hook_text", "")
                intro = variant.get("intro_text", "")
                caption_preview = variant.get("caption", "")[:120]

                with col:
                    # Badge angle
                    st.markdown(
                        f'<div style="background:{bg};border:1px solid {color};border-radius:8px;'
                        f'padding:0.4rem 0.8rem;margin-bottom:0.5rem;">'
                        f'<span style="color:{color};font-weight:700;font-size:0.85rem;">'
                        f'{icon} {label}</span></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Hook**")
                    st.markdown(
                        f'<div style="background:#FFF8EC;border-left:3px solid #C8972A;'
                        f'padding:0.5rem 0.8rem;border-radius:4px;color:#1A1A2E;'
                        f'font-size:1rem;font-weight:600;margin-bottom:0.75rem;">'
                        f'"{hook}"</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(f"🎬 Intro : *{intro}*")
                    st.caption(f"📹 B-Roll : `{broll}`  |  ⏱️ {saves}")
                    st.caption(f"📝 {caption_preview}…")

                    selected_idx = st.session_state.get("auto_selected_idx")
                    btn_label = "✓ Sélectionné" if selected_idx == i else "Choisir ce concept"
                    btn_type  = "primary" if selected_idx == i else "secondary"

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
    st.markdown("## 📝 Script Viral")
    st.caption("Génère un script complet optimisé pour stopper le scroll — avant de créer le reel.")

    if not _GEN_AVAILABLE:
        st.error("ANTHROPIC_API_KEY non définie.")
    else:
        sv_idea = st.text_input(
            "Ton idée",
            placeholder="ex: automatiser ses emails avec GPT, gagner 1h par jour sur Excel…",
            key="sv_idea_input",
        )

        _opt_col1, _opt_col2 = st.columns(2)
        with _opt_col1:
            _lang_choice = st.radio(
                "Langue",
                ["Français", "English"],
                horizontal=True,
                key="sv_lang_radio",
            )
        with _opt_col2:
            _mode_choice = st.radio(
                "Mode",
                ["Standard", "A/B Testing"],
                horizontal=True,
                key="sv_mode_radio",
            )
        sv_lang = "en" if _lang_choice == "English" else "fr"
        sv_mode = "ab" if _mode_choice == "A/B Testing" else "standard"
        st.session_state["sv_lang"] = sv_lang

        sv_col1, sv_col2 = st.columns([3, 1])
        with sv_col1:
            sv_clicked = st.button(
                "Générer A/B/C" if sv_mode == "ab" else "Générer le script viral",
                type="primary",
                disabled=not sv_idea.strip(),
                use_container_width=True,
                key="btn_sv",
            )
        with sv_col2:
            if st.button("Reset", type="secondary", use_container_width=True, key="btn_sv_reset"):
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
                        plan = generate_montage_plan(_chosen.get("script", {}), lang=_cur_lang)
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
                    f'<div style="background:#F5F5F7;border-radius:8px;padding:0.5rem 0.8rem;'
                    f'margin-top:0.5rem;font-size:0.82rem;color:#1A1A2E">'
                    f'<span style="font-weight:700;color:#C8972A">Pourquoi ça va performer : </span>{why}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)

            # ── Overlay + Angle viral + CTA ───────────────────────────────────
            ov_col, info_col = st.columns([1, 1])

            with ov_col:
                st.markdown("### 3. Overlay texte")
                for line in sv.get("overlay_lines", []):
                    st.markdown(
                        f'<div style="background:#1A1A2E;color:#F2F0EA;font-weight:700;'
                        f'font-size:1rem;padding:0.4rem 0.8rem;border-radius:6px;'
                        f'margin-bottom:6px;text-align:center">{line}</div>',
                        unsafe_allow_html=True,
                    )

            with info_col:
                st.markdown("### 4. Angle viral")
                viral = sv.get("viral_angle", {})
                st.markdown(
                    f'<div style="background:#FFF8EC;border:1px solid #C8972A;border-radius:8px;'
                    f'padding:0.6rem 0.8rem;margin-bottom:0.5rem;">'
                    f'<div style="font-size:0.72rem;color:#C8972A;font-weight:700">ÉMOTION</div>'
                    f'<div style="font-weight:600;color:#1A1A2E">{viral.get("emotion","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="background:#F5F5F7;border-radius:8px;padding:0.6rem 0.8rem;margin-bottom:0.5rem;">'
                    f'<div style="font-size:0.72rem;color:#6B6B8A;font-weight:700">MÉCANISME PSY</div>'
                    f'<div style="color:#1A1A2E;font-size:0.9rem">{viral.get("mechanism","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="background:#F5F5F7;border-radius:8px;padding:0.6rem 0.8rem;">'
                    f'<div style="font-size:0.72rem;color:#6B6B8A;font-weight:700">CTA</div>'
                    f'<div style="font-weight:600;color:#1A1A2E">{sv.get("cta_optimized","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Variante A/B agressive ────────────────────────────────────────
            ab = sv.get("ab_variant", {})
            if ab:
                st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
                with st.expander("### 5. Variante A/B — Version agressive", expanded=False):
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
            st.markdown("### 6. Plan de montage TEXT-CENTRIC")
            st.caption("Une phrase par scène · minimum 2.5s · animations sur le texte uniquement.")

            montage_col1, montage_col2 = st.columns([3, 1])
            with montage_col2:
                if st.button("Générer le montage", type="primary",
                             use_container_width=True, key="btn_montage"):
                    with st.spinner("Génération du plan de montage…"):
                        try:
                            _cur_lang = st.session_state.get("sv_lang", "fr")
                            plan = generate_montage_plan(sv.get("script", {}), lang=_cur_lang)
                            st.session_state["sv_montage"] = plan
                        except Exception as exc:
                            st.error(f"Erreur : {exc}")

            montage = st.session_state.get("sv_montage")
            if montage:
                total = montage.get("total_duration", 0)
                val   = montage.get("validation", {})

                # Bandeau validation
                all_ok = all(val.values()) if val else False
                val_color = "#d1fae5" if all_ok else "#fee2e2"
                val_icon  = "✅" if all_ok else "⚠️"
                checks = " · ".join(
                    f"{'✓' if v else '✗'} {k.replace('_', ' ')}"
                    for k, v in val.items()
                )
                st.markdown(
                    f'<div style="background:{val_color};border-radius:8px;'
                    f'padding:0.5rem 0.8rem;margin-bottom:0.75rem;font-size:0.82rem">'
                    f'{val_icon} {checks} · <strong>{total}s total</strong></div>',
                    unsafe_allow_html=True,
                )

                # Requêtes Pexels suggérées
                pexels_q = montage.get("pexels_queries", [])
                if pexels_q:
                    st.markdown(
                        '<div style="background:#F0F7FF;border-radius:8px;'
                        'padding:0.5rem 0.8rem;margin-bottom:0.75rem;font-size:0.82rem">'
                        '<strong>🎬 Pexels suggérés :</strong> '
                        + " · ".join(f'<code>{q}</code>' for q in pexels_q)
                        + "</div>",
                        unsafe_allow_html=True,
                    )

                # Timeline scène par scène
                ANIM_ICONS = {
                    "fade_in": "✨", "slide_in": "↑", "slide": "↑",
                    "typing": "⌨️", "pop": "💥",
                }
                TYPE_COLORS = {
                    "hook": "#f87171", "pain": "#fb923c", "twist": "#facc15",
                    "solution": "#4ade80", "result": "#60a5fa", "cta": "#c084fc",
                }
                scenes = montage.get("scenes", [])
                for scene in scenes:
                    stype    = scene.get("type", "")
                    duration = scene.get("duration", 2.5)
                    text     = scene.get("text", "")
                    kw       = scene.get("keyword_highlight", "")
                    anim     = scene.get("text_animation", scene.get("animation", "fade_in"))
                    emphasis = scene.get("emphasis", False)
                    color    = TYPE_COLORS.get(stype, "#6B6B8A")
                    anim_icon = ANIM_ICONS.get(anim, "▶")

                    display_text = text
                    if kw and kw in text:
                        display_text = text.replace(
                            kw,
                            f'<span style="color:#C8972A;font-weight:800">{kw}</span>'
                        )
                    if emphasis:
                        display_text = f'<strong>{display_text}</strong>'

                    st.markdown(
                        f'<div style="display:flex;gap:0.75rem;align-items:stretch;'
                        f'padding:0.6rem 0;border-bottom:1px solid #F0F0F5;">'
                        f'<div style="width:4px;background:{color};border-radius:2px;'
                        f'flex-shrink:0"></div>'
                        f'<div style="min-width:36px;font-size:0.75rem;color:#6B6B8A;'
                        f'padding-top:2px;font-weight:600">{duration}s</div>'
                        f'<div style="min-width:68px;font-size:0.72rem;font-weight:700;'
                        f'color:{color};text-transform:uppercase;padding-top:2px">{stype}</div>'
                        f'<div style="flex:1;font-weight:600;color:#1A1A2E">{display_text}</div>'
                        f'<div style="min-width:90px;font-size:0.78rem;color:#6B6B8A;'
                        f'text-align:right">{anim_icon} {anim}</div>'
                        f'</div>',
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
                st.markdown("### Générer le Reel")

                idea_for_reel = st.session_state.get("sv_idea_stored", "")
                _reel_lang = st.session_state.get("sv_lang", "fr")
                reel_yaml, reel_slug = build_yaml_from_viral_script(
                    sv, montage, idea_for_reel,
                    video_paths=_pexels_paths or None,
                    lang=_reel_lang,
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

            # ── Caption Instagram ──────────────────────────────────────────
            st.markdown('<hr class="gold-hr">', unsafe_allow_html=True)
            st.markdown("### Caption Instagram")

            _cap_lang  = st.session_state.get("sv_lang", "fr")
            _cap_stored = st.session_state.get("sv_caption", "")

            cap_col1, cap_col2 = st.columns([1, 3])
            with cap_col1:
                if st.button(
                    "Générer le caption" if _cap_lang == "fr" else "Generate caption",
                    type="secondary",
                    use_container_width=True,
                    key="btn_sv_caption",
                ):
                    with st.spinner("Génération du caption…" if _cap_lang == "fr" else "Generating caption…"):
                        try:
                            _cap_idea = st.session_state.get("sv_idea_stored", "")
                            _cap_montage = st.session_state.get("sv_montage", {})
                            _cap_sv = st.session_state.get("sv_result", {})
                            _cap_text = generate_caption(_cap_sv, _cap_montage, _cap_idea, lang=_cap_lang)
                            st.session_state["sv_caption"] = _cap_text
                            _cap_stored = _cap_text
                        except Exception as _ce:
                            st.error(f"Erreur caption : {_ce}")

            if _cap_stored:
                with cap_col2:
                    st.text_area(
                        "caption_output",
                        value=_cap_stored,
                        height=200,
                        key="sv_caption_display",
                        label_visibility="collapsed",
                    )

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
    st.markdown("## Créer un Reel")

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
    st.markdown("## Génération Batch")
    st.caption("Gérez et générez plusieurs reels d'un seul clic.")

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
    st.markdown("## 📹 Vidéothèque")

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
    st.markdown("## Bibliothèque Musicale")
    st.caption("Beats lo-fi synthétiques — générés localement avec numpy, aucune dépendance externe.")

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
