# -*- coding: utf-8 -*-
"""
utils/source_scoring.py — Score de fiabilité des sources (0.0–10.0).
Priorise les sources mondiales reconnues, suisses et francophones.

Usage:
    from utils.source_scoring import score_source, is_trusted_source, score_label
    score = score_source("McKinsey", "https://mckinsey.com/...", signal_title)
    label = score_label(score)   # "★★★★★ Elite"
"""
from __future__ import annotations
import re
from urllib.parse import urlparse

# ── Scores par domaine (0–10) ─────────────────────────────────────────────────

_DOMAIN_SCORES: dict[str, float] = {
    # Tier 1 — Cabinets de conseil / recherche (10)
    "mckinsey.com":            10.0,
    "gartner.com":             10.0,
    "hbr.org":                  9.5,
    "harvardbusiness.org":      9.5,
    "sloanreview.mit.edu":      9.5,
    "weforum.org":              9.5,
    "oecd.org":                 9.5,
    "technologyreview.com":     9.5,   # MIT Tech Review
    "brookings.edu":            9.0,
    "rand.org":                 9.0,
    "deloitte.com":             9.0,
    "pwc.com":                  9.0,
    "bcg.com":                  9.0,
    "bain.com":                 9.0,
    "accenture.com":            8.5,
    "kpmg.com":                 8.5,
    "ey.com":                   8.5,
    # Tier 1 — Presse économique / généraliste mondiale
    "ft.com":                   9.5,
    "wsj.com":                  9.5,
    "reuters.com":              9.5,
    "apnews.com":               9.0,
    "bloomberg.com":            9.0,
    "economist.com":            9.5,
    "bbc.com":                  8.5,
    "bbc.co.uk":                8.5,
    "theguardian.com":          8.5,
    "nytimes.com":              8.5,
    "washingtonpost.com":       8.5,
    "afp.com":                  9.0,
    # Tier 1 — Institutions / organismes officiels
    "europa.eu":                9.5,
    "un.org":                   9.5,
    "who.int":                  9.5,
    "imf.org":                  9.5,
    "worldbank.org":            9.5,
    "wipo.int":                 9.0,
    "bis.org":                  9.0,
    "snb.ch":                   9.0,
    "admin.ch":                 9.0,
    "bfs.admin.ch":             9.0,
    # Tier 2 — Tech & Innovation
    "wired.com":                8.5,
    "techcrunch.com":           8.0,
    "theverge.com":             8.0,
    "arstechnica.com":          8.0,
    "venturebeat.com":          7.5,
    "zdnet.com":                7.5,
    "cnet.com":                 7.0,
    "forbes.com":               7.5,
    "businessinsider.com":      7.0,
    "fastcompany.com":          7.5,
    "inc.com":                  7.0,
    "mit.edu":                  9.5,
    "stanford.edu":             9.5,
    # Tier 2 — Labs IA officiels
    "openai.com":               8.0,
    "anthropic.com":            8.0,
    "deepmind.google":          8.5,
    "research.google":          8.5,
    "ai.meta.com":              8.0,
    "microsoft.com":            7.5,
    # Tier 2 — Suisse francophone
    "letemps.ch":               8.5,
    "rts.ch":                   8.5,
    "bilan.ch":                 8.0,
    "swissinfo.ch":             8.5,
    "watson.ch":                7.5,
    "tdg.ch":                   7.5,
    "24heures.ch":              7.0,
    "rp.ch":                    7.0,
    "heidi.news":               7.5,
    "arcinfo.ch":               7.0,
    # Tier 2 — Presse française
    "lemonde.fr":               8.5,
    "lesechos.fr":              8.5,
    "lefigaro.fr":              8.0,
    "liberation.fr":            7.5,
    "latribune.fr":             8.0,
    "leparisien.fr":            7.0,
    "numerama.com":             7.5,
    "01net.com":                7.0,
    "silicon.fr":               7.0,
    "frenchweb.fr":             7.0,
    # Tier 3 — Contenus éditoriaux modérés
    "medium.com":               5.0,
    "substack.com":             5.5,
    "linkedin.com":             6.0,
    # Google News (agrégateur — score de base, enrichi par le titre)
    "news.google.com":          5.0,
}

# Mapping nom de source → score (pour Google News où l'URL est un redirect)
_NAME_SCORES: dict[str, float] = {
    "mckinsey":          10.0,
    "gartner":           10.0,
    "hbr":                9.5,
    "harvard business":   9.5,
    "harvard":            9.0,
    "mit":                9.0,
    "wef":                9.5,
    "davos":              9.5,
    "oecd":               9.5,
    "onu":                9.5,
    "reuters":            9.5,
    "bloomberg":          9.0,
    " ft ":               9.5,
    "financial times":    9.5,
    "wsj":                9.5,
    "wall street journal":9.5,
    "economist":          9.5,
    "bbc":                8.5,
    "guardian":           8.5,
    "ny times":           8.5,
    "new york times":     8.5,
    "ap news":            9.0,
    "afp":                9.0,
    "deloitte":           9.0,
    "pwc":                9.0,
    "bcg":                9.0,
    "bain":               9.0,
    "accenture":          8.5,
    "kpmg":               8.5,
    "le temps":           8.5,
    "rts":                8.5,
    "swissinfo":          8.5,
    "bilan":              8.0,
    "le monde":           8.5,
    "les echos":          8.5,
    "figaro":             8.0,
    "latribune":          8.0,
    "numerama":           7.5,
    "techcrunch":         8.0,
    "wired":              8.5,
    "the verge":          8.0,
    "forbes":             7.5,
    "fast company":       7.5,
    "fastcompany":        7.5,
    "openai":             8.0,
    "anthropic":          8.0,
    "microsoft":          7.5,
    "google":             7.5,
}

# Regex pour extraire le publisher en fin de titre Google News
# "Article title — Publisher Name" ou "Article title - Publisher Name"
_PUBLISHER_RE = re.compile(r'[—–-]\s*([^—–\-]+)\s*$')

_DEFAULT_SCORE = 5.0


def _extract_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def _score_from_name(name: str) -> float:
    """Score à partir d'un nom de source (partiel)."""
    name_l = name.lower()
    for key, sc in _NAME_SCORES.items():
        if key in name_l:
            return sc
    return 0.0


def score_source(source_name: str = "", source_url: str = "",
                 signal_title: str = "") -> float:
    """
    Score de fiabilité (0.0–10.0) pour une source.

    Ordre de priorité :
    1. Domaine de l'URL (exact puis sous-chaîne)
    2. Nom de la source
    3. Publisher extrait du titre (pour Google News)
    """
    # 1. URL-based scoring
    if source_url and "news.google.com" not in source_url:
        domain = _extract_domain(source_url)
        if domain in _DOMAIN_SCORES:
            return _DOMAIN_SCORES[domain]
        for known, sc in _DOMAIN_SCORES.items():
            if known in domain:
                return sc

    # 2. Source name scoring
    if source_name and "google news" not in source_name.lower():
        sc = _score_from_name(source_name)
        if sc > 0:
            return sc

    # 3. For Google News aggregated signals, extract publisher from title
    if signal_title:
        m = _PUBLISHER_RE.search(signal_title)
        if m:
            publisher = m.group(1).strip()
            sc = _score_from_name(publisher)
            if sc > 0:
                return sc

    # 4. Fallback
    return _DEFAULT_SCORE


def is_trusted_source(source_url: str = "", source_name: str = "",
                       signal_title: str = "", min_score: float = 7.0) -> bool:
    """Retourne True si la source dépasse le seuil de fiabilité."""
    return score_source(source_name, source_url, signal_title) >= min_score


def score_label(score: float) -> str:
    """Label lisible pour affichage UI."""
    if score >= 9.5:  return "★★★★★ Elite"
    if score >= 9.0:  return "★★★★½ Très fiable"
    if score >= 8.0:  return "★★★★ Fiable"
    if score >= 7.0:  return "★★★ Reconnu"
    if score >= 5.0:  return "★★ Standard"
    return "★ Faible"
