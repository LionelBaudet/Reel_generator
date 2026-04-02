"""
utils/validation.py — Validation et auto-correction d'une config reel avant rendu.

Règles :
- hook / cta : durée minimum 3.0s
- toutes les scènes : durée minimum 2.8s
- durée auto si le texte est long (> 6 mots → +0.4s par mot supplémentaire)
- warning si le texte dépasse 8 mots (surcharge visuelle)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Durées minimales par type de scène
MIN_DURATIONS: dict[str, float] = {
    "hook":     3.0,
    "cta":      3.0,
    "result":   3.0,
    "pain":     2.8,
    "shift":    2.8,
    "solution": 3.0,
    "twist":    2.8,
    "_default": 2.8,
}

# Vitesse de lecture confortable sur mobile (~1.8 mots / seconde)
WORDS_PER_SECOND = 1.8
# À partir de combien de mots on rallonge automatiquement
WORD_THRESHOLD = 5


def _min_duration_for_text(text: str, base_min: float) -> float:
    """Calcule la durée minimum pour un texte donné."""
    words = len(text.split())
    if words <= WORD_THRESHOLD:
        return base_min
    extra = (words - WORD_THRESHOLD) / WORDS_PER_SECOND
    return round(max(base_min, base_min + extra * 0.5), 1)


def validate_scenes(scenes: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Valide et corrige une liste de scènes.
    Retourne (scenes_corrigées, liste_de_messages).
    """
    issues: list[str] = []
    corrected: list[dict] = []

    for i, scene in enumerate(scenes):
        s = dict(scene)  # copie pour ne pas muter l'original
        stype    = s.get("type", "_default")
        text     = s.get("text", "")
        duration = float(s.get("duration", MIN_DURATIONS.get(stype, 2.8)))

        base_min = MIN_DURATIONS.get(stype, MIN_DURATIONS["_default"])
        auto_min = _min_duration_for_text(text, base_min)

        if duration < auto_min:
            issues.append(
                f"Scène {i+1} [{stype}] : durée {duration}s → {auto_min}s "
                f"({len(text.split())} mots)"
            )
            s["duration"] = auto_min

        words = len(text.split())
        if words > 10:
            issues.append(
                f"Scène {i+1} [{stype}] : texte long ({words} mots) — "
                "risque de surcharge visuelle"
            )

        corrected.append(s)

    return corrected, issues


def validate_config(config: dict) -> tuple[dict, list[str]]:
    """
    Valide et corrige la configuration complète d'un reel.
    Retourne (config_corrigée, liste_de_messages).
    """
    c = dict(config)
    all_issues: list[str] = []

    scenes = c.get("scenes", [])
    if not scenes:
        all_issues.append("Aucune scène définie.")
        return c, all_issues

    corrected_scenes, scene_issues = validate_scenes(scenes)
    c["scenes"] = corrected_scenes
    all_issues.extend(scene_issues)

    # Recalculer total_duration
    total = sum(float(s.get("duration", 2.8)) for s in corrected_scenes)
    c["total_duration"] = round(total, 1)

    # Vérifier présence hook en première scène
    first_type = corrected_scenes[0].get("type", "")
    if first_type != "hook":
        all_issues.append(
            f"La première scène est '{first_type}', pas 'hook' — "
            "le hook doit être visible dès la première frame."
        )

    # Vérifier le fond
    bg = c.get("background", {})
    opacity = float(bg.get("overlay_opacity", 0.55))
    if opacity < 0.45:
        c.setdefault("background", {})["overlay_opacity"] = 0.50
        all_issues.append(f"overlay_opacity {opacity} trop bas → 0.50 (lisibilité texte)")

    return c, all_issues


def self_check(config: dict) -> dict[str, bool]:
    """
    Retourne un dict de vérifications binaires pour le SELF_CHECK.
    """
    scenes   = config.get("scenes", [])
    first    = scenes[0] if scenes else {}
    bg       = config.get("background", {})
    opacity  = float(bg.get("overlay_opacity", 0.55))

    hook_ok      = first.get("type") == "hook"
    hook_big     = first.get("font_size", "lg") in ("xl",) or first.get("emphasis", False)
    rhythm_ok    = all(float(s.get("duration", 0)) >= 2.8 for s in scenes)
    text_first   = all(s.get("text", "") != "" for s in scenes)
    bg_discrete  = opacity >= 0.45
    pexels_ok    = bool(
        config.get("background", {}).get("videos") or
        config.get("pexels_queries")
    )

    return {
        "hook lisible":      hook_ok,
        "hook gros texte":   hook_big,
        "rythme lisible":    rhythm_ok,
        "texte prioritaire": text_first,
        "fond discret":      bg_discrete,
        "pexels cohérents":  pexels_ok,
    }
