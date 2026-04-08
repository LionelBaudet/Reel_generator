# -*- coding: utf-8 -*-
"""
utils/hook_optimizer.py — Analyse et optimisation automatique des hooks Instagram.
Score sur 5 critères. Si < 7.5 → génère 10 alternatives et sélectionne le gagnant.
"""
from __future__ import annotations

import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
Tu es un expert en hooks Instagram viraux pour une audience de professionnels 25-45 ans
(freelances, employés corporate, solopreneurs, data/AI workers).
La marque est @ownyourtime.ai — ton humain, direct, un peu provocateur.
Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

ANALYZE_PROMPT = """\
Hook à analyser : "{hook}"
Contexte du reel : "{context}"

ÉTAPE 1 — Score le hook sur ces 5 critères (note de 0 à 10) :
- scroll_stopping : Est-ce que ça stoppe le scroll en < 2 secondes ?
- clarity : C'est immédiatement compréhensible ?
- curiosity : Crée une tension ou question dans l'esprit du viewer ?
- viral_potential : Les gens vont partager ou sauvegarder ?
- niche_fit : Pertinent pour AI, productivité, automatisation, data, revenus ?

Calcule average = (somme des 5 notes) / 5.
Si average >= 7.5 → verdict "ACCEPTED", ne génère pas d'alternatives.
Si average < 7.5 → verdict "REJECTED", génère 10 alternatives.

ÉTAPE 2 (si REJECTED) — Génère 10 hooks alternatifs, 2 par style :
- curiosity : crée une question que le cerveau veut voir répondre
- provocation : challenge une croyance commune
- contrast : avant/après, eux/toi, ancien/nouveau
- mistake : "Tu fais X de la mauvaise façon"
- result : chiffre ou résultat concret et spécifique

Règles pour chaque hook :
- Max 10 mots
- Fonctionne SANS SON (85% des reels sont en mode muet)
- Jamais de clichés ("boost ta productivité", "travaille moins", etc.)
- Jamais de ton guru ou motivationnel
- Pense comme un créateur qui veut stopper le scroll à la frame 0

Retourne ce JSON exact :
{{
  "original_score": {{
    "scroll_stopping": <note>,
    "clarity": <note>,
    "curiosity": <note>,
    "viral_potential": <note>,
    "niche_fit": <note>,
    "average": <moyenne arrondie à 1 décimale>,
    "verdict": "ACCEPTED" ou "REJECTED"
  }},
  "alternatives": [
    {{"rank": 1, "hook": "<texte>", "style": "<style>", "score": <note/10>, "why": "<raison courte>"}},
    ...10 items si REJECTED, sinon []
  ],
  "winner": "<meilleur hook (original si ACCEPTED, meilleure alternative si REJECTED)>",
  "winner_highlight": "<2-3 mots clés du winner à surligner en or>",
  "winner_score": <note/10>,
  "optimized": "<version winner légèrement retravaillée, plus forte>",
  "aggressive": "<variante plus provocatrice, pour A/B test>",
  "safe": "<variante plus large audience>",
  "intro_text": "<phrase intro 6-8 mots adaptée au winner>",
  "intro_subtext": "<sous-titre 5-7 mots, complète la tension>"
}}
"""


def _client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY non définie.")
    return anthropic.Anthropic(api_key=key)


def _parse(raw: str) -> dict:
    raw = raw.strip()
    # Enlever les blocs ```json ... ``` ou ``` ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    # Nettoyer virgules trailing
    raw = re.sub(r",\s*\]", "]", raw)
    raw = re.sub(r",\s*\}", "}", raw)
    return json.loads(raw)


def analyze_hook(hook_text: str, context: str = "") -> dict:
    """
    Analyse un hook et retourne le rapport complet.
    Retourne un dict avec original_score, alternatives, winner, etc.
    """
    prompt = ANALYZE_PROMPT.format(
        hook=hook_text,
        context=context or "reel AI/productivité @ownyourtime.ai",
    )
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse(msg.content[0].text)


SOLUTION_PROMPT = """\
Analyse cette réponse IA affichée dans un reel Instagram pour @ownyourtime.ai.

SOLUTION : "{solution}"
CONTEXTE : "{context}"

Score sur 5 critères (entier de 0 à 10) :
- credibility : réponse réaliste, professionnelle, crédible
- save_worthy : le viewer va sauvegarder ce reel pour réutiliser ça
- clarity : structure lisible en quelques secondes
- wow_factor : ça fait dire "je peux utiliser ça maintenant"
- length_fit : longueur adaptée pour être lue en 11 secondes à l'écran

average = (somme 5 notes) / 5, arrondi à 1 décimale.
verdict = "GOOD" si average >= 7.5, sinon "NEEDS_IMPROVEMENT".
Si NEEDS_IMPROVEMENT : génère improved_solution (en ANGLAIS, structurée, max 15 lignes).
Si GOOD : improved_solution = "".

Réponds UNIQUEMENT avec ce JSON, sans markdown, sans texte autour :
{{"scores":{{"credibility":0,"save_worthy":0,"clarity":0,"wow_factor":0,"length_fit":0,"average":0.0,"verdict":""}},"issues":[],"improved_solution":"","improvement_notes":""}}

Remplace les valeurs par les vraies notes.
"""


def analyze_solution(solution_text: str, context: str = "") -> dict:
    """Score la réponse IA du reel et propose une version améliorée si nécessaire."""
    prompt = SOLUTION_PROMPT.format(
        solution=solution_text.strip(),
        context=context or "reel AI/productivité @ownyourtime.ai",
    )
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse(msg.content[0].text)


def inject_winner(config: dict, analysis: dict) -> dict:
    """
    Injecte le hook gagnant dans un config dict existant.
    Retourne une copie du config mis à jour.
    """
    updated = {**config}

    updated["hook"] = {
        **config.get("hook", {}),
        "text":      analysis["winner"],
        "highlight": analysis["winner_highlight"],
    }

    if "intro" in config:
        updated["intro"] = {
            **config["intro"],
            "text":    analysis["intro_text"],
            "subtext": analysis["intro_subtext"],
        }

    return updated
