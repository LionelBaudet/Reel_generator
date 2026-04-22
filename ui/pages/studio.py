"""ui/pages/studio.py — Manual reel config editor (Studio tab)."""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st
import yaml

from ui.components import page_header, hr


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(cmd: list, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=cwd,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def _available_videos(root: Path) -> dict[str, Path]:
    vid_dir = root / "assets" / "video"
    return {p.name: p for p in sorted(vid_dir.glob("*.mp4"))} if vid_dir.exists() else {}


def _available_music(root: Path) -> dict[str, Path]:
    aud_dir = root / "assets" / "audio"
    if not aud_dir.exists():
        return {}
    return {p.name: p for p in sorted(aud_dir.glob("*.wav")) if p.stat().st_size > 10_000}


def _batch_configs(root: Path) -> list[Path]:
    d = root / "config" / "batch"
    return sorted(d.glob("reel_*.yaml")) if d.exists() else []


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _config_to_form(cfg: dict) -> dict:
    return {
        "intro_text":      cfg.get("intro", {}).get("text", ""),
        "intro_subtext":   cfg.get("intro", {}).get("subtext", ""),
        "intro_video":     cfg.get("intro", {}).get("video", ""),
        "intro_duration":  cfg.get("intro", {}).get("duration", 3),
        "hook_text":       cfg.get("hook", {}).get("text", ""),
        "hook_highlight":  cfg.get("hook", {}).get("highlight", ""),
        "hook_duration":   cfg.get("hook", {}).get("duration", 3),
        "prompt_text":     cfg.get("prompt", {}).get("text", ""),
        "prompt_output":   cfg.get("prompt", {}).get("output_preview", ""),
        "prompt_saves":    cfg.get("prompt", {}).get("saves", ""),
        "prompt_duration": cfg.get("prompt", {}).get("duration", 14),
        "cta_headline":    cfg.get("cta", {}).get("headline", "Save THIS."),
        "cta_subtext":     cfg.get("cta", {}).get("subtext", ""),
        "cta_duration":    cfg.get("cta", {}).get("duration", 3),
        "audio_music":     cfg.get("audio", {}).get("background_music", ""),
        "audio_volume":    cfg.get("audio", {}).get("volume", 0.28),
    }


def _form_to_config(f: dict, base: dict | None = None) -> dict:
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


# ── Main render ────────────────────────────────────────────────────────────────

def render(root: Path) -> None:
    page_header(
        "Studio",
        "Créer un Reel",
        "Configure manuellement chaque section du reel — intro, hook, prompt, CTA — "
        "prévisualise les frames clés et génère la vidéo finale.",
    )

    # ── Config selector ────────────────────────────────────────────────────────
    all_configs  = [root / "config" / "reel_config.yaml"] + _batch_configs(root)
    config_names = {p.stem: p for p in all_configs if p.exists()}

    col_load, col_save = st.columns([2, 2])
    with col_load:
        selected_cfg_name = st.selectbox(
            "Charger une config",
            options=["(nouveau)"] + list(config_names.keys()),
            key="studio_cfg_selector",
        )
    with col_save:
        new_cfg_name = st.text_input(
            "Nom de la config (pour sauvegarder)",
            value=selected_cfg_name if selected_cfg_name != "(nouveau)" else "reel_nouveau",
            key="studio_cfg_new_name",
        )

    if selected_cfg_name != "(nouveau)" and selected_cfg_name in config_names:
        base_cfg  = _load_yaml(config_names[selected_cfg_name])
        form_vals = _config_to_form(base_cfg)
    else:
        base_cfg  = {}
        form_vals = _config_to_form({})

    hr()

    # ── Form + preview (2 columns) ─────────────────────────────────────────────
    left, right = st.columns([3, 2])

    prefill = st.session_state.pop("gen_prefill", None)
    if prefill:
        form_vals["intro_video"] = prefill.get("intro_video", form_vals["intro_video"])
        st.info(f"✨ Vidéo pré-sélectionnée depuis la Vidéothèque : `{Path(form_vals['intro_video']).name}`")

    with left:
        with st.expander("📽️ Intro — Vidéo d'accroche", expanded=bool(prefill)):
            videos       = _available_videos(root)
            video_opts   = ["(aucune)"] + list(videos.keys())
            current_vid  = Path(form_vals["intro_video"]).name if form_vals["intro_video"] else "(aucune)"
            intro_vid_sel = st.selectbox(
                "Vidéo stock", video_opts,
                index=video_opts.index(current_vid) if current_vid in video_opts else 0,
                key="studio_intro_video_sel",
            )
            intro_video = str(videos[intro_vid_sel]) if intro_vid_sel != "(aucune)" else ""
            fi_text    = st.text_input("Texte principal",  value=form_vals["intro_text"],    key="studio_intro_text")
            fi_subtext = st.text_input("Sous-texte",        value=form_vals["intro_subtext"], key="studio_intro_subtext")
            fi_dur     = st.slider("Durée (s)", 2, 6, int(form_vals["intro_duration"]),       key="studio_intro_dur")

        with st.expander("⚡ Hook — Phrase d'accroche", expanded=True):
            fh_text = st.text_input("Texte du hook",          value=form_vals["hook_text"],      key="studio_hook_text")
            fh_hl   = st.text_input("Mots à souligner (or)",  value=form_vals["hook_highlight"], key="studio_hook_hl",
                                    help="Sous-ensemble exact du texte du hook")
            fh_dur  = st.slider("Durée (s)", 2, 5, int(form_vals["hook_duration"]),             key="studio_hook_dur")

        with st.expander("💬 Prompt ChatGPT — Le moment WOW", expanded=True):
            st.caption("✍️ Prompt utilisateur — court et casual (2–3 lignes)")
            fp_text  = st.text_area("Prompt (affiché dans la bulle utilisateur)",
                                    value=form_vals["prompt_text"], height=90, key="studio_prompt_text")
            st.caption("🤖 Réponse ChatGPT — longue et impressionnante")
            fp_out   = st.text_area("Réponse (streamée mot par mot)",
                                    value=form_vals["prompt_output"], height=220, key="studio_prompt_out")
            fp_saves = st.text_input("Badge 'saves' (ex: 20 min/day)",
                                     value=form_vals["prompt_saves"], key="studio_prompt_saves")
            fp_dur   = st.slider("Durée (s)", 8, 20, int(form_vals["prompt_duration"]),  key="studio_prompt_dur")

        with st.expander("📣 CTA — Call to Action", expanded=False):
            fc_head = st.text_input("Titre CTA",      value=form_vals["cta_headline"], key="studio_cta_head")
            fc_sub  = st.text_input("Sous-texte CTA", value=form_vals["cta_subtext"],  key="studio_cta_sub")
            fc_dur  = st.slider("Durée (s)", 2, 5, int(form_vals["cta_duration"]),     key="studio_cta_dur")

        with st.expander("🎵 Audio", expanded=False):
            music_files = _available_music(root)
            music_opts  = ["(aucune)"] + list(music_files.keys())
            cur_music   = Path(form_vals["audio_music"]).name if form_vals["audio_music"] else "(aucune)"
            music_sel   = st.selectbox(
                "Musique de fond", music_opts,
                index=music_opts.index(cur_music) if cur_music in music_opts else 0,
                key="studio_audio_sel",
            )
            audio_path = str(music_files[music_sel]) if music_sel != "(aucune)" else ""
            audio_vol  = st.slider("Volume", 0.0, 1.0, float(form_vals["audio_volume"]), 0.01, key="studio_audio_vol")

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

        if st.button("🔍 Générer l'aperçu", type="primary", key="studio_btn_preview"):
            tmp_cfg = root / "output" / "_preview_tmp.yaml"
            _save_yaml(tmp_cfg, live_cfg)
            with st.spinner("Génération des aperçus..."):
                result = _run([sys.executable, "main.py", "--config", str(tmp_cfg),
                                "--output", "output/", "--preview"], cwd=str(root))
            if result.returncode == 0:
                preview_files = {
                    "Intro":  root / "output" / "preview_intro.png",
                    "Hook":   root / "output" / "preview_hook.png",
                    "Prompt": root / "output" / "preview_prompt.png",
                    "CTA":    root / "output" / "preview_cta.png",
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

    hr()

    # ── Action buttons ─────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns([2, 2, 3])

    with col_a:
        output_name = st.text_input("Nom du fichier de sortie", value=f"{new_cfg_name}.mp4",
                                    key="studio_output_filename")

    with col_b:
        save_col, _ = st.columns([1, 1])
        with save_col:
            if st.button("💾 Sauvegarder config", type="secondary", key="studio_save_cfg"):
                save_path = root / "config" / "batch" / f"{new_cfg_name}.yaml"
                if not new_cfg_name.startswith("reel_"):
                    save_path = root / "config" / "batch" / f"reel_{new_cfg_name}.yaml"
                _save_yaml(save_path, live_cfg)
                st.success(f"Config sauvegardée : {save_path.name}")

    with col_c:
        if st.button("🚀 Générer le Reel", type="primary", use_container_width=True, key="studio_btn_gen"):
            tmp_cfg  = root / "output" / "_gen_tmp.yaml"
            _save_yaml(tmp_cfg, live_cfg)
            out_path = root / "output" / output_name

            progress = st.progress(0, text="Initialisation...")
            start_t  = time.time()

            with st.spinner(f"Génération en cours ({live_cfg['reel']['duration']}s de vidéo)..."):
                proc = subprocess.Popen(
                    [sys.executable, "main.py", "--config", str(tmp_cfg), "--output", str(out_path)],
                    cwd=str(root),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                )
                log_lines: list[str] = []
                for line in proc.stdout:
                    log_lines.append(line.rstrip())
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
                with open(out_path, "rb") as vf:
                    st.video(vf.read())
                with open(out_path, "rb") as f:
                    st.download_button(
                        "⬇️ Télécharger le Reel",
                        data=f,
                        file_name=output_name,
                        mime="video/mp4",
                        type="primary",
                        key="studio_dl_btn",
                    )
            else:
                st.error("La génération a échoué.")
                with st.expander("Logs"):
                    st.code("\n".join(log_lines[-30:]))
