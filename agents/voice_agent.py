"""
agents/voice_agent.py — Converts reel scripts into voiceover audio.

Pipeline:
  1. Split each scene into timed fragments
  2. Generate TTS per fragment (ElevenLabs → gTTS fallback)
  3. Insert calibrated silences between fragments and scenes
  4. Merge all audio into a single MP3
  5. Export to output/audio/reel_voice.mp3

Input : script dict (hook/tension/shift/proof/solution/result/cta)
Output: {"audio_path": "output/audio/reel_voice.mp3", "duration": X.X}
"""
from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path

log = logging.getLogger(__name__)

_AUDIO_DIR = Path("output/audio")

# Silence after each full scene (ms)
_SCENE_POST_PAUSE: dict[str, int] = {
    "hook":     800,   # let the hook land
    "tension":  400,   # rapid-fire fragments
    "shift":    700,   # breath before the turn
    "proof":    600,   # let the stat sink in
    "solution": 500,
    "result":   800,   # let the result resonate
    "cta":      300,
}
_FRAGMENT_PAUSE_MS = 350   # between fragments inside a scene
_SCENE_ORDER = ["hook", "tension", "shift", "proof", "solution", "result", "cta"]

# ElevenLabs
_MODEL_ID        = "eleven_multilingual_v2"
_VOICE_ID_FR     = "pNInz6obpgDQGcFmaJgB"   # Adam — deep, authoritative, works in FR
_VOICE_ID_EN     = "pNInz6obpgDQGcFmaJgB"


class VoiceAgent:
    """
    Converts a reel script dict into a merged MP3 voiceover.

    Usage:
        agent = VoiceAgent()
        result = agent.generate(script, lang="fr")
        # {"audio_path": "output/audio/reel_voice.mp3", "duration": 18.4}
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self._client  = None
        self._use_elevenlabs = False

        if self._api_key:
            try:
                from elevenlabs.client import ElevenLabs  # type: ignore
                self._client = ElevenLabs(api_key=self._api_key)
                self._use_elevenlabs = True
                log.info("[VoiceAgent] ElevenLabs ready")
            except ImportError:
                log.warning("[VoiceAgent] elevenlabs package not installed — using gTTS")
        else:
            log.info("[VoiceAgent] No ELEVENLABS_API_KEY — using gTTS")

    # ── Public ────────────────────────────────────────────────────────────────

    def generate(
        self,
        script: dict,
        lang: str = "fr",
        output_filename: str = "reel_voice.mp3",
    ) -> dict:
        """Generate voiceover for a full script. Returns path + duration."""
        try:
            from pydub import AudioSegment  # type: ignore
        except ImportError:
            return {"audio_path": None, "duration": 0, "error": "pydub not installed — run: pip install pydub"}

        _AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        output_path = _AUDIO_DIR / output_filename

        scenes = [(k, script[k]) for k in _SCENE_ORDER if script.get(k)]
        if not scenes:
            return {"audio_path": None, "duration": 0, "error": "empty script"}

        combined = AudioSegment.empty()

        for scene_key, text in scenes:
            log.info(f"[VoiceAgent] {scene_key}: {text[:60]}…")
            fragments = self._split_fragments(text)
            post_ms   = _SCENE_POST_PAUSE.get(scene_key, 500)

            for i, frag in enumerate(fragments):
                audio_bytes = self._tts(frag, lang)
                if audio_bytes:
                    seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                    combined += seg
                    if i < len(fragments) - 1:
                        combined += AudioSegment.silent(duration=_FRAGMENT_PAUSE_MS)

            combined += AudioSegment.silent(duration=post_ms)

        # Fade out last 300 ms
        if len(combined) > 300:
            combined = combined.fade_out(300)

        combined.export(str(output_path), format="mp3", bitrate="192k")
        duration = round(len(combined) / 1000.0, 2)
        log.info(f"[VoiceAgent] Exported: {output_path} ({duration}s)")

        return {"audio_path": str(output_path), "duration": duration}

    # ── Fragment splitting ────────────────────────────────────────────────────

    def _split_fragments(self, text: str) -> list[str]:
        """
        Split scene text at natural pause points.
        Tension scene: "Ton poste. Automatisé. Cette année." → 3 fragments.
        """
        # Split on sentence-final punctuation or em-dash
        parts = re.split(r'(?<=[.!?])\s+|(?<=—)\s*|(?<=\.)\s+', text.strip())
        fragments: list[str] = []
        for part in parts:
            # Further split on commas between short clauses (≤4 words each side)
            sub = re.split(r',\s+(?=\S)', part)
            fragments.extend(s.strip() for s in sub if s.strip())
        return fragments or [text.strip()]

    # ── TTS dispatch ─────────────────────────────────────────────────────────

    def _tts(self, text: str, lang: str = "fr") -> bytes | None:
        if self._use_elevenlabs and self._client:
            result = self._elevenlabs(text, lang)
            if result:
                return result
        return self._gtts(text, lang)

    def _elevenlabs(self, text: str, lang: str = "fr") -> bytes | None:
        try:
            from elevenlabs import VoiceSettings  # type: ignore
            voice_id = _VOICE_ID_FR if lang == "fr" else _VOICE_ID_EN
            gen = self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=_MODEL_ID,
                voice_settings=VoiceSettings(
                    stability=0.50,
                    similarity_boost=0.75,
                    style=0.05,           # slight expressiveness
                    use_speaker_boost=True,
                ),
            )
            return b"".join(gen)
        except Exception as exc:
            log.warning(f"[VoiceAgent] ElevenLabs error: {exc}")
            return None

    def _gtts(self, text: str, lang: str = "fr") -> bytes | None:
        try:
            from gtts import gTTS  # type: ignore
            buf = io.BytesIO()
            gTTS(text=text, lang=lang, slow=False).write_to_fp(buf)
            buf.seek(0)
            return buf.read()
        except Exception as exc:
            log.error(f"[VoiceAgent] gTTS error: {exc}")
            return None
