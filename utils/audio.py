"""
Gestion audio pour le générateur de reels.
Charge la musique de fond ou génère du silence si aucun fichier n'est disponible.
"""

import logging
import os
import struct
import wave
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_silence(duration_seconds: float, output_path: str, sample_rate: int = 44100) -> str:
    """
    Génère un fichier WAV de silence de la durée spécifiée.

    Args:
        duration_seconds: Durée en secondes
        output_path: Chemin de sortie du fichier WAV
        sample_rate: Fréquence d'échantillonnage (44100 Hz par défaut)

    Returns:
        Chemin vers le fichier généré
    """
    n_frames = int(sample_rate * duration_seconds)
    n_channels = 2  # Stéréo

    logger.info(f"Génération de {duration_seconds}s de silence → {output_path}")

    with wave.open(output_path, 'w') as wav_file:
        wav_file.setnchannels(n_channels)
        wav_file.setsampwidth(2)       # 16 bits
        wav_file.setframerate(sample_rate)
        # Écrire des zéros (silence) par blocs de 1024 frames
        silence_frame = b'\x00' * n_channels * 2
        chunk_size = 1024
        full_chunks = n_frames // chunk_size
        remainder = n_frames % chunk_size

        for _ in range(full_chunks):
            wav_file.writeframes(silence_frame * chunk_size)
        if remainder:
            wav_file.writeframes(silence_frame * remainder)

    return output_path


def get_audio_clip(audio_config: dict, total_duration: float):
    """
    Prépare le clip audio pour le reel.
    Retourne un AudioFileClip MoviePy ou None si pas d'audio.

    Args:
        audio_config: Section 'audio' du fichier de configuration
        total_duration: Durée totale de la vidéo en secondes

    Returns:
        AudioFileClip ou None
    """
    try:
        from moviepy.editor import AudioFileClip, CompositeAudioClip
    except ImportError:
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
        except ImportError:
            logger.error("MoviePy n'est pas installé")
            return None

    bg_music_path = audio_config.get("background_music", "")
    volume = float(audio_config.get("volume", 0.3))

    # Vérifier si le fichier de musique existe
    if bg_music_path and os.path.exists(bg_music_path):
        logger.info(f"Chargement de la musique: {bg_music_path}")
        try:
            audio_clip = AudioFileClip(bg_music_path)
            # Boucler si nécessaire
            if audio_clip.duration < total_duration:
                from moviepy.audio.AudioClip import concatenate_audioclips
                repeats = int(total_duration / audio_clip.duration) + 1
                audio_clip = concatenate_audioclips([audio_clip] * repeats)
            # Couper à la durée exacte et ajuster le volume
            audio_clip = audio_clip.subclip(0, total_duration).volumex(volume)
            return audio_clip
        except Exception as e:
            logger.warning(f"Erreur chargement audio {bg_music_path}: {e}")

    # Générer un beat lo-fi synthétique si pas de fichier audio disponible
    try:
        from utils.audio_gen import ensure_lofi_beat
        beat_path = ensure_lofi_beat("assets/audio/lofi_beat.wav", duration=max(35.0, total_duration + 5))
        logger.info(f"Beat lo-fi généré : {beat_path}")
        audio_clip = AudioFileClip(beat_path)
        if audio_clip.duration < total_duration:
            from moviepy.audio.AudioClip import concatenate_audioclips
            repeats = int(total_duration / audio_clip.duration) + 1
            audio_clip = concatenate_audioclips([audio_clip] * repeats)
        audio_clip = audio_clip.subclip(0, total_duration).volumex(volume)
        return audio_clip
    except Exception as e:
        logger.warning(f"Beat lo-fi indisponible ({e}) — génération de silence")

    silence_path = "output/silence_temp.wav"
    os.makedirs("output", exist_ok=True)
    generate_silence(total_duration, silence_path)

    try:
        audio_clip = AudioFileClip(silence_path).volumex(0)
        return audio_clip
    except Exception as e:
        logger.warning(f"Impossible de créer le clip audio de silence: {e}")
        return None
