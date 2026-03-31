"""
Générateur synthétique de beat lo-fi.
Produit un WAV bouclable sans aucune dépendance externe.

Style : lo-fi hip-hop à 85 BPM — kick/snare/hihat + basse + pad chaud.
"""

import math
import logging
import numpy as np
import wave
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

SR  = 44100     # fréquence d'échantillonnage
BPM = 85        # tempo lo-fi classique


# ── Primitives sonores ──────────────────────────────────────────────────────

def _envelope(n: int, attack: float = 0.002, decay: float = 0.3,
              sustain: float = 0.0, release: float = 0.05) -> np.ndarray:
    """Enveloppe ADSR simple."""
    t = np.linspace(0, 1, n)
    total = attack + decay + release
    env = np.zeros(n)
    a_end = attack / total
    d_end = (attack + decay) / total
    r_start = 1.0 - release / total

    env[t <= a_end]  = t[t <= a_end] / a_end
    mask_d = (t > a_end) & (t <= d_end)
    env[mask_d] = 1.0 - (t[mask_d] - a_end) / (d_end - a_end) * (1 - sustain)
    mask_s = (t > d_end) & (t <= r_start)
    env[mask_s] = sustain
    mask_r = t > r_start
    env[mask_r] = sustain * (1 - (t[mask_r] - r_start) / (release / total))
    return np.clip(env, 0, 1)


def _kick(duration: float = 0.45) -> np.ndarray:
    """Kick drum style 808 : sweep fréquentiel + décroissance."""
    n = int(SR * duration)
    t = np.linspace(0, duration, n)
    # La fréquence descend de 150 Hz à 50 Hz exponentiellement
    freq = 150 * np.exp(-t * 14) + 50
    phase = np.cumsum(2 * np.pi * freq / SR)
    amp   = np.exp(-t * 8) * 0.90
    click = np.exp(-t * 300) * 0.15   # transient initial
    return (np.sin(phase) * amp + click) * 0.85


def _snare(duration: float = 0.22) -> np.ndarray:
    """Snare acoustique : bruit + ton à 220 Hz."""
    n = int(SR * duration)
    t = np.linspace(0, duration, n)
    noise = np.random.randn(n)
    tone  = np.sin(2 * np.pi * 220 * t)
    env   = np.exp(-t * 22)
    return (noise * 0.55 + tone * 0.25) * env * 0.75


def _hihat_closed(duration: float = 0.06) -> np.ndarray:
    """Hi-hat fermé : bruit haute fréquence."""
    n = int(SR * duration)
    t = np.linspace(0, duration, n)
    noise = np.random.randn(n)
    env   = np.exp(-t * 80)
    return noise * env * 0.30


def _hihat_open(duration: float = 0.18) -> np.ndarray:
    """Hi-hat ouvert : durée plus longue."""
    n = int(SR * duration)
    t = np.linspace(0, duration, n)
    noise = np.random.randn(n)
    env   = np.exp(-t * 20)
    return noise * env * 0.20


def _bass_note(freq: float, duration: float, amp: float = 0.55) -> np.ndarray:
    """Note de basse lo-fi : fondamentale + harmoniques douces."""
    n = int(SR * duration)
    t = np.linspace(0, duration, n)
    w = (
        np.sin(2 * np.pi * freq * t) * 0.65
        + np.sin(2 * np.pi * freq * 2 * t) * 0.25
        + np.sin(2 * np.pi * freq * 3 * t) * 0.10
    )
    env = _envelope(n, attack=0.01, decay=duration * 0.7, sustain=0.1, release=0.2)
    return w * env * amp


def _pad_chord(freqs: list[float], duration: float, amp: float = 0.18) -> np.ndarray:
    """Accord de pad (style piano électrique lo-fi)."""
    n = int(SR * duration)
    t = np.linspace(0, duration, n)
    w = np.zeros(n)
    for f in freqs:
        # Légère désaccordage pour chaleur
        detune = 1 + np.random.uniform(-0.002, 0.002)
        w += np.sin(2 * np.pi * f * detune * t) * 0.5
        w += np.sin(2 * np.pi * f * 2 * detune * t) * 0.25
    env = _envelope(n, attack=0.06, decay=duration * 0.6, sustain=0.15, release=0.2)
    return w * env * amp


def _lowpass_filter(signal: np.ndarray, cutoff: float = 4000.0) -> np.ndarray:
    """
    Filtre passe-bas IIR du premier ordre (sans scipy).
    Donne le caractère 'muffled' du lo-fi.
    """
    rc  = 1.0 / (2 * math.pi * cutoff)
    dt  = 1.0 / SR
    a   = dt / (rc + dt)
    out = np.zeros_like(signal)
    prev = 0.0
    for i, x in enumerate(signal):
        prev = prev + a * (x - prev)
        out[i] = prev
    return out


def _vinyl_noise(n: int, amplitude: float = 0.008) -> np.ndarray:
    """Craquements de vinyle discrets."""
    noise = np.random.randn(n) * amplitude
    # Quelques pops aléatoires
    n_pops = n // (SR // 2)    # environ 1 pop par demi-seconde
    for _ in range(n_pops):
        pos = np.random.randint(0, n)
        pop_len = np.random.randint(50, 200)
        end = min(n, pos + pop_len)
        t = np.linspace(0, 1, end - pos)
        noise[pos:end] += np.random.choice([-1, 1]) * np.exp(-t * 30) * 0.015
    return noise


# ── Progressions d'accords par tonalité ──────────────────────────────────────

CHORD_PROGRESSIONS = {
    # (bpm, [(freq_basse, [notes_accord]), ...])
    "dm": (85, [           # Dm - Am - Bb - F  (chaud, classique lo-fi)
        (73.4,  [293.7, 349.2, 440.0]),   # Dm : D2 / D3 F3 A3
        (110.0, [220.0, 261.6, 329.6]),   # Am : A2 / A3 C3 E3
        (116.5, [233.1, 293.7, 349.2]),   # Bb : Bb2 / Bb2 D3 F3
        (87.3,  [174.6, 220.0, 261.6]),   # F  : F2 / F2 A2 C3
    ]),
    "am": (80, [           # Am - F - C - G  (mélancolique, rêveur)
        (110.0, [220.0, 261.6, 329.6]),   # Am : A2 / A3 C3 E3
        (87.3,  [174.6, 220.0, 261.6]),   # F  : F2 / F2 A2 C3
        (130.8, [261.6, 329.6, 392.0]),   # C  : C3 / C3 E3 G3
        (98.0,  [196.0, 246.9, 293.7]),   # G  : G2 / G2 B2 D3
    ]),
    "em": (88, [           # Em - C - G - D  (lumineux, énergique)
        (82.4,  [164.8, 196.0, 246.9]),   # Em : E2 / E2 G2 B2
        (130.8, [261.6, 329.6, 392.0]),   # C  : C3 / C3 E3 G3
        (98.0,  [196.0, 246.9, 293.7]),   # G  : G2 / G2 B2 D3
        (73.4,  [146.8, 185.0, 220.0]),   # D  : D2 / D2 F#2 A2
    ]),
    "gm": (82, [           # Gm - Eb - Bb - F  (sombre, introspectif)
        (98.0,  [196.0, 233.1, 293.7]),   # Gm : G2 / G2 Bb2 D3
        (77.8,  [155.6, 196.0, 233.1]),   # Eb : Eb2 / Eb2 G2 Bb2
        (116.5, [233.1, 293.7, 349.2]),   # Bb : Bb2 / Bb2 D3 F3
        (87.3,  [174.6, 220.0, 261.6]),   # F  : F2 / F2 A2 C3
    ]),
}


# ── Construction du beat ────────────────────────────────────────────────────

def generate_lofi_beat(output_path: str, duration_secs: float = 30.0,
                       key: str = "dm") -> str:
    """
    Génère un beat lo-fi et l'exporte en WAV stéréo 44.1 kHz.

    Args:
        output_path:   Chemin de sortie (.wav)
        duration_secs: Durée souhaitée
        key:           Tonalité — "dm" | "am" | "em" | "gm"

    Returns:
        Chemin du fichier créé
    """
    if key not in CHORD_PROGRESSIONS:
        logger.warning(f"Tonalité inconnue '{key}', utilisation de 'dm'")
        key = "dm"

    bpm, chords = CHORD_PROGRESSIONS[key]

    np.random.seed({"dm": 42, "am": 43, "em": 44, "gm": 45}[key])

    beat_s   = SR * 60 / bpm          # samples par temps
    bar_s    = int(beat_s * 4)        # samples par mesure (4/4)
    total_n  = int(SR * duration_secs)

    logger.info(f"Génération du beat lo-fi ({duration_secs}s @ {bpm} BPM, key={key})...")

    # ── Pré-générer les sons ──────────────────────────────────────────
    kick_snd  = _kick()
    snare_snd = _snare()
    hh_c_snd  = _hihat_closed()
    hh_o_snd  = _hihat_open()

    # ── Construire une mesure complète ────────────────────────────────
    def place(buffer, sound, pos):
        """Insère un son dans le buffer à la position donnée."""
        end = min(len(buffer), pos + len(sound))
        buf_len = end - pos
        buffer[pos:end] += sound[:buf_len]

    # ── Génération mesure par mesure ──────────────────────────────────
    n_bars = int(math.ceil(total_n / bar_s)) + 1
    raw = np.zeros(n_bars * bar_s)

    for bar in range(n_bars):
        bar_start = bar * bar_s
        chord_idx = bar % 4
        bfreq, cnotes = chords[chord_idx]

        # Basse (note tenue sur la mesure entière)
        bass = _bass_note(bfreq, bar_s / SR)
        place(raw, bass, bar_start)

        # Pad (léger, en arrière-plan)
        pad = _pad_chord(cnotes, bar_s / SR)
        place(raw, pad, bar_start)

        # Batterie — parcourir les 8èmes de la mesure
        for eighth in range(8):
            pos = bar_start + int(eighth * beat_s / 2)
            beat_in_bar = eighth / 2    # 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5

            # Kick : temps 1 et 3 (+ variation sur le "et" du 2 parfois)
            if beat_in_bar == 0.0:
                place(raw, kick_snd, pos)
            elif beat_in_bar == 2.0:
                place(raw, kick_snd, pos)
            elif beat_in_bar == 2.5 and bar % 2 == 1:
                # Ghost kick sur le "et" du 3 (variation)
                place(raw, kick_snd * 0.4, pos)

            # Snare : temps 2 et 4
            if beat_in_bar in (1.0, 3.0):
                place(raw, snare_snd, pos)

            # Hi-hat : toutes les 8èmes (open sur le "et" du 4)
            if beat_in_bar == 3.5:
                place(raw, hh_o_snd, pos)
            else:
                # Légère variation de vélocité pour humanisation
                vel = 0.7 + 0.3 * np.random.random()
                place(raw, hh_c_snd * vel, pos)

    # ── Traitement final ──────────────────────────────────────────────
    # Tronquer à la durée voulue
    raw = raw[:total_n]

    # Filtre passe-bas (warmth lo-fi)
    logger.info("Application du filtre lo-fi...")
    raw = _lowpass_filter(raw, cutoff=3800)

    # Craquements vinyle
    raw += _vinyl_noise(total_n)

    # Normalisation douce
    peak = np.max(np.abs(raw))
    if peak > 0:
        raw = raw / peak * 0.75

    # Fade in/out (0.5s)
    fade_n = min(int(SR * 0.5), total_n // 4)
    raw[:fade_n]  *= np.linspace(0, 1, fade_n)
    raw[-fade_n:] *= np.linspace(1, 0, fade_n)

    # ── Export WAV stéréo ─────────────────────────────────────────────
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Stéréo : canal droit légèrement décalé pour la profondeur
    delay_samples = int(SR * 0.012)   # 12ms de délai stéréo
    right = np.concatenate([np.zeros(delay_samples), raw[:-delay_samples]])
    stereo = np.stack([raw, right], axis=1)

    # Convertir en int16
    stereo_int = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)

    with wave.open(output_path, 'w') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo_int.tobytes())

    size_kb = Path(output_path).stat().st_size // 1024
    logger.info(f"Beat lo-fi généré : {output_path} ({size_kb} KB, {duration_secs}s)")
    return output_path


def ensure_lofi_beat(path: str = "assets/audio/lofi_beat.wav",
                     duration: float = 35.0,
                     key: str = "dm") -> str:
    """
    S'assure qu'un fichier de beat lo-fi existe.
    Le génère si absent.

    Args:
        path:     Chemin de sortie WAV
        duration: Durée en secondes
        key:      Tonalité — "dm" | "am" | "em" | "gm"
    """
    p = Path(path)
    if p.exists() and p.stat().st_size > 50_000:
        logger.info(f"Beat existant réutilisé : {path}")
        return path
    return generate_lofi_beat(path, duration_secs=duration, key=key)


def ensure_all_beats(duration: float = 35.0) -> dict:
    """
    Génère tous les beats lo-fi manquants (une tonalité par fichier).
    Retourne un dict {key: path}.
    """
    results = {}
    for k in CHORD_PROGRESSIONS:
        path = f"assets/audio/lofi_beat_{k}.wav"
        results[k] = ensure_lofi_beat(path, duration=duration, key=k)
    return results
