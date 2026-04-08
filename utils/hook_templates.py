# -*- coding: utf-8 -*-
"""
utils/hook_templates.py — Règles type-spécifiques pour la génération de hooks.

Fournit :
- CTA_KEYWORDS    : mot-clé CTA par type ("Commente PROMPT", "Commente DAX"…)
- USER_FIRST      : flag viewer-centric (le hook doit parler au viewer, pas à l'outil)
- TYPE_SCORE_BONUSES : signaux de scoring bonus par type d'idée
- TOOL_FIRST_STARTERS : débuts de hook qui rendent un hook outil-centric
- get_cta_for_type()   : retourne le CTA idéal pour un type d'idée
- is_tool_first()      : détecte si un hook est outil-first
- rewrite_to_user_first() : réécriture locale basique sans API
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# CTA keywords par type
# "Commente {keyword}" ou "Écris {keyword}"
# ─────────────────────────────────────────────────────────────────────────────

CTA_KEYWORDS: dict[str, str] = {
    "before_after_time":      "SYSTÈME",
    "prompt_reveal":          "PROMPT",
    "tool_demo":              "DÉMO",
    "comparison":             "RÉSULTAT",
    "data_workflow":          "SCRIPT",
    "budget_finance":         "BUDGET",
    "career_work":            "TEMPLATE",
    "controversial_opinion":  "OUI",
    "build_in_public":        "SUITE",
    "storytelling_personal":  "SUITE",
    "educational_explainer":  "GUIDE",
    "reactive_reply":         "RÉPONSE",
}

# Version anglaise
CTA_KEYWORDS_EN: dict[str, str] = {
    "before_after_time":      "SYSTEM",
    "prompt_reveal":          "PROMPT",
    "tool_demo":              "DEMO",
    "comparison":             "RESULT",
    "data_workflow":          "SCRIPT",
    "budget_finance":         "BUDGET",
    "career_work":            "TEMPLATE",
    "controversial_opinion":  "YES",
    "build_in_public":        "UPDATE",
    "storytelling_personal":  "MORE",
    "educational_explainer":  "GUIDE",
    "reactive_reply":         "ANSWER",
}

# ─────────────────────────────────────────────────────────────────────────────
# USER-FIRST : le hook doit parler AU viewer (pas à l'outil)
# True  = hook viewer-centric obligatoire ("Tu perds", "Ton budget", "Tu fais")
# False = hook outil/créateur-first acceptable ("Le prompt exact", "J'ai testé")
# ─────────────────────────────────────────────────────────────────────────────

USER_FIRST: dict[str, bool] = {
    "before_after_time":      True,
    "prompt_reveal":          False,  # "Le prompt exact" = OK
    "tool_demo":              False,  # "J'ai testé" = OK
    "comparison":             False,  # "J'ai testé X vs Y" = OK
    "data_workflow":          True,   # "Tu fais encore ça à la main"
    "budget_finance":         True,   # "Tu perds CHF 400"
    "career_work":            True,   # "Ton job est à risque"
    "controversial_opinion":  True,   # "Tu crois que… Faux."
    "build_in_public":        False,  # "Semaine 1 : 0 vente" = OK
    "storytelling_personal":  False,  # récit perso = OK
    "educational_explainer":  True,   # "Tu ne comprends pas encore…"
    "reactive_reply":         False,  # "Vous m'avez demandé" = OK
}

# ─────────────────────────────────────────────────────────────────────────────
# Starters qui rendent un hook OUTIL-FIRST
# Pénalisé pour les types USER_FIRST = True
# ─────────────────────────────────────────────────────────────────────────────

TOOL_FIRST_STARTERS: list[str] = [
    "ce prompt", "chatgpt ", "l'ia ", "cet outil", "cette app",
    "ce script", "cette formule", "ce workflow", "claude ", "gpt-",
    "power automate", "power bi ", "notion ", "zapier ",
    "cette méthode", "cette technique",
    # EN
    "this prompt", "chatgpt ", "the ai ", "this tool", "this app",
    "this script", "this formula", "claude ", "gpt-", "power automate",
    "this method",
]

# ─────────────────────────────────────────────────────────────────────────────
# Bonus de scoring par type
# Liste de (signal, bonus_score)
# ─────────────────────────────────────────────────────────────────────────────

TYPE_SCORE_BONUSES: dict[str, list[tuple[str, float]]] = {
    "before_after_time": [
        ("→", 2.0), ("min", 0.8), ("heures", 1.0), ("minutes", 1.0),
        ("tu perds", 2.0), ("tu fais encore", 1.5), ("ça te prenait", 1.5),
        ("prenait", 1.5), ("passé de", 1.5),
    ],
    "budget_finance": [
        ("chf", 2.0), ("€", 1.5), ("$", 1.5), ("sans le voir", 2.5),
        ("tu perds", 2.5), ("fuit", 2.0), ("argent", 1.5), ("dépenses", 1.0),
    ],
    "controversial_opinion": [
        ("tu crois", 1.5), ("faux", 2.0), ("en réalité", 1.5),
        ("personne ne", 1.5), ("tout le monde", 1.0), ("honnêtement", 1.0),
    ],
    "comparison": [
        ("vs", 1.5), ("est mort", 2.0), ("le gagnant", 1.5),
        ("j'ai testé", 1.5), ("remplace", 1.5), ("surpris", 1.0),
    ],
    "data_workflow": [
        ("vlookup est mort", 3.0), ("à la main", 2.0), ("encore", 1.5),
        ("remplace", 1.5), ("3 onglets", 1.0), ("fusionne", 1.0),
    ],
    "career_work": [
        ("sans le voir", 2.0), ("risque", 1.5), ("side income", 2.0),
        ("patron", 1.5), ("remplacer", 1.5), ("chf 600", 2.0), ("augmentation", 1.5),
    ],
    "prompt_reveal": [
        ("prompt exact", 2.0), ("j'utilise", 1.5), ("depuis", 1.0),
        ("1h", 1.5), ("30 sec", 1.5), ("toujours", 1.0),
    ],
    "educational_explainer": [
        ("vraiment", 1.0), ("la vraie différence", 1.5), ("ce que", 1.0),
        ("tu ne sais pas", 2.0), ("personne n'explique", 2.0),
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Exemples de hooks par type (niveau elite — pour injection dans les prompts)
# Complètent les abc_templates de idea_classifier.py
# ─────────────────────────────────────────────────────────────────────────────

ELITE_HOOK_EXAMPLES: dict[str, dict[str, list[str]]] = {
    "before_after_time": {
        "viewer_first": [
            "Tu perds encore 2h sur ça",
            "Tu fais ça à la main. Encore.",
            "Cette tâche te prend 45 min. Elle devrait prendre 3.",
        ],
        "transformation": [
            "2h → 8 minutes",
            "Avant : 45 min. Après : 90 sec.",
            "Mon rapport de 2h. Fait en 8 min.",
        ],
        "shortcut": [
            "J'ai arrêté de faire ça manuellement",
            "Le système que j'aurais voulu trouver avant",
        ],
    },
    "prompt_reveal": {
        "discovery": [
            "Le prompt exact que j'utilise",
            "Mon prompt pour ça. Gratuit. Le voilà.",
            "Ce prompt m'évite 1h par jour",
        ],
        "secret": [
            "Le prompt que personne ne partage",
            "J'ai testé 20 prompts. Un seul marche vraiment.",
        ],
    },
    "tool_demo": {
        "discovery": [
            "J'ai testé ça pendant 30 jours",
            "Cet outil fait X en 2 minutes. Vraiment.",
        ],
        "surprise": [
            "Je pensais que c'était nul. J'avais tort.",
            "Ce truc fait ça tout seul. J'en reviens pas.",
        ],
    },
    "comparison": {
        "verdict": [
            "VLOOKUP est mort. Voilà ce qui le remplace.",
            "J'ai testé X et Y. Il y a un gagnant clair.",
            "X vs Y — le résultat m'a surpris.",
        ],
        "credibility": [
            "J'ai utilisé les deux pendant 1 mois",
            "Après 30 jours avec les deux. Mon verdict.",
        ],
    },
    "data_workflow": {
        "viewer_first": [
            "Tu fais encore ça à la main ?",
            "VLOOKUP est mort. Tu ne le sais pas encore.",
            "3 lignes de Python. 2h d'Excel évitées.",
        ],
        "replacement": [
            "Cette formule remplace 3 onglets",
            "Mon dashboard se rafraîchit tout seul",
        ],
    },
    "budget_finance": {
        "viewer_loss": [
            "Tu perds CHF 400 sans le voir",
            "Ton argent fuit déjà",
            "Il y avait CHF 400 de pertes cachées dans mon budget",
        ],
        "discovery": [
            "Ce que ChatGPT a trouvé m'a choqué",
            "J'avais raté ça depuis 6 mois",
        ],
    },
    "career_work": {
        "viewer_risk": [
            "Ton patron peut te remplacer demain",
            "Si t'as pas de side income, tu prends un risque",
            "Cette demande d'augmentation m'a rapporté CHF 600",
        ],
        "result": [
            "J'ai gagné CHF 600 avec cet email",
            "Mon CV réécrit en 3 minutes. Rappelé le lendemain.",
        ],
    },
    "controversial_opinion": {
        "challenge_belief": [
            "Ton travail de 40h. Faisable en 20.",
            "Tu crois que tu maîtrises ton temps. Faux.",
            "Les gens qui ne promptent pas = les nouveaux mauvais en Excel",
        ],
        "strong_take": [
            "Personne ne te dit ça sur l'IA au travail",
            "La moitié de ta semaine est évitable",
        ],
    },
    "build_in_public": {
        "transparency": [
            "Semaine 1 : 0 vente. Voilà ce que j'ai appris.",
            "Mon plus gros fail du mois. Détaillé.",
        ],
        "honest": [
            "Ce que j'aurais fait différemment",
            "J'aurais dû faire ça dès le début",
        ],
    },
    "storytelling_personal": {
        "personal_story": [
            "Le jour où j'ai automatisé ma tâche la plus longue",
            "Ce que l'IA a changé après 8 ans comme analyste",
        ],
        "decision": [
            "Pourquoi j'ai tout arrêté pour construire en public",
            "Ce moment où j'ai réalisé que je perdais mon temps",
        ],
    },
    "educational_explainer": {
        "knowledge_gap": [
            "La vraie différence entre un prompt moyen et un bon prompt",
            "Ce que 'temperature' signifie vraiment dans une API IA",
            "Tu ne sais pas encore ce qu'est un workflow IA",
        ],
        "authority": [
            "Ce que personne n'explique sur les LLMs",
            "La vraie raison pour laquelle ChatGPT te donne des réponses nulles",
        ],
    },
    "reactive_reply": {
        "community": [
            "Vous m'avez posé cette question 50 fois. La réponse.",
            "Ce DM revient tout le temps. Je réponds.",
        ],
        "honest_reply": [
            "La vraie réponse à ça. Pas la version polie.",
            "J'avais évité cette question. Plus maintenant.",
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Fonctions utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def get_cta_for_type(idea_type: str, lang: str = "fr") -> str:
    """Retourne le CTA complet : 'Commente PROMPT' ou 'Comment PROMPT'."""
    keywords = CTA_KEYWORDS if lang != "en" else CTA_KEYWORDS_EN
    keyword  = keywords.get(idea_type, "OUI" if lang != "en" else "YES")
    verb     = "Commente" if lang != "en" else "Comment"
    return f"{verb} {keyword}"


def is_tool_first(hook: str, idea_type: str = "") -> bool:
    """
    Retourne True si le hook est outil-first pour un type qui devrait être viewer-first.
    Toujours False pour les types où tool-first est acceptable.
    """
    if not USER_FIRST.get(idea_type, False):
        return False
    hook_lower = hook.strip().lower()
    return any(hook_lower.startswith(s) for s in TOOL_FIRST_STARTERS)


def get_type_score_bonuses(idea_type: str) -> list[tuple[str, float]]:
    """Retourne les bonus de scoring pour un type donné."""
    return TYPE_SCORE_BONUSES.get(idea_type, [])


def get_elite_examples(idea_type: str) -> list[str]:
    """Retourne une liste plate des exemples elite pour un type."""
    examples_dict = ELITE_HOOK_EXAMPLES.get(idea_type, {})
    result: list[str] = []
    for examples in examples_dict.values():
        result.extend(examples)
    return result


def build_type_rules(idea_type: str, lang: str = "fr") -> str:
    """
    Construit un bloc de règles type-spécifiques à injecter dans le prompt Claude.
    Retourne une chaîne multilignes prête à être intégrée dans le prompt.
    """
    if not idea_type:
        return ""

    cta      = get_cta_for_type(idea_type, lang)
    uf       = USER_FIRST.get(idea_type, False)
    examples = get_elite_examples(idea_type)[:5]  # max 5 exemples

    if lang == "en":
        lines = [
            f"── TYPE-SPECIFIC RULES ({idea_type}) ──",
            f"PREFERRED CTA : \"{cta}\" — use this CTA or a close variant.",
        ]
        if uf:
            lines += [
                "USER-FIRST RULE : hooks must speak TO the viewer.",
                "Start with 'You', 'Your', 'You're' — NOT with 'This prompt / ChatGPT / The AI / This tool'.",
                "WRONG: 'This prompt saves you 1h' → RIGHT: 'You're wasting 1h on this'",
            ]
        else:
            lines += [
                "Creator-first or tool-first hooks are acceptable for this type.",
            ]
    else:
        lines = [
            f"── RÈGLES TYPE-SPÉCIFIQUES ({idea_type}) ──",
            f"CTA PRIORITAIRE : \"{cta}\" — utilise ce CTA ou une variante proche.",
        ]
        if uf:
            lines += [
                "RÈGLE VIEWER-FIRST : le hook doit parler AU viewer.",
                "Commence par 'Tu', 'Ton', 'Tes' — PAS par 'Ce prompt / ChatGPT / L'IA / Cet outil'.",
                "FAUX : 'Ce prompt te sauve 1h' → JUSTE : 'Tu perds encore 1h sur ça'",
            ]
        else:
            lines += [
                "Pour ce type, les hooks outil-first ou créateur-first sont acceptables.",
            ]

    if examples:
        ex_label = "ELITE HOOKS for this type" if lang == "en" else "HOOKS ELITE pour ce type"
        lines.append(f"{ex_label} :")
        for ex in examples:
            lines.append(f'  "{ex}"')

    lines.append("")
    return "\n".join(lines)
