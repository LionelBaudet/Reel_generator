"""ui/pages/batch.py — Batch production runner."""
from __future__ import annotations
import subprocess
import sys
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


def _batch_configs(root: Path) -> list[Path]:
    d = root / "config" / "batch"
    return sorted(d.glob("reel_*.yaml")) if d.exists() else []


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Main render ────────────────────────────────────────────────────────────────

def render(root: Path) -> None:
    page_header(
        "Production",
        "Génération Batch",
        "Gérez plusieurs configs YAML simultanément — générez en série, "
        "suivez la progression et téléchargez les reels produits.",
    )

    configs   = _batch_configs(root)
    out_batch = root / "output" / "batch"
    out_batch.mkdir(parents=True, exist_ok=True)

    if not configs:
        st.info("Aucun fichier reel_*.yaml dans config/batch/. Créez-en un depuis l'onglet Studio.")
        return

    st.markdown(f"**{len(configs)} config(s) disponible(s)**")

    for cfg_path in configs:
        cfg     = _load_yaml(cfg_path)
        stem    = cfg_path.stem
        out_mp4 = out_batch / f"{stem}.mp4"
        has_vid = out_mp4.exists()

        with st.container():
            st.markdown('<div class="reel-card">', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])

            with c1:
                hook_text    = cfg.get("hook", {}).get("text", stem)
                prompt_short = cfg.get("prompt", {}).get("text", "")[:60].replace("\n", " ")
                st.markdown(f"**{stem}**")
                st.caption(f"🎣 {hook_text[:50]}")
                st.caption(f"💬 {prompt_short}...")

            with c2:
                dur   = cfg.get("reel", {}).get("duration", "?")
                music = Path(cfg.get("audio", {}).get("background_music", "")).stem or "—"
                st.caption(f"⏱️ {dur}s")
                st.caption(f"🎵 {music}")

            with c3:
                if has_vid:
                    size_kb = out_mp4.stat().st_size // 1024
                    st.markdown(f'<span class="badge-ok">✓ {size_kb} KB</span>', unsafe_allow_html=True)
                    with open(out_mp4, "rb") as f:
                        st.download_button("⬇️", data=f, file_name=out_mp4.name,
                                           mime="video/mp4", key=f"batch_dl_{stem}")
                else:
                    st.markdown('<span class="badge-miss">Non généré</span>', unsafe_allow_html=True)

            with c4:
                if st.button("▶ Générer", key=f"batch_run_{stem}", type="secondary"):
                    with st.spinner(f"Génération de {stem}..."):
                        result = _run([
                            sys.executable, "main.py",
                            "--config", str(cfg_path),
                            "--output", str(out_batch / f"{stem}.mp4"),
                        ], cwd=str(root))
                    if result.returncode == 0:
                        st.success("✓ Généré !")
                        st.rerun()
                    else:
                        st.error("Échec")
                        st.code(result.stderr[-500:] if result.stderr else "")

            st.markdown("</div>", unsafe_allow_html=True)

    hr()

    # ── Generate all ───────────────────────────────────────────────────────────
    col_all, _ = st.columns([1, 3])
    with col_all:
        if st.button("🚀 Générer TOUS les reels", type="primary", use_container_width=True, key="batch_run_all"):
            total  = len(configs)
            prog   = st.progress(0, text="Batch en cours...")
            errors: list[str] = []
            for i, cfg_path in enumerate(configs):
                stem    = cfg_path.stem
                out_mp4 = out_batch / f"{stem}.mp4"
                prog.progress(i / total, text=f"[{i+1}/{total}] {stem}...")
                result = _run([
                    sys.executable, "main.py",
                    "--config", str(cfg_path),
                    "--output", str(out_mp4),
                ], cwd=str(root))
                if result.returncode != 0:
                    errors.append(stem)
            prog.progress(1.0, text="Batch terminé !")
            if errors:
                st.warning(f"{total - len(errors)}/{total} générés. Échecs : {', '.join(errors)}")
            else:
                st.success(f"✓ {total} reels générés dans output/batch/")
            st.rerun()

    # ── Gallery of generated videos ────────────────────────────────────────────
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
                        key=f"batch_gallery_{mp4.stem}",
                    )
