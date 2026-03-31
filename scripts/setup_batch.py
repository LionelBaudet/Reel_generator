#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de setup complet pour la génération de reels en batch.

Ce script fait tout en une commande :
  1. Télécharge les vidéos stock thématiques (Pexels ou Mixkit CC0)
  2. Génère les 4 musiques lo-fi (tonalités différentes)
  3. Lance la génération batch de tous les reels

Usage:
    # Setup complet + génération
    python scripts/setup_batch.py --api-key VOTRE_CLE_PEXELS

    # Setup seulement (sans lancer la génération)
    python scripts/setup_batch.py --api-key VOTRE_CLE_PEXELS --setup-only

    # Sans clé API (Mixkit CC0 en fallback)
    python scripts/setup_batch.py

    # Regénérer un seul reel
    python scripts/setup_batch.py --config config/batch/reel_meeting_prep.yaml

Clé Pexels gratuite : https://www.pexels.com/api/
"""

import argparse
import io
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Forcer UTF-8 sur Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ajouter le dossier racine au path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("setup_batch")


# ── Etape 1 : Videos ─────────────────────────────────────────────────────────

def setup_videos(api_key: str | None = None, force: bool = False) -> dict:
    """
    Télécharge toutes les vidéos manquantes.
    Retourne {theme: path|None}.
    """
    logger.info("=== Etape 1 : Videos stock ===")
    from scripts.download_batch_videos import THEMES, DEST_DIR, download_theme

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for theme_key, theme in THEMES.items():
        dest = DEST_DIR / theme["filename"]
        if dest.exists() and dest.stat().st_size > 100_000 and not force:
            logger.info(f"  [{theme_key}] Deja present : {dest.name} ({dest.stat().st_size // 1024} KB)")
            results[theme_key] = str(dest)
        else:
            logger.info(f"  [{theme_key}] Telechargement : {theme['description']}...")
            ok = download_theme(theme_key, api_key=api_key, force=force)
            results[theme_key] = str(dest) if ok else None
            if not ok:
                logger.warning(f"  [{theme_key}] Echec — fallback animation utilisee a la generation")

    ok_count = sum(1 for v in results.values() if v)
    logger.info(f"Videos : {ok_count}/{len(THEMES)} disponibles\n")
    return results


# ── Etape 2 : Musiques ────────────────────────────────────────────────────────

def setup_music(force: bool = False) -> dict:
    """
    Génère tous les beats lo-fi manquants (4 tonalités).
    Retourne {key: path}.
    """
    logger.info("=== Etape 2 : Musiques lo-fi ===")

    os.chdir(ROOT)   # important : chemins relatifs depuis la racine

    from utils.audio_gen import CHORD_PROGRESSIONS, ensure_lofi_beat

    results = {}
    for key, (bpm, _) in CHORD_PROGRESSIONS.items():
        path = f"assets/audio/lofi_beat_{key}.wav"
        p    = Path(path)
        if p.exists() and p.stat().st_size > 50_000 and not force:
            logger.info(f"  [{key}] Deja present : {p.name} ({p.stat().st_size // 1024} KB)")
            results[key] = path
        else:
            logger.info(f"  [{key}] Generation ({bpm} BPM)...")
            t0 = time.time()
            results[key] = ensure_lofi_beat(path, duration=35.0, key=key)
            logger.info(f"  [{key}] Genere en {time.time()-t0:.1f}s")

    logger.info(f"Musiques : {len(results)} tonalites disponibles\n")
    return results


# ── Etape 3 : Generation des reels ───────────────────────────────────────────

def run_batch(output_dir: str = "output/batch") -> list:
    """
    Lance la génération batch de tous les reels dans config/batch/.
    Retourne la liste des fichiers générés.
    """
    logger.info("=== Etape 3 : Generation des reels ===")

    batch_dir = ROOT / "config" / "batch"
    yaml_files = sorted(batch_dir.glob("*.yaml")) + sorted(batch_dir.glob("*.yml"))
    # Ignorer .gitkeep et fichiers non-reel
    yaml_files = [f for f in yaml_files if f.stem.startswith("reel_")]

    if not yaml_files:
        logger.error(f"Aucun fichier reel_*.yaml dans {batch_dir}")
        return []

    out_dir = ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"{len(yaml_files)} reel(s) a generer dans {out_dir}")

    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--batch", str(batch_dir),
        "--output", str(out_dir),
        "--verbose",
    ]

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(ROOT))
    elapsed = time.time() - t0

    if result.returncode == 0:
        generated = sorted(out_dir.glob("reel_*.mp4"))
        logger.info(f"\nGeneration terminee en {elapsed:.0f}s")
        logger.info(f"{len(generated)} reel(s) dans : {out_dir}")
        for mp4 in generated:
            size_kb = mp4.stat().st_size // 1024
            logger.info(f"  {mp4.name} ({size_kb} KB)")
        return [str(f) for f in generated]
    else:
        logger.error("La generation a echoue (voir logs ci-dessus)")
        return []


def run_single(config_path: str, output_dir: str = "output/batch") -> str | None:
    """Lance la génération d'un seul reel."""
    out_dir = ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    config_stem = Path(config_path).stem
    output_path = str(out_dir / f"{config_stem}.mp4")

    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--config", config_path,
        "--output", output_path,
    ]

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(ROOT))
    elapsed = time.time() - t0

    if result.returncode == 0 and Path(output_path).exists():
        size_kb = Path(output_path).stat().st_size // 1024
        logger.info(f"Reel genere en {elapsed:.0f}s : {output_path} ({size_kb} KB)")
        return output_path
    return None


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Setup complet et generation batch de reels @ownyourtime.ai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Setup complet + generation de tous les reels
  python scripts/setup_batch.py --api-key VOTRE_CLE

  # Sans cle API (videos de secours Mixkit CC0)
  python scripts/setup_batch.py

  # Preparer les assets seulement (pas de generation)
  python scripts/setup_batch.py --api-key VOTRE_CLE --setup-only

  # Generer un seul reel (apres setup)
  python scripts/setup_batch.py --config config/batch/reel_meeting_prep.yaml

  # Forcer le re-telechargement de tout
  python scripts/setup_batch.py --api-key VOTRE_CLE --force
        """,
    )
    parser.add_argument("--api-key",    help="Cle API Pexels (gratuite sur pexels.com/api)")
    parser.add_argument("--config",     help="Generer un seul reel (chemin YAML)")
    parser.add_argument("--output",     default="output/batch", help="Dossier de sortie")
    parser.add_argument("--setup-only", action="store_true", help="Preparer assets sans generer")
    parser.add_argument("--force",      action="store_true", help="Re-telecharger / re-generer tout")
    parser.add_argument("--skip-video", action="store_true", help="Passer l'etape download video")
    parser.add_argument("--skip-music", action="store_true", help="Passer l'etape generation musique")
    args = parser.parse_args()

    os.chdir(ROOT)

    print("\n" + "=" * 55)
    print("  REELS GENERATOR — Batch Setup @ownyourtime.ai")
    print("=" * 55 + "\n")

    # Etape 1 : Videos
    if not args.skip_video:
        setup_videos(api_key=args.api_key, force=args.force)
    else:
        logger.info("Etape 1 : Videos ignorees (--skip-video)")

    # Etape 2 : Musiques
    if not args.skip_music:
        setup_music(force=args.force)
    else:
        logger.info("Etape 2 : Musiques ignorees (--skip-music)")

    if args.setup_only:
        logger.info("Setup termine. Lancez maintenant :")
        logger.info("  python scripts/setup_batch.py --setup-only  (fait)")
        logger.info("  python main.py --batch config/batch/ --output output/batch/")
        return

    # Etape 3 : Generation
    if args.config:
        result = run_single(args.config, output_dir=args.output)
        if result:
            print(f"\nReel disponible : {result}")
        else:
            print("\nEchec de la generation.")
            sys.exit(1)
    else:
        results = run_batch(output_dir=args.output)
        if results:
            print(f"\n{len(results)} reel(s) disponibles dans : {ROOT / args.output}")
        else:
            print("\nAucun reel genere.")
            sys.exit(1)


if __name__ == "__main__":
    main()
