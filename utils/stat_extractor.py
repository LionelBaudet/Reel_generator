# -*- coding: utf-8 -*-
"""
utils/stat_extractor.py — Extraction automatique de stats et faits accrocheurs.

Détecte pourcentages, ratios, durées, montants dans un texte court (titre + résumé)
et les convertit en formulations humaines pour un hook de reel.

Usage:
    from utils.stat_extractor import detect_best_stat, extract_stats_from_signal
    stat = detect_best_stat("32% of managers use AI weekly — McKinsey")
    # → "1 manager sur 3 utilise l'IA chaque semaine"
"""
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass
class ExtractedStat:
    raw:       str    # fragment original
    humanized: str    # version lisible pour reel
    type:      str    # "percentage" | "ratio" | "time" | "money" | "count" | "comparison"
    impact:    float  # score d'accroche estimé (0–1)

    def __str__(self) -> str:
        return self.humanized


# ── Patterns regex ─────────────────────────────────────────────────────────────

_PCT_RE   = re.compile(r'(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)
_TIME_RE  = re.compile(
    r'(\d+(?:\.\d+)?)\s*'
    r'(hours?|heures?|h\b|minutes?|min\b|jours?|days?|semaines?|weeks?|months?|mois)',
    re.IGNORECASE
)
_MONEY_RE = re.compile(
    r'(\$|€|£|CHF)\s*(\d[\d\s,]*(?:\.\d+)?)\s*(k|million|M|B|billion|Mds)?',
    re.IGNORECASE
)
_MONEY_SUFFIX_RE = re.compile(
    r'(\d[\d\s,]*(?:\.\d+)?)\s*(k|million|M|B|billion|Mds)?\s*'
    r'(dollars?|\$|euros?|€|francs?|CHF)',
    re.IGNORECASE
)
_RATIO_RE       = re.compile(r'(\d+)\s+(?:in|out of|sur|parmi)\s+(\d+)', re.IGNORECASE)
_ONE_X_RE       = re.compile(r'\bone[- ](\w+)\b', re.IGNORECASE)   # "one-third", "one in two"
_MULTIPLIER_RE  = re.compile(r'(\d+(?:\.\d+)?)\s*[×x]\s*(?:more|plus|faster|rapide)', re.IGNORECASE)
_COMPARISON_RE  = re.compile(
    r'(\d+(?:\.\d+)?)\s*%?\s*(more|plus|less|moins|higher|lower|plus élevé|réduit|augmenté)',
    re.IGNORECASE
)
_MILLION_RE     = re.compile(r'(\d+(?:\.\d+)?)\s*(million|billion|Mds)\b', re.IGNORECASE)

# Mots indiquant fractions verbales
_FRACTION_MAP = {
    "one-third": ("1 sur 3", 0.85), "one third": ("1 sur 3", 0.85),
    "un tiers": ("1 sur 3", 0.85), "1/3": ("1 sur 3", 0.85),
    "one-quarter": ("1 sur 4", 0.80), "one quarter": ("1 sur 4", 0.80),
    "un quart": ("1 sur 4", 0.80), "1/4": ("1 sur 4", 0.80),
    "one-half": ("1 sur 2", 0.80), "half": ("1 sur 2", 0.80),
    "la moitié": ("1 sur 2", 0.80), "1/2": ("1 sur 2", 0.80),
    "two-thirds": ("2 sur 3", 0.80), "deux tiers": ("2 sur 3", 0.80),
    "three-quarters": ("3 sur 4", 0.78), "three quarters": ("3 sur 4", 0.78),
}

# Contexte professionnel pour humaniser les pourcentages
_PRO_CONTEXTS = [
    "manager", "employee", "worker", "salarié", "cadre", "professionnel",
    "entreprise", "company", "organisation", "bureau", "office",
    "remote", "télétravail",
]


def _humanize_pct(pct: float, context_text: str = "") -> str:
    """Convertit un % en formulation naturelle."""
    ctx = context_text.lower()

    # Ratio approché
    if 30 <= pct <= 37:
        subject = "manager" if any(w in ctx for w in ["manager", "manager"]) else "professionnel"
        return f"1 {subject} sur 3"
    if 48 <= pct <= 52:
        return "1 personne sur 2"
    if 23 <= pct <= 27:
        return "1 personne sur 4"
    if 18 <= pct <= 22:
        return "1 personne sur 5"
    if 63 <= pct <= 67:
        return "2 personnes sur 3"
    if 73 <= pct <= 77:
        return "3 personnes sur 4"

    # Formulation directe
    if pct >= 80:
        return f"{int(pct)}% des personnes"
    if pct >= 60:
        return f"plus de {int(pct)}%"
    if pct >= 40:
        return f"près de {int(pct)}%"
    return f"{int(pct)}%"


def _humanize_time(val: str, unit: str) -> str:
    """Humanise une durée."""
    unit_l = unit.lower().rstrip("s")
    mapping = {
        "hour": "h", "heure": "h", "h": "h",
        "minute": "min", "min": "min",
        "day": "jour", "jour": "jour",
        "week": "semaine", "semaine": "semaine",
        "month": "mois", "mois": "mois",
    }
    unit_fr = mapping.get(unit_l, unit)
    v = float(val)
    if unit_fr == "h" and v == int(v):
        return f"{int(v)}h"
    if unit_fr == "min" and v == int(v):
        return f"{int(v)} min"
    return f"{val} {unit_fr}"


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_stats_from_signal(text: str) -> list[ExtractedStat]:
    """Extrait toutes les stats détectables dans un texte."""
    stats: list[ExtractedStat] = []
    text = text or ""

    # Fractions verbales (highest impact — very natural)
    text_l = text.lower()
    for phrase, (humanized, impact) in _FRACTION_MAP.items():
        if phrase in text_l:
            stats.append(ExtractedStat(raw=phrase, humanized=humanized,
                                        type="ratio", impact=impact))

    # Ratios numériques: "1 in 3", "1 sur 5"
    for m in _RATIO_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a < b <= 20:
            stats.append(ExtractedStat(
                raw=m.group(0),
                humanized=f"{a} personne{'s' if a > 1 else ''} sur {b}",
                type="ratio",
                impact=0.80
            ))

    # Pourcentages
    for m in _PCT_RE.finditer(text):
        pct = float(m.group(1))
        if 2 <= pct <= 98:
            stats.append(ExtractedStat(
                raw=m.group(0),
                humanized=_humanize_pct(pct, text),
                type="percentage",
                impact=0.65 + (0.25 if 25 <= pct <= 75 else 0.0)
            ))

    # Millions / Milliards
    for m in _MILLION_RE.finditer(text):
        val, unit = m.group(1), m.group(2).lower()
        unit_fr = {"million": "million", "billion": "milliard", "mds": "milliards"}
        stats.append(ExtractedStat(
            raw=m.group(0),
            humanized=f"{val} {unit_fr.get(unit, unit)}",
            type="count",
            impact=0.70
        ))

    # Durées
    for m in _TIME_RE.finditer(text):
        val, unit = m.group(1), m.group(2)
        h = _humanize_time(val, unit)
        stats.append(ExtractedStat(
            raw=m.group(0),
            humanized=h + " par semaine" if "week" in unit.lower() or "semaine" in unit.lower() else h,
            type="time",
            impact=0.72
        ))

    # Montants (préfixe)
    for m in _MONEY_RE.finditer(text):
        symbol, amount = m.group(1), m.group(2).replace(",", "").replace(" ", "")
        mult = m.group(3) or ""
        mult_fr = {"k": "k", "m": "M", "million": "M", "b": "Mds", "billion": "Mds",
                   "mds": "Mds"}.get(mult.lower(), mult)
        stats.append(ExtractedStat(
            raw=m.group(0),
            humanized=f"{symbol}{amount}{mult_fr}",
            type="money",
            impact=0.78
        ))

    # Déduplique par type (garde le meilleur impact)
    seen: dict[str, ExtractedStat] = {}
    for s in stats:
        key = s.type + s.humanized[:20]
        if key not in seen or seen[key].impact < s.impact:
            seen[key] = s

    return sorted(seen.values(), key=lambda x: x.impact, reverse=True)


def detect_best_stat(text: str, context_hint: str = "") -> str:
    """
    Retourne la formulation de la meilleure stat détectée.
    Retourne "" si aucune stat trouvée.
    """
    combined = f"{text} {context_hint}"
    stats = extract_stats_from_signal(combined)
    if not stats:
        return ""
    return stats[0].humanized
