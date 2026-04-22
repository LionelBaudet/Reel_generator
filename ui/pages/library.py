"""ui/pages/library.py — Video B-roll library + Music library (two sub-tabs)."""
from __future__ import annotations
import re
import urllib.parse
import urllib.request
from pathlib import Path

import streamlit as st

from ui.components import page_header, hr


# ── Helpers ────────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:40]


def _batch_configs(root: Path) -> list[Path]:
    d = root / "config" / "batch"
    return sorted(d.glob("reel_*.yaml")) if d.exists() else []


def _load_yaml(path: Path) -> dict:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Video library tab ──────────────────────────────────────────────────────────

def _render_video_library(root: Path) -> None:
    page_header(
        "Assets",
        "Vidéothèque B-Roll",
        "Recherche et téléchargement de B-roll via Pexels, gestion de la bibliothèque locale "
        "et thèmes prédéfinis CC0 sans clé API.",
    )

    vid_dir = root / "assets" / "video"
    vid_dir.mkdir(parents=True, exist_ok=True)

    # ── Pexels search ──────────────────────────────────────────────────────────
    st.markdown("### 🔍 Rechercher des vidéos par mot-clé")

    has_key = bool(st.session_state.get("pexels_key", "").strip())
    if not has_key:
        st.info("💡 Entrez votre clé API Pexels dans la sidebar pour activer la recherche. "
                "Clé gratuite sur **pexels.com/api**")
    else:
        col_q, col_n, col_orient, col_btn = st.columns([4, 1, 1, 1])
        with col_q:
            query = st.text_input(
                "Mot-clé ou phrase",
                placeholder="stats, meeting, laptop, data analysis, coffee...",
                key="lib_pexels_query",
                label_visibility="collapsed",
            )
        with col_n:
            n_results = st.selectbox("Résultats", [6, 9, 15, 20], index=1, key="lib_pexels_n")
        with col_orient:
            orient = st.selectbox("Format", ["landscape", "portrait", "square"], key="lib_pexels_orient")
        with col_btn:
            search_btn = st.button("🔍 Rechercher", type="primary",
                                   use_container_width=True, key="lib_btn_pexels_search")

        if search_btn:
            if not query.strip():
                st.warning("Entrez un mot-clé avant de rechercher.")
            else:
                with st.spinner(f"Recherche « {query} » sur Pexels..."):
                    import json as _json
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
                        st.session_state["lib_pexels_results"]    = data.get("videos", [])
                        st.session_state["lib_pexels_total"]      = data.get("total_results", 0)
                        st.session_state["lib_pexels_last_query"] = query.strip()
                        st.session_state["lib_pexels_error"]      = None
                    except Exception as e:
                        st.session_state["lib_pexels_results"] = []
                        st.session_state["lib_pexels_error"]   = str(e)

        err     = st.session_state.get("lib_pexels_error")
        results = st.session_state.get("lib_pexels_results", [])
        last_q  = st.session_state.get("lib_pexels_last_query", "")
        total   = st.session_state.get("lib_pexels_total", 0)

        if err:
            st.error(f"Erreur Pexels : {err}")
        elif results:
            st.caption(f"**{total} vidéos** trouvées pour « {last_q} » — {len(results)} affichées")
            hr()

            for row_start in range(0, len(results), 3):
                row_videos = results[row_start:row_start + 3]
                cols = st.columns(3)

                for col_idx, video in enumerate(row_videos):
                    files     = video.get("video_files", [])
                    mp4_files = [f for f in files if f.get("file_type") == "video/mp4"] or files
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
                    idx      = row_start + col_idx

                    with cols[col_idx]:
                        if thumb:
                            st.markdown(
                                f'<img src="{thumb}" '
                                f'style="width:100%;border-radius:10px;margin-bottom:6px;" />',
                                unsafe_allow_html=True,
                            )

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

                        if pex_url:
                            st.markdown(
                                f'<a href="{pex_url}" target="_blank" '
                                f'style="font-size:.75rem;color:#E8B84B;text-decoration:none;">'
                                f'Voir sur Pexels ↗</a>',
                                unsafe_allow_html=True,
                            )

                        default_name = f"{_slugify(last_q)}_{idx+1:02d}.mp4"
                        fname = st.text_input(
                            "Nom",
                            value=default_name,
                            key=f"lib_pex_fname_{idx}",
                            label_visibility="collapsed",
                        )

                        if st.button("💾 Télécharger", key=f"lib_pex_dl_{idx}",
                                     type="primary", use_container_width=True):
                            dest = vid_dir / fname
                            prog = st.progress(0, text="Connexion...")
                            dl_headers = {
                                "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/2.0)",
                                "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                            }
                            try:
                                req = urllib.request.Request(dl_url, headers=dl_headers)
                                with urllib.request.urlopen(req, timeout=120) as resp:
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
                                st.session_state["lib_prefill_video"] = fname
                                st.session_state["lib_prefill_query"] = last_q
                            except Exception as e:
                                st.error(f"Échec : {e}")
                                if dest.exists():
                                    dest.unlink()
                            st.rerun()

                        st.markdown("---")

            # CTA after download
            if st.session_state.get("lib_prefill_video"):
                vname = st.session_state["lib_prefill_video"]
                qname = st.session_state.get("lib_prefill_query", "")
                hr()
                st.markdown(
                    f'<div class="reel-card" style="border-color:#E8B84B">'
                    f'<b>✨ Vidéo téléchargée : <code>{vname}</code></b><br>'
                    f'<span style="color:#8e8ea0">Allez dans <b>🎬 Studio</b> '
                    f'→ section Intro → sélectionnez <code>{vname}</code> '
                    f'pour créer votre reel.</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("✨ Pré-remplir un Reel avec ce thème", type="primary",
                             key="lib_btn_prefill_reel"):
                    st.session_state["gen_prefill"] = {
                        "intro_video": str(vid_dir / vname),
                        "query": qname,
                    }
                    st.info("Allez dans l'onglet **🎬 Studio** — la vidéo est pré-sélectionnée.")

    hr()

    # ── Preset themes ──────────────────────────────────────────────────────────
    with st.expander("📦 Télécharger les thèmes prédéfinis (Mixkit CC0 — sans clé API)", expanded=False):
        try:
            from scripts.download_batch_videos import THEMES, download_theme, DEST_DIR
            theme_cols = st.columns(len(THEMES))
            for i, (theme_key, theme) in enumerate(THEMES.items()):
                with theme_cols[i]:
                    dest   = DEST_DIR / theme["filename"]
                    has_it = dest.exists() and dest.stat().st_size > 100_000
                    icon   = "✅" if has_it else "❌"
                    st.markdown(f"{icon} **{theme_key}**")
                    st.caption(theme["description"])
                    if has_it:
                        st.caption(f"{dest.stat().st_size // 1024} KB")
                    if st.button("Re-DL" if has_it else "Télécharger",
                                 key=f"lib_theme_dl_{theme_key}", type="secondary"):
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

    hr()

    # ── Local library ──────────────────────────────────────────────────────────
    st.markdown("### 🗂️ Bibliothèque locale")
    existing = sorted(vid_dir.glob("*.mp4"))
    if existing:
        st.caption(f"{len(existing)} vidéo(s) disponible(s) dans assets/video/")
        lib_cols = st.columns(3)
        for i, vid in enumerate(existing):
            with lib_cols[i % 3]:
                size_mb = vid.stat().st_size / (1024 * 1024)
                is_new  = (st.session_state.get("lib_prefill_video") == vid.name)
                label   = f"{'🆕 ' if is_new else ''}**{vid.name}** — {size_mb:.1f} MB"
                st.caption(label)
                st.video(str(vid))
                if st.button("🗑️ Supprimer", key=f"lib_del_vid_{vid.stem}", type="secondary"):
                    vid.unlink()
                    st.rerun()
    else:
        st.info("Aucune vidéo dans la bibliothèque. Utilisez la recherche ci-dessus.")

    hr()

    # ── Manual upload ──────────────────────────────────────────────────────────
    with st.expander("📤 Ajouter une vidéo depuis mon ordinateur", expanded=False):
        st.caption("Uploadez votre propre vidéo (MP4 / MOV — redimensionnée automatiquement).")
        uploaded = st.file_uploader("Choisir un fichier", type=["mp4", "mov", "avi"],
                                    key="lib_vid_uploader")
        if uploaded:
            target_name = st.text_input("Nom du fichier vidéo", value=uploaded.name,
                                        key="lib_upload_video_name")
            if st.button("💾 Sauvegarder dans assets/video/", type="primary", key="lib_save_upload"):
                dest = vid_dir / target_name
                with open(dest, "wb") as f:
                    f.write(uploaded.read())
                st.success(f"Vidéo sauvegardée : {dest.name}")
                st.rerun()


# ── Music library tab ──────────────────────────────────────────────────────────

def _render_music_library(root: Path) -> None:
    page_header(
        "Assets",
        "Bibliothèque Musicale",
        "Beats lo-fi synthétiques générés localement — aucune dépendance externe, "
        "gestion des pistes et aperçu audio intégré.",
    )

    try:
        from utils.audio_gen import CHORD_PROGRESSIONS, ensure_lofi_beat
        audio_gen_ok = True
    except ImportError:
        audio_gen_ok = False
        st.warning("Module audio_gen non disponible.")

    if not audio_gen_ok:
        return

    MUSIC_INFO = {
        "dm": {"label": "Dm — Chaud & classique",   "emoji": "🌅", "desc": "Dm - Am - Bb - F"},
        "am": {"label": "Am — Mélancolique",          "emoji": "🌙", "desc": "Am - F - C - G"},
        "em": {"label": "Em — Lumineux & énergique",  "emoji": "⚡", "desc": "Em - C - G - D"},
        "gm": {"label": "Gm — Sombre & introspectif", "emoji": "🌑", "desc": "Gm - Eb - Bb - F"},
    }

    any_missing = any(
        not (root / f"assets/audio/lofi_beat_{k}.wav").exists()
        for k in CHORD_PROGRESSIONS
    )
    if any_missing:
        if st.button("⚡ Générer toutes les musiques manquantes", type="primary", key="music_gen_all"):
            with st.spinner("Génération des beats lo-fi..."):
                for key, (bpm, _) in CHORD_PROGRESSIONS.items():
                    path = f"assets/audio/lofi_beat_{key}.wav"
                    ensure_lofi_beat(path, duration=35.0, key=key)
            st.success("Tous les beats générés !")
            st.rerun()

    st.markdown("---")

    cols = st.columns(2)
    for i, (key, (bpm, chords)) in enumerate(CHORD_PROGRESSIONS.items()):
        info  = MUSIC_INFO.get(key, {"label": key, "emoji": "🎵", "desc": ""})
        path  = root / f"assets/audio/lofi_beat_{key}.wav"
        exists = path.exists() and path.stat().st_size > 10_000

        with cols[i % 2]:
            st.markdown('<div class="reel-card">', unsafe_allow_html=True)
            st.markdown(f"### {info['emoji']} {info['label']}")
            st.caption(f"**{bpm} BPM** — Progression : {info['desc']}")

            if exists:
                size_kb = path.stat().st_size // 1024
                st.caption(f"📁 lofi_beat_{key}.wav — {size_kb} KB")
                st.audio(str(path), format="audio/wav")

                users = [
                    c.stem for c in _batch_configs(root)
                    if f"lofi_beat_{key}" in _load_yaml(c).get("audio", {}).get("background_music", "")
                ]
                if users:
                    st.caption(f"Utilisée par : {', '.join(users)}")

                regen_col, _ = st.columns([1, 2])
                with regen_col:
                    if st.button("🔄 Régénérer", key=f"music_regen_{key}", type="secondary"):
                        with st.spinner(f"Génération {key}..."):
                            path.unlink()
                            ensure_lofi_beat(str(path), duration=35.0, key=key)
                        st.success("Régénéré !")
                        st.rerun()
            else:
                st.markdown('<span class="badge-miss">Non généré</span>', unsafe_allow_html=True)
                if st.button(f"▶ Générer ({bpm} BPM)", key=f"music_gen_{key}", type="primary"):
                    with st.spinner(f"Génération {key} @ {bpm} BPM..."):
                        ensure_lofi_beat(str(path), duration=35.0, key=key)
                    st.success(f"lofi_beat_{key}.wav généré !")
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    hr()

    # ── Custom upload ──────────────────────────────────────────────────────────
    st.markdown("### 🎵 Ajouter une musique personnalisée")
    st.caption("Uploadez un fichier MP3 ou WAV à utiliser comme fond musical.")
    uploaded_music = st.file_uploader("Choisir un fichier audio", type=["mp3", "wav", "ogg"],
                                      key="music_uploader")
    if uploaded_music:
        music_name = st.text_input("Nom du fichier audio", value=uploaded_music.name,
                                   key="music_upload_name")
        if st.button("💾 Sauvegarder dans assets/audio/", type="primary", key="music_save_upload"):
            dest = root / "assets" / "audio" / music_name
            with open(dest, "wb") as f:
                f.write(uploaded_music.read())
            st.success(f"Musique sauvegardée : {dest.name}")
            st.rerun()


# ── Main render ────────────────────────────────────────────────────────────────

def render(root: Path) -> None:
    tab_videos, tab_music = st.tabs(["🎬 Vidéothèque B-Roll", "🎵 Bibliothèque Musicale"])
    with tab_videos:
        _render_video_library(root)
    with tab_music:
        _render_music_library(root)
