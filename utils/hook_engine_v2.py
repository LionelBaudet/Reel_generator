# -*- coding: utf-8 -*-
"""
utils/hook_engine_v2.py — Hook Engine V2

Pipeline complet de génération, évaluation et sélection de hooks.

CORE PRINCIPLE:
  We do NOT generate one hook.
  We generate MANY → evaluate → eliminate → refine → select ONE.

Pipeline :
  1. Classification de l'idée
  2. Génération des angles (3–5 selon le type)
  3. Génération masse de candidats (15+)
  4. Filtrage strict (outil-first, trop long, vague, abstrait)
  5. Scoring V2 (0–10, boosts + pénalités + type-spécifique)
  6. Sélection top 3 (diversité sémantique assurée)
  7. Réécriture automatique si score < 6
  8. Sélection finale (lisibilité mobile-first)
  9. Validation publish-ready
  10. Output structuré

100% local — aucun appel API requis.
Optionnel : réécriture Claude pour hooks < 5.0 (use_api_rewrite=True).
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_idea_type(idea: str) -> str:
    """
    Classifie l'idée en l'un des 12 types de contenu.
    Délègue à idea_classifier.classify_idea() en priorité,
    sinon heuristique locale de fallback.
    """
    try:
        from utils.idea_classifier import classify_idea
        return classify_idea(idea)["type"]
    except ImportError:
        pass

    i = idea.lower()

    if any(k in i for k in ["prompt", "chatgpt", "claude", "gpt", "llm"]):
        return "prompt_reveal"
    if any(k in i for k in ["→", " h →", "min →", "avant :", "après :", "before", "after", "prenait", "passé de"]):
        return "before_after_time"
    if any(k in i for k in ["vs ", "versus", "comparaison", "meilleur que", "compare"]):
        return "comparison"
    if any(k in i for k in ["budget", "argent", "dépenses", "chf", "€", "$", "économ", "finance"]):
        return "budget_finance"
    if any(k in i for k in ["excel", "data", "workflow", "vlookup", "python", "script", "formule"]):
        return "data_workflow"
    if any(k in i for k in ["job", "carrière", "salaire", "cv", "augmentation", "career", "patron"]):
        return "career_work"
    if any(k in i for k in ["j'ai testé", "demo", "démo", "outil", "app ", "tool "]):
        return "tool_demo"
    if any(k in i for k in ["semaine 1", "build in public", "en public", "mois 1", "jour 1"]):
        return "build_in_public"
    if any(k in i for k in ["opinion", "faux", "personne ne", "en réalité", "la vérité"]):
        return "controversial_opinion"
    if any(k in i for k in ["histoire", "personnel", "perso", "le jour où", "quand j'ai"]):
        return "storytelling_personal"
    if any(k in i for k in ["expliquer", "comprendre", "différence", "ce qu'est", "c'est quoi"]):
        return "educational_explainer"
    if any(k in i for k in ["vous m'avez", "dm ", "question posée", "réponse à"]):
        return "reactive_reply"

    return "before_after_time"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — ANGLE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

# Tous les angles disponibles
ALL_ANGLES = [
    "pain", "loss", "time_gain", "money_gain", "discovery",
    "invisible_problem", "transformation", "shortcut", "secret",
    "authority", "opinion", "comparison", "proof",
]

# Angles prioritaires par type
_TYPE_ANGLES: dict[str, list[str]] = {
    "before_after_time":     ["time_gain", "transformation", "pain", "shortcut"],
    "prompt_reveal":         ["shortcut", "discovery", "secret", "authority"],
    "tool_demo":             ["discovery", "proof", "comparison", "transformation"],
    "comparison":            ["comparison", "proof", "opinion", "discovery"],
    "data_workflow":         ["pain", "time_gain", "transformation", "shortcut"],
    "budget_finance":        ["loss", "invisible_problem", "pain", "money_gain"],
    "career_work":           ["pain", "loss", "money_gain", "transformation"],
    "controversial_opinion": ["opinion", "invisible_problem", "comparison", "pain"],
    "build_in_public":       ["proof", "transformation", "authority", "discovery"],
    "storytelling_personal": ["transformation", "pain", "discovery", "shortcut"],
    "educational_explainer": ["invisible_problem", "discovery", "authority", "opinion"],
    "reactive_reply":        ["proof", "opinion", "discovery", "authority"],
}


def generate_angles(idea: str, idea_type: str) -> list[str]:
    """Retourne 3–5 angles pertinents selon l'idea_type."""
    return _TYPE_ANGLES.get(idea_type, ["pain", "loss", "time_gain", "discovery", "transformation"])[:5]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — MASS HOOK GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _extract_ctx(idea: str) -> dict:
    """Extrait les éléments contextuels de l'idée."""
    i = idea.lower()
    ctx: dict = {
        "time_str":  "",
        "money_str": "",
        "number":    "",
        "topic":     _shorten_topic(idea),
    }
    t = re.search(r"(\d+\s*(?:h|min|sec|heures?|minutes?|secondes?))", i)
    if t:
        ctx["time_str"] = t.group(1).strip()
    m = re.search(r"(\d+\s*(?:chf|€|\$|eur))", i)
    if m:
        ctx["money_str"] = m.group(1).strip()
    n = re.search(r"\b(\d+)\b", idea)
    if n:
        ctx["number"] = n.group(1)
    return ctx


def _shorten_topic(idea: str) -> str:
    """Extrait un sujet court (max 3 mots significatifs, sans chiffres ni mots vides)."""
    topic = re.sub(r"\d+\s*(h|min|sec|heures?|minutes?|secondes?|chf|€|\$)", "", idea, flags=re.IGNORECASE)
    topic = re.sub(r"[→\-–—].*", "", topic)
    topic = topic.strip(" .,:!")
    stop = {
        "de", "du", "la", "le", "les", "des", "un", "une", "en", "au", "aux",
        "et", "ou", "par", "sur", "dans", "avec", "pour", "que", "qui", "son",
        "ton", "mon", "sa", "ta", "ma", "ses", "tes", "mes", "comme", "sans",
        "plus", "tres", "tout", "tous", "cette", "cet", "ce",
        # participes/adjectifs qui ne font pas bon sujet seuls
        "genere", "generee", "cache", "cachee", "cachees", "caches",
        "planifie", "identifie", "automatise", "calcule", "analyse",
        "from", "with", "for", "the", "and", "your", "our",
    }
    # Prendre les mots dans l ordre (pas en sautant partout)
    words = [w for w in topic.split() if w.lower() not in stop and len(w) > 2]
    return " ".join(words[:2]) if words else "ca"


def generate_hook_candidates(idea: str, idea_type: str, angles: list[str]) -> list[str]:
    """
    Génère au moins 15 hooks candidats répartis sur 8 patterns.
    Distribution : user_pain · loss · time_transformation · discovery
                   prompt_reveal · controversial · tool · proof
    """
    ctx       = _extract_ctx(idea)
    time_str  = ctx["time_str"]  or "quelques minutes"
    number    = ctx["number"]
    money_str = ctx["money_str"]
    topic     = ctx["topic"].lower()

    candidates: list[str] = []

    # ── Pattern 1 : USER PAIN ─────────────────────────────────────────────────
    if "pain" in angles:
        candidates += [
            f"Tu fais encore {topic} à la main",
            f"Ton {topic} te fait perdre du temps",
            f"Tu perds du temps sur {topic} chaque semaine",
        ]
        if time_str:
            candidates += [
                f"Tu passes encore {time_str} sur {topic}",
                f"Tu perds {time_str} sur ça. Chaque semaine.",
            ]

    # ── Pattern 2 : LOSS / INVISIBLE PROBLEM ─────────────────────────────────
    if "loss" in angles or "invisible_problem" in angles:
        if money_str:
            candidates += [
                f"Tu perds {money_str} sans le voir",
                f"{money_str} qui fuit chaque mois",
                f"Il y avait {money_str} de pertes cachées",
            ]
        else:
            candidates += [
                f"Tu perds de l'argent sur {topic}. Sans le voir.",
                f"Ton {topic} fuit déjà",
                f"Tu crois gérer {topic}. Tu perds.",
            ]

    # ── Pattern 3 : TIME TRANSFORMATION ──────────────────────────────────────
    if "time_gain" in angles or "transformation" in angles:
        if time_str and number:
            try:
                n = int(number)
                alt_after = "2 min" if n > 10 else "30 sec"
            except ValueError:
                alt_after = "2 min"
            candidates += [
                f"{time_str} → {alt_after}",
                f"Avant : {time_str}. Maintenant : {alt_after}.",
                f"J'ai divise {time_str} par 10",
            ]
        elif time_str:
            candidates += [
                f"Avant : {time_str}. Maintenant : 3 min.",
                f"J'ai divise {time_str} par 10",
                f"{time_str} de boulot → automatise",
            ]
        else:
            candidates += [
                f"2h de {topic} → 8 minutes",
                "Avant : 2h. Apres : 8 min.",
                f"J'ai arrete de faire {topic} a la main",
            ]

    # ── Pattern 4 : DISCOVERY ─────────────────────────────────────────────────
    if "discovery" in angles or "secret" in angles:
        candidates += [
            f"Je ne voyais pas ça dans mon {topic}",
            f"Personne ne t'explique {topic} comme ça",
            f"On pensait maîtriser {topic}. Faux.",
        ]
        if money_str:
            candidates.append(f"{money_str} cachés dans ton {topic}")
        else:
            candidates.append(f"Ce que {topic} cache vraiment")

    # ── Pattern 5 : PROMPT REVEAL ─────────────────────────────────────────────
    if idea_type == "prompt_reveal" or "shortcut" in angles:
        candidates += [
            "Le prompt exact que j'utilise",
            f"1 prompt remplace {topic}",
            f"Mon prompt pour {topic}. Gratuit. Le voilà.",
            "J'ai testé 20 prompts. Un seul marche vraiment.",
        ]

    # ── Pattern 6 : CONTROVERSIAL ─────────────────────────────────────────────
    if "opinion" in angles or "comparison" in angles:
        candidates += [
            f"La moitié de ton temps sur {topic} est inutile",
            f"Tu fais {topic} depuis des années. C'est faux.",
            f"Personne ne te dit ça sur {topic}",
        ]

    # ── Pattern 7 : TOOL (seulement si pertinent) ─────────────────────────────
    if idea_type in ("tool_demo", "prompt_reveal", "comparison"):
        candidates += [
            f"J'ai testé ça pendant 30 jours",
            f"ChatGPT fait {topic} en 30 secondes",
        ]

    # ── Pattern 8 : PROOF / AUTHORITY ─────────────────────────────────────────
    if "proof" in angles or "authority" in angles:
        n_label = number or "30"
        candidates += [
            f"Après {n_label} jours sur {topic}. Mon verdict.",
            f"J'ai analysé {topic} pendant 6 mois",
        ]

    # ── Compléter si < 15 ─────────────────────────────────────────────────────
    if len(candidates) < 15:
        extras = [
            f"Tu n'as pas besoin d'1h pour {topic}",
            f"{topic.capitalize()} prend 3 minutes. Pas plus.",
            f"Le truc que je ne refais plus jamais à la main",
            f"J'aurais voulu savoir ça avant",
            f"Ce système m'a sauvé {time_str or '1h'} par semaine",
        ]
        candidates += extras[: 15 - len(candidates)]

    # Dédupliquer + nettoyer
    seen: set[str] = set()
    result = []
    for c in candidates:
        c = c.strip()
        if c and c not in seen and len(c.split()) >= 3:
            seen.add(c)
            result.append(c)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — HARD FILTER
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_FIRST_PREFIXES = [
    "ce prompt", "chatgpt ", "l'ia ", "cet outil", "cette app",
    "ce script", "cette formule", "ce workflow", "claude ", "gpt-", "gpt ",
    "power automate", "power bi ", "notion ", "zapier ", "openai ",
    "cette méthode", "cette technique",
    "this prompt", "this tool", "this app", "this script",
    "the ai ", "chatgpt,",
]

_ABSTRACT_WORDS = [
    "liberté", "succès", "bonheur", "mindset", "journey", "parcours",
    "transformation digitale", "révolution", "futur", "potentiel",
    "freedom", "happiness", "potential", "revolutionnaire",
]

_WEAK_STARTERS = [
    "voici ", "comment ", "découvrez", "astuce", "guide ",
    "apprenez", "saviez-vous", "did you know", "here's how",
    "dans cette vidéo", "today i ", "let me show",
    "je vais vous", "je vous montre", "aujourd'hui je",
]

_VAGUE_PATTERNS = [
    r"\bincroyable\b", r"\bfascinant\b", r"\bimpressionnant\b",
    r"\brévolutionnaire\b", r"\bexceptionnel\b", r"quelque chose de",
]


def is_tool_first(hook: str) -> bool:
    """Retourne True si le hook commence par un nom d'outil ou de technologie."""
    h = hook.strip().lower()
    return any(h.startswith(p) for p in _TOOL_FIRST_PREFIXES)


def filter_bad_hooks(hooks: list[str], idea_type: str = "") -> list[str]:
    """
    Filtre les hooks problématiques.
    Règles :
    - outil-first rejeté sauf pour tool_demo / prompt_reveal / comparison
    - > 12 mots rejeté
    - < 3 mots rejeté (fragment)
    - starters faibles (blog/tuto) rejetés
    - mots abstraits rejetés
    - patterns vagues rejetés
    """
    allow_tool = idea_type in ("tool_demo", "prompt_reveal", "comparison")
    result = []

    for hook in hooks:
        h     = hook.strip()
        h_low = h.lower()
        words = h.split()

        if len(words) > 12:
            continue
        if len(words) < 3:
            continue
        if not allow_tool and is_tool_first(h):
            continue
        if any(h_low.startswith(s) for s in _WEAK_STARTERS):
            continue
        if any(w in h_low for w in _ABSTRACT_WORDS):
            continue
        if any(re.search(p, h_low) for p in _VAGUE_PATTERNS):
            continue

        result.append(h)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — SCORING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _has_user(hook: str) -> bool:
    return bool(re.search(r"\btu\b|\bton\b|\btes\b|\byou\b|\byour\b", hook.lower()))


def _has_outcome(hook: str) -> bool:
    h = hook.lower()
    if re.search(r"\d+", h):
        return True
    return any(w in h for w in [
        "perds", "perd", "perdre", "gagne", "économises",
        "fuit", "fuite", "coûte", "évites",
        "lose", "save", "earn", "waste", "gain",
    ])


def score_hook_v2(hook: str, idea_type: str = "", angle: str = "") -> float:
    """
    Scoring V2 d'un hook (0.0–10.0).
    Base 5.0 — boosts si signaux forts — pénalités si signaux faibles.
    """
    h     = hook.strip()
    h_low = h.lower()
    words = h.split()
    score = 3.0  # base basse — chaque point doit etre merite

    # BOOSTS — plafond implicite par categorie pour eviter l'inflation

    # Interpellation directe "Tu / Ton / Tes" — signal viewer-first
    if _has_user(hook):
        score += 1.5

    # Perte OU argent (exclusif — prendre le plus fort)
    has_loss  = any(s in h_low for s in ["perds", "perd", "perdre", "fuit",
                    "fuite", "perte", "lose", "losing", "lost", "waste"])
    has_money = any(kw in h_low for kw in ["chf", "euro", "argent", "money", "budget"])
    if has_loss:
        score += 2.0
    elif has_money:
        score += 1.5

    # Contraste / transformation (fort signal)
    if "→" in h or re.search(r"\\bavant\\b.{1,20}\\bapr", h_low):
        score += 1.5

    # Chiffre (duree = plus fort, simple nombre = moindre)
    if re.search(r"\\d+\\s*(h|min|sec|heures?|minutes?|secondes?)", h_low):
        score += 1.0
    elif re.search(r"\\d+", h_low):
        score += 0.5

    # Curiosite / gap d'information
    if any(w in h_low for w in ["personne ne", "sans le voir", "cache",
                                  "secret", "nobody", "vraiment"]):
        score += 1.0

    # Outcome sans perte
    if not has_loss and _has_outcome(hook):
        score += 0.5

    # Langage parle / contractions
    if any(w in h_low for w in ["t'es", "c'est", "j'ai", "y'a", "encore",
                                  "you're", "don't", "i've"]):
        score += 0.5

    # Longueur ideale (bonus limite)
    if len(words) <= 5:
        score += 1.0
    elif len(words) <= 7:
        score += 0.5

    # Bonus angle-spécifique
    _angle_bonuses = {
        "loss":             (["perds", "fuit", "coûte"], 0.5),
        "time_gain":        (["min", "→", "h "], 0.5),
        "invisible_problem":(["sans le voir", "caché", "sans savoir"], 1.0),
        "discovery":        (["je ne voyais", "trouvé", "découvert"], 0.5),
        "shortcut":         (["prompt", "1 ", "simple", "3 min"], 0.5),
    }
    if angle in _angle_bonuses:
        signals, bonus = _angle_bonuses[angle]
        if any(s in h_low for s in signals):
            score += bonus

    # ── PÉNALITÉS ─────────────────────────────────────────────────────────────

    # Outil-first (viewer-first attendu)
    if is_tool_first(hook) and idea_type not in ("tool_demo", "prompt_reveal", "comparison"):
        score -= 3.0

    # Trop long
    if len(words) > 12:
        score -= 3.0
    elif len(words) > 10:
        score -= 2.0

    # Ton motivationnel
    if any(kw in h_low for kw in ["prouve", "ose ", "prêt à", "ready to",
                                    "commence", "crois en", "believe in"]):
        score -= 2.0

    # Starters blog/tuto
    if any(h_low.startswith(s) for s in _WEAK_STARTERS):
        score -= 3.0

    # Ton dramatique/artificiel
    if any(kw in h_low for kw in ["va transformer ta vie", "va changer", "incroyable",
                                    "révolutionnaire", "fascinant"]):
        score -= 1.5

    # Abstrait
    if any(kw in h_low for kw in ["liberté", "succès", "bonheur", "mindset", "journey"]):
        score -= 2.0

    # Ton passif/corporate
    if any(kw in h_low for kw in ["permettre de", "afin de", "en vue de",
                                    "in order to", "facilitates", "enables you to"]):
        score -= 1.5

    # Générique (aucun signal fort pour un hook > 5 mots)
    _strong = ["tu ", "ton ", "tes ", "perds", "fuit", "coûte", "→",
               "€", "$", "chf", "min", "sec", "lose", "save"]
    if len(words) > 5 and not any(s in h_low for s in _strong):
        score -= 1.5

    # ── Bonus type-spécifiques (hook_templates.py) ────────────────────────────
    if idea_type:
        try:
            from utils.hook_templates import get_type_score_bonuses
            for signal, bonus in get_type_score_bonuses(idea_type):
                if signal in h_low:
                    score += bonus
        except ImportError:
            pass

    return round(max(0.0, min(10.0, score)), 1)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — TOP SELECTION
# ─────────────────────────────────────────────────────────────────────────────

def select_top_hooks(hooks_with_scores: list[dict], n: int = 3) -> list[dict]:
    """
    Retourne les n meilleurs hooks en garantissant la diversité sémantique.
    Évite deux hooks qui commencent par les mêmes 3 mots.
    """
    ranked = sorted(hooks_with_scores, key=lambda x: x["score"], reverse=True)

    selected: list[dict] = []
    seen_starts: set[str] = set()

    for h in ranked:
        start = " ".join(h["text"].lower().split()[:3])
        if start not in seen_starts:
            seen_starts.add(start)
            selected.append(h)
        if len(selected) >= n:
            break

    # Compléter si la diversité a trop filtré
    if len(selected) < n:
        for h in ranked:
            if h not in selected:
                selected.append(h)
            if len(selected) >= n:
                break

    return selected[:n]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — REWRITE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def rewrite_hook(hook: str, strategy: str) -> str:
    """
    Réécrit un hook localement selon une stratégie. Sans API.

    Strategies :
    - convert_to_user     : outil-first → viewer-first ("Ce prompt…" → "Tu fais encore…")
    - shorten             : raccourcir aux 6 mots les plus forts
    - add_number          : injecter un chiffre si absent
    - make_more_direct    : supprimer passif / formulations longues
    - add_contrast        : ajouter structure avant/après si absente
    """
    h     = hook.strip()
    h_low = h.lower()
    words = h.split()

    if strategy == "convert_to_user":
        # "Ce prompt fait ton meal planning en 90 sec"
        # → "Tu perds 30 min chaque dimanche"
        if is_tool_first(h):
            # Extraire la durée si présente
            t = re.search(r"(\d+\s*(?:h|min|sec|heures?|minutes?))", h_low)
            if t:
                return f"Tu perds {t.group(1)} à la main"
            # Extraire le sujet (après le verbe)
            rest = re.sub(
                r"^(ce prompt|chatgpt|l'ia|cet outil|cette app|claude|gpt)\s+\w+\s*",
                "", h_low
            ).strip()
            if rest:
                return f"Tu fais encore ça à la main"
            return "Tu perds du temps sur ça"
        # Forcer "Tu" en début si absent
        if not h_low.startswith("tu "):
            h = re.sub(r"^(cette|ce|cet)\s+\w+\s+te\s+", "Tu ", h, flags=re.IGNORECASE)
            if not h.lower().startswith("tu"):
                h = "Tu " + h[0].lower() + h[1:]
        return h

    elif strategy == "shorten":
        # Garder les 6 premiers mots les plus significatifs
        if len(words) > 7:
            # Retirer les mots vides en fin
            stopwords_end = {"de", "du", "les", "des", "et", "en", "à", "la", "le", "sur"}
            trimmed = words[:7]
            while trimmed and trimmed[-1].lower() in stopwords_end:
                trimmed = trimmed[:-1]
            return " ".join(trimmed) if trimmed else " ".join(words[:6])
        return h

    elif strategy == "add_number":
        if not re.search(r"\d+", h):
            if any(w in h_low for w in ["temps", "time", "heure", "hour", "minute", "semaine"]):
                return h.rstrip(" .") + " (30 min)"
            if any(w in h_low for w in ["argent", "money", "budget", "dépenses"]):
                return h.rstrip(" .") + " (400€)"
        return h

    elif strategy == "make_more_direct":
        h = re.sub(r"\bpour pouvoir\b", "pour", h, flags=re.IGNORECASE)
        h = re.sub(r"\bafin de\b", "pour", h, flags=re.IGNORECASE)
        h = re.sub(r"\ben vue de\b", "pour", h, flags=re.IGNORECASE)
        h = re.sub(r"\bqui te permet de\b", "pour", h, flags=re.IGNORECASE)
        h = re.sub(r"\bpermettre de\b", "faire", h, flags=re.IGNORECASE)
        w = h.split()
        if len(w) > 8:
            h = " ".join(w[:7])
        return h.strip()

    elif strategy == "add_contrast":
        if "→" not in h and "avant" not in h_low:
            w = h.split()
            if len(w) <= 6:
                return f"Avant : {h} → maintenant : 2 min"
        return h

    return h


def _pick_rewrite_strategies(hook: str) -> list[str]:
    """Choisit les stratégies de réécriture adaptées au hook."""
    strategies = []
    h_low = hook.lower()
    words = hook.split()

    if is_tool_first(hook):
        strategies.append("convert_to_user")
    if len(words) > 9:
        strategies.append("shorten")
    if not re.search(r"\d+", h_low):
        strategies.append("add_number")
    if not _has_user(hook) and "convert_to_user" not in strategies:
        strategies.append("convert_to_user")
    strategies.append("make_more_direct")

    return strategies


def _auto_rewrite(hook_dict: dict, idea_type: str = "") -> dict:
    """
    Réécrit automatiquement un hook si son score < 6.
    Essaie plusieurs stratégies, garde la meilleure version.
    """
    if hook_dict["score"] >= 6.0:
        return {**hook_dict, "was_rewritten": False, "original_text": hook_dict["text"]}

    original   = hook_dict["text"]
    best_text  = original
    best_score = hook_dict["score"]
    used_strategy = None

    for strategy in _pick_rewrite_strategies(original):
        candidate = rewrite_hook(original, strategy)
        if candidate != original:
            candidate_score = score_hook_v2(candidate, idea_type)
            if candidate_score > best_score:
                best_score    = candidate_score
                best_text     = candidate
                used_strategy = strategy

    return {
        **hook_dict,
        "text":              best_text,
        "score":             best_score,
        "was_rewritten":     best_text != original,
        "original_text":     original,
        "rewrite_strategy":  used_strategy,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — FINAL SELECTION
# ─────────────────────────────────────────────────────────────────────────────

def choose_best_hook(top_hooks: list[dict]) -> dict:
    """
    Choisit le meilleur hook parmi le top 3.
    Critères : lisibilité mobile < 1 sec, trigger émotionnel, clarté.
    """
    if not top_hooks:
        return {"text": "", "score": 0.0}
    if len(top_hooks) == 1:
        return top_hooks[0]

    def _readability(h: dict) -> float:
        t     = h["text"]
        words = t.split()
        bonus = h["score"]

        # Court = lisible < 1 sec
        if len(words) <= 5:
            bonus += 2.0
        elif len(words) <= 7:
            bonus += 1.0

        # Commence par "Tu" = immédiat
        if t.lower().startswith("tu "):
            bonus += 1.0

        # Phrase simple (pas de virgule)
        if "," not in t:
            bonus += 0.5

        # Ancrage chiffré
        if re.search(r"\d+", t):
            bonus += 0.5

        # Pénalité : trop de mots de liaison
        filler = ["qui", "que", "dont", "lequel", "laquelle", "lesquels"]
        if sum(1 for w in t.lower().split() if w in filler) > 1:
            bonus -= 0.5

        return bonus

    return sorted(top_hooks, key=_readability, reverse=True)[0]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — SELF VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_hook_final(hook: str) -> tuple[bool, list[str]]:
    """
    Validation publish-ready avant sortie.
    Retourne (is_publishable: bool, issues: list[str]).

    Questions :
    1. Would this stop me from scrolling?
    2. Is it instantly understandable?
    3. Is it human, not AI-written?
    4. Is it short enough for mobile?
    """
    issues: list[str] = []
    h     = hook.strip()
    h_low = h.lower()
    words = h.split()

    if len(words) > 10:
        issues.append(f"Trop long : {len(words)} mots (max 10)")
    if len(words) < 3:
        issues.append("Trop court : min 3 mots")
    if is_tool_first(h):
        issues.append("Outil-first : parler au viewer, pas à l'outil")
    if any(d in h_low for d in ["va transformer ta vie", "va changer", "incroyable"]):
        issues.append("Ton dramatique ou artificiel")
    if any(m in h_low for m in ["prouve que t'es prêt", "ose le", "dare to", "believe in"]):
        issues.append("Ton motivationnel — remplacer par quelque chose de concret")
    if any(v in h_low for v in ["quelque chose", "n'importe quoi", "plein de choses"]):
        issues.append("Formulation vague — rendre concret")
    if any(c in h_low for c in ["synergies", "leviers", "approche holistique", "best practices"]):
        issues.append("Ton corporate/LinkedIn")
    if h.endswith("?") and len(words) > 8:
        issues.append("Question trop longue — raccourcir ou transformer en affirmation")

    # Aucun signal fort
    strong = ["tu ", "ton ", "tes ", "perds", "perd", "fuit", "coûte",
              "→", "avant", "après", "€", "$", "chf", "min", "sec"]
    if len(words) > 4 and not any(s in h_low for s in strong):
        issues.append("Aucun signal fort (perte / gain / chiffre / interpellation)")

    return len(issues) == 0, issues


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONAL — API REWRITE (pour hooks < seuil après pipeline local)
# ─────────────────────────────────────────────────────────────────────────────

_API_REWRITE_SYSTEM = """\
Tu réécris des hooks Instagram faibles en versions plus performantes pour @ownyourtime.ai.
Audience : professionnels 25-45 ans. Compte faceless productivité / IA / revenus.

Règles strictes :
- Max 8 mots
- Langage parlé, pas rédigé
- Concret : perte visible, argent, erreur, problème direct
- Commence de préférence par "Tu / Ton / Tes" pour interpeller le viewer
- Jamais : "Voici", "Comment", "Astuce", "Guide", "Découvrez", "Ce prompt", "ChatGPT"
- Modèles préférés :
  "Tu perds X sans le voir"
  "Tu fais encore ça à la main"
  "2h → 8 minutes"
  "Le prompt exact que j'utilise"

Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

_API_REWRITE_PROMPT = """\
Réécris ces {n} hooks. Pour chaque hook, génère une version améliorée.

Hooks :
{hooks_list}

Retourne ce JSON exact :
{{
  "rewrites": [
    {{"original": "<texte original>", "improved": "<version améliorée, max 8 mots>"}},
    ...
  ]
}}
"""


def _api_rewrite_hooks(hooks: list[str]) -> dict[str, str]:
    """
    Réécrit les hooks via Claude en 1 seul appel.
    Retourne {original: improved}. Retourne {} si pas de clé API.
    """
    if not hooks:
        return {}
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}
    try:
        import anthropic
        hooks_list = "\n".join(f'- "{h}"' for h in hooks)
        prompt = _API_REWRITE_PROMPT.format(n=len(hooks), hooks_list=hooks_list)
        msg = anthropic.Anthropic(api_key=api_key).messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=_API_REWRITE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = re.sub(r",\s*([\]\}])", r"\1", raw)
        data = json.loads(raw)
        return {
            item["original"]: item["improved"]
            for item in data.get("rewrites", [])
            if item.get("original") and item.get("improved")
               and item["original"] != item["improved"]
        }
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE — run_hook_engine()
# ─────────────────────────────────────────────────────────────────────────────

def run_hook_engine(
    idea: str,
    idea_type: Optional[str]  = None,
    context:   Optional[dict] = None,
    history:   Optional[list] = None,
    use_api_rewrite: bool      = False,
    api_rewrite_threshold: float = 5.0,
) -> dict:
    """
    Pipeline complet Hook Engine V2.

    Params :
        idea                   : idée brute ("Meal planning généré en 90 secondes")
        idea_type              : optionnel — auto-détecté si absent
        context                : optionnel — {"niche": "...", "audience": "..."}
        history                : optionnel — liste de dicts {"text", "views", "likes", "comments"}
        use_api_rewrite        : True = appel Claude pour réécrire les hooks < seuil
        api_rewrite_threshold  : score minimum en dessous duquel réécrire via API

    Returns :
        {
          "best_hook":      str,
          "best_score":     float,
          "top_3":          list[str],
          "top_3_detailed": list[dict],
          "all_candidates": list[str],
          "scores":         dict[str, float],
          "idea_type":      str,
          "angles":         list[str],
          "validation":     {"is_publishable": bool, "issues": list[str]},
          "meta":           {"total_generated": int, "after_filter": int, "rewrites_applied": int},
        }
    """

    # ── Step 1 : Classification ────────────────────────────────────────────────
    detected_type = idea_type or classify_idea_type(idea)

    # ── Step 2 : Angles ───────────────────────────────────────────────────────
    angles = generate_angles(idea, detected_type)
    dominant_angle = angles[0] if angles else ""

    # ── Step 3 : Génération masse ──────────────────────────────────────────────
    raw_candidates = generate_hook_candidates(idea, detected_type, angles)

    # Enrichir avec exemples elite (inspiration, pas hooks directs)
    try:
        from utils.hook_templates import get_elite_examples
        raw_candidates = raw_candidates + get_elite_examples(detected_type)[:3]
    except ImportError:
        pass

    total_generated = len(raw_candidates)

    # ── Step 4 : Filtrage ─────────────────────────────────────────────────────
    filtered = filter_bad_hooks(raw_candidates, idea_type=detected_type)
    if len(filtered) < 5:
        filtered = raw_candidates  # filtrage trop agressif → fallback
    after_filter = len(filtered)

    # ── Step 5 : Scoring ──────────────────────────────────────────────────────
    # Boost historique si dispo
    history_tops: list[str] = []
    if history:
        try:
            from utils.hook_engine import history_boost as _hboost, performance_score
            history_sorted = sorted(history, key=performance_score, reverse=True)
            history_tops = [e.get("text", "") for e in history_sorted[:5] if e.get("text")]
        except ImportError:
            pass

    scored: list[dict] = []
    for hook_text in filtered:
        base  = score_hook_v2(hook_text, idea_type=detected_type, angle=dominant_angle)
        boost = 0.0
        if history_tops:
            try:
                from utils.hook_engine import history_boost as _hboost
                boost = _hboost(hook_text, history_tops)
            except ImportError:
                pass
        total = round(min(10.0, base + boost), 1)
        scored.append({
            "text":          hook_text,
            "score":         total,
            "base_score":    base,
            "history_boost": boost,
            "angle":         dominant_angle,
        })

    # ── Step 6 : Top selection ─────────────────────────────────────────────────
    top_3 = select_top_hooks(scored, n=3)

    # ── Step 7a : API rewrite (optionnel, avant rewrite local) ─────────────────
    if use_api_rewrite:
        weak_texts = [h["text"] for h in top_3 if h["score"] < api_rewrite_threshold]
        if weak_texts:
            api_rewrites = _api_rewrite_hooks(weak_texts)
            for h in top_3:
                if h["text"] in api_rewrites:
                    new_text  = api_rewrites[h["text"]]
                    new_score = score_hook_v2(new_text, detected_type, dominant_angle)
                    if new_score > h["score"]:
                        h.update({"text": new_text, "score": new_score,
                                   "was_rewritten": True, "original_text": h["text"]})

    # ── Step 7b : Rewrite local pour hooks < 6 ────────────────────────────────
    rewrites_applied = 0
    top_3_final = []
    for h in top_3:
        rewritten = _auto_rewrite(h, idea_type=detected_type)
        if rewritten.get("was_rewritten"):
            rewrites_applied += 1
            # Rescorer après réécriture
            rewritten["score"] = score_hook_v2(
                rewritten["text"], detected_type, dominant_angle
            )
        top_3_final.append(rewritten)

    # ── Step 8 : Sélection finale ──────────────────────────────────────────────
    best = choose_best_hook(top_3_final)

    # ── Step 9 : Validation ───────────────────────────────────────────────────
    is_pub, issues = validate_hook_final(best["text"])

    # Dernier recours si validation échoue
    if not is_pub and is_tool_first(best["text"]):
        fixed      = rewrite_hook(best["text"], "convert_to_user")
        is_pub2, issues2 = validate_hook_final(fixed)
        if is_pub2 or len(issues2) < len(issues):
            best   = {**best, "text": fixed, "score": score_hook_v2(fixed, detected_type)}
            is_pub, issues = is_pub2, issues2

    # ── Step 10 : Output ──────────────────────────────────────────────────────
    scores_map = {h["text"]: h["score"] for h in scored}

    return {
        "best_hook":      best["text"],
        "best_score":     best["score"],
        "top_3":          [h["text"] for h in top_3_final],
        "top_3_detailed": top_3_final,
        "all_candidates": filtered,
        "scores":         scores_map,
        "idea_type":      detected_type,
        "angles":         angles,
        "validation": {
            "is_publishable": is_pub,
            "issues":         issues,
        },
        "meta": {
            "total_generated":  total_generated,
            "after_filter":     after_filter,
            "rewrites_applied": rewrites_applied,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION HELPER — pour generate.py
# ─────────────────────────────────────────────────────────────────────────────

def enrich_viral_script_with_v2(sv: dict, idea: str, lang: str = "fr") -> dict:
    """
    Lance Hook Engine V2 sur une idée et enrichit un script viral existant.
    Remplace sv["best_hook"]["text"] si V2 trouve un hook de meilleur score.
    Ajoute sv["hook_engine_v2"] avec le rapport complet.

    Usage dans generate.py :
        from utils.hook_engine_v2 import enrich_viral_script_with_v2
        sv = enrich_viral_script_with_v2(sv, idea)
    """
    idea_type = sv.get("idea_type", "")
    result    = run_hook_engine(idea, idea_type=idea_type or None)

    sv["hook_engine_v2"] = result

    # Remplacer best_hook si V2 fait mieux
    current_best_score = sv.get("best_hook", {}).get("score", 0)
    if result["best_score"] > current_best_score:
        sv["best_hook"] = {
            "text":   result["best_hook"],
            "score":  result["best_score"],
            "reason": "Hook Engine V2 — score supérieur au hook Claude",
        }
        # Mettre à jour aussi le script
        if sv.get("script"):
            sv["script"]["hook"] = result["best_hook"]

    return sv


# ─────────────────────────────────────────────────────────────────────────────
# __main__ — Test + exemple de sortie
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import io, sys
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    SEP = "-" * 60

    idea_1 = "Meal planning de la semaine genere en 90 secondes."
    print("\n" + SEP)
    print("  HOOK ENGINE V2 - Test 1")
    print("  Idee : " + idea_1)
    print(SEP)

    r = run_hook_engine(idea_1)
    print("Type   : " + r["idea_type"])
    print("Angles : " + ", ".join(r["angles"]))
    print("Candidats : {} -> {} apres filtre, {} reecritures".format(
        r["meta"]["total_generated"], r["meta"]["after_filter"], r["meta"]["rewrites_applied"]
    ))
    print("\n-- TOP 3 --")
    for i, h in enumerate(r["top_3_detailed"], 1):
        rewr = " [reecrit]" if h.get("was_rewritten") else ""
        print("  {}. [{:.1f}] {}{}".format(i, h["score"], h["text"], rewr))
    print("\n-> BEST : {}  [{:.1f}/10]".format(r["best_hook"], r["best_score"]))
    pub = r["validation"]["is_publishable"]
    status = "PUBLISHABLE" if pub else "NEEDS WORK"
    print("   VALIDATION : " + status)
    for issue in r["validation"].get("issues", []):
        print("   ! " + issue)

    print("\n" + SEP)
    print("  Test 2 : rewrite strategies")
    print(SEP)
    bad = "Ce prompt fait ton meal planning en 90 sec"
    print("Hook original : " + bad)
    for s in ["convert_to_user", "shorten", "add_number"]:
        rw = rewrite_hook(bad, s)
        sc = score_hook_v2(rw)
        print("  [{:20s}] [{:.1f}] {}".format(s, sc, rw))

    print("\n" + SEP)
    print("  Test 3 : budget_finance")
    print(SEP)
    idea_2 = "Depenses cachees dans budget avec ChatGPT. 400 CHF de pertes."
    r2 = run_hook_engine(idea_2)
    print("Type : " + r2["idea_type"])
    for i, h in enumerate(r2["top_3_detailed"], 1):
        rewr = " [reecrit]" if h.get("was_rewritten") else ""
        print("  {}. [{:.1f}] {}{}".format(i, h["score"], h["text"], rewr))
    print("  -> BEST : {}  [{:.1f}]".format(r2["best_hook"], r2["best_score"]))
