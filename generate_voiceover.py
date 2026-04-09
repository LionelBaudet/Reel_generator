"""
generate_voiceover.py
Generates a voiceover MP3 from a YAML config using the ElevenLabs TTS API.

Usage:
    python generate_voiceover.py --config config/reel_01.yaml
    python generate_voiceover.py --config config/reel_01.yaml --output assets/voiceover/custom.mp3
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL_ID     = "eleven_multilingual_v2"   # supports FR + EN
VOICEOVER_DIR        = Path("assets/voiceover")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_env() -> str:
    """Load and return the ElevenLabs API key from .env."""
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        sys.exit(
            "Error: ELEVENLABS_API_KEY is not set.\n"
            "Add it to your .env file:  ELEVENLABS_API_KEY=sk-..."
        )
    return api_key


def _safe_filename(text: str) -> str:
    """Convert arbitrary text to a filesystem-safe filename (no extension)."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:60]  # cap length


def _resolve_output_path(config: dict, override: str | None) -> Path:
    """Return the MP3 output path for this config."""
    if override:
        return Path(override)

    title = config.get("title", "reel")
    filename = _safe_filename(title) + ".mp3"
    VOICEOVER_DIR.mkdir(parents=True, exist_ok=True)
    return VOICEOVER_DIR / filename


# ---------------------------------------------------------------------------
# Core API call
# ---------------------------------------------------------------------------

def generate_voiceover(
    config: dict,
    output_path: str | Path | None = None,
    api_key: str | None = None,
) -> Path:
    """
    Generate a voiceover MP3 via ElevenLabs TTS API.

    Args:
        config:      Parsed YAML dict (must contain a 'voiceover' section).
        output_path: Where to write the MP3. Defaults to
                     assets/voiceover/{title}.mp3
        api_key:     ElevenLabs API key. If None, loaded from .env.

    Returns:
        Path to the saved MP3 file.

    Raises:
        SystemExit on unrecoverable error (missing key, API error, …).
    """
    if api_key is None:
        api_key = _load_env()

    # ── Extract voiceover params from config ──────────────────────────────
    vo = config.get("voiceover", {})
    if not vo:
        sys.exit("Error: YAML config is missing a 'voiceover' section.")

    text = vo.get("text", "").strip()
    if not text:
        sys.exit("Error: voiceover.text is empty in the YAML config.")

    voice_id         = vo.get("voice_id", "EXAVITQu4vr4xnSDxMaL")  # Sarah
    stability        = float(vo.get("stability", 0.5))
    similarity_boost = float(vo.get("similarity_boost", 0.75))
    style            = float(vo.get("style", 0.0))
    speed            = float(vo.get("speed", 1.0))
    model_id         = vo.get("model_id", DEFAULT_MODEL_ID)

    out_path = _resolve_output_path(config, output_path)

    # ── Build request ─────────────────────────────────────────────────────
    url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }

    payload = {
        "text":     text,
        "model_id": model_id,
        "voice_settings": {
            "stability":        stability,
            "similarity_boost": similarity_boost,
            "style":            style,
            "use_speaker_boost": True,
            "speed":            speed,
        },
    }

    print(f"[voiceover] Requesting TTS from ElevenLabs (voice={voice_id})...")
    snippet = text[:80] + ("..." if len(text) > 80 else "")
    print(f"[voiceover] Text ({len(text)} chars): {snippet}")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.exceptions.Timeout:
        sys.exit("Error: ElevenLabs API request timed out (60 s).")
    except requests.exceptions.ConnectionError as exc:
        sys.exit(f"Error: Could not connect to ElevenLabs API — {exc}")

    # ── Handle API errors ─────────────────────────────────────────────────
    if response.status_code == 401:
        sys.exit("Error: Invalid ElevenLabs API key (401 Unauthorized).")
    if response.status_code == 422:
        detail = response.json().get("detail", response.text)
        sys.exit(f"Error: ElevenLabs rejected the request (422) — {detail}")
    if response.status_code == 429:
        sys.exit("Error: ElevenLabs rate limit reached (429). Try again later.")
    if not response.ok:
        sys.exit(
            f"Error: ElevenLabs API returned {response.status_code} — "
            f"{response.text[:200]}"
        )

    # ── Save audio ────────────────────────────────────────────────────────
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)

    size_kb = out_path.stat().st_size // 1024
    print(f"[voiceover] Saved: {out_path}  ({size_kb} KB)")

    return out_path


# ---------------------------------------------------------------------------
# Per-scene voiceover (sync mode)
# ---------------------------------------------------------------------------

def generate_scene_voiceovers(
    scenes:       list[dict],
    voice_config: dict,
    output_dir:   str | Path,
    api_key:      str | None = None,
) -> list[dict]:
    """
    Generate one MP3 per scene for frame-accurate voiceover sync.

    Args:
        scenes:       list of scene dicts, each must have a 'text' key.
        voice_config: voiceover settings (voice_id, speed, stability, …)
                      same shape as the 'voiceover' section in YAML.
        output_dir:   folder where per-scene MP3s are saved.
        api_key:      ElevenLabs API key. If None, loaded from .env.

    Returns:
        list of dicts: [{text, path, duration_hint}, …]
        duration_hint is None until ffprobe confirms; caller can use
        it to set scene duration in the YAML / template.
    """
    if api_key is None:
        api_key = _load_env()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    voice_id         = voice_config.get("voice_id", "EXAVITQu4vr4xnSDxMaL")
    stability        = float(voice_config.get("stability", 0.5))
    similarity_boost = float(voice_config.get("similarity_boost", 0.75))
    style            = float(voice_config.get("style", 0.0))
    speed            = float(voice_config.get("speed", 1.0))
    model_id         = voice_config.get("model_id", DEFAULT_MODEL_ID)

    url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }

    results = []
    for i, scene in enumerate(scenes):
        text = str(scene.get("text", "")).strip()
        if not text:
            results.append({"text": text, "path": "", "duration_hint": None})
            continue

        out_path = output_dir / f"scene_{i:02d}.mp3"
        payload = {
            "text":     text,
            "model_id": model_id,
            "voice_settings": {
                "stability":        stability,
                "similarity_boost": similarity_boost,
                "style":            style,
                "use_speaker_boost": True,
                "speed":            speed,
            },
        }

        print(f"[voiceover] Scene {i+1}/{len(scenes)}: {text[:60]}")
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.exceptions.Timeout:
            print(f"[voiceover] Timeout on scene {i} — skipping")
            results.append({"text": text, "path": "", "duration_hint": None})
            continue
        except requests.exceptions.ConnectionError as exc:
            print(f"[voiceover] Connection error on scene {i}: {exc}")
            results.append({"text": text, "path": "", "duration_hint": None})
            continue

        if r.status_code == 401:
            sys.exit("Error: Invalid ElevenLabs API key (401 Unauthorized).")
        if r.status_code == 429:
            sys.exit("Error: ElevenLabs rate limit (429). Try again later.")
        if not r.ok:
            print(f"[voiceover] API error {r.status_code} on scene {i} — skipping")
            results.append({"text": text, "path": "", "duration_hint": None})
            continue

        out_path.write_bytes(r.content)
        print(f"[voiceover]   -> {out_path.name} ({out_path.stat().st_size // 1024} KB)")
        results.append({"text": text, "path": str(out_path), "duration_hint": None})

    # Probe durations with mutagen or wave fallback (no ffprobe needed)
    for item in results:
        p = item["path"]
        if not p or not Path(p).exists():
            continue
        try:
            import mutagen.mp3
            audio = mutagen.mp3.MP3(p)
            item["duration_hint"] = audio.info.length
        except Exception:
            # Raw estimation: MP3 at 128 kbps ~ 128 bits/ms → bytes * 8 / 128000
            size = Path(p).stat().st_size
            item["duration_hint"] = round(size * 8 / 128_000, 2)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a voiceover MP3 from a YAML reel config."
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to the reel YAML config (e.g. config/reel_01.yaml)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Override output path for the MP3 (optional)"
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        sys.exit(f"Error: Config file not found — {config_path}")

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    generate_voiceover(config, output_path=args.output)


if __name__ == "__main__":
    main()
