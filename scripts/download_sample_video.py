#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Télécharge une vidéo stock gratuite depuis Pexels ou Pixabay
pour le segment d'accroche du reel.

Usage:
    python scripts/download_sample_video.py
    python scripts/download_sample_video.py --api-key VOTRE_CLE_PEXELS
    python scripts/download_sample_video.py --url https://...  (URL directe)

Sources gratuites:
    - Pexels  : https://www.pexels.com/api/ (clé API gratuite)
    - Pixabay : https://pixabay.com/videos/ (téléchargement direct)
    - Videvo  : https://www.videvo.net/
    - Mixkit  : https://mixkit.co/free-stock-video/

Cherchez: "person typing laptop", "working computer", "keyboard typing"
"""

import argparse
import io
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

# Forcer UTF-8 sur Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Dossier de destination
DEST_DIR = Path(__file__).parent.parent / "assets" / "video"
DEST_FILE = DEST_DIR / "typing_person.mp4"

# ── Vidéos libres de droits avec URL directe ──────────────────────────────
# Ces vidéos sont en licence Creative Commons (CC0 / domaine public)
# Source: Archive.org et autres sources CC0
FREE_VIDEO_OPTIONS = [
    {
        "name": "Person typing on laptop (Mixkit - gratuit)",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-hands-of-a-man-typing-on-a-laptop-in-the-dark-4188-large.mp4",
        "credit": "Mixkit — Utilisation gratuite sans attribution",
    },
    {
        "name": "Hands typing on keyboard (Mixkit - gratuit)",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-typing-on-a-laptop-keyboard-2928-large.mp4",
        "credit": "Mixkit — Utilisation gratuite sans attribution",
    },
    {
        "name": "Person working on laptop (Mixkit - gratuit)",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-young-woman-talking-on-the-phone-while-working-on-her-4272-large.mp4",
        "credit": "Mixkit — Utilisation gratuite sans attribution",
    },
]


def download_from_url(url: str, dest: Path) -> bool:
    """Télécharge une vidéo depuis une URL directe."""
    print(f"Téléchargement depuis: {url}")
    print(f"Destination: {dest}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
        "Referer": "https://mixkit.co/",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {pct:.1f}% ({downloaded // 1024} KB / {total // 1024} KB)", end="", flush=True)

        print(f"\nTéléchargé: {dest} ({dest.stat().st_size // 1024} KB)")
        return True

    except Exception as e:
        print(f"\nEchec: {e}")
        if dest.exists():
            dest.unlink()
        return False


def download_from_pexels(api_key: str, query: str = "typing laptop keyboard") -> bool:
    """Télécharge une vidéo depuis l'API Pexels (nécessite une clé API gratuite)."""
    import json

    print(f"Recherche Pexels: '{query}'...")
    search_url = (
        f"https://api.pexels.com/videos/search"
        f"?query={urllib.parse.quote(query)}&per_page=5&orientation=landscape"
    )

    # User-Agent requis par l'API Pexels pour les requêtes Python
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/1.0)",
    }
    req = urllib.request.Request(search_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        videos = data.get("videos", [])
        if not videos:
            print("Aucune vidéo trouvée sur Pexels.")
            return False

        print(f"{data.get('total_results', 0)} videos trouvees, selection de la meilleure...")

        # Prendre la première vidéo avec une bonne résolution (HD ou SD)
        for video in videos:
            files = video.get("video_files", [])
            # Trier par largeur décroissante et prendre la meilleure qualité MP4
            mp4_files = [
                f for f in files
                if f.get("file_type") == "video/mp4" and f.get("quality") in ("hd", "sd", "uhd")
            ]
            mp4_files.sort(key=lambda f: f.get("width", 0), reverse=True)

            if mp4_files:
                chosen = mp4_files[0]
                print(f"Video selectionnee: {video['url']}")
                print(f"  Resolution: {chosen.get('width')}x{chosen.get('height')} ({chosen.get('quality')})")
                print(f"  Duree: {video.get('duration')}s")
                return download_from_url(chosen["link"], DEST_FILE)

    except Exception as e:
        print(f"Erreur Pexels API: {e}")

    return False


def try_all_free_videos() -> bool:
    """Essaie de télécharger une vidéo depuis la liste des sources gratuites."""
    for option in FREE_VIDEO_OPTIONS:
        print(f"\nEssai: {option['name']}")
        print(f"Crédit: {option['credit']}")
        if download_from_url(option["url"], DEST_FILE):
            return True
        print("Passage à la source suivante...")
    return False


def show_manual_instructions():
    """Affiche les instructions pour télécharger manuellement."""
    print("""
Téléchargement automatique non disponible.

Téléchargez manuellement une vidéo "personne qui tape sur un clavier":

1. MIXKIT (gratuit, sans inscription)
   https://mixkit.co/free-stock-video/typing/
   → Télécharger une vidéo → renommer en 'typing_person.mp4'
   → Placer dans: assets/video/typing_person.mp4

2. PEXELS (gratuit, sans inscription)
   https://www.pexels.com/videos/search/typing%20laptop/
   → Télécharger → renommer → placer dans assets/video/

3. PIXABAY (gratuit, sans inscription)
   https://pixabay.com/videos/search/typing/
   → Télécharger → renommer → placer dans assets/video/

4. AVEC API PEXELS (automatique):
   a. Créez un compte gratuit sur https://www.pexels.com/api/
   b. Copiez votre clé API
   c. Lancez: python scripts/download_sample_video.py --api-key VOTRE_CLE

Note: Si aucune vidéo n'est trouvée, le générateur utilise automatiquement
une animation de remplacement (écran de terminal animé).
""")


def main():
    parser = argparse.ArgumentParser(description="Telechargement de video stock pour l'intro du reel")
    parser.add_argument("--api-key", help="Clé API Pexels (gratuite sur pexels.com/api)")
    parser.add_argument("--url", help="URL directe vers une vidéo MP4")
    parser.add_argument("--query", default="typing laptop keyboard", help="Termes de recherche Pexels")
    parser.add_argument("--output", default=str(DEST_FILE), help="Chemin de sortie")
    args = parser.parse_args()

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest = Path(args.output)

    # Vérifier si la vidéo existe déjà
    if dest.exists() and dest.stat().st_size > 10000:
        print(f"La vidéo existe déjà: {dest} ({dest.stat().st_size // 1024} KB)")
        print("Supprimez-la pour re-télécharger.")
        return

    print("=== Téléchargement de la vidéo d'accroche ===\n")

    # Option 1: URL directe
    if args.url:
        success = download_from_url(args.url, dest)
    # Option 2: API Pexels
    elif args.api_key:
        success = download_from_pexels(args.api_key, args.query)
    # Option 3: Essayer les sources gratuites
    else:
        print("Tentative de téléchargement depuis les sources gratuites...")
        success = try_all_free_videos()

    if success:
        print(f"\nVidéo prête: {dest}")
        print("Lancez maintenant: python main.py --config config/reel_config.yaml --output output/reel.mp4")
    else:
        show_manual_instructions()


if __name__ == "__main__":
    main()
