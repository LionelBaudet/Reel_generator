"""
utils/pexels.py — Intégration Pexels pour B-roll automatique.
Nécessite PEXELS_API_KEY dans .env ou st.secrets.

Usage :
    from utils.pexels import get_pexels_videos
    paths = get_pexels_videos(["man working laptop night", "minimal desk typing"])
"""

import hashlib
import logging
import os
from pathlib import Path

import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
CACHE_DIR = Path("assets/video/pexels")

# Résolutions acceptables (pas de 4K, portrait en priorité)
_PREFERRED_W = [1080, 720, 1280]


def _api_key() -> str:
    key = os.environ.get("PEXELS_API_KEY", "")
    return key


def _best_file(files: list) -> dict | None:
    """Sélectionne le meilleur fichier vidéo (HD portrait ou landscape)."""
    # Préférer les fichiers dont la hauteur > largeur (portrait)
    portrait = [f for f in files if f.get("height", 0) > f.get("width", 0)]
    candidates = portrait if portrait else files
    # Parmi eux, prendre ~1080p
    for w in _PREFERRED_W:
        for f in candidates:
            if abs(f.get("width", 0) - w) < 200:
                return f
    # Fallback : plus grande résolution dispo
    return max(candidates, key=lambda f: f.get("width", 0)) if candidates else None


def search_videos(query: str, per_page: int = 5) -> list[dict]:
    """
    Recherche des vidéos sur Pexels.
    Retourne une liste de dicts: {id, url, width, height, duration}
    """
    key = _api_key()
    if not key:
        logger.warning("PEXELS_API_KEY manquante — vidéos Pexels indisponibles")
        return []

    try:
        r = requests.get(
            PEXELS_VIDEO_URL,
            headers={"Authorization": key},
            params={"query": query, "per_page": per_page, "orientation": "portrait"},
            timeout=10,
        )
        r.raise_for_status()
        results = []
        for video in r.json().get("videos", []):
            best = _best_file(video.get("video_files", []))
            if best and best.get("link"):
                results.append({
                    "id":       video["id"],
                    "url":      best["link"],
                    "width":    best.get("width", 0),
                    "height":   best.get("height", 0),
                    "duration": video.get("duration", 30),
                })
        logger.info(f"Pexels '{query}' → {len(results)} résultats")
        return results
    except Exception as e:
        logger.warning(f"Pexels search error: {e}")
        return []


def _cache_path(query: str, video_id: int) -> Path:
    slug = query.replace(" ", "_")[:30]
    return CACHE_DIR / f"{video_id}_{slug}.mp4"


def download_video(url: str, out: Path) -> bool:
    """Télécharge une vidéo Pexels dans out (créé si absent). Retourne True si OK."""
    if out.exists() and out.stat().st_size > 10_000:
        logger.info(f"Pexels cache hit : {out.name}")
        return True
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
        logger.info(f"Pexels téléchargé : {out.name} ({out.stat().st_size // 1024} KB)")
        return True
    except Exception as e:
        logger.warning(f"Pexels download error: {e}")
        if out.exists():
            out.unlink()
        return False


def get_pexels_videos(queries: list[str], max_videos: int = 3,
                      fallback_path: str = "") -> list[str]:
    """
    Télécharge jusqu'à max_videos vidéos cohérentes pour les requêtes données.
    Retourne une liste de chemins locaux (str).
    Si PEXELS_API_KEY absente, retourne [fallback_path] si fourni.
    """
    if not _api_key():
        logger.info("Pas de clé Pexels — fallback broll local")
        return [fallback_path] if fallback_path else []

    paths = []
    for query in queries[:max_videos]:
        videos = search_videos(query, per_page=5)
        if not videos:
            continue
        # Préférer la vidéo la plus longue (moins de loop visible)
        video = max(videos, key=lambda v: v["duration"])
        out = _cache_path(query, video["id"])
        if download_video(video["url"], out):
            paths.append(str(out))
        if len(paths) >= max_videos:
            break

    if not paths and fallback_path:
        logger.info("Aucune vidéo Pexels téléchargée — fallback broll local")
        return [fallback_path]

    return paths
