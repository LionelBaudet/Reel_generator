#!/usr/bin/env python3
"""
generate.py — Générateur FULL AUTONOME de reels Instagram
Usage:
    python generate.py "automatiser reporting"
    python generate.py "gagner du temps emails" --run
    python generate.py "relancer clients automatiquement" --preview
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)
import textwrap
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import anthropic
from dotenv import load_dotenv

load_dotenv()  # charge F:/reels_generator/.env si présent

# ── Config ────────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"


def _client() -> anthropic.Anthropic:
    """Crée le client à la demande pour lire la clé au bon moment."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY non définie.")
    return anthropic.Anthropic(api_key=key)


def _call_with_retry(**kwargs) -> anthropic.types.Message:
    """
    Wrapper autour de messages.create avec retry exponentiel.
    Gère les erreurs 529 (overloaded) et 500 transitoires.
    Retries : 3 tentatives, délais 3s → 6s → 12s.
    """
    import time
    import logging
    _log = logging.getLogger(__name__)

    max_retries = 3
    delay = 3.0
    for attempt in range(max_retries + 1):
        try:
            return _client().messages.create(**kwargs)
        except anthropic.InternalServerError as e:
            # 529 overloaded or 500 transient
            if attempt < max_retries:
                _log.warning(
                    f"Anthropic API surchargée (tentative {attempt+1}/{max_retries}) "
                    f"— nouvelle tentative dans {delay:.0f}s…"
                )
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except anthropic.RateLimitError as e:
            if attempt < max_retries:
                _log.warning(f"Rate limit Anthropic — attente {delay:.0f}s…")
                time.sleep(delay)
                delay *= 2
            else:
                raise

BROLL_CATEGORIES = {
    "night_work":  "assets/video/night_work.mp4",
    "meetings":    "assets/video/meeting_prep.mp4",
    "emails":      "assets/video/typing_person.mp4",
    "excel":       "assets/video/excel_work.mp4",
    "reports":     "assets/video/report_screen.mp4",
}

AUDIO_VARIANTS = [
    "assets/audio/lofi_beat.wav",
    "assets/audio/lofi_beat_dm.wav",
    "assets/audio/lofi_beat_am.wav",
    "assets/audio/lofi_beat_em.wav",
]

# ── Prompt système ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Tu es un expert en contenu viral Instagram pour une audience de 25-45 ans qui travaille en corporate / startup.
La marque est @ownyourtime.ai — ton humain, direct, un peu provocateur. Jamais corporate.
Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

USER_PROMPT_TEMPLATE = """\
Idée du reel : "{idea}"

Génère un reel Instagram de 18-20 secondes sur cette idée.
Catégories B-roll disponibles : night_work, meetings, emails, excel, reports

Retourne exactement ce JSON (toutes les valeurs en français sauf output_preview en anglais) :
{{
  "broll_category": "<la catégorie la plus pertinente parmi les 5>",
  "slug": "<nom de fichier snake_case, ex: reel_reporting_auto>",
  "saves_time": "<ex: 45 min/jour>",
  "intro_text": "<phrase de 6-8 mots qui choque ou intrigue>",
  "intro_subtext": "<sous-titre 5-7 mots, complète la tension>",
  "hook_text": "<hook ULTRA punchy max 8 mots, stoppe le scroll>",
  "hook_highlight": "<2-3 mots du hook à mettre en surbrillance>",
  "prompt_title": "<titre court du use case, ex: Rapport mensuel>",
  "prompt_text": "<2-3 lignes de prompt IA réaliste que l'user taperait>",
  "prompt_output": "<réponse IA crédible en anglais, 8-12 lignes, structurée avec titres>",
  "cta_headline": "<appel à l'action 2-3 mots, ex: Save THIS.>",
  "cta_subtext": "<sous-texte CTA avec emoji, MAX 40 caractères>",
  "hook_variants": [
    "<variante hook A — angle frustration>",
    "<variante hook B — angle gain de temps>",
    "<variante hook C — angle social proof>",
  ],
  "caption": "<caption Instagram 3-4 lignes + 8-10 hashtags pertinents>"
}}

Règles absolues :
- hook_text : max 8 mots, percutant, pas de question rhétorique molle
- intro_text : crée une dissonance cognitive (ex: "Mon chef croit que c'est moi qui écris ça.")
- prompt_text : doit ressembler à ce qu'un vrai utilisateur taperait, minuscules, naturel
- prompt_output : en ANGLAIS, propre, structuré, doit donner envie de sauvegarder
- caption : humain, sans hashtags génériques, specifique au sujet
- saves_time : réaliste et précis
"""

# ── Core ──────────────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> object:
    """Parse JSON robuste : nettoie markdown, virgules trailing, extrait le premier bloc JSON."""
    raw = raw.strip()
    # Enlever blocs ```json ... ``` ou ``` ... ```
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\n?```\s*$", "", raw)
    raw = raw.strip()
    # Extraire le premier objet/tableau JSON si du texte précède
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
    if match:
        raw = match.group(1)
    # Nettoyer virgules trailing
    raw = re.sub(r",\s*\]", "]", raw)
    raw = re.sub(r",\s*\}", "}", raw)
    return json.loads(raw)


def call_claude(idea: str) -> dict:
    message = _call_with_retry(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": USER_PROMPT_TEMPLATE.format(idea=idea)}],
    )
    return _parse_json(message.content[0].text)


VARIANTS_PROMPT_TEMPLATE = """\
Idée du reel : "{idea}"

Génère 3 variantes de reel Instagram (18-20s) sur cette même idée, chacune avec un angle émotionnel distinct :
- Variante 1 : angle FRUSTRATION (joue sur la douleur, ce qui énerve au quotidien)
- Variante 2 : angle GAIN DE TEMPS (joue sur le résultat chiffré, l'efficacité)
- Variante 3 : angle SOCIAL PROOF (comparaison, ce que font les autres / l'outsider)

Catégories B-roll disponibles : night_work, meetings, emails, excel, reports

Retourne UNIQUEMENT ce tableau JSON de 3 objets :
[
  {{
    "angle": "frustration",
    "broll_category": "<parmi les 5 catégories>",
    "slug": "reel_{slug}_v1",
    "saves_time": "<ex: 45 min/jour>",
    "intro_text": "<6-8 mots, choc ou dissonance cognitive>",
    "intro_subtext": "<5-7 mots, complète la tension>",
    "hook_text": "<max 8 mots ULTRA punchy, stoppe le scroll>",
    "hook_highlight": "<2-3 mots à surligner>",
    "prompt_title": "<titre court du use case>",
    "prompt_text": "<2-3 lignes prompt IA naturel, minuscules>",
    "prompt_output": "<réponse IA en ANGLAIS, 8-12 lignes structurées>",
    "cta_headline": "<2-3 mots>",
    "cta_subtext": "<sous-texte avec emoji, MAX 40 caractères>",
    "caption": "<caption Instagram 3-4 lignes + 8 hashtags>"
  }},
  {{ "angle": "gain", "slug": "reel_{slug}_v2", ... }},
  {{ "angle": "social_proof", "slug": "reel_{slug}_v3", ... }}
]

Règles absolues :
- Les 3 hooks doivent être radicalement différents (pas de paraphrase entre eux)
- Chaque variante peut choisir un broll_category différent si ça colle mieux
- prompt_output : toujours en ANGLAIS, propre et structuré (doit donner envie de sauvegarder)
- Aucun texte hors du JSON
"""


_VIRAL_SCRIPT_SYSTEM_FR = """\
Tu crées des scripts pour Instagram Reels en 2026 pour le compte @ownyourtime.ai.
Audience : professionnels 25-45 ans (corporate, freelance, solopreneurs, data/AI workers).

OBJECTIF ABSOLU : sortie publish-ready. Refuser les outputs moyens.

─── CONCEPT ÉDITORIAL ───────────────────────────────────────────────────────

Chaque reel suit cette logique :
  ACTUALITÉ RÉELLE → PROBLÈME QUE ÇA CRÉE → COMMENT L'IA AIDE CONCRÈTEMENT → EXEMPLE LIVE

Si un contexte d'actualité est fourni (actu, outil IA, prompt, résultat) :
→ Ancre le hook ou la scène pain dans l'actualité réelle
→ Montre l'outil IA exact dans la solution
→ Affiche le prompt concret dans la scène solution ou overlay
→ Montre le résultat obtenu de façon chiffrée ou très concrète
→ Le prompt IA doit apparaître en anglais dans overlay_lines (1 ligne max 6 mots, ex: "Analyse my budget vs last month")

─── RÈGLES FONDAMENTALES ────────────────────────────────────────────────────

RÈGLES D'ÉCRITURE :
- Chaque ligne = max 6 mots
- Une idée par ligne — jamais deux
- Langage parlé, pas littéraire
- Résultats concrets > tension conceptuelle
- Concret, court, immédiat > abstrait, long, philosophique

RÈGLE USER-FIRST (OBLIGATOIRE sauf indication contraire) :
→ Le hook doit parler AU VIEWER, pas à l'outil.
→ Commence par "Tu", "Ton", "Tes" — pas par "Ce prompt / ChatGPT / L'IA / Cet outil"
→ EXCEPTION : types prompt_reveal, tool_demo, comparison, build_in_public — tool-first OK

RÈGLE CTA (OBLIGATOIRE) :
→ Format : "Commente MOT" ou "Écris MOT"
→ MOT = 1 mot en majuscules lié au sujet du reel
→ JAMAIS : "Suis-moi", "Prouve que t'es prêt", "Pour plus de contenu"

─── SCORING HOOK ────────────────────────────────────────────────────────────

+3 langage naturellement parlé (quelqu'un le dirait vraiment)
+3 résultat concret et immédiat (chiffre, temps, argent)
+2 compréhensible en moins d'1 seconde
+2 perte visible (argent / temps sans le voir)
+2 interpellation directe "Tu / Ton / Tes"
-3 formulation abstraite, vague, poétique
-3 ton dramatique ou artificiel
-2 outil-first quand viewer-first attendu
-2 CTA motivationnel ou imprécis

─── STRUCTURE DU SCRIPT ─────────────────────────────────────────────────────

hook     → stoppe le scroll en < 1 seconde (ancré dans l'actu si contexte fourni)
pain     → la douleur réelle que le viewer ressent (le problème créé par l'actu)
shift    → le retournement inattendu (mais / sauf que / j'ai trouvé)
solution → l'outil IA exact + le prompt concret (simple, actionnable)
result   → le résultat chiffré ou très concret ("maintenant X / fini / plus jamais")
cta      → "Commente MOT" ou "Écris MOT"

AUTO-CHECK avant de répondre :
• Un vrai créateur dirait ça naturellement ?
• C'est clair en 1 seconde ?
• C'est trop dramatique ou trop abstrait ?
• Le hook parle-t-il au viewer (pas à l'outil) ?
• Le CTA est-il court et frictionless ?
• Si actu fournie → est-elle visible dans le hook ou la scène pain ?
• Si prompt IA fourni → apparaît-il dans overlay_lines ?
Si non → réécris avant de répondre.

Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

_VIRAL_SCRIPT_SYSTEM_EN = """\
You create Instagram Reels scripts in 2026 for the @ownyourtime.ai account.

PRIMARY GOAL: sound human, not AI-written.
The ideal creator = direct, simple, concrete. Not a motivational coach.

WRITING RULES:
- Each line = max 6 words
- One idea per line — never two
- Spoken language, not written prose
- If it sounds "written" → rewrite in spoken language
- If it's vague or abstract → replace with something concrete
- If it sounds like LinkedIn or copywriting → redo
- Favor "what is happening" over "what it means"
- Concrete outcomes > conceptual tension

HOOK SCORE:
+3 naturally spoken language
+3 concrete and immediate outcome
+2 understandable in under 1 second
+2 real visible loss (money / time)
-3 abstract or vague phrasing
-3 dramatic or artificial tone
-2 motivational or vague CTA

EXAMPLES:
✗ "Your budget is lying to you every month." → too dramatic
✓ "You're losing money and don't see it."

✗ "You don't manage. You endure." → too abstract
✓ "You work. But money disappears."

✗ "AI cuts what you refuse to." → vague, artificial
✓ "ChatGPT finds the wasted spending."

✗ "Prove you're ready." → motivational CTA
✓ "Comment BUDGET."

STRUCTURE: hook → pain → shift → solution → result → cta

CTA: always concrete — "Comment PROMPT", "Type GUIDE", "Comment YES".
Never: "Follow me", "Prove you're ready", nothing vague.

SELF-CHECK before answering:
• Would a real creator actually say this?
• Is it clear in 1 second?
• Is it too dramatic?
• Is it too abstract?
• Is the CTA direct and frictionless?
If not → rewrite.

Respond ONLY with valid JSON, no markdown, no text before or after.
"""

def _viral_script_system(lang: str = "fr") -> str:
    return _VIRAL_SCRIPT_SYSTEM_EN if lang == "en" else _VIRAL_SCRIPT_SYSTEM_FR

# backward-compatible alias
VIRAL_SCRIPT_SYSTEM = _VIRAL_SCRIPT_SYSTEM_FR

VIRAL_SCRIPT_PROMPT = """\
Idée : "{idea}"

{type_rules}
{daily_context}
Génère un script reel Instagram viral pour @ownyourtime.ai (compte faceless).

ÉTAPE 1 — Génère 10 hooks. Score chacun avec le système ci-dessous.
ÉTAPE 2 — Sélectionne le meilleur (score le plus élevé, langage parlé, concret).
ÉTAPE 3 — Écris le script ligne par ligne (max 6 mots/ligne, langage parlé uniquement).
ÉTAPE 4 — Auto-check : un vrai créateur dirait ça ? c'est clair en 1s ? trop dramatique ? → réécris si besoin.

SCORING HOOK :
+3 langage naturellement parlé (quelqu'un le dirait vraiment)
+3 résultat concret et immédiat
+2 compréhensible en moins d'1 seconde
+2 perte visible (argent, temps, opportunité concrète)
-3 formulation abstraite, vague, poétique
-3 ton dramatique, artificiel, ou "copywriter"
-2 CTA motivationnel ou imprécis

Retourne ce JSON exact :
{{
  "hooks": [
    {{"text": "<max 8 mots>", "score": 0, "type": "<perte|contradiction|curiosité|croyance>", "why": "<1 phrase>"}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}},
    {{"text": "<max 8 mots>", "score": 0, "type": "...", "why": "..."}}
  ],
  "best_hook": {{
    "text": "<hook sélectionné — score le plus élevé, sonne humain et concret>",
    "score": 0,
    "reason": "<pourquoi il performe — 1 phrase simple et directe>"
  }},
  "script": {{
    "hook":     "<meilleur hook — max 8 mots>",
    "pain":     "<tension / douleur réelle — max 6 mots>",
    "shift":    "<retournement inattendu — max 6 mots>",
    "solution": "<action simple et concrète — max 6 mots>",
    "result":   "<résultat chiffré si possible — max 6 mots>",
    "cta":      "<déclencheur de commentaire — max 8 mots>"
  }},
  "overlay_lines": [
    "<max 6 mots — ligne 1 du script>",
    "<max 6 mots — ligne 2>",
    "<max 6 mots — ligne 3>",
    "<max 6 mots — ligne 4>",
    "<max 6 mots — ligne 5>",
    "<max 6 mots — ligne 6>"
  ],
  "viral_angle": {{
    "emotion": "<frustration | curiosité | envie | FOMO | contradiction>",
    "mechanism": "<mécanisme psychologique activé — 1 phrase>"
  }},
  "cta_optimized": "<CTA orienté commentaires, naturel, max 10 mots>",
  "why_it_performs": "<explication en 2 phrases : pourquoi ce script va performer>",
  "ab_variant": {{
    "hook": "<version encore plus agressive du best hook>",
    "overlay_lines": ["<ligne 1>", "<ligne 2>", "<ligne 3>"],
    "why": "<ce qui la rend plus agressive>"
  }}
}}
"""


_MONTAGE_SYSTEM_FR = """\
Tu génères un plan de montage TEXT-CENTRIC pour Instagram Reels.

RÈGLES :
- Chaque scène = 1 seule idée, max 6 mots. Langage parlé, pas littéraire.
- Le texte à l'écran doit sonner comme quelqu'un qui parle, pas comme un slogan.
- Concret > abstrait. "Tu perds 200€/mois" > "Tu subis chaque mois."
- La vidéo de fond est une ambiance calme, jamais distrayante.
- Structure : hook → pain → shift → solution → result → cta
- Durées : hook 3.2s min, cta 3.2s min, autres 2.8s min.
- Plus de 5 mots → +0.4s par mot supplémentaire.
- Animations texte : impact_in (hook), slide_up, typing, pop, fade_in.
- Hook → toujours impact_in.
- CTA : "Commente PROMPT" ou "Écris GUIDE" — jamais motivationnel.
- 3 requêtes Pexels lifestyle calme, cohérentes avec le sujet.
- LANGUE : Français.

TEMPLATE : viral_text_centric_v1
Réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

_MONTAGE_SYSTEM_EN = """\
You generate a TEXT-CENTRIC montage plan for Instagram Reels.

RULES:
- Each scene = 1 idea only, max 6 words. Spoken language, not prose.
- On-screen text must sound like someone talking, not a slogan.
- Concrete > abstract. "You waste $200/month" > "You endure every month."
- Background video = calm ambiance, never distracting.
- Structure: hook → pain → shift → solution → result → cta
- Durations: hook 3.2s min, cta 3.2s min, others 2.8s min.
- More than 5 words → +0.4s per extra word.
- Text animations: impact_in (hook), slide_up, typing, pop, fade_in.
- Hook → always impact_in.
- CTA: "Comment PROMPT" or "Type GUIDE" — never motivational.
- 3 calm lifestyle Pexels queries consistent with the topic.
- LANGUAGE: English.

TEMPLATE: viral_text_centric_v1
Respond ONLY with valid JSON, no markdown, no text before or after.
"""

def _montage_system(lang: str = "fr") -> str:
    return _MONTAGE_SYSTEM_EN if lang == "en" else _MONTAGE_SYSTEM_FR

# backward-compatible alias
MONTAGE_SYSTEM = _MONTAGE_SYSTEM_FR

MONTAGE_JSON_TEMPLATE = """
Retourne ce JSON exact (sans markdown, sans texte autour) :
{"total_duration": 18, "pexels_queries": ["man working late laptop dark", "person thinking at screen", "minimal desk typing calm"], "background": {"style": "slow ambient", "transitions": "smooth crossfade", "overlay_opacity": 0.55, "motion": "minimal"}, "scenes": [{"id": 1, "type": "hook", "duration": 3.2, "text": "...", "keyword_highlight": "...", "text_animation": "impact_in", "font_size": "xl", "emphasis": true}, {"id": 2, "type": "pain", "duration": 2.8, "text": "...", "keyword_highlight": "", "text_animation": "slide_up", "font_size": "lg", "emphasis": false}, {"id": 3, "type": "shift", "duration": 2.8, "text": "...", "keyword_highlight": "...", "text_animation": "slide_up", "font_size": "lg", "emphasis": true}, {"id": 4, "type": "solution", "duration": 3.0, "text": "...", "keyword_highlight": "", "text_animation": "typing", "font_size": "lg", "emphasis": false}, {"id": 5, "type": "result", "duration": 3.0, "text": "...", "keyword_highlight": "...", "text_animation": "pop", "font_size": "lg", "emphasis": true}, {"id": 6, "type": "cta", "duration": 3.2, "text": "...", "keyword_highlight": "", "text_animation": "pop", "font_size": "xl", "emphasis": true}], "validation": {"hook_visible_frame_0": true, "all_scenes_min_2s8": true, "text_readable_mobile": true, "bg_calm": true}}

Remplace les ... par les vraies valeurs selon le script fourni.
Règles de durée :
- hook / cta : 3.2s minimum — JAMAIS moins
- pain / shift : 2.8s minimum
- solution / result : 3.0s minimum
- Si le texte a plus de 5 mots → +0.4s par mot supplémentaire
font_size : xl uniquement pour hook et cta — lg pour le reste
pexels_queries : lifestyle calme lié au sujet (laptop / desk / focus / person thinking)
total_duration : somme exacte des durées des scènes
"""


def generate_montage_plan(script: dict, lang: str = "fr", idea_type: str = "") -> dict:
    """Génère un plan de montage scène par scène à partir d'un script structuré."""
    # Inject type-specific CTA keyword hint if available
    cta_hint = ""
    if idea_type:
        try:
            from utils.hook_templates import get_cta_for_type
            cta_word = get_cta_for_type(idea_type, lang)
            cta_hint = f'\nCTA RECOMMANDÉ : "{cta_word}" — utilise ce CTA ou variante proche.\n'
        except ImportError:
            pass

    script_lines = "\n".join([
        "Script to transform into a dynamic video montage config:\n",
        f"Hook    : {script.get('hook', '')}",
        f"Pain    : {script.get('pain', '')}",
        f"Twist   : {script.get('twist', '')}",
        f"Solution: {script.get('solution', '')}",
        f"Result  : {script.get('result', '')}",
        f"CTA     : {script.get('cta', '')}",
    ])
    prompt = script_lines + cta_hint + MONTAGE_JSON_TEMPLATE

    message = _call_with_retry(
        model=MODEL,
        max_tokens=2000,
        system=_montage_system(lang),
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text)


def build_yaml_from_viral_script(sv: dict, montage: dict, idea: str,
                                   video_paths: list | None = None,
                                   lang: str = "fr",
                                   voiceover_path: str = "",
                                   scene_voiceovers: list | None = None,
                                   bg_music_volume: float = 0.0) -> tuple:
    """
    Construit un YAML viral_text_centric_v1 depuis le script viral + plan de montage.
    video_paths : liste de chemins locaux de vidéos Pexels (optionnel).
    Retourne (yaml_string, slug).
    """
    slug       = re.sub(r"[^\w]", "_", idea.lower().strip())[:24]
    full_slug  = f"reel_script_{slug}"
    duration   = float(montage.get("total_duration", 18))
    audio_path = AUDIO_VARIANTS[hash(slug) % len(AUDIO_VARIANTS)]
    overlay_op = float(montage.get("background", {}).get("overlay_opacity", 0.55))

    # Fallback broll local si pas de vidéos Pexels
    idea_lower = idea.lower()
    broll_map = [
        (["email", "mail", "message", "relance"], "emails"),
        (["réunion", "meeting", "call", "client"], "meetings"),
        (["excel", "tableau", "formule", "data"], "excel"),
        (["report", "rapport", "dashboard", "kpi"], "reports"),
        (["nuit", "night", "travail", "heures"], "night_work"),
    ]
    broll_cat = "emails"
    for keywords, category in broll_map:
        if any(kw in idea_lower for kw in keywords):
            broll_cat = category
            break
    fallback_video = BROLL_CATEGORIES.get(broll_cat, BROLL_CATEGORIES["emails"])

    pexels_queries = montage.get("pexels_queries", [])
    scenes_data    = montage.get("scenes", [])

    # ── Section background.videos ─────────────────────────────────────────────
    if video_paths:
        bg_videos_yaml = ""
        for i, path in enumerate(video_paths):
            q = pexels_queries[i] if i < len(pexels_queries) else ""
            bg_videos_yaml += f'    - path: "{path}"\n      query: "{q}"\n'
    else:
        # Pas encore téléchargées : queries seulement, path vide
        bg_videos_yaml = ""
        for q in pexels_queries:
            bg_videos_yaml += f'    - query: "{q}"\n      path: ""\n'
        if not pexels_queries:
            bg_videos_yaml = f'    - path: "{fallback_video}"\n      query: ""\n'

    # Build scene_voiceovers YAML block if provided
    # Always normalize to forward slashes so YAML stays valid on Windows
    if scene_voiceovers:
        _svo_lines = "  scene_voiceovers:\n"
        for item in scene_voiceovers:
            p = item if isinstance(item, str) else item.get("path", "")
            p = p.replace("\\", "/")
            _svo_lines += f'    - "{p}"\n'
        scene_vo_block = _svo_lines
    else:
        scene_vo_block = ""

    yaml_content = f"""\
# Reel viral text-centric : {idea}
# Généré depuis Script Viral + Plan de Montage — {datetime.now().strftime("%Y-%m-%d %H:%M")}
# Template : viral_text_centric_v1

reel:
  template: viral_text_centric_v1
  duration: {duration}
  fps: 30
  width: 1080
  height: 1920

background:
  videos:
{bg_videos_yaml}\
  style: "slow ambient"
  transitions: "smooth crossfade"
  overlay_opacity: {overlay_op}
  motion: "minimal"

broll_video: "{fallback_video}"

audio:
  background_music: "{audio_path}"
  volume: {bg_music_volume}
  voiceover: "{voiceover_path}"
  voiceover_volume: 1.0
{scene_vo_block}
scenes:
"""
    for scene in scenes_data:
        text      = str(scene.get("text", "")).replace('"', "'")
        keyword   = str(scene.get("keyword_highlight", "")).replace('"', "'")
        emphasis  = str(scene.get("emphasis", False)).lower()
        dur       = max(2.8, float(scene.get("duration", 2.8)))
        stype     = scene.get("type", "scene")
        if stype in ("hook", "cta"):
            dur = max(3.0, dur)
        text_anim = scene.get("text_animation", scene.get("animation", "fade_in"))
        font_size = scene.get("font_size", "xl" if stype in ("hook", "cta") else "lg")

        yaml_content += f"""\
  - type: "{stype}"
    duration: {dur}
    text: "{text}"
    keyword_highlight: "{keyword}"
    text_animation: "{text_anim}"
    font_size: "{font_size}"
    emphasis: {emphasis}
"""

    # Page finale dorée systématique
    follow_text = "Follow for more" if lang == "en" else "Follow pour plus"
    yaml_content += f"""\
  - type: "gold_outro"
    duration: 3.0
    handle: "@ownyourtime.ai"
    follow_text: "{follow_text}"
"""

    return yaml_content, full_slug


_AB_SYSTEM_FR = """\
Tu crées 3 versions d'un script Instagram Reel pour @ownyourtime.ai en 2026.
Audience : professionnels 25-45 ans (corporate, freelance, solopreneurs, data/AI workers).

RÈGLE PRINCIPALE : chaque version doit sonner humain, pas écrit par une IA.
Un vrai créateur parle simplement, directement, concrètement.

VERSION A = Safe — clair, direct, large audience, aucun mot compliqué
VERSION B = Curiosité — gap d'information simple, question concrète, pas de dramatisation
VERSION C = Direct/Franc — ton cash, sans filtre, concret, léger provoc sans être artificiel

RÈGLE USER-FIRST (OBLIGATOIRE sauf indication contraire) :
→ Le hook doit parler AU VIEWER, pas à l'outil.
→ Commence par "Tu", "Ton", "Tes" — pas par "Ce prompt / ChatGPT / L'IA / Cet outil"
→ EXCEPTION : types prompt_reveal, tool_demo, comparison, build_in_public — tool-first OK
→ Les 3 versions A/B/C doivent respecter cette règle
→ La différenciation A/B/C vient de l'ANGLE (sécurité, curiosité, provocation), pas du sujet parlé

RÈGLE CTA (OBLIGATOIRE) :
→ Format : "Commente MOT" ou "Écris MOT"
→ MOT = 1 mot en majuscules lié au sujet
→ JAMAIS : "Suis-moi", "Prouve que t'es prêt", "Pour plus de contenu"

RÈGLES :
- Chaque ligne = max 6 mots, langage parlé
- Concret > abstrait. "Tu perds 200€/mois" > "Tu subis."
- C plus direct que A, pas juste plus dramatique

SCORING HOOK :
+3 langage parlé naturel
+3 résultat concret et visible
+2 clair en moins d'1 seconde
+2 interpellation "Tu / Ton / Tes"
-3 abstrait, vague, dramatique
-2 CTA flou ou motivationnel
-2 outil-first quand viewer-first attendu

Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

_AB_SYSTEM_EN = """\
You create 3 versions of an Instagram Reel script for @ownyourtime.ai in 2026.

MAIN RULE: every version must sound human, not AI-written.
A real creator speaks simply, directly, concretely.

VERSION A = Safe — clear, direct, broad audience, no complicated words
VERSION B = Curiosity — simple information gap, concrete question, no dramatization
VERSION C = Direct/Frank — straight talk, no filter, concrete, slightly provocative without sounding fake

RULES:
- Each line = max 6 words, spoken language
- Concrete > abstract. "You waste $200/month" > "You endure."
- CTA: "Comment PROMPT", "Type GUIDE" — never motivational
- C more direct than A, not just more dramatic

HOOK SCORE:
+3 natural spoken language
+3 concrete and visible outcome
+2 clear in under 1 second
-3 abstract, vague, dramatic
-2 vague or motivational CTA

Respond ONLY with valid JSON, no markdown, no text before or after.
"""

_AB_PROMPT_TEMPLATE = """\
{lang_prefix}Idée : "{idea}"

Génère 3 versions (A/B/C) du script reel pour @ownyourtime.ai.

Retourne ce JSON exact :
{{
  "versions": [
    {{
      "id": "A",
      "type": "safe",
      "hook": {{"text": "<max 8 mots — clair, accessible>", "score": 0}},
      "script": {{
        "hook":     "<même texte que hook.text>",
        "pain":     "<tension — max 6 mots>",
        "shift":    "<retournement — max 6 mots>",
        "solution": "<action concrète — max 6 mots>",
        "result":   "<résultat chiffré — max 6 mots>",
        "cta":      "<déclencheur commentaire — max 8 mots>"
      }},
      "overlay_lines": ["<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>"],
      "tone": "<description du ton en 3 mots>"
    }},
    {{
      "id": "B",
      "type": "curiosity",
      "hook": {{"text": "<max 8 mots — gap d'information, intrigue>", "score": 0}},
      "script": {{
        "hook": "<même texte que hook.text>",
        "pain": "<max 6 mots>",
        "shift": "<max 6 mots>",
        "solution": "<max 6 mots>",
        "result": "<max 6 mots>",
        "cta": "<max 8 mots>"
      }},
      "overlay_lines": ["<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>"],
      "tone": "<description du ton en 3 mots>"
    }},
    {{
      "id": "C",
      "type": "aggressive",
      "hook": {{"text": "<max 8 mots — provocation, contradiction, pattern interrupt>", "score": 0}},
      "script": {{
        "hook": "<même texte que hook.text>",
        "pain": "<max 6 mots>",
        "shift": "<max 6 mots>",
        "solution": "<max 6 mots>",
        "result": "<max 6 mots>",
        "cta": "<max 8 mots>"
      }},
      "overlay_lines": ["<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>","<max 6 mots>"],
      "tone": "<description du ton en 3 mots>"
    }}
  ],
  "selection": {{
    "safest": "A",
    "most_viral": "<A|B|C>",
    "most_likely_to_convert": "<A|B|C>",
    "recommendation": "<1-2 phrases : quelle version utiliser selon l'objectif>"
  }}
}}
"""

def generate_ab_versions(idea: str, lang: str = "fr", context: dict | None = None) -> dict:
    """Génère 3 versions A/B/C (safe / curiosité / agressif) pour une même idée.
    context : dict optionnel venant de generate_daily_ideas() — enrichit le prompt.
    """
    from utils.idea_classifier import classify_idea, build_ab_type_context
    from utils.hook_templates import build_type_rules
    from utils.quality_validator import post_process_script

    classification = classify_idea(idea)
    type_ctx       = build_ab_type_context(classification, lang=lang)
    type_rules     = build_type_rules(classification["type"], lang=lang)
    daily_context  = _build_daily_context_block(context, lang=lang)

    lang_prefix = "IMPORTANT: Generate ALL text values in English.\n\n" if lang == "en" else ""
    system = _AB_SYSTEM_EN if lang == "en" else _AB_SYSTEM_FR
    prompt = lang_prefix + type_ctx + type_rules + daily_context + _AB_PROMPT_TEMPLATE.format(idea=idea, lang_prefix="")

    message = _call_with_retry(
        model=MODEL,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    result = _parse_json(message.content[0].text)

    # Post-processing local sur chaque version A/B/C
    versions = result.get("versions", [])
    for v in versions:
        v = post_process_script(v, lang=lang)
    result["versions"] = versions

    # Attacher la classification pour affichage
    result["idea_type"]       = classification["type"]
    result["idea_type_label"] = classification["label"] if lang != "en" else classification["label_en"]
    result["idea_angle"]      = classification["angle"] if lang != "en" else classification["angle_en"]
    result["idea_confidence"] = classification["confidence"]

    return result


def optimize_script_hooks(sv: dict, history_path: str | Path | None = None,
                           use_api_rewrite: bool = False) -> dict:
    """
    Lance le pipeline d'optimisation locale sur les hooks d'un script viral.
    Peut être appelé juste après generate_viral_script() sans appel API supplémentaire.
    use_api_rewrite=True : réécrit les hooks faibles via Claude (1 appel, optionnel).
    """
    from utils.hook_engine import optimize_hooks as _run_optimize
    idea_type = sv.get("idea_type", "")
    return _run_optimize(
        sv.get("hooks", []),
        history_path=history_path,
        use_api_rewrite=use_api_rewrite,
        idea_type=idea_type,
    )


def _build_daily_context_block(context: dict, lang: str = "fr") -> str:
    """
    Construit le bloc contexte à injecter dans le prompt de script
    quand l'idée vient de generate_daily_ideas().
    """
    if not context:
        return ""
    actu              = context.get("actu_link", "")
    emotion           = context.get("emotion", "")
    fmt               = context.get("format", "")
    hook              = context.get("hook_preview", "")
    why               = context.get("why", "")
    source_title      = context.get("source_title", context.get("source_stat", ""))
    source_label      = context.get("source_label", "")
    source_url        = context.get("source_url", "")
    source_score      = context.get("source_score", 0.0)
    ai_tool           = context.get("ai_tool", "")
    ai_prompt_example = context.get("ai_prompt_example", "")
    ai_result         = context.get("ai_result", "")
    ctx_type          = context.get("context", "")   # pro | perso | mixte
    best_stat         = context.get("best_stat", "")
    why_now           = context.get("why_now", "")
    practical_tip     = context.get("practical_tip", "")
    concrete_use_case = context.get("concrete_use_case", "")

    if lang == "en":
        lines = ["CONTEXT FROM TODAY'S IDEA SELECTION (anchor the script to this):"]
        if actu:               lines.append(f"- Current event: {actu}")
        if best_stat:          lines.append(f"- Key stat to use: \"{best_stat}\"")
        if why_now:            lines.append(f"- Why it matters now: {why_now}")
        if emotion:            lines.append(f"- Target emotion: {emotion}")
        if fmt:                lines.append(f"- Format: {fmt}")
        if hook:               lines.append(f"- Suggested hook direction: {hook}")
        if why:                lines.append(f"- Why it stops scroll: {why}")
        if ctx_type:           lines.append(f"- Context type: {ctx_type}")
        if practical_tip:      lines.append(f"- Practical tip to show: {practical_tip}")
        if concrete_use_case:  lines.append(f"- Concrete use case: {concrete_use_case}")
        if ai_tool:            lines.append(f"- AI tool to feature: {ai_tool}")
        if ai_prompt_example:  lines.append(f"- Concrete AI prompt to display: {ai_prompt_example}")
        if ai_result:          lines.append(f"- Result to show: {ai_result}")
        if source_title:       lines.append(f"- Real news source title: {source_title}")
        if source_label:       lines.append(f"- Source label (for display): {source_label}")
        if source_url:         lines.append(f"- Source URL (real, verified): {source_url}")
        if source_score:       lines.append(f"- Source reliability: {source_score}/10")
        lines.append(
            "→ Anchor the hook or pain scene in the current event.\n"
            "→ Use the key stat in the hook or pain (do not invent other stats).\n"
            "→ Show the concrete AI prompt in overlay_lines.\n"
            "→ The concrete use case is the payoff scene.\n"
            "→ NEVER invent statistics or URLs.\n"
        )
    else:
        lines = ["CONTEXTE DE L'IDÉE DU JOUR (ancre le script dans cette actualité) :"]
        if actu:               lines.append(f"- Actualité : {actu}")
        if best_stat:          lines.append(f"- Stat clé à utiliser : \"{best_stat}\"")
        if why_now:            lines.append(f"- Pourquoi maintenant : {why_now}")
        if emotion:            lines.append(f"- Émotion cible : {emotion}")
        if fmt:                lines.append(f"- Format : {fmt}")
        if hook:               lines.append(f"- Direction hook suggérée : {hook}")
        if why:                lines.append(f"- Pourquoi ça stoppe : {why}")
        if ctx_type:           lines.append(f"- Contexte : {ctx_type}")
        if practical_tip:      lines.append(f"- Astuce concrète à montrer : {practical_tip}")
        if concrete_use_case:  lines.append(f"- Cas d'usage concret : {concrete_use_case}")
        if ai_tool:            lines.append(f"- Outil IA à montrer : {ai_tool}")
        if ai_prompt_example:  lines.append(f"- Prompt IA à afficher à l'écran : {ai_prompt_example}")
        if ai_result:          lines.append(f"- Résultat concret à montrer : {ai_result}")
        if source_title:       lines.append(f"- Titre de la source réelle : {source_title}")
        if source_label:       lines.append(f"- Label source (affichage) : {source_label}")
        if source_url:         lines.append(f"- URL source (réelle, vérifiée) : {source_url}")
        if source_score:       lines.append(f"- Fiabilité source : {source_score}/10")
        lines.append(
            "→ Ancre le hook OU la scène pain dans l'actualité et/ou la stat.\n"
            "→ Utilise la stat clé dans le hook ou la tension — ne l'invente pas.\n"
            "→ Montre le prompt IA concret dans les overlay_lines.\n"
            "→ Le cas d'usage concret = le payoff du script.\n"
            "→ N'INVENTE AUCUNE STAT, AUCUNE URL.\n"
        )

    return "\n".join(lines) + "\n"


def generate_viral_script(idea: str, lang: str = "fr", context: dict | None = None) -> dict:
    """
    Génère un script reel viral complet depuis une idée courte.
    context : dict optionnel venant de generate_daily_ideas() — enrichit le prompt
              avec l'actu, l'émotion, le format et le hook suggéré.
    """
    from utils.idea_classifier import classify_idea, build_type_context
    from utils.hook_templates import build_type_rules
    from utils.quality_validator import post_process_script

    classification = classify_idea(idea)
    type_ctx       = build_type_context(classification, lang=lang)
    type_rules     = build_type_rules(classification["type"], lang=lang)
    daily_context  = _build_daily_context_block(context, lang=lang)

    lang_prefix = "IMPORTANT: Generate ALL text values in English.\n\n" if lang == "en" else ""
    prompt = lang_prefix + type_ctx + VIRAL_SCRIPT_PROMPT.format(
        idea=idea,
        type_rules=type_rules,
        daily_context=daily_context,
    )

    message = _call_with_retry(
        model=MODEL,
        max_tokens=2000,
        system=_viral_script_system(lang),
        messages=[{"role": "user", "content": prompt}],
    )
    result = _parse_json(message.content[0].text)

    # Post-processing local : fix CTAs, overlay lines, flag tool-first hooks
    result = post_process_script(result, lang=lang)

    # Attacher la classification au résultat pour affichage dans l'app
    result["idea_type"]       = classification["type"]
    result["idea_type_label"] = classification["label"] if lang != "en" else classification["label_en"]
    result["idea_angle"]      = classification["angle"] if lang != "en" else classification["angle_en"]
    result["idea_confidence"] = classification["confidence"]

    return result


_CAPTION_SYSTEM_FR = """\
Tu es un expert en copywriting Instagram pour les comptes faceless productivité/IA/revenus.
Tu écris des captions courtes, humaines, qui donnent envie de sauvegarder et de follow.
Pas de hashtags génériques. Pas de "Découvrez comment". Naturel, direct, léger.
Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

_CAPTION_SYSTEM_EN = """\
You are an Instagram copywriting expert for faceless productivity/AI/income accounts.
You write short, human captions that make people want to save and follow.
No generic hashtags. No "Discover how". Natural, direct, punchy.
Respond ONLY with valid JSON, no markdown, no text before or after.
"""

def generate_caption(sv: dict, montage: dict, idea: str, lang: str = "fr",
                     daily_context: dict | None = None) -> str:
    """Génère un caption Instagram prêt à publier depuis le script viral.
    daily_context : dict optionnel de generate_daily_ideas() — ajoute la source en fin de caption.
    """
    script = sv.get("script", {})
    hook   = sv.get("best_hook", {}).get("text", script.get("hook", ""))
    cta    = script.get("cta", "")
    scenes = montage.get("scenes", [])
    scene_texts = " / ".join(s.get("text", "") for s in scenes if s.get("text"))

    # Build source block for caption
    source_block = ""
    if daily_context:
        source_stat  = daily_context.get("source_title", daily_context.get("source_stat", ""))
        source_url   = daily_context.get("source_url", "")
        source_label = daily_context.get("source_label", "")
        if source_stat or source_url:
            if lang == "en":
                source_block = (
                    f'\nSource stat used in reel: "{source_stat}"\n'
                    f'Source URL: "{source_url}"\n'
                    "→ Add a 'Source: [label] → link in bio' line at the very end of the caption "
                    "(after hashtags). Keep it short and factual.\n"
                )
            else:
                source_block = (
                    f'\nStat source utilisée dans le reel : "{source_stat}"\n'
                    f'URL source : "{source_url}"\n'
                    "→ Ajoute une ligne 'Source : [label] → lien en bio' tout à la fin du caption "
                    "(après les hashtags). Courte et factuelle.\n"
                )

    if lang == "en":
        system  = _CAPTION_SYSTEM_EN
        prompt  = (
            f'Reel topic: "{idea}"\n'
            f'Hook: "{hook}"\n'
            f'Scene texts: "{scene_texts}"\n'
            f'CTA: "{cta}"\n'
            f'{source_block}\n'
            'Generate an Instagram caption. Return JSON:\n'
            '{"caption": "<2-4 punchy lines>\\n\\n<CTA line: Follow @ownyourtime.ai for more>\\n\\n<10-12 hashtags without line break>\\n\\n<Source line if provided>"}'
        )
    else:
        system  = _CAPTION_SYSTEM_FR
        prompt  = (
            f'Sujet du reel : "{idea}"\n'
            f'Hook : "{hook}"\n'
            f'Textes des scènes : "{scene_texts}"\n'
            f'CTA : "{cta}"\n'
            f'{source_block}\n'
            'Génère un caption Instagram. Retourne ce JSON :\n'
            '{"caption": "<2-4 lignes percutantes>\\n\\n<ligne CTA : Follow @ownyourtime.ai pour plus>\\n\\n<10-12 hashtags sans saut de ligne>\\n\\n<Ligne source si fournie>"}'
        )

    message = _call_with_retry(
        model=MODEL,
        max_tokens=700,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    data = _parse_json(message.content[0].text)
    return data.get("caption", "")


_DAILY_IDEAS_SYSTEM = """\
Tu es un créateur de contenu Instagram pour @ownyourtime.ai en 2026.
Audience : professionnels 25-45 ans (corporate, startup, solopreneurs, vie perso).
Ton : direct, concret, jamais corporate.

CONCEPT ÉDITORIAL — RÈGLE ABSOLUE :
  ACTUALITÉ RÉELLE + STAT FIABLE → TENSION / PRISE DE CONSCIENCE → ASTUCE CONCRÈTE → CAS D'USAGE RÉEL → CTA

Exemples du niveau attendu :
  Actu: "1 manager sur 3 utilise déjà l'IA au quotidien"
  Hook: "Ton manager utilise déjà l'IA. Pas toi."
  Astuce: "Prépare chaque réunion avec ce prompt en 2 min."
  Cas concret: "Copie ordre du jour + objectifs + participants → Claude fait le brief."

  Actu: "Retour au bureau / pression productivité"
  Hook: "On te demande 5 jours au bureau. Pas 5x plus de résultats."
  Astuce: "Voilà l'automatisation qui te donne 45 min par jour."

  Actu: "Inflation / pouvoir d'achat"
  Hook: "Ton salaire suit. Pas ton pouvoir d'achat."
  Astuce: "ChatGPT repère 3 fuites d'argent en 2 min."
  Cas concret: "Uploader relevé bancaire → demander 3 dépenses récurrentes inutiles."

FILTRE QUALITÉ STRICT — REJETTE :
✗ Idée trop générique ("utilise l'IA", "sois productif", "l'IA peut t'aider")
✗ Idée purement inspirationnelle sans astuce
✗ Idée sans cas d'usage immédiatement imaginable
✗ Idée sans ancrage actu ou stat réelle
✗ Source inventée ou non fournie dans la liste

POUR CHAQUE IDÉE, OBLIGATOIRE :
- best_stat   : stat/chiffre le plus accrocheur du signal (copié ou reformulé naturellement)
- why_now     : pourquoi ce sujet résonne MAINTENANT (1 phrase courte)
- practical_tip : l'astuce concrète que le viewer peut appliquer aujourd'hui (1 action)
- concrete_use_case : le cas d'usage précis (sujet + outil + action + résultat)
- ai_tool     : outil IA exact à montrer
- ai_prompt_example : le prompt que le viewer taperait (naturel, 1-2 lignes)
- ai_result   : résultat obtenu (chiffré ou très concret)

DOMAINES — varie entre les 3 idées (pro / perso / mixte) :
Pro : réunions, emails, rapports, données, CV, négociation, veille, présentation
Perso : budget, santé, voyage, formation, reconversion, side hustle

RÈGLES SOURCES :
- source_title : titre EXACT du signal fourni (copié mot pour mot)
- source_url   : URL EXACTE du signal (copiée telle quelle)
- source_score : score de fiabilité fourni dans la liste (décimal, ex: 9.5)
- N'invente AUCUNE URL, stat, chiffre absent de la liste fournie

Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

_DAILY_IDEAS_PROMPT = """\
Date du jour : {date}

{signals_block}

Génère exactement 3 idées de reels pour @ownyourtime.ai.
Chaque idée = actualité réelle + stat fiable + astuce concrète + cas d'usage imaginable.

STRUCTURE DE CHAQUE IDÉE :
- "idea"              : titre court du reel (5-8 mots, accrocheur)
- "context"           : "pro" | "perso" | "mixte"
- "hook_preview"      : hook max 8 mots, parlé, stoppe le scroll
- "emotion"           : "frustration" | "curiosité" | "FOMO" | "envie" | "surprise"
- "actu_link"         : résumé 1 phrase de l'actualité utilisée
- "best_stat"         : stat/chiffre le plus fort du signal (naturel, ex: "1 manager sur 3")
- "why_now"           : pourquoi ce sujet est urgent maintenant (1 phrase courte)
- "practical_tip"     : astuce concrète actionnable dès aujourd'hui (1 action simple)
- "concrete_use_case" : cas précis — qui + outil + action + résultat (1-2 phrases)
- "ai_tool"           : outil IA exact (ChatGPT | Claude | Gemini | Perplexity | Copilot)
- "ai_prompt_example" : prompt concret que le viewer taperait (naturel, 1-2 lignes)
- "ai_result"         : résultat obtenu — chiffré ou très concret (max 10 mots)
- "source_title"      : titre EXACT copié depuis la liste de signaux
- "source_label"      : publication + date (ex: "McKinsey, 2025-04-21")
- "source_url"        : URL EXACTE copiée depuis la liste
- "source_score"      : score de fiabilité du signal (copié depuis [Fiabilité: X.X/10])
- "score"             : ton score editorial 0-10
- "why"               : pourquoi ça stoppe le scroll — 1 phrase

Retourne exactement ce JSON :
{{
  "ideas": [
    {{
      "idea": "<5-8 mots>",
      "context": "<pro | perso | mixte>",
      "hook_preview": "<max 8 mots, parlé>",
      "emotion": "<frustration | curiosité | FOMO | envie | surprise>",
      "actu_link": "<résumé actu — 1 phrase>",
      "best_stat": "<stat accrocheur du signal>",
      "why_now": "<pourquoi urgent maintenant — 1 phrase>",
      "practical_tip": "<astuce concrète — 1 action>",
      "concrete_use_case": "<qui + outil + action + résultat>",
      "ai_tool": "<outil exact>",
      "ai_prompt_example": "<prompt que le viewer taperait>",
      "ai_result": "<résultat concret — max 10 mots>",
      "source_title": "<titre exact du signal>",
      "source_label": "<publication + date>",
      "source_url": "<URL exacte>",
      "source_score": 0.0,
      "score": 0,
      "why": "<pourquoi ça stoppe — 1 phrase>"
    }},
    {{
      "idea": "...", "context": "...", "hook_preview": "...", "emotion": "...",
      "actu_link": "...", "best_stat": "...", "why_now": "...",
      "practical_tip": "...", "concrete_use_case": "...",
      "ai_tool": "...", "ai_prompt_example": "...", "ai_result": "...",
      "source_title": "...", "source_label": "...", "source_url": "...",
      "source_score": 0.0, "score": 0, "why": "..."
    }},
    {{
      "idea": "...", "context": "...", "hook_preview": "...", "emotion": "...",
      "actu_link": "...", "best_stat": "...", "why_now": "...",
      "practical_tip": "...", "concrete_use_case": "...",
      "ai_tool": "...", "ai_prompt_example": "...", "ai_result": "...",
      "source_title": "...", "source_label": "...", "source_url": "...",
      "source_score": 0.0, "score": 0, "why": "..."
    }}
  ],
  "date": "{date}",
  "note": "<angle dominant des signaux aujourd'hui — 1 phrase>"
}}
"""

FORMAT_LABELS = {
    "provocateur":      ("🔥", "Provocateur"),
    "transformation":   ("⚡", "Avant / Après"),
    "storytelling":     ("🎭", "Storytelling"),
    "reaction_actu":    ("📡", "Réaction Actu"),
    "comparaison":      ("⚖️", "Comparaison"),
    "education_simple": ("💡", "Éducatif"),
    "tu_fais_encore":   ("😤", "Tu fais encore ça ?"),
    "ton_job_change":   ("📈", "Ton job change"),
}

EMOTION_COLORS = {
    "frustration":    "#f87171",
    "curiosité":      "#60a5fa",
    "FOMO":           "#f59e0b",
    "contradiction":  "#a78bfa",
    "envie":          "#34d399",
}


def validate_daily_idea(idea: dict) -> list[str]:
    """
    Valide une idée selon le filtre qualité éditorial.
    Retourne une liste d'erreurs (vide = idée valide).
    """
    errors: list[str] = []
    if not isinstance(idea, dict):
        return ["not a dict"]

    # Champs obligatoires
    required = ["practical_tip", "concrete_use_case", "best_stat",
                "hook_preview", "source_url"]
    for field_name in required:
        val = idea.get(field_name, "")
        if not val or (isinstance(val, str) and len(val.strip()) < 8):
            errors.append(f"champ '{field_name}' manquant ou trop court")

    # Hook trop générique
    generic_hooks = [
        "l'ia peut t'aider", "utilise l'ia", "sois productif",
        "améliore ta productivité", "use ai to", "be more productive",
        "l'intelligence artificielle", "ia au travail"
    ]
    hook = idea.get("hook_preview", "").lower().strip()
    if any(g in hook for g in generic_hooks):
        errors.append("hook trop générique")

    # practical_tip trop vague
    generic_tips = ["utilise l'ia", "use ai", "sois plus efficace",
                    "améliore", "optimise ta productivité"]
    tip = idea.get("practical_tip", "").lower()
    if any(g in tip for g in generic_tips):
        errors.append("practical_tip trop vague")

    return errors


def generate_daily_ideas(date: str | None = None) -> dict:
    """
    Génère 3 idées de reels du jour : actualité réelle + stat + astuce + cas concret.

    Flow :
      1. fetch_daily_signals()         — RSS Google News + feeds directs
      2. filter_relevant_signals()     — score et filtre par pertinence thématique
      3. enrich_signals_for_prompt()   — score source, stat, blacklist, angle
      4. Claude génère 3 idées enrichies (stat + astuce + cas concret)
      5. validate_daily_idea()         — filtre qualité sur chaque idée

    Retourne un dict avec "ideas", "date", "note", "_signals_*".
    """
    from utils.signals import (
        fetch_daily_signals, filter_relevant_signals,
        enrich_signals_for_prompt, signals_to_prompt_block
    )

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # 1. Fetch & keyword-filter signals
    logger.info("Fetching daily signals…")
    raw_signals = fetch_daily_signals()
    relevant    = filter_relevant_signals(raw_signals, top_n=20)

    if not relevant:
        logger.warning("No relevant signals — falling back to date-only prompt")
        enriched_list = []
        signals_block = (
            "Aucun signal RSS disponible. "
            "Génère 3 idées basées sur les tendances IA/travail actuelles de 2025-2026."
        )
    else:
        # 2. Enrich: blacklist + source scoring + stat extraction + angle detection
        enriched_list, signals_block = enrich_signals_for_prompt(relevant, lang="fr")
        logger.info(
            f"Enriched pipeline: {len(enriched_list)}/{len(relevant)} signals "
            f"(after blacklist filter)"
        )
        if not signals_block:
            signals_block = signals_to_prompt_block(relevant, lang="fr")

    # 3. Call Claude — escape { } in signal content to prevent .format() KeyError
    signals_block_safe = signals_block.replace("{", "{{").replace("}", "}}")
    message = _call_with_retry(
        model=MODEL,
        max_tokens=2200,
        system=_DAILY_IDEAS_SYSTEM,
        messages=[{
            "role": "user",
            "content": _DAILY_IDEAS_PROMPT.format(
                date=date, signals_block=signals_block_safe
            ),
        }],
    )
    result = _parse_json(message.content[0].text)

    # 4. Quality filter — log but don't discard (UI can show warnings)
    ideas = result.get("ideas", [])
    for i, idea in enumerate(ideas):
        errors = validate_daily_idea(idea)
        if errors:
            logger.warning(
                f"Idea {i+1} quality issues: {'; '.join(errors)} "
                f"— hook: {idea.get('hook_preview', '')[:50]}"
            )
            idea["_quality_warnings"] = errors
        else:
            idea["_quality_warnings"] = []

    # 5. Attach pipeline metadata
    result["_signals_fetched"]  = len(raw_signals)
    result["_signals_relevant"] = len(relevant)
    result["_signals_enriched"] = len(enriched_list)
    return result


def generate_variants(idea: str) -> list:
    """Génère 3 variantes de concept reel pour une même idée (un seul appel API)."""
    slug_base = re.sub(r"[^\w]", "_", idea.lower().strip())[:20]
    message = _call_with_retry(
        model=MODEL,
        max_tokens=3500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": VARIANTS_PROMPT_TEMPLATE.format(idea=idea, slug=slug_base),
        }],
    )
    return _parse_json(message.content[0].text)


_CTA_SUBTEXT_MAX = 40  # ~960px usable / 24px/char moyenne à 44px bold


def build_yaml(data: dict, idea: str) -> str:
    video_path = BROLL_CATEGORIES.get(data["broll_category"], BROLL_CATEGORIES["emails"])
    audio_idx = hash(data["slug"]) % len(AUDIO_VARIANTS)
    audio_path = AUDIO_VARIANTS[audio_idx]

    # Tronquer le cta_subtext si Claude dépasse la limite
    cta_sub = data.get("cta_subtext", "")
    if len(cta_sub) > _CTA_SUBTEXT_MAX:
        cta_sub = cta_sub[:_CTA_SUBTEXT_MAX].rstrip() + "…"
        data = {**data, "cta_subtext": cta_sub}

    # Indenter les blocs multilignes
    def indent_block(text: str, spaces: int = 4) -> str:
        lines = text.strip().splitlines()
        pad = " " * spaces
        return "\n" + "\n".join(pad + ln for ln in lines)

    prompt_text = indent_block(data["prompt_text"])
    prompt_output = indent_block(data["prompt_output"])

    yaml_content = f"""\
# Reel : {idea}
# Généré automatiquement par generate.py — {datetime.now().strftime("%Y-%m-%d %H:%M")}

reel:
  template: prompt_reveal
  duration: 20
  fps: 30
  width: 1080
  height: 1920

intro:
  video: "{video_path}"
  duration: 3
  start_at: 0
  text: "{data['intro_text']}"
  subtext: "{data['intro_subtext']}"
  fade_in: 0.2
  fade_out: 0.5
  overlay_opacity: 0.55

hook:
  text: "{data['hook_text']}"
  highlight: "{data['hook_highlight']}"
  duration: 3

prompt:
  title: "{data['prompt_title']}"
  text: |{prompt_text}
  output_preview: |{prompt_output}
  saves: "{data['saves_time']}"
  duration: 11

cta:
  headline: "{data['cta_headline']}"
  subtext: "{data['cta_subtext']}"
  handle: "@ownyourtime.ai"
  duration: 3

audio:
  background_music: "{audio_path}"
  volume: 0.28
  typing_sound: "assets/audio/typing.mp3"
  typing_volume: 0.5
"""
    return yaml_content


def print_results(idea: str, data: dict, yaml_content: str, output_path: Path):
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  REEL GENERE : {idea.upper()}")
    print(f"{sep}\n")

    print("CONCEPT")
    print(f"  B-Roll       : {data['broll_category']}")
    print(f"  Temps économisé : {data['saves_time']}")
    print(f"  Fichier      : {output_path.name}\n")

    print("HOOK PRINCIPAL")
    print(f"  → {data['hook_text']}\n")

    print("HOOKS ALTERNATIFS (A/B test)")
    for i, variant in enumerate(data.get("hook_variants", []), 1):
        label = ["A (frustration)", "B (gain temps)", "C (social proof)"][i - 1]
        print(f"  {label} : {variant}")

    print(f"\nCAPTION INSTAGRAM")
    print(textwrap.indent(data["caption"], "  "))

    print(f"\n{sep}")
    print(f"  YAML → {output_path}")
    print(f"{sep}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Génère un reel complet depuis une idée")
    parser.add_argument("idea", help='Idée du reel, ex: "automatiser reporting"')
    parser.add_argument(
        "--run",
        action="store_true",
        help="Lance automatiquement main.py après la génération",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Lance main.py en mode preview (PNG uniquement)",
    )
    parser.add_argument(
        "--output-dir",
        default="config/batch",
        help="Dossier de sortie du YAML (défaut: config/batch)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERREUR : variable ANTHROPIC_API_KEY non définie.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    print(f"\nGeneration en cours pour : \"{args.idea}\" ...")

    try:
        data = call_claude(args.idea)
    except json.JSONDecodeError as e:
        print(f"ERREUR JSON de Claude : {e}")
        sys.exit(1)
    except anthropic.APIError as e:
        print(f"ERREUR API Anthropic : {e}")
        sys.exit(1)

    yaml_content = build_yaml(data, args.idea)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{data['slug']}.yaml"
    output_path.write_text(yaml_content, encoding="utf-8")

    print_results(args.idea, data, yaml_content, output_path)

    if args.run or args.preview:
        import subprocess
        cmd = ["python", "main.py", "--config", str(output_path), "--output", "output/"]
        if args.preview:
            cmd.append("--preview")
        print(f"Lancement : {' '.join(cmd)}\n")
        subprocess.run(cmd)


if __name__ == "__main__":
    main()
