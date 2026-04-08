# -*- coding: utf-8 -*-
"""
utils/quality_validator.py — Couche de validation et auto-correction locale.

Pipeline post-génération (100% local, sans appel API) :
  1. validate_hook()          — score + détection des faiblesses
  2. validate_cta()           — score + détection CTA faible
  3. validate_script()        — validation section par section
  4. validate_overlay_lines() — validation des lignes overlay
  5. auto_fix_cta()           — correction automatique du CTA
  6. auto_fix_overlay_lines() — nettoyage des lignes trop longues
  7. post_process_script()    — orchestrateur principal (appelé par generate.py)

Aucune dépendance API. Résultats déterministes et explicables.
"""
from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────────────────────
# Seuils
# ─────────────────────────────────────────────────────────────────────────────

MAX_HOOK_WORDS      = 10
MAX_LINE_WORDS      = 8   # overlay + script lines
MAX_CTA_WORDS       = 8
MIN_PUBLISHABLE_SCORE = 5.5

# ─────────────────────────────────────────────────────────────────────────────
# Patterns de détection
# ─────────────────────────────────────────────────────────────────────────────

_WEAK_HOOK_PATTERNS: list[str] = [
    "le problème n'est pas", "the problem is not",
    "la solution est", "the solution is",
    "voici comment", "here's how to",
    "découvrez", "learn how",
    "optimiser votre", "optimize your",
    "améliorer vos", "improve your",
    "booster votre", "boost your",
    "maximiser", "maximize",
    "le problème c'est que", "the problem is that",
    "dans cette vidéo", "in this video",
    "dans ce reel", "in this reel",
]

_WEAK_CTA_PATTERNS: list[str] = [
    "suis-moi", "suivez-moi", "follow me",
    "prouve que t'es", "abonne-toi pour",
    "partage si", "like si tu", "n'oublie pas de",
    "pour plus de contenu", "for more content",
    "clique sur le lien", "click the link",
    "va voir mon", "check out my",
    "rejoins ma", "join my",
    "likez", "partagez", "commentez si vous",
]

_STRONG_CTA_PATTERNS: list[str] = [
    "commente", "écris", "comment ", "type ",
    "↓", "⬇", "prompt", "guide", "script",
    "budget", "système", "template", "démo", "demo",
    "oui", "yes", "non", "no", "suite", "résultat",
    "réponse", "answer",
]

_AI_SOUNDING_WORDS: list[str] = [
    "fascinant", "incroyable", "révolutionnaire", "transformateur",
    "puissant outil", "extraordinaire", "paradigme", "disruptif",
    "fascinating", "incredible", "revolutionary", "transformative",
    "extraordinary", "paradigm", "disruptive", "groundbreaking",
    "game-changing", "game changer", "next level",
    # Over-dramatic
    "coupe sans pitié", "refuses to", "au-delà de", "sans compromis",
    "le problème n'est pas", "la vérité profonde",
    "truth is", "deep truth", "wake up",
]

_MOTIVATIONAL_WORDS: list[str] = [
    "prouve que t'es prêt", "prove you're ready", "tu es capable",
    "you can do it", "crois en toi", "believe in yourself",
    "commence maintenant", "start now", "transforme ta vie",
    "transform your life", "le moment est venu", "the time is now",
]

_LONG_QUESTION_THRESHOLD = 7  # mots au-delà desquels une question est "faible"


# ─────────────────────────────────────────────────────────────────────────────
# Validation du hook
# ─────────────────────────────────────────────────────────────────────────────

def validate_hook(hook: str, idea_type: str = "") -> dict:
    """
    Valide un hook.

    Retourne :
    {
        "score":         float,   # 0.0–10.0
        "issues":        list,    # problèmes détectés
        "is_publishable": bool,   # score >= seuil ET aucun problème critique
    }
    """
    issues: list[str] = []
    score = 10.0
    h = hook.strip().lower()
    words = h.split()

    # Longueur
    if len(words) > MAX_HOOK_WORDS:
        issues.append(f"Trop long : {len(words)} mots (max {MAX_HOOK_WORDS})")
        score -= 2.5

    if len(words) < 2:
        issues.append("Hook vide ou trop court")
        score -= 5.0

    # Patterns faibles
    for pattern in _WEAK_HOOK_PATTERNS:
        if pattern in h:
            issues.append(f"Formulation faible : «{pattern}»")
            score -= 3.0

    # Mots qui sonnent IA/copywriter
    for word in _AI_SOUNDING_WORDS:
        if word in h:
            issues.append(f"Sonne IA/copywriter : «{word}»")
            score -= 2.0

    # Ton motivationnel
    for word in _MOTIVATIONAL_WORDS:
        if word in h:
            issues.append(f"Ton motivationnel : «{word}»")
            score -= 2.0

    # Question longue (style blog)
    if h.endswith("?") and len(words) > _LONG_QUESTION_THRESHOLD:
        issues.append(f"Question trop longue ({len(words)} mots) — risque de scroll-skip")
        score -= 1.5

    # Vérification USER-FIRST
    try:
        from utils.hook_templates import USER_FIRST, TOOL_FIRST_STARTERS
        if idea_type and USER_FIRST.get(idea_type, False):
            for starter in TOOL_FIRST_STARTERS:
                if h.startswith(starter.lower()):
                    issues.append(f"Hook outil-first pour un type viewer-first : «{starter}»")
                    score -= 2.0
                    break
    except ImportError:
        pass

    # Aucun signal fort du tout
    _strong_signals = [
        "tu ", "ton ", "tes ", "you ", "your ",
        "perds", "fuis", "fuite", "lose", "leak",
        "→", "erreur", "mistake", "faux", "wrong",
        "chf", "€", "$", "sans le voir",
        "j'ai testé", "i tested", "le prompt", "this prompt",
    ]
    has_signal = any(sig in h for sig in _strong_signals) or re.search(r"\d+", h)
    if not has_signal and len(words) > 4:
        issues.append("Aucun signal fort (pas de perte, chiffre, erreur ou interpellation)")
        score -= 1.5

    return {
        "score": round(max(0.0, min(10.0, score)), 1),
        "issues": issues,
        "is_publishable": score >= MIN_PUBLISHABLE_SCORE and len(issues) == 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation du CTA
# ─────────────────────────────────────────────────────────────────────────────

def validate_cta(cta: str) -> dict:
    """
    Valide un CTA.

    Retourne :
    {
        "score":     float,
        "issues":    list,
        "is_strong": bool,
    }
    """
    issues: list[str] = []
    score = 5.0  # neutre par défaut
    c = cta.strip().lower()
    words = c.split()

    # Longueur
    if len(words) > MAX_CTA_WORDS:
        issues.append(f"CTA trop long : {len(words)} mots (max {MAX_CTA_WORDS})")
        score -= 2.0

    if not c:
        issues.append("CTA vide")
        return {"score": 0.0, "issues": issues, "is_strong": False}

    # Patterns faibles
    for pattern in _WEAK_CTA_PATTERNS:
        if pattern in c:
            issues.append(f"CTA faible : «{pattern}»")
            score -= 3.0

    # Patterns forts
    for pattern in _STRONG_CTA_PATTERNS:
        if pattern in c:
            score += 3.0
            break

    # Vérifie la structure "Verbe MOT" (idéal)
    if re.match(r"^(commente|écris|comment|type|répondre|write)\s+\w+", c):
        score += 2.0

    return {
        "score": round(min(10.0, max(0.0, score)), 1),
        "issues": issues,
        "is_strong": score >= 6.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation du script complet
# ─────────────────────────────────────────────────────────────────────────────

def validate_script(script: dict, idea_type: str = "") -> dict:
    """
    Valide toutes les sections d'un script.

    Retourne :
    {
        "issues_by_section": dict,   # {section: [issues]}
        "all_issues":        list,   # liste plate
        "is_publishable":    bool,
        "section_scores":    dict,   # {section: score}
    }
    """
    issues_by_section: dict[str, list[str]] = {}
    section_scores: dict[str, float] = {}

    for key in ("hook", "pain", "shift", "solution", "result", "cta"):
        text = script.get(key, "")
        if not text:
            issues_by_section[key] = ["Vide"]
            section_scores[key] = 0.0
            continue

        words = text.strip().split()
        section_issues: list[str] = []
        score = 10.0

        # Longueur
        if len(words) > MAX_LINE_WORDS:
            section_issues.append(f"Trop long : {len(words)} mots (max {MAX_LINE_WORDS})")
            score -= 2.0

        # Mots IA
        tl = text.lower()
        for word in _AI_SOUNDING_WORDS:
            if word in tl:
                section_issues.append(f"Sonne IA : «{word}»")
                score -= 2.0

        # Motivationnel
        for word in _MOTIVATIONAL_WORDS:
            if word in tl:
                section_issues.append(f"Ton motivationnel : «{word}»")
                score -= 2.0

        # CTA spécifique
        if key == "cta":
            cta_v = validate_cta(text)
            section_issues.extend(cta_v["issues"])
            score = (score + cta_v["score"]) / 2.0

        # Section shift : doit avoir un retournement
        if key == "shift" and len(words) > 1:
            _shift_signals = [
                "mais", "sauf que", "pourtant", "en fait", "jusqu'au jour",
                "until", "but", "except", "actually", "then", "puis",
                "et là", "et pourtant", "j'ai trouvé", "i found",
            ]
            if not any(sig in tl for sig in _shift_signals):
                section_issues.append("Shift trop neutre : manque de retournement")
                score -= 1.0

        # Section result : doit être concret/chiffré
        if key == "result" and len(words) > 1:
            if not re.search(r"\d+", tl) and not any(
                sig in tl for sig in ["maintenant", "now", "plus jamais",
                                       "fini", "done", "today", "aujourd'hui"]
            ):
                section_issues.append("Résultat trop vague : pas de chiffre ou d'ancrage concret")
                score -= 1.0

        issues_by_section[key] = section_issues
        section_scores[key] = round(max(0.0, min(10.0, score)), 1)

    all_issues = [
        f"{k}: {'; '.join(v)}"
        for k, v in issues_by_section.items() if v
    ]

    return {
        "issues_by_section": issues_by_section,
        "all_issues": all_issues,
        "is_publishable": len(all_issues) == 0,
        "section_scores": section_scores,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation des overlay lines
# ─────────────────────────────────────────────────────────────────────────────

def validate_overlay_lines(lines: list[str]) -> dict:
    """
    Valide les lignes overlay.

    Retourne :
    {
        "issues":      list,
        "is_ok":       bool,
        "line_checks": list[dict],
    }
    """
    all_issues: list[str] = []
    line_checks: list[dict] = []

    for i, line in enumerate(lines, 1):
        line_issues: list[str] = []
        words = line.strip().split()

        if len(words) > MAX_LINE_WORDS:
            line_issues.append(f"Trop long : {len(words)} mots")
        if len(words) < 1:
            line_issues.append("Ligne vide")

        for word in _AI_SOUNDING_WORDS:
            if word in line.lower():
                line_issues.append(f"Sonne IA : «{word}»")

        line_checks.append({
            "index": i,
            "text": line,
            "issues": line_issues,
            "ok": len(line_issues) == 0,
        })
        if line_issues:
            all_issues.extend(f"Ligne {i}: {iss}" for iss in line_issues)

    return {
        "issues": all_issues,
        "is_ok": len(all_issues) == 0,
        "line_checks": line_checks,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auto-fix
# ─────────────────────────────────────────────────────────────────────────────

def auto_fix_cta(cta: str, idea_type: str = "", lang: str = "fr") -> str:
    """
    Corrige un CTA faible localement.
    Si le CTA est déjà fort → retourne tel quel.
    Sinon → retourne le CTA idéal pour le type.
    """
    validation = validate_cta(cta)
    if validation["is_strong"]:
        return cta

    try:
        from utils.hook_templates import get_cta_for_type
        return get_cta_for_type(idea_type, lang)
    except ImportError:
        return "Commente OUI" if lang != "en" else "Comment YES"


def auto_fix_overlay_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    """
    Corrige les lignes overlay trop longues par troncature intelligente.
    Retourne (lignes_nettoyées, liste_des_corrections_appliquées).
    """
    fixed: list[str] = []
    corrections: list[str] = []

    for line in lines:
        words = line.strip().split()
        if len(words) > MAX_LINE_WORDS:
            truncated = " ".join(words[:MAX_LINE_WORDS])
            corrections.append(f"Overlay tronquée : «{line}» → «{truncated}»")
            fixed.append(truncated)
        else:
            fixed.append(line)

    return fixed, corrections


def _flag_tool_first_hook(hook: str, idea_type: str) -> str | None:
    """
    Si le hook est outil-first pour un type viewer-first, retourne un avertissement.
    Sinon retourne None.
    """
    try:
        from utils.hook_templates import is_tool_first
        if is_tool_first(hook, idea_type):
            return (
                f"Hook outil-first détecté pour le type viewer-first «{idea_type}» : "
                f"«{hook}». Conseil : commencer par «Tu/Ton/Tes»."
            )
    except ImportError:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Post-processor principal
# ─────────────────────────────────────────────────────────────────────────────

def post_process_script(result: dict, lang: str = "fr") -> dict:
    """
    Orchestrateur principal : valide et corrige automatiquement le résultat
    retourné par generate_viral_script().

    Opérations (toutes locales, sans appel API) :
      1. Auto-fix du CTA dans script + cta_optimized
      2. Auto-fix des overlay lines trop longues
      3. Flag du hook outil-first si viewer-first attendu
      4. Validation du script section par section

    Ajoute dans le résultat :
      result["_quality"] = {
          "hook_validation":    dict,
          "script_validation":  dict,
          "cta_validation":     dict,
          "overlay_validation": dict,
          "fixes_applied":      list,
          "warnings":           list,
      }

    Retourne le résultat modifié (même dict, modifié en place).
    """
    idea_type = result.get("idea_type", "")
    script    = result.get("script", {})
    fixes:    list[str] = []
    warnings: list[str] = []

    # ── 1. Fix CTA dans le script ─────────────────────────────────────────────
    cta_orig = script.get("cta", "")
    cta_val  = validate_cta(cta_orig)
    if not cta_val["is_strong"]:
        fixed_cta = auto_fix_cta(cta_orig, idea_type, lang)
        result["script"] = {**script, "cta": fixed_cta}
        script = result["script"]
        if fixed_cta != cta_orig:
            fixes.append(f"CTA script : «{cta_orig}» → «{fixed_cta}»")

    # ── 2. Fix cta_optimized ──────────────────────────────────────────────────
    cta_opt_orig = result.get("cta_optimized", "")
    if cta_opt_orig:
        cta_opt_val = validate_cta(cta_opt_orig)
        if not cta_opt_val["is_strong"]:
            fixed_cta_opt = auto_fix_cta(cta_opt_orig, idea_type, lang)
            if fixed_cta_opt != cta_opt_orig:
                result["cta_optimized"] = fixed_cta_opt
                fixes.append(f"CTA optimized : «{cta_opt_orig}» → «{fixed_cta_opt}»")

    # ── 3. Fix overlay lines ──────────────────────────────────────────────────
    overlay = result.get("overlay_lines", [])
    if overlay:
        cleaned_overlay, overlay_fixes = auto_fix_overlay_lines(overlay)
        result["overlay_lines"] = cleaned_overlay
        fixes.extend(overlay_fixes)

    # ── 4. Flag hook outil-first ──────────────────────────────────────────────
    best_hook = result.get("best_hook", {}).get("text", "")
    if best_hook:
        tool_first_warn = _flag_tool_first_hook(best_hook, idea_type)
        if tool_first_warn:
            warnings.append(tool_first_warn)

    # ── 5. Validation qualité globale (debug/UI) ──────────────────────────────
    hook_val    = validate_hook(best_hook, idea_type)
    script_val  = validate_script(script, idea_type)
    overlay_val = validate_overlay_lines(result.get("overlay_lines", []))
    cta_final   = validate_cta(script.get("cta", ""))

    result["_quality"] = {
        "hook_validation":    hook_val,
        "script_validation":  script_val,
        "cta_validation":     cta_final,
        "overlay_validation": overlay_val,
        "fixes_applied":      fixes,
        "warnings":           warnings,
        "is_publishable":     (
            hook_val["score"] >= MIN_PUBLISHABLE_SCORE
            and script_val["is_publishable"]
            and cta_final["is_strong"]
        ),
    }

    return result
