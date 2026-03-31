#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Télécharge plusieurs vidéos stock thématiques depuis Pexels.

Usage:
    python scripts/download_batch_videos.py --api-key VOTRE_CLE
    python scripts/download_batch_videos.py --api-key VOTRE_CLE --theme meeting
    python scripts/download_batch_videos.py --list   # afficher les thèmes

Clé API Pexels gratuite : https://www.pexels.com/api/
"""

import argparse
import io
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DEST_DIR = Path(__file__).parent.parent / "assets" / "video"

# ── Manifeste des thèmes ──────────────────────────────────────────────────────
# Chaque thème définit plusieurs requêtes de recherche par ordre de priorité.
# La première vidéo HD trouvée est utilisée.
THEMES = {
    "typing": {
        "filename": "typing_person.mp4",
        "queries":  ["person typing laptop keyboard dark", "hands typing keyboard"],
        "description": "Personne qui tape sur un clavier",
    },
    "meeting": {
        "filename": "meeting_prep.mp4",
        "queries":  ["business meeting planning office", "team meeting whiteboard",
                     "office collaboration workspace"],
        "description": "Reunion / preparation de meeting",
    },
    "excel": {
        "filename": "excel_work.mp4",
        "queries":  ["data analysis spreadsheet computer", "working laptop data",
                     "person working computer screen"],
        "description": "Travail sur ordinateur / données",
    },
    "notes": {
        "filename": "notes_writing.mp4",
        "queries":  ["writing notes notebook coffee", "taking notes pen paper",
                     "studying writing desk"],
        "description": "Prise de notes / écriture",
    },
}

# Vidéos de secours (Mixkit, CC0) si Pexels échoue
FALLBACK_URLS = {
    "typing":  "https://assets.mixkit.co/videos/preview/mixkit-typing-on-a-laptop-keyboard-2928-large.mp4",
    "meeting": "https://assets.mixkit.co/videos/preview/mixkit-two-people-looking-at-a-laptop-together-4819-large.mp4",
    "excel":   "https://assets.mixkit.co/videos/preview/mixkit-hands-of-a-man-typing-on-a-laptop-in-the-dark-4188-large.mp4",
    "notes":   "https://assets.mixkit.co/videos/preview/mixkit-woman-writing-in-a-notebook-2228-large.mp4",
}


# ── Helpers réseau ────────────────────────────────────────────────────────────

def _download(url: str, dest: Path, label: str = "") -> bool:
    """Télécharge une URL vers dest avec barre de progression."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/2.0)",
        "Accept":     "video/mp4,video/*;q=0.9,*/*;q=0.8",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {pct:.0f}%  ({downloaded // 1024} KB / {total // 1024} KB)   ",
                              end="", flush=True)
        size_kb = dest.stat().st_size // 1024
        print(f"\r  OK — {size_kb} KB{' ' * 20}")
        return True
    except Exception as e:
        print(f"\r  Echec : {e}{' ' * 30}")
        if dest.exists():
            dest.unlink()
        return False


def _pexels_search(api_key: str, query: str) -> list:
    """Retourne les videos Pexels pour une requête (liste de dicts)."""
    url = (
        "https://api.pexels.com/videos/search"
        f"?query={urllib.parse.quote(query)}&per_page=5&orientation=landscape"
    )
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/2.0)",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("videos", [])
    except Exception as e:
        print(f"  Erreur Pexels ({query}): {e}")
        return []


def _best_mp4(video: dict) -> str | None:
    """Choisit la meilleure URL MP4 HD dans les fichiers d'une vidéo Pexels."""
    files = [
        f for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4" and f.get("quality") in ("hd", "sd", "uhd")
    ]
    files.sort(key=lambda f: f.get("width", 0), reverse=True)
    return files[0]["link"] if files else None


# ── Téléchargement d'un thème ─────────────────────────────────────────────────

def download_theme(theme_key: str, api_key: str | None = None,
                   force: bool = False) -> bool:
    """
    Télécharge la vidéo pour un thème donné.

    Stratégie :
      1. Pexels API (si api_key fourni)
      2. URL Mixkit de secours
    """
    theme = THEMES[theme_key]
    dest  = DEST_DIR / theme["filename"]

    if dest.exists() and dest.stat().st_size > 100_000 and not force:
        print(f"  Existant ({dest.stat().st_size // 1024} KB) — ignoré (--force pour re-télécharger)")
        return True

    # ── Tentative Pexels ──────────────────────────────────────────────
    if api_key:
        for query in theme["queries"]:
            print(f"  Pexels: '{query}'...")
            videos = _pexels_search(api_key, query)
            for vid in videos:
                mp4_url = _best_mp4(vid)
                if mp4_url:
                    res_w = next(
                        (f.get("width") for f in vid.get("video_files", [])
                         if f.get("link") == mp4_url), "?")
                    print(f"  Video: {vid.get('url')} ({res_w}px, {vid.get('duration')}s)")
                    if _download(mp4_url, dest):
                        return True
            print(f"  Aucune video Pexels pour '{query}', essai suivant...")

    # ── Fallback Mixkit ───────────────────────────────────────────────
    fallback = FALLBACK_URLS.get(theme_key)
    if fallback:
        print(f"  Fallback Mixkit (CC0)...")
        return _download(fallback, dest)

    print(f"  Aucune source disponible pour '{theme_key}'.")
    return False


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Telecharge les videos stock pour la generation de reels en batch"
    )
    parser.add_argument("--api-key", help="Cle API Pexels (gratuite sur pexels.com/api)")
    parser.add_argument("--theme",   choices=list(THEMES), help="Telecharger un seul theme")
    parser.add_argument("--force",   action="store_true",  help="Re-telecharger meme si le fichier existe")
    parser.add_argument("--list",    action="store_true",  help="Afficher les themes disponibles")
    args = parser.parse_args()

    if args.list:
        print("\nThemes disponibles:")
        for k, v in THEMES.items():
            dest = DEST_DIR / v["filename"]
            status = f"OK ({dest.stat().st_size // 1024} KB)" if dest.exists() else "MANQUANT"
            print(f"  {k:10} — {v['description']:40} [{status}]")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    themes_to_dl = [args.theme] if args.theme else list(THEMES.keys())

    print(f"\n=== Telechargement de {len(themes_to_dl)} video(s) ===\n")
    ok, ko = 0, 0
    for theme_key in themes_to_dl:
        theme = THEMES[theme_key]
        print(f"[{theme_key}] {theme['description']}")
        if download_theme(theme_key, api_key=args.api_key, force=args.force):
            ok += 1
        else:
            ko += 1
        print()

    print(f"Resultat : {ok} OK, {ko} echec(s)")
    if ok > 0:
        print(f"Videos dans : {DEST_DIR}")
    if ko > 0:
        print("\nPour les echecs, telechargez manuellement depuis :")
        print("  https://mixkit.co/free-stock-video/")
        print("  https://www.pexels.com/videos/")


if __name__ == "__main__":
    main()
