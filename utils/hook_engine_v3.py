# -*- coding: utf-8 -*-
"""
utils/hook_engine_v3.py  --  Hook Engine V3

Improvements over V2:
  - Native dual-language templates  (FR + EN, not translated)
  - Structured hook candidates      (text + angle + pattern_type + language)
  - classify_hook_pattern()         detect the pattern of any hook
  - classify_idea_type_with_confidence()  classification + confidence score
  - 4 sub-scorers                   readability / emotional / mobile / pattern_fit
  - Composite scoring V3            weighted, capped, stricter than V2
  - extract_winning_patterns()      learns feature boosts from history
  - boost_patterns_from_history()   applies learned boosts to candidates
  - rewrite_until_strong()          iterates until score >= threshold (max 3x)
  - 9 rewrite strategies            (vs 5 in V2)
  - Stricter final validation       auto-triggers rewrite on failure
  - generate_best_hook()            clean public API

Delegates to:
  hook_engine_v2  :  classify_idea_type, generate_angles, is_tool_first
  hook_engine     :  load_history, performance_score, history_boost
  idea_classifier :  classify_idea (for confidence score)

All local -- no Claude API required (optional api_rewrite param available).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Delegate imports (graceful fallback if modules not present)
# ---------------------------------------------------------------------------

try:
    from utils.hook_engine_v2 import (
        classify_idea_type as _classify_v2,
        generate_angles    as _angles_v2,
        is_tool_first      as _is_tool_first_v2,
        _extract_ctx       as _extract_ctx_v2,
        validate_hook_final as _validate_v2,
    )
    _HAS_V2 = True
except ImportError:
    _HAS_V2 = False

try:
    from utils.hook_engine import (
        load_history      as _load_history_v1,
        history_boost     as _history_boost_v1,
    )
    _HAS_V1 = True
except ImportError:
    _HAS_V1 = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOOL_OK_TYPES = {"tool_demo", "prompt_reveal", "comparison"}

PATTERN_TYPES = [
    "user_pain", "loss", "time_contrast", "transformation",
    "discovery", "prompt_reveal", "authority", "controversial",
    "comparison", "tool_demo", "generic",
]

_TOOL_FIRST_PREFIXES = [
    "ce prompt", "chatgpt", "l'ia", "cet outil", "cette app",
    "ce script", "cette formule", "ce workflow", "claude ", "gpt-", "gpt ",
    "power automate", "notion ", "zapier ", "openai ",
    "this prompt", "this tool", "this app", "this script", "the ai ",
]

_WEAK_STARTERS_V3 = [
    "voici ", "comment ", "decouvrez", "astuce", "guide ",
    "apprenez", "did you know", "here's how", "in this video",
    "je vais vous", "je vous montre", "today i ", "let me show",
]

_ABSTRACT_WORDS_V3 = [
    "liberte", "succes", "bonheur", "mindset", "journey",
    "transformation digitale", "revolution", "futur", "potentiel",
    "freedom", "happiness", "potential",
]

_MOTIVATIONAL = [
    "prouve que t'es pret", "ose le", "dare to", "believe in",
    "begins with", "start your", "crois en toi",
]


# ===========================================================================
# SECTION 1  --  IDEA CLASSIFIER (with confidence)
# ===========================================================================

def classify_idea_type(idea: str) -> str:
    """
    Classifies idea into one of 12 content types.
    Delegates to V2 (which delegates to idea_classifier.py).
    """
    if _HAS_V2:
        return _classify_v2(idea)

    # Inline fallback
    i = idea.lower()
    if any(k in i for k in ["prompt", "chatgpt", "claude", "gpt"]):
        return "prompt_reveal"
    if any(k in i for k in ["budget", "argent", "chf", "depenses", "finance"]):
        return "budget_finance"
    if any(k in i for k in ["excel", "vlookup", "data", "dax", "python", "script"]):
        return "data_workflow"
    if any(k in i for k in ["vs ", "versus", "comparaison"]):
        return "comparison"
    if any(k in i for k in ["augmentation", "salaire", "cv", "job", "carriere"]):
        return "career_work"
    if any(k in i for k in ["fail", "build in public", "semaine 1", "mois 1"]):
        return "build_in_public"
    if any(k in i for k in ["personne ne", "opinion", "en realite", "faux"]):
        return "controversial_opinion"
    return "before_after_time"


def classify_idea_type_with_confidence(idea: str) -> dict:
    """
    Returns: {
        "type": str,
        "confidence": float,   # 0.0 - 1.0
        "scores": dict,        # raw scores per category if available
        "label": str,
    }
    """
    # Try idea_classifier.py first (has weighted scoring + confidence)
    try:
        from utils.idea_classifier import classify_idea
        result = classify_idea(idea)
        return {
            "type":       result["type"],
            "confidence": result.get("confidence", 0.75),
            "scores":     result.get("scores", {}),
            "label":      result.get("label", result["type"]),
        }
    except ImportError:
        pass

    # Fallback: compute a simple confidence from keyword overlap
    detected = classify_idea_type(idea)
    i = idea.lower()
    words = set(i.split())

    _SIGNALS: dict[str, list[str]] = {
        "prompt_reveal":         ["prompt", "chatgpt", "claude", "gpt", "le prompt"],
        "budget_finance":        ["budget", "chf", "depenses", "argent", "euros"],
        "data_workflow":         ["excel", "vlookup", "dax", "data", "python"],
        "before_after_time":     ["avant", "apres", "heures", "minutes", "passe de"],
        "comparison":            ["vs", "versus", "comparaison", "gagnant"],
        "career_work":           ["augmentation", "salaire", "cv", "job"],
        "controversial_opinion": ["faux", "personne ne", "opinion", "realite"],
        "tool_demo":             ["teste", "demo", "outil", "app"],
        "build_in_public":       ["semaine 1", "fail", "mois 1", "build"],
        "educational_explainer": ["explique", "comprendre", "difference", "quest"],
    }

    top_score = sum(1 for kw in _SIGNALS.get(detected, []) if kw in i)
    total_kws = len(_SIGNALS.get(detected, [1]))
    confidence = min(0.95, 0.5 + (top_score / total_kws) * 0.5)

    _LABELS = {
        "before_after_time":     "Avant / Apres Temps",
        "prompt_reveal":         "Prompt Reveal",
        "tool_demo":             "Demo Outil",
        "comparison":            "Comparaison",
        "data_workflow":         "Data Workflow",
        "budget_finance":        "Budget / Finance",
        "career_work":           "Carriere / Travail",
        "controversial_opinion": "Opinion Controverse",
        "build_in_public":       "Build In Public",
        "storytelling_personal": "Storytelling",
        "educational_explainer": "Explainer Educatif",
        "reactive_reply":        "Reponse Reactive",
    }

    return {
        "type":       detected,
        "confidence": round(confidence, 2),
        "scores":     {},
        "label":      _LABELS.get(detected, detected),
    }


# ===========================================================================
# SECTION 2  --  ANGLE ENGINE (delegates to V2)
# ===========================================================================

def generate_angles(idea: str, idea_type: str) -> list[str]:
    """Returns 3-5 relevant angles for this idea_type."""
    if _HAS_V2:
        return _angles_v2(idea, idea_type)

    _MAP = {
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
    return _MAP.get(idea_type, ["pain", "loss", "time_gain", "discovery"])[:5]


# ===========================================================================
# SECTION 3  --  CONTEXT PARSING (enhanced from V2)
# ===========================================================================

_FR_STOP = {
    "de","du","la","le","les","des","un","une","en","au","aux","et","ou",
    "par","sur","dans","avec","pour","que","qui","son","ton","mon","sa","ta",
    "ma","ses","tes","mes","comme","sans","plus","tres","tout","tous","cette",
    "cet","ce","voila","voici","comment","exactement","vraiment","maintenant",
    "genere","generee","fait","utilise","analyse","cree","identifie","planifie",
    "calcule","automatise","via","apres","avant","quand","depuis","pendant",
    # participes/verbes courants qui ne font pas bon sujet
    "trouve","choque","cree","est","sont","etait","ete","sera","faut","peut","doit",
    # tool names / proper nouns not useful as topic
    "chatgpt","claude","gpt","openai","notion","zapier","excel",
    # "vlookup" kept as valid topic -- it IS the subject in VLOOKUP-type ideas
    "xlookup","powerbi","tableau","copilot","midjourney",
    # adjectives/state words that bleed from idea titles into topics
    "mort","vrai","faux","exact","cree","remplace","teste",
    # temporal nouns — usually just noise in topics
    "mois","semaine","semaines","jours","annee","annees","heures",
    # meta words from reel format
    "reel","reels","voici","systeme","preuve","raison",
    # relative pronouns / demonstratives
    "lequel","laquelle","lesquels","lesquelles","auquel","duquel","dont","quel","quelle",
}
_EN_STOP = {
    "the","a","an","in","on","at","of","for","with","from","and","or","but",
    "your","my","our","its","this","that","these","those","is","are","was",
    "were","been","have","has","had","do","does","did","will","would","could",
    "should","may","might","created","generated","made","done","using","used",
    # tool names as topic is meaningless
    "chatgpt","claude","gpt","openai","notion","zapier",
    # "vlookup" kept as valid topic -- it IS the subject in VLOOKUP-type ideas
    "xlookup","powerbi","tableau","copilot","midjourney",
    # adjectives/state words
    "dead","old","new","best","exact","real","true","false",
    # temporal nouns
    "month","months","week","weeks","days","years","hours",
}


def _extract_topic(idea: str) -> str:
    """
    Extracts 2 meaningful words from the idea (its core subject).
    """
    text = re.sub(r"[+\-]?\d+\s*(h|min|sec|heures?|minutes?|secondes?|chf|€|\$)",
                  "", idea, flags=re.IGNORECASE)
    # Also strip standalone currency signs (e.g. "+CHF" left after number removal)
    text = re.sub(r"[+\-]?\s*(chf|€|\$)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[→\-–—].*", "", text)
    text = re.sub(r"[.,!?;:]", " ", text).strip()
    # Strip French elisions: "d'augmentation" → "augmentation", "l'email" → "email"
    text = re.sub(r"\bqu'|\b[dlnjcsmtDLNJCSMT]'", " ", text)
    # Strip standalone numbers (no unit) — e.g. "600" in "demande +CHF 600"
    text = re.sub(r"\b\d+\b", " ", text)
    stop = _FR_STOP | _EN_STOP
    words = [w for w in text.split() if w.lower() not in stop and len(w) > 2]
    return " ".join(words[:2]).lower() if words else "ca"


def _parse_ctx(idea: str) -> dict:
    """
    Enhanced context extraction for V3.
    Returns: time_str, time_before, money_str, number, topic, tool_name
    """
    i = idea.lower()
    ctx: dict = {
        "time_str":    "",
        "time_before": "",
        "money_str":   "",
        "number":      "",
        "topic":       "",
        "tool_name":   "",
    }

    # Extract ALL time values (convert to minutes for sorting)
    time_hits = re.findall(
        r"(\d+)\s*(h\b|heures?\b|min\b|minutes?\b|sec\b|secondes?\b)",
        i, flags=re.IGNORECASE
    )
    time_vals: list[tuple[float, str]] = []
    for n_str, unit in time_hits:
        n = int(n_str)
        unit = unit.lower().rstrip("s")
        if unit in ("h", "heure"):
            time_vals.append((n * 60, f"{n}h"))
        elif unit in ("min", "minute"):
            time_vals.append((n, f"{n} min"))
        else:
            time_vals.append((n / 60, f"{n_str} sec"))

    time_vals.sort(key=lambda x: x[0], reverse=True)

    if len(time_vals) >= 2:
        ctx["time_before"] = time_vals[0][1]
        ctx["time_str"]    = time_vals[1][1]
    elif len(time_vals) == 1:
        ctx["time_str"] = time_vals[0][1]
        # Infer a plausible "before" time (10-20x longer)
        mins = time_vals[0][0]
        if mins <= 1:    ctx["time_before"] = "30 min"
        elif mins <= 5:  ctx["time_before"] = "45 min"
        elif mins <= 15: ctx["time_before"] = "1h"
        else:            ctx["time_before"] = "2h"

    # Arrow pattern: "2h -> 8 min" -- extract directly
    arrow_m = re.search(
        r"(\d+\s*(?:h|heures?))\s*[→>-]+\s*(\d+\s*(?:min|minutes?|sec))", i
    )
    if arrow_m:
        ctx["time_before"] = arrow_m.group(1).strip()
        ctx["time_str"]    = arrow_m.group(2).strip()

    # Money
    money_m = re.search(r"(\d+)\s*(chf\b|€|\$|eur\b)", i, flags=re.IGNORECASE)
    if money_m:
        unit = money_m.group(2).upper()
        ctx["money_str"] = f"{money_m.group(1)} {unit}"

    # First standalone number
    num_m = re.search(r"\b(\d+)\b", idea)
    if num_m:
        ctx["number"] = num_m.group(1)

    # Known tool names
    for tool in ["ChatGPT", "Claude", "GPT-4", "Excel", "Notion",
                 "Power BI", "Zapier", "Python", "VLOOKUP", "DAX"]:
        if tool.lower() in i:
            ctx["tool_name"] = tool
            break

    ctx["topic"] = _extract_topic(idea)
    return ctx


# ===========================================================================
# SECTION 4  --  DUAL-LANGUAGE TEMPLATE BANKS + CANDIDATE GENERATION
# ===========================================================================

# Each template: (text, pattern_type, angle, required_ctx_keys)
# If required_ctx_keys is empty, a fallback is always used.

_FR_TEMPLATES: list[tuple[str, str, str, list[str]]] = [
    # USER_PAIN
    ("Tu fais encore {topic} a la main",         "user_pain",  "pain",            ["topic"]),
    ("Ton {topic} te prend trop de temps",        "user_pain",  "pain",            ["topic"]),
    ("Tu perds {time_str} sur {topic} chaque semaine","user_pain","pain",          ["time_str","topic"]),
    ("Tu bosses encore {time_str} sur ca",        "user_pain",  "pain",            ["time_str"]),
    ("Tu fais encore ca a la main",               "user_pain",  "pain",            []),
    # LOSS
    ("Tu perds {money_str} sans le voir",         "loss",       "loss",            ["money_str"]),
    # ("Ton {topic} fuit deja" removed -- semantically wrong for non-finance types)
    ("Tu crois gerer {topic}. Tu perds.",         "loss",       "loss",            ["topic"]),
    ("{time_str} perdues chaque semaine",          "loss",       "loss",            ["time_str"]),
    # ("Tu travailles. L'argent part." removed -- zero-context generic, always wins irrelevantly)
    # TIME_CONTRAST
    ("{time_before} -> {time_str}",               "time_contrast","time_gain",     ["time_before","time_str"]),
    ("Avant : {time_before}. Maintenant : {time_str}.","time_contrast","time_gain",["time_before","time_str"]),
    ("J'ai divise {time_before} par 10",          "time_contrast","transformation",["time_before"]),
    ("Mon {topic} de {time_before}. Fait en {time_str}.","time_contrast","transformation",["topic","time_before","time_str"]),
    # ("2h -> 8 minutes" removed -- zero-context generic; use {time_before}->{time_str} instead)
    # DISCOVERY
    ("{money_str} caches dans ton {topic}",       "discovery",  "invisible_problem",["money_str","topic"]),
    ("Je ne voyais pas ca dans mon {topic}",      "discovery",  "discovery",       ["topic"]),
    ("On pensait maitriser {topic}. Faux.",        "discovery",  "invisible_problem",["topic"]),
    ("Ce que {topic} cache vraiment",             "discovery",  "secret",          ["topic"]),
    ("J'avais rate ca depuis 6 mois",             "discovery",  "discovery",       []),
    # PROMPT_REVEAL
    ("Le prompt exact que j'utilise",             "prompt_reveal","shortcut",      []),
    ("Mon prompt pour {topic}. Gratuit.",         "prompt_reveal","shortcut",      ["topic"]),
    ("1 prompt remplace {topic}",                 "prompt_reveal","shortcut",      ["topic"]),
    ("Le prompt qui fait {topic} en {time_str}",  "prompt_reveal","shortcut",      ["topic","time_str"]),
    ("J'ai teste 20 prompts. Un seul marche.",    "prompt_reveal","authority",     []),
    # CONTROVERSIAL
    ("La moitie de ton {topic} est inutile",      "controversial","opinion",       ["topic"]),
    ("Tu travailles {time_before} sur ca pour rien","controversial","opinion",     ["time_before"]),
    ("Personne ne dit ca sur {topic}",            "controversial","opinion",       ["topic"]),
    ("Tu fais {topic} depuis des annees. Faux.",  "controversial","opinion",       ["topic"]),
    ("La vraie raison pour laquelle {topic} ne marche pas","controversial","opinion",["topic"]),
    # TOOL_DEMO (only injected for relevant types)
    ("ChatGPT fait {topic} en {time_str}",        "tool_demo",  "discovery",       ["topic","time_str"]),
    ("J'ai teste ca pendant 30 jours",            "tool_demo",  "proof",           []),
    ("Cet outil remplace {topic}",                "tool_demo",  "comparison",      ["topic"]),
    # AUTHORITY / PROOF
    ("Apres {number} essais sur {topic}. Mon verdict.","authority","proof",        ["number","topic"]),
    ("J'ai analyse {topic} pendant 6 mois",       "authority",  "authority",       ["topic"]),
    ("Mon verdict honnete sur {topic}",           "authority",  "proof",           ["topic"]),
]

_EN_TEMPLATES: list[tuple[str, str, str, list[str]]] = [
    # USER_PAIN
    ("You're still doing {topic} manually",       "user_pain",  "pain",            ["topic"]),
    ("Your {topic} is taking way too long",       "user_pain",  "pain",            ["topic"]),
    ("You waste {time_str} on {topic} every week","user_pain",  "pain",            ["time_str","topic"]),
    ("Still spending {time_str} on this?",        "user_pain",  "pain",            ["time_str"]),
    ("You're still doing this the hard way",      "user_pain",  "pain",            []),
    # LOSS
    ("You're losing {money_str} without seeing it","loss",      "loss",            ["money_str"]),
    # ("Your {topic} is already leaking" removed -- too narrow for general use)
    ("You think you're on top of {topic}. You're not.","loss",  "loss",            ["topic"]),
    ("{time_str} wasted every single week",       "loss",       "loss",            ["time_str"]),
    # ("You work. Money disappears." removed -- zero-context generic)
    # TIME_CONTRAST
    ("{time_before} -> {time_str}",               "time_contrast","time_gain",     ["time_before","time_str"]),
    ("Before: {time_before}. Now: {time_str}.",   "time_contrast","time_gain",     ["time_before","time_str"]),
    ("I cut {time_before} down to {time_str}",    "time_contrast","transformation",["time_before","time_str"]),
    ("My {time_before} {topic}. Done in {time_str}.","time_contrast","transformation",["time_before","topic","time_str"]),
    ("2 hours -> 8 minutes",                      "time_contrast","time_gain",     []),
    # DISCOVERY
    ("{money_str} hidden in your {topic}",        "discovery",  "invisible_problem",["money_str","topic"]),
    ("I couldn't see this in my {topic}",         "discovery",  "discovery",       ["topic"]),
    ("We thought we had {topic}. We didn't.",     "discovery",  "invisible_problem",["topic"]),
    ("What your {topic} is actually hiding",      "discovery",  "secret",          ["topic"]),
    ("I missed this for 6 months",                "discovery",  "discovery",       []),
    # PROMPT_REVEAL
    ("The exact prompt I use every day",          "prompt_reveal","shortcut",      []),
    ("My prompt for {topic}. Free.",              "prompt_reveal","shortcut",      ["topic"]),
    ("1 prompt replaces {topic}",                 "prompt_reveal","shortcut",      ["topic"]),
    ("The prompt that does {topic} in {time_str}","prompt_reveal","shortcut",      ["topic","time_str"]),
    ("I tested 20 prompts. Only one works.",      "prompt_reveal","authority",     []),
    # CONTROVERSIAL
    ("Half your {topic} time is completely wasted","controversial","opinion",      ["topic"]),
    ("You work {time_before} on this for nothing","controversial","opinion",       ["time_before"]),
    ("Nobody tells you this about {topic}",       "controversial","opinion",       ["topic"]),
    ("You've been doing {topic} wrong for years", "controversial","opinion",       ["topic"]),
    ("The real reason your {topic} doesn't work", "controversial","opinion",       ["topic"]),
    # TOOL_DEMO
    ("ChatGPT does {topic} in {time_str}",        "tool_demo",  "discovery",       ["topic","time_str"]),
    ("I tested this for 30 days",                 "tool_demo",  "proof",           []),
    ("This tool replaces {topic}",                "tool_demo",  "comparison",      ["topic"]),
    # AUTHORITY / PROOF
    ("After {number} attempts on {topic}. My verdict.","authority","proof",       ["number","topic"]),
    ("I analyzed {topic} for 6 months",           "authority",  "authority",       ["topic"]),
    ("My honest verdict on {topic}",              "authority",  "proof",           ["topic"]),
]


def _fill(template: str, ctx: dict) -> str:
    """Fill a template with context values. Returns empty string if key missing."""
    try:
        return template.format(**ctx)
    except KeyError:
        return ""


def _can_fill(required: list[str], ctx: dict) -> bool:
    """Check if all required context keys are available and non-empty."""
    return all(ctx.get(k) for k in required)


def _build_candidates(
    templates: list[tuple[str, str, str, list[str]]],
    ctx: dict,
    active_angles: list[str],
    allow_tool: bool,
    language: str,
) -> list[dict]:
    """
    Fills templates and returns list of hook dicts.
    Respects active_angles and allow_tool filter.
    """
    results = []
    fallbacks = []  # templates with no requirements

    for tpl_text, pattern, angle, required in templates:
        # Skip tool templates unless allowed
        if pattern == "tool_demo" and not allow_tool:
            continue

        # Check angle relevance (be lenient -- use if angle is in active set OR no angle filter)
        angle_ok = (angle in active_angles or not active_angles)

        if _can_fill(required, ctx):
            text = _fill(tpl_text, ctx)
            if text:
                entry = {
                    "text":         text,
                    "angle":        angle,
                    "pattern_type": pattern,
                    "language":     language,
                    "score":        0.0,
                }
                if angle_ok:
                    results.append(entry)
                else:
                    fallbacks.append(entry)
        elif not required:
            # No requirements -- always include as fallback
            text = _fill(tpl_text, ctx)
            if text:
                fallbacks.append({
                    "text":         text,
                    "angle":        angle,
                    "pattern_type": pattern,
                    "language":     language,
                    "score":        0.0,
                })

    # Ensure at least 15 candidates total
    combined = results + fallbacks
    return combined


def generate_hook_candidates(
    idea: str,
    idea_type: str,
    angles: list[str],
    language: str = "fr",
) -> list[dict]:
    """
    Generates 18-24 hook candidates (structured dicts).
    Distributes across FR or EN native templates.
    """
    ctx         = _parse_ctx(idea)
    allow_tool  = idea_type in _TOOL_OK_TYPES
    bank        = _FR_TEMPLATES if language == "fr" else _EN_TEMPLATES

    candidates = _build_candidates(bank, ctx, angles, allow_tool, language)

    # If we have enough on-angle results, drop off-angle fallbacks
    on_angle  = [c for c in candidates if c.get("angle") in angles]
    off_angle = [c for c in candidates if c.get("angle") not in angles]
    if len(on_angle) >= 12:
        candidates = on_angle + off_angle[:3]  # keep only 3 off-angle fallbacks
    # else: include all (we need the padding)

    # Deduplicate by lowercase text
    seen: set[str] = set()
    unique = []
    for c in candidates:
        key = c["text"].lower().strip()
        if key not in seen and len(c["text"].split()) >= 3:
            seen.add(key)
            unique.append(c)

    return unique


# ===========================================================================
# SECTION 5  --  HOOK PATTERN CLASSIFIER
# ===========================================================================

def classify_hook_pattern(hook: str) -> str:
    """
    Identifies the dominant pattern type of a hook.
    Returns one of: user_pain, tool_first, curiosity, loss, time_contrast,
                    transformation, authority, opinion, comparison, generic.
    """
    h    = hook.strip().lower()
    words = h.split()

    # Tool-first (check before user_pain)
    if any(h.startswith(p) for p in _TOOL_FIRST_PREFIXES):
        return "tool_first"

    # Time contrast: contains arrow or avant/apres with time
    if "→" in hook or "->" in hook:
        return "time_contrast"
    if re.search(r"\bavant\b.{1,20}\b(apres|maintenant|now)\b", h):
        return "time_contrast"

    # Loss / invisible problem
    if any(w in h for w in ["perds", "perd", "perdre", "fuit", "coute",
                              "lose", "losing", "lost", "waste", "wasting"]):
        return "loss"

    # User pain (starts with tu/you/ton/your + douleur)
    if re.search(r"^(tu |ton |tes |you |your )", h):
        if any(w in h for w in ["encore", "still", "trop", "too long", "trop de"]):
            return "user_pain"
        return "user_pain"  # default for viewer-first hooks

    # Curiosity / discovery
    if any(w in h for w in ["personne ne", "nobody", "sans le voir", "cache",
                              "secret", "vraiment", "hidden", "actually"]):
        return "curiosity"

    # Transformation
    if any(w in h for w in ["passe de", "went from", "divise", "cut down",
                              "avant :", "before:", "plus jamais", "never again"]):
        return "transformation"

    # Authority / proof
    if any(w in h for w in ["j'ai teste", "i tested", "j'ai analyse", "verdict",
                              "apres 30", "after 30", "pendant", "for months"]):
        return "authority"

    # Controversial / opinion
    if any(w in h for w in ["la moitie", "half your", "pour rien", "for nothing",
                              "inutile", "useless", "faux.", "wrong for years"]):
        return "opinion"

    # Comparison
    if any(w in h for w in [" vs ", " vs.", "versus", "gagnant", "winner",
                              "remplace", "replaces", "est mort", "is dead"]):
        return "comparison"

    # Prompt reveal
    if any(w in h for w in ["prompt", "1 prompt", "le prompt", "the prompt"]):
        return "prompt_reveal"

    # Length-based fallback: very short = probably strong, long = generic
    if len(words) <= 5:
        return "user_pain"

    return "generic"


# ===========================================================================
# SECTION 6  --  HARD FILTER
# ===========================================================================

def is_tool_first(hook: str) -> bool:
    """Returns True if hook starts with a tool/AI name."""
    h = hook.strip().lower()
    return any(h.startswith(p) for p in _TOOL_FIRST_PREFIXES)


def is_weak_hook(hook: str) -> bool:
    """
    Returns True if the hook is likely to underperform.
    Combines V1 + V2 detection rules.
    """
    h     = hook.strip().lower()
    words = h.split()

    if len(words) > 12: return True
    if len(words) < 3:  return True

    if any(h.startswith(s) for s in _WEAK_STARTERS_V3):
        return True

    if any(w in h for w in _ABSTRACT_WORDS_V3):
        return True

    if any(m in h for m in _MOTIVATIONAL):
        return True

    # Long question (blog-style)
    if h.endswith("?") and len(words) > 8:
        return True

    # No strong signal for hooks > 5 words
    _strong = ["tu ", "ton ", "tes ", "you ", "your ", "perds", "fuit",
               "coute", "lose", "→", "->", "€", "$", "chf", "min", "sec",
               "prompt", "j'ai", "j'utilise", "i tested", "mon verdict"]
    if len(words) > 5 and not any(s in h for s in _strong):
        return True

    return False


def filter_bad_hooks(hooks: list[dict], idea_type: str = "") -> list[dict]:
    """
    Hard filter on structured hook dicts.
    Removes: tool-first (unless appropriate), too long, weak, abstract, vague.
    """
    allow_tool = idea_type in _TOOL_OK_TYPES
    result = []

    for hk in hooks:
        text  = hk.get("text", "").strip()
        h_low = text.lower()
        words = text.split()

        if len(words) > 12: continue
        if len(words) < 3:  continue
        if not allow_tool and is_tool_first(text): continue
        if any(h_low.startswith(s) for s in _WEAK_STARTERS_V3): continue
        if any(w in h_low for w in _ABSTRACT_WORDS_V3): continue
        if re.search(r"\b(incroyable|fascinant|revolutionnaire)\b", h_low): continue

        result.append(hk)

    return result if len(result) >= 5 else hooks  # fail-safe


# ===========================================================================
# SECTION 7  --  SCORING ENGINE V3
# ===========================================================================

def score_readability(hook: str, language: str = "fr") -> float:
    """
    Measures readability on mobile (0-10).
    Prioritizes: short length, clean syntax, no subordinate clauses.
    """
    words = hook.split()
    n     = len(words)
    score = 0.0

    # Length scoring (primary factor)
    if n <= 4:   score += 4.0
    elif n <= 6: score += 3.0
    elif n <= 8: score += 2.0
    elif n <= 10: score += 1.0
    # > 10 words: 0 bonus

    # Syntax simplicity (no commas, semicolons, parentheses)
    if "," not in hook:  score += 1.0
    if ";" not in hook:  score += 0.5
    if "(" not in hook:  score += 0.5

    # Visual anchors (numbers, arrows)
    if re.search(r"\d+", hook):          score += 1.0
    if "→" in hook or "->" in hook:      score += 1.5

    # Clean ending (full stop or none -- not a vague ellipsis)
    if hook.strip().endswith("..."):     score -= 1.0

    return round(min(10.0, max(0.0, score)), 1)


def score_emotional_trigger(hook: str, idea_type: str = "") -> float:
    """
    Measures emotional pull (0-10).
    Loss > gain > curiosity > frustration.
    """
    h = hook.lower()
    score = 0.0

    # Loss trigger (strongest scroll-stopper)
    if any(w in h for w in ["perds", "perd", "perdre", "fuit", "fuite",
                              "lose", "losing", "lost", "waste", "wasting"]):
        score += 4.0

    # Money loss (even stronger)
    if any(kw in h for kw in ["chf", "euro", "argent", "money", "budget"]):
        if any(w in h for w in ["perds", "fuit", "lose", "waste"]):
            score += 1.0  # combined: +5 total
        else:
            score += 2.5  # money alone

    # Time transformation (strong emotional contrast)
    if "→" in hook or "->" in hook:
        score += 2.5

    # Before/after explicit
    if re.search(r"\bavant\b.{1,20}\bapr", h) or re.search(r"\bbefore\b.{1,20}\bnow\b", h):
        score += 2.0

    # Gain trigger (less than loss)
    if any(w in h for w in ["gagne", "economises", "earn", "save", "saved"]):
        score += 1.5

    # Curiosity / invisible problem
    if any(w in h for w in ["sans le voir", "cache", "caches", "hidden",
                              "secret", "personne ne", "nobody", "vraiment"]):
        score += 2.0

    # Frustration / still doing it wrong
    if any(w in h for w in ["encore", "still", "always", "toujours",
                              "pour rien", "for nothing", "inutile"]):
        score += 1.0

    return round(min(10.0, max(0.0, score)), 1)


def score_mobile_clarity(hook: str) -> float:
    """
    Would this stop scroll in < 1 second on a phone? (0-10)
    """
    words = hook.split()
    score = 3.0  # base

    # Length (most important for instant comprehension)
    n = len(words)
    if n <= 4:   score += 3.0
    elif n <= 6: score += 2.0
    elif n <= 8: score += 1.0
    elif n > 10: score -= 2.0

    # Starts with "Tu" / "You" / "Ton" / "Your" -- immediate viewer connection
    if re.search(r"^(tu |ton |you |your )", hook.lower()):
        score += 1.5

    # Concrete number
    if re.search(r"\d+", hook):
        score += 1.0

    # Short avg word length (no complex vocabulary)
    if words:
        avg = sum(len(w) for w in words) / len(words)
        if avg <= 4:   score += 1.0
        elif avg >= 8: score -= 0.5

    # No comma = single clear idea
    if "," not in hook:
        score += 0.5

    return round(min(10.0, max(0.0, score)), 1)


def score_pattern_match(hook: str, idea_type: str = "", angle: str = "") -> float:
    """
    Is the hook pattern appropriate for the idea type and angle? (0-10)
    """
    pattern = classify_hook_pattern(hook)
    h       = hook.lower()
    score   = 5.0  # neutral base

    # Preferred patterns per type
    _PREFERRED: dict[str, list[str]] = {
        "before_after_time":     ["time_contrast", "user_pain", "comparison"],  # no loss
        "prompt_reveal":         ["prompt_reveal", "authority", "tool_first"],
        "tool_demo":             ["tool_first", "authority", "comparison"],
        "comparison":            ["comparison", "authority", "time_contrast"],
        "data_workflow":         ["user_pain", "time_contrast", "comparison"],  # no loss (penalized)
        "budget_finance":        ["loss", "discovery", "user_pain"],
        "career_work":           ["loss", "user_pain", "transformation"],
        "controversial_opinion": ["opinion", "curiosity", "user_pain"],
        "build_in_public":       ["authority", "transformation", "user_pain"],
        "storytelling_personal": ["transformation", "user_pain", "discovery"],
        "educational_explainer": ["curiosity", "opinion", "user_pain"],
        "reactive_reply":        ["authority", "opinion", "curiosity"],
    }
    preferred = _PREFERRED.get(idea_type, ["user_pain", "loss"])

    if pattern in preferred[:2]: score += 3.0
    elif pattern in preferred:   score += 1.5
    elif pattern == "generic":   score -= 1.5
    elif pattern == "tool_first" and idea_type not in _TOOL_OK_TYPES:
        score -= 4.0  # heavy penalty

    # Angle bonus
    _ANGLE_SIGNALS = {
        "loss":             ["perds", "fuit", "lose", "sans le voir"],
        "time_gain":        ["→", "->", "min", " h "],
        "invisible_problem":["sans le voir", "cache", "without seeing", "hidden"],
        "discovery":        ["je ne voyais", "i couldn't see", "cache", "hidden"],
        "shortcut":         ["prompt", "1 prompt", "3 min", "simple"],
        "money_gain":       ["chf", "€", "$", "money", "argent"],
    }
    if angle in _ANGLE_SIGNALS:
        if any(s in h for s in _ANGLE_SIGNALS[angle]):
            score += 1.0

    return round(min(10.0, max(0.0, score)), 1)


def score_hook_v3(
    hook:              str,
    idea_type:         str     = "",
    angle:             str     = "",
    language:          str     = "fr",
    history_patterns:  dict    = None,
) -> float:
    """
    Composite V3 score (0-10).
    Weighted from 4 sub-dimensions:
      readability(20%) + emotion(40%) + mobile(20%) + pattern_fit(20%)
    + history_boost  -- applies learned pattern boosts
    + hard penalties -- tool-first, weak starters, abstract, motivational
    """
    rd   = score_readability(hook, language)
    em   = score_emotional_trigger(hook, idea_type)
    mob  = score_mobile_clarity(hook)
    pat  = score_pattern_match(hook, idea_type, angle)

    # Weights: readability 20%, emotion 25%, mobile 20%, pattern_fit 35%
    # Rationale: pattern fit is now the strongest discriminator so type-appropriate
    # hooks beat generic loss hooks. Emotion stays meaningful but not dominant.
    composite = rd * 0.20 + em * 0.25 + mob * 0.20 + pat * 0.35

    # Hard type-pattern mismatch penalty
    # If the hook pattern doesn't fit the idea_type at all, dock it
    if idea_type:
        hook_pattern = classify_hook_pattern(hook)
        _MISMATCH_PENALTY: dict[str, list[str]] = {
            # for these types, "loss" hooks are semantically wrong
            "prompt_reveal":         ["loss", "generic"],
            "before_after_time":     ["loss", "generic"],   # time-savings → contrast, not loss
            "build_in_public":       ["loss", "generic"],
            "storytelling_personal": ["loss", "generic"],
            "educational_explainer": ["loss", "generic"],
            "reactive_reply":        ["loss", "generic"],
            # data/tool types: generic fallbacks AND loss hooks don't fit
            "data_workflow":         ["loss", "generic"],   # VLOOKUP/DAX = features, not losses
            "tool_demo":             ["generic"],
            "comparison":            ["loss", "generic"],   # comparison = features, not losses
            "career_work":           ["generic"],
            "budget_finance":        ["generic"],            # loss is OK for budget, not generic
        }
        bad_patterns = _MISMATCH_PENALTY.get(idea_type, [])
        if hook_pattern in bad_patterns:
            composite -= 2.5

    # Hard penalties (applied after weighted composite)
    h     = hook.strip().lower()
    words = hook.split()

    if is_tool_first(hook) and idea_type not in _TOOL_OK_TYPES:
        composite -= 3.0

    if len(words) > 12:
        composite -= 3.0
    elif len(words) > 10:
        composite -= 1.5

    if any(h.startswith(s) for s in _WEAK_STARTERS_V3):
        composite -= 3.0

    if any(w in h for w in _ABSTRACT_WORDS_V3):
        composite -= 2.0

    if any(m in h for m in _MOTIVATIONAL):
        composite -= 2.0

    if re.search(r"\b(incroyable|fascinant|revolutionnaire|amazing|incredible)\b", h):
        composite -= 1.5

    # History pattern boosts (small but meaningful)
    if history_patterns:
        composite += _apply_history_boosts(hook, history_patterns)

    # Type-specific bonus from hook_templates if available
    if idea_type:
        try:
            from utils.hook_templates import get_type_score_bonuses
            for signal, bonus in get_type_score_bonuses(idea_type):
                if signal in h:
                    composite += min(bonus, 1.0)  # cap each bonus at 1.0
        except ImportError:
            pass

    return round(max(0.0, min(10.0, composite)), 1)


def _apply_history_boosts(hook: str, patterns: dict) -> float:
    """
    Applies learned history boosts based on detected features.
    Returns total boost (0.0 - 2.0).
    """
    h     = hook.lower()
    words = hook.split()
    boost = 0.0

    if patterns.get("viewer_first") and re.search(r"^(tu |ton |you |your )", h):
        boost += patterns["viewer_first"]
    if patterns.get("has_number") and re.search(r"\d+", h):
        boost += patterns["has_number"]
    if patterns.get("has_contrast") and ("→" in hook or "->" in hook):
        boost += patterns["has_contrast"]
    if patterns.get("is_concise") and len(words) <= 6:
        boost += patterns["is_concise"]
    if patterns.get("loss_driven") and any(w in h for w in ["perds", "fuit", "lose", "waste"]):
        boost += patterns["loss_driven"]
    if patterns.get("money_anchor") and any(kw in h for kw in ["chf", "€", "$", "argent", "money"]):
        boost += patterns["money_anchor"]

    # Pattern-type boost
    detected_pattern = classify_hook_pattern(hook)
    pt_key = f"pattern_{detected_pattern}"
    if pt_key in patterns:
        boost += patterns[pt_key]

    return round(min(2.0, boost), 1)


# ===========================================================================
# SECTION 8  --  HISTORY / LEARNING LAYER
# ===========================================================================

_HISTORY_PATH = Path("assets/hook_history.json")


def load_history(history_path: Optional[str] = None) -> list[dict]:
    """
    Loads hook performance history from JSON.
    Format: {"hooks": [{"text", "views", "likes", "comments", "saves", ...}]}
    """
    if _HAS_V1:
        try:
            return _load_history_v1(history_path)
        except Exception:
            pass

    p = Path(history_path) if history_path else _HISTORY_PATH
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("hooks", [])
    except Exception:
        return []


def performance_score(item: dict) -> float:
    """
    Engagement score for a hook history entry.
    Saves > comments > likes > views (intent hierarchy).
    """
    views    = float(item.get("views",    0) or 0)
    likes    = float(item.get("likes",    0) or 0)
    comments = float(item.get("comments", 0) or 0)
    saves    = float(item.get("saves",    0) or 0)
    return saves * 5.0 + comments * 4.0 + likes * 2.0 + views * 0.1


def extract_winning_patterns(history: list[dict]) -> dict:
    """
    Analyzes top-performing hooks to find features that correlate with success.

    Method:
    - Compare feature prevalence in top third vs bottom third
    - A feature is "winning" if it appears in > 40% of top hooks
      and is overrepresented vs the full set (lift > 1.2)

    Returns: {"feature_name": boost_value}  e.g. {"viewer_first": 0.6, "has_number": 0.4}
    """
    if len(history) < 3:
        return {}

    sorted_h = sorted(history, key=performance_score, reverse=True)
    n        = len(sorted_h)
    top_n    = max(3, n // 3)
    top      = sorted_h[:top_n]

    def _features(hk: dict) -> set[str]:
        text  = hk.get("text", "")
        h_low = text.lower()
        words = text.split()
        feats: set[str] = set()

        if re.search(r"^(tu |ton |you |your )", h_low):
            feats.add("viewer_first")
        if re.search(r"\d+", h_low):
            feats.add("has_number")
        if "→" in text or "->" in text:
            feats.add("has_contrast")
        if len(words) <= 6:
            feats.add("is_concise")
        if any(w in h_low for w in ["perds", "perd", "lose", "losing", "fuit", "waste"]):
            feats.add("loss_driven")
        if any(kw in h_low for kw in ["chf", "€", "$", "argent", "money"]):
            feats.add("money_anchor")

        pt = hk.get("pattern_type") or classify_hook_pattern(text)
        if pt and pt != "generic":
            feats.add(f"pattern_{pt}")

        return feats

    # Count features in top vs all
    top_counts: dict[str, int] = {}
    all_counts: dict[str, int] = {}

    for hk in sorted_h:
        for f in _features(hk):
            all_counts[f] = all_counts.get(f, 0) + 1

    for hk in top:
        for f in _features(hk):
            top_counts[f] = top_counts.get(f, 0) + 1

    boosts: dict[str, float] = {}
    for feat, tc in top_counts.items():
        ac      = all_counts.get(feat, 1)
        top_rate = tc / top_n
        all_rate = ac / n
        lift     = top_rate / max(all_rate, 0.01)

        if top_rate >= 0.40 and lift >= 1.2:
            boost = round(min(1.0, (lift - 1.0) * 0.4), 1)
            if boost > 0:
                boosts[feat] = boost

    return boosts


def boost_patterns_from_history(
    hooks: list[dict],
    winning_patterns: dict,
) -> list[dict]:
    """
    Enriches hook dicts with history_boost based on detected winning features.
    Modifies score in-place (adds boost).
    """
    if not winning_patterns:
        return hooks

    boosted = []
    for hk in hooks:
        b = _apply_history_boosts(hk.get("text", ""), winning_patterns)
        boosted.append({
            **hk,
            "history_boost": b,
            "score": round(min(10.0, hk.get("score", 0.0) + b), 1),
        })
    return boosted


# ===========================================================================
# SECTION 9  --  REWRITE ENGINE V3
# ===========================================================================

def rewrite_hook(hook: str, strategy: str, language: str = "fr") -> str:
    """
    Rewrites a hook using one of 9 local strategies. No API needed.

    Strategies:
      convert_to_user_focus  -- outil-first -> viewer-first
      remove_tool_first      -- strip tool name prefix
      add_number             -- inject a concrete number if absent
      shorten                -- trim to 6 most impactful words
      add_contrast           -- add before->after structure
      make_more_concrete     -- replace vague words with concrete ones
      make_more_natural      -- remove corporate/copywriter tone
      simplify_language      -- shorten complex words/phrases
      strengthen_emotion     -- add loss/gain framing
    """
    h = hook.strip()
    h_low = h.lower()
    words = h.split()

    if strategy == "convert_to_user_focus":
        # Don't rewrite contrast/transformation hooks (already strong)
        if "\u2192" in h or "->" in h:
            return h
        # Don't prepend "Tu" to first-person hooks (j'ai, j'utilise, mon, ...)
        if re.search(r"^(j\'|j |mon |ma |mes |j\'ai|j\'utilise|j\'ai )", h_low):
            return h
        if is_tool_first(h):
            t = re.search(r"(\d+\s*(?:h|min|sec|heures?|minutes?))", h_low)
            if t:
                if language == "en":
                    return f"You're wasting {t.group(1)} on this"
                return f"Tu perds {t.group(1)} a la main"
            if language == "en":
                return "You're still doing this manually"
            return "Tu fais encore ca a la main"
        # Force "Tu" only for tool-named or noun-led hooks (not numbers, not prompts)
        if not re.search(r"^(tu |ton |you |your )", h_low):
            # Skip: starts with number, or first-person pattern, or prompt words
            if re.search(r"^\d", h) or re.search(r"^(le |la |les |mon |ma |mes |un |une )", h_low):
                return h  # don't reframe -- already a valid hook structure
            if language == "en":
                h = re.sub(r"^(this|the) ", "Your ", h, flags=re.IGNORECASE)
                if not h.lower().startswith(("you", "your")):
                    h = "You " + h[0].lower() + h[1:]
            else:
                h = re.sub(r"^(cette|ce|cet)\s+\w+\s+te\s+", "Tu ", h, flags=re.IGNORECASE)
                if not h.lower().startswith("tu"):
                    h = "Tu " + h[0].lower() + h[1:]
        return h

    elif strategy == "remove_tool_first":
        for prefix in _TOOL_FIRST_PREFIXES:
            if h_low.startswith(prefix):
                rest = h[len(prefix):].strip()
                verb_match = re.match(r"(fait|does|fait|remplace|replaces|analyse|analyzes)\s+", rest.lower())
                if verb_match:
                    rest = rest[verb_match.end():]
                if rest:
                    if language == "en":
                        return f"You can now {rest.lower()}"
                    return f"Tu peux maintenant {rest.lower()}"
        return h

    elif strategy == "add_number":
        if not re.search(r"\d+", h):
            if language == "en":
                if any(w in h_low for w in ["time", "hours", "minutes", "week"]):
                    return h.rstrip(". ") + " (30 min)"
                if any(w in h_low for w in ["money", "budget", "spending"]):
                    return h.rstrip(". ") + " ($400)"
            else:
                if any(w in h_low for w in ["temps", "heure", "minute", "semaine"]):
                    return h.rstrip(". ") + " (30 min)"
                if any(w in h_low for w in ["argent", "budget", "depenses"]):
                    return h.rstrip(". ") + " (400€)"
        return h

    elif strategy == "shorten":
        if len(words) > 7:
            fr_stop_end = {"de", "du", "la", "le", "sur", "pour", "en", "et",
                           "the", "of", "for", "on", "and", "in"}
            trimmed = words[:7]
            while trimmed and trimmed[-1].lower() in fr_stop_end:
                trimmed = trimmed[:-1]
            return " ".join(trimmed) if trimmed else " ".join(words[:6])
        return h

    elif strategy == "add_contrast":
        if "→" not in h and "->" not in h and "avant" not in h_low:
            if len(words) <= 6:
                if language == "en":
                    return f"Before: {h} -> now: 2 min"
                return f"Avant : {h} -> maintenant : 2 min"
        return h

    elif strategy == "make_more_concrete":
        replacements_fr = [
            (r"\bbeaucoup de temps\b",    "2 heures"),
            (r"\btrop de temps\b",        "45 minutes"),
            (r"\bde l'argent\b",          "400€"),
            (r"\bdes ressources\b",       "du temps"),
        ]
        replacements_en = [
            (r"\ba lot of time\b",        "2 hours"),
            (r"\btoo much time\b",        "45 minutes"),
            (r"\bmoney\b",                "$400"),
        ]
        reps = replacements_en if language == "en" else replacements_fr
        for pattern, repl in reps:
            h = re.sub(pattern, repl, h, flags=re.IGNORECASE)
        return h

    elif strategy == "make_more_natural":
        # Remove corporate / copywriter phrases
        patterns_fr = [
            (r"\bpour pouvoir\b", "pour"),
            (r"\bafin de\b",      "pour"),
            (r"\boptimiser\b",    "ameliorer"),
            (r"\blevier\b",       "outil"),
            (r"\bsynergie\b",     "truc"),
        ]
        patterns_en = [
            (r"\bin order to\b",      "to"),
            (r"\bleverage\b",         "use"),
            (r"\boptimize\b",         "improve"),
            (r"\bsynergy\b",          "thing"),
        ]
        reps = patterns_en if language == "en" else patterns_fr
        for pattern, repl in reps:
            h = re.sub(pattern, repl, h, flags=re.IGNORECASE)
        return h.strip()

    elif strategy == "simplify_language":
        if len(words) > 8:
            h = " ".join(words[:7])
        h = re.sub(r"\bqui te permet de\b", "pour", h, flags=re.IGNORECASE)
        h = re.sub(r"\bqui vous permet de\b", "pour", h, flags=re.IGNORECASE)
        h = re.sub(r"\bthat allows you to\b", "to", h, flags=re.IGNORECASE)
        return h.strip()

    elif strategy == "strengthen_emotion":
        # Guard: don't rewrite if already strong
        has_contrast  = "\u2192" in h or "->" in h
        has_loss      = any(w in h_low for w in ["perds", "fuit", "lose", "waste",
                                                   "inutile", "useless", "pour rien"])
        viewer_first  = bool(re.search(r"^(tu |ton )", h_low))
        if has_contrast or has_loss or viewer_first:
            return h  # already emotionally strong or viewer-first
        # Rewrite: extract core topic, wrap in loss framing
        core = _extract_topic(h)
        if not core or core == "ca":
            core = " ".join(h.split()[:3]).lower()  # fallback: first 3 words
        if language == "en":
            return f"You waste time on {core}"
        return f"Tu perds du temps sur {core}" 

    return h


def rewrite_until_strong(
    hook_data:    dict,
    idea_type:    str    = "",
    language:     str    = "fr",
    threshold:    float  = 6.5,
    max_iter:     int    = 3,
    history_patterns: dict = None,
) -> dict:
    """
    Iteratively rewrites a hook until score >= threshold or max_iter reached.
    Tries strategies in priority order, keeps best result at each step.
    """
    original = hook_data.get("text", "")
    current  = dict(hook_data)
    angle    = hook_data.get("angle", "")

    h_low_check = hook_data.get("text", "").lower()
    _STRATEGY_ORDER = [
        "convert_to_user_focus",
        "remove_tool_first",
        "shorten",
        "add_number",
        "make_more_concrete",
        # strengthen_emotion only if no contrast already present
        *(["strengthen_emotion"] if ("\u2192" not in hook_data.get("text","") and
                                     "->" not in hook_data.get("text","")) else []),
        "make_more_natural",
        "simplify_language",
        "add_contrast",
    ]

    for iteration in range(max_iter):
        if current["score"] >= threshold:
            break

        best_text  = current["text"]
        best_score = current["score"]
        best_strat = None

        for strategy in _STRATEGY_ORDER:
            candidate = rewrite_hook(current["text"], strategy, language)
            if candidate == current["text"]:
                continue
            new_score = score_hook_v3(
                candidate, idea_type, angle, language, history_patterns
            )
            if new_score > best_score:
                best_score = new_score
                best_text  = candidate
                best_strat = strategy

        if best_text == current["text"]:
            break  # no strategy improved it

        current = {
            **current,
            "text":            best_text,
            "score":           best_score,
            "was_rewritten":   True,
            "rewrite_strategy": best_strat,
            "rewrite_iter":    iteration + 1,
        }

    current.setdefault("original_text",    original)
    current.setdefault("was_rewritten",    current["text"] != original)
    current.setdefault("rewrite_strategy", None)
    return current


# ===========================================================================
# SECTION 10  --  TOP SELECTION + FINAL VALIDATOR
# ===========================================================================

def select_top_hooks(hooks: list[dict], n: int = 5) -> list[dict]:
    """
    Returns top n hooks by score with semantic diversity.
    Avoids hooks starting with the same 3 words.
    """
    ranked = sorted(hooks, key=lambda x: x.get("score", 0), reverse=True)
    selected: list[dict] = []
    seen_starts: set[str] = set()

    for hk in ranked:
        start = " ".join(hk["text"].lower().split()[:3])
        if start not in seen_starts:
            seen_starts.add(start)
            selected.append(hk)
        if len(selected) >= n:
            break

    # Fill remaining slots without diversity constraint
    if len(selected) < n:
        for hk in ranked:
            if hk not in selected:
                selected.append(hk)
            if len(selected) >= n:
                break

    return selected[:n]


def choose_best_hook(top_hooks: list[dict], language: str = "fr") -> dict:
    """
    Final selection from top hooks.
    Uses a readability-weighted tiebreak over the score.
    """
    if not top_hooks:
        return {"text": "", "score": 0.0}
    if len(top_hooks) == 1:
        return top_hooks[0]

    def _final_rank(hk: dict) -> float:
        text  = hk.get("text", "")
        words = text.split()
        h_low = text.lower()
        rank  = hk.get("score", 0.0)

        # Tiebreak bonuses (capped at 0.3 total so they don't override a real score gap)
        bonus = 0.0
        if re.search(r"^(tu |ton |you |your )", h_low):     bonus += 0.2
        if len(words) <= 5:                                  bonus += 0.2
        elif len(words) <= 7:                                bonus += 0.1
        if re.search(r"\d+", text):                          bonus += 0.1
        if "→" in text or "->" in text:                      bonus += 0.1
        if "," in text:                                      bonus -= 0.1

        rank += min(bonus, 0.3)  # cap: tiebreak can't override a real score difference
        return rank

    return sorted(top_hooks, key=_final_rank, reverse=True)[0]


def validate_hook_final(
    hook:      str,
    idea_type: str = "",
    language:  str = "fr",
) -> dict:
    """
    Validates a hook before returning it as publish-ready.
    Returns: {
        "is_publishable": bool,
        "score": float,
        "issues": list[str],
        "checks": dict,      # individual check results
    }
    """
    h     = hook.strip()
    h_low = h.lower()
    words = h.split()
    issues: list[str] = []
    checks: dict[str, bool] = {}

    # 1. Instantly understandable?
    checks["instantly_clear"] = len(words) <= 9
    if not checks["instantly_clear"]:
        issues.append(f"Too long: {len(words)} words (max 9)")

    # 2. Fragment guard
    checks["not_fragment"] = len(words) >= 3
    if not checks["not_fragment"]:
        issues.append("Too short: min 3 words")

    # 3. Speaks to a human?
    checks["human_address"] = bool(re.search(r"\b(tu |ton |tes |you |your )", h_low))
    # Note: not required for prompt_reveal / tool_demo / comparison -- viewer-first optional

    # 4. Not tool-first when inappropriate
    checks["no_bad_tool_first"] = not (
        is_tool_first(h) and idea_type not in _TOOL_OK_TYPES
    )
    if not checks["no_bad_tool_first"]:
        issues.append("Tool-first hook: address the viewer instead")

    # 5. Not motivational
    checks["not_motivational"] = not any(m in h_low for m in _MOTIVATIONAL)
    if not checks["not_motivational"]:
        issues.append("Motivational tone: replace with concrete benefit")

    # 6. Not abstract
    checks["not_abstract"] = not any(w in h_low for w in _ABSTRACT_WORDS_V3)
    if not checks["not_abstract"]:
        issues.append("Abstract language: use concrete phrasing")

    # 7. Has a strong signal (pain/gain/curiosity/contrast)
    strong = ["tu ", "ton ", "tes ", "you ", "your ", "perds", "fuit", "lose",
              "→", "->", "€", "$", "chf", "min", "sec", "cache", "hidden"]
    # For prompt_reveal, first-person authority signals are equally strong
    if idea_type == "prompt_reveal":
        strong = strong + ["prompt", "j'ai", "j'utilise", "i tested", "i use", "my prompt"]
    checks["has_strong_signal"] = len(words) <= 5 or any(s in h_low for s in strong)
    if not checks["has_strong_signal"]:
        issues.append("No strong signal: add loss, number, contrast, or viewer focus")

    # 8. Not dramatic/fake
    checks["not_dramatic"] = not re.search(
        r"\b(va transformer ta vie|va changer|incroyable|revolutionnaire)\b", h_low
    )
    if not checks["not_dramatic"]:
        issues.append("Dramatic/artificial tone")

    # 9. Not corporate
    checks["not_corporate"] = not re.search(
        r"\b(synergies?|leviers?|approche holistique|best practices|paradigme)\b", h_low
    )
    if not checks["not_corporate"]:
        issues.append("Corporate tone: rewrite in spoken language")

    # 10. No weak starter
    checks["no_weak_starter"] = not any(h_low.startswith(s) for s in _WEAK_STARTERS_V3)
    if not checks["no_weak_starter"]:
        issues.append("Weak starter (blog/tutorial style)")

    score = score_hook_v3(h, idea_type, language=language)
    is_pub = len(issues) == 0

    return {
        "is_publishable": is_pub,
        "score":          score,
        "issues":         issues,
        "checks":         checks,
    }


# ===========================================================================
# SECTION 11  --  PUBLIC API
# ===========================================================================

def generate_best_hook(
    idea:          str,
    language:      str           = "fr",
    idea_type:     Optional[str] = None,
    history_path:  Optional[str] = None,
    niche:         Optional[str] = None,
    audience:      Optional[str] = None,
) -> dict:
    """
    Main entry point for Hook Engine V3.
    Full 12-step pipeline: classify -> angles -> generate -> filter ->
    score -> history-boost -> rewrite -> select -> validate -> return.

    Returns:
    {
      "best_hook":             str,
      "best_score":            float,
      "top_hooks":             list[str],
      "top_hooks_detailed":    list[dict],
      "all_candidates":        list[str],
      "idea_type":             str,
      "idea_type_confidence":  float,
      "angles":                list[str],
      "winning_patterns":      dict,
      "language":              str,
      "validation":            dict,
      "meta":                  dict,
    }
    """

    # ---- Step 1: Classification -----------------------------------------
    clf         = classify_idea_type_with_confidence(idea)
    detected    = idea_type or clf["type"]
    confidence  = clf["confidence"]

    # ---- Step 2: Angles --------------------------------------------------
    angles         = generate_angles(idea, detected)
    dominant_angle = angles[0] if angles else "pain"

    # ---- Step 3: Generate candidates ------------------------------------
    candidates = generate_hook_candidates(idea, detected, angles, language)
    total_gen  = len(candidates)

    # ---- Step 4: Filter --------------------------------------------------
    filtered   = filter_bad_hooks(candidates, detected)
    after_filt = len(filtered)

    # ---- Step 5: Load history + extract winning patterns ----------------
    history          = load_history(history_path)
    winning_patterns = extract_winning_patterns(history)

    # ---- Step 6: Score all hooks ----------------------------------------
    scored = []
    for hk in filtered:
        s = score_hook_v3(
            hk["text"],
            idea_type        = detected,
            angle            = hk.get("angle", dominant_angle),
            language         = language,
            history_patterns = winning_patterns,
        )
        scored.append({**hk, "score": s})

    # ---- Step 7: History pattern boost ----------------------------------
    scored = boost_patterns_from_history(scored, winning_patterns)

    # ---- Step 8: Select top hooks (before rewrite) ----------------------
    top_5 = select_top_hooks(scored, n=5)

    # ---- Step 9: Rewrite weak hooks ------------------------------------
    rewrites = 0
    top_5_final = []
    for hk in top_5:
        if hk["score"] < 6.5:
            rewritten = rewrite_until_strong(
                hk, detected, language,
                threshold=6.5, max_iter=3,
                history_patterns=winning_patterns,
            )
            if rewritten.get("was_rewritten"):
                rewrites += 1
            top_5_final.append(rewritten)
        else:
            top_5_final.append({
                **hk,
                "was_rewritten":   False,
                "original_text":   hk["text"],
                "rewrite_strategy": None,
            })

    # ---- Step 10: Final selection ----------------------------------------
    best = choose_best_hook(top_5_final, language)

    # ---- Step 11: Validate + last-resort fix ----------------------------
    validation = validate_hook_final(best["text"], detected, language)

    if not validation["is_publishable"] and not validation["checks"].get("no_bad_tool_first", True):
        fixed     = rewrite_hook(best["text"], "convert_to_user_focus", language)
        fixed_val = validate_hook_final(fixed, detected, language)
        if fixed_val["is_publishable"] or len(fixed_val["issues"]) < len(validation["issues"]):
            best       = {**best, "text": fixed, "score": fixed_val["score"]}
            validation = fixed_val

    # ---- Step 12: Output ------------------------------------------------
    return {
        "best_hook":            best["text"],
        "best_score":           best.get("score", 0.0),
        "top_hooks":            [hk["text"] for hk in top_5_final],
        "top_hooks_detailed":   top_5_final,
        "all_candidates":       [hk["text"] for hk in filtered],
        "idea_type":            detected,
        "idea_type_confidence": confidence,
        "angles":               angles,
        "winning_patterns":     winning_patterns,
        "language":             language,
        "validation":           validation,
        "meta": {
            "total_generated":  total_gen,
            "after_filter":     after_filt,
            "rewrites_applied": rewrites,
            "history_size":     len(history),
        },
    }


# Alias for existing pipeline integration
def enrich_viral_script(sv: dict, idea: str, language: str = "fr") -> dict:
    """
    Drop-in helper for generate.py.
    Runs V3 pipeline and upgrades sv["best_hook"] if V3 scores higher.
    Adds sv["hook_engine_v3"] with full report.
    """
    idea_type = sv.get("idea_type", "")
    result    = generate_best_hook(idea, language=language,
                                   idea_type=idea_type or None)
    sv["hook_engine_v3"] = result

    current_score = sv.get("best_hook", {}).get("score", 0) or 0
    if result["best_score"] > current_score:
        sv["best_hook"] = {
            "text":   result["best_hook"],
            "score":  result["best_score"],
            "reason": "Hook Engine V3",
        }
        if sv.get("script"):
            sv["script"]["hook"] = result["best_hook"]

    return sv


# ===========================================================================
# SECTION 12  --  TEST RUNNER
# ===========================================================================

if __name__ == "__main__":
    import io, sys
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    SEP  = "-" * 62
    SEP2 = "=" * 62

    TEST_CASES = [
        ("Meal planning de la semaine genere en 90 secondes.", "fr"),
        ("Mon rapport de 2h -> 8 minutes. Voila le systeme.",  "fr"),
        ("Le prompt exact que j'utilise pour mes emails clients.", "fr"),
        ("VLOOKUP est mort. Voila ce qui le remplace.",         "fr"),
        ("ChatGPT a analyse mes depenses du mois. Ce qu'il a trouve m'a choque.", "fr"),
        ("Ton travail de 40h/semaine peut se faire en 20h. Preuve.", "fr"),
        ("Mon plus gros fail du mois.",                        "fr"),
        ("Demande d'augmentation : +CHF 600.",                 "fr"),
        ("3 mesures DAX que tout analyste devrait avoir.",     "fr"),
        ("Ce Reel a ete cree avec ce prompt. Voila lequel.",   "fr"),
    ]

    print(SEP2)
    print("  HOOK ENGINE V3 -- Test Suite (10 ideas)")
    print(SEP2)

    for idx, (idea, lang) in enumerate(TEST_CASES, 1):
        result = generate_best_hook(idea, language=lang)

        pub_flag = "OK" if result["validation"]["is_publishable"] else "!!"
        score    = result["best_score"]

        print()
        print(f"[{idx:02d}] {idea[:55]}")
        print(f"     Type  : {result['idea_type']}  (conf {result['idea_type_confidence']:.0%})")
        print(f"     Hooks : {result['meta']['total_generated']} gen | "
              f"{result['meta']['after_filter']} filtered | "
              f"{result['meta']['rewrites_applied']} rewritten")
        print(f"     BEST  [{score:.1f}] [{pub_flag}] : {result['best_hook']}")

        if not result["validation"]["is_publishable"]:
            for issue in result["validation"]["issues"]:
                print(f"            ! {issue}")

        # Show top 3 briefly
        for i, hk in enumerate(result["top_hooks_detailed"][:3], 1):
            rewr = " [rw]" if hk.get("was_rewritten") else ""
            print(f"       {i}. [{hk['score']:.1f}] {hk['text']}{rewr}")

    # Sub-scorer demo
    print()
    print(SEP)
    print("  Sub-scorer breakdown demo")
    print(SEP)
    demo_hooks = [
        ("Tu perds 30 min chaque dimanche",              "fr", "budget_finance", "loss"),
        ("Ce prompt fait ton meal planning en 90 sec",    "fr", "prompt_reveal",  "shortcut"),
        ("2h -> 8 minutes",                               "fr", "before_after_time","time_gain"),
        ("You waste 2 hours on this every week",          "en", "before_after_time","pain"),
        ("Discover how to optimize your workflow",         "en", "data_workflow",  "shortcut"),
    ]
    header = f"  {'Hook':<42} Rd   Em   Mb   Pt  Total"
    print(header)
    print("  " + "-" * 58)
    for hook, lang, itype, angle in demo_hooks:
        rd  = score_readability(hook, lang)
        em  = score_emotional_trigger(hook, itype)
        mob = score_mobile_clarity(hook)
        pt  = score_pattern_match(hook, itype, angle)
        tot = score_hook_v3(hook, itype, angle, lang)
        print(f"  {hook[:42]:<42} {rd:3.0f}  {em:3.0f}  {mob:3.0f}  {pt:3.0f}  {tot:.1f}")

    # Rewrite demo
    print()
    print(SEP)
    print("  Rewrite Engine V3 demo")
    print(SEP)
    bad_hooks = [
        ("Ce prompt fait ton meal planning en 90 sec", "fr", "before_after_time"),
        ("ChatGPT va transformer ta vie professionnelle", "fr", "tool_demo"),
        ("Discover how to leverage AI for your workflow", "en", "data_workflow"),
    ]
    for hook, lang, itype in bad_hooks:
        start_score = score_hook_v3(hook, itype, language=lang)
        result = rewrite_until_strong(
            {"text": hook, "score": start_score, "angle": "pain"},
            itype, lang, threshold=6.5, max_iter=3
        )
        strat = result.get("rewrite_strategy", "none")
        print(f"  IN  [{start_score:.1f}] {hook}")
        print(f"  OUT [{result['score']:.1f}] {result['text']}  (strat: {strat})")
        print()
