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
import os
import re
import sys
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
    message = _client().messages.create(
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

─── EXEMPLES ────────────────────────────────────────────────────────────────

✗ "Ton budget familial te ment chaque mois." → trop dramatique
✓ "Tu perds de l'argent sans le voir."

✗ "Tu ne gères pas. Tu subis." → trop abstrait
✓ "Tu bosses. Mais l'argent part."

✗ "Ce prompt va transformer ton travail." → outil-first, vague
✓ "Tu écris encore ces emails toi-même ?"

✗ "L'IA coupe ce que tu refuses." → vague, artificiel
✓ "ChatGPT repère les dépenses inutiles." (OK pour budget_finance)

✗ "Prouve que t'es prêt." → CTA motivationnel
✓ "Commente BUDGET."

─── STRUCTURE DU SCRIPT ─────────────────────────────────────────────────────

hook     → stoppe le scroll en < 1 seconde
pain     → la douleur réelle que le viewer ressent
shift    → le retournement inattendu (mais / sauf que / j'ai trouvé)
solution → l'action concrète (simple, rapide, actionnable)
result   → le résultat chiffré ou ancré ("maintenant X / fini / plus jamais")
cta      → "Commente MOT" ou "Écris MOT"

AUTO-CHECK avant de répondre :
• Un vrai créateur dirait ça naturellement ?
• C'est clair en 1 seconde ?
• C'est trop dramatique ou trop abstrait ?
• Le hook parle-t-il au viewer (pas à l'outil) ?
• Le CTA est-il court et frictionless ?
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

    message = _client().messages.create(
        model=MODEL,
        max_tokens=2000,
        system=_montage_system(lang),
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text)


def build_yaml_from_viral_script(sv: dict, montage: dict, idea: str,
                                   video_paths: list | None = None,
                                   lang: str = "fr",
                                   voiceover_path: str = "") -> tuple:
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
  volume: 0.28
  voiceover: "{voiceover_path}"
  voiceover_volume: 1.0

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

def generate_ab_versions(idea: str, lang: str = "fr") -> dict:
    """Génère 3 versions A/B/C (safe / curiosité / agressif) pour une même idée."""
    from utils.idea_classifier import classify_idea, build_ab_type_context
    from utils.hook_templates import build_type_rules
    from utils.quality_validator import post_process_script

    classification = classify_idea(idea)
    type_ctx       = build_ab_type_context(classification, lang=lang)
    type_rules     = build_type_rules(classification["type"], lang=lang)

    lang_prefix = "IMPORTANT: Generate ALL text values in English.\n\n" if lang == "en" else ""
    system = _AB_SYSTEM_EN if lang == "en" else _AB_SYSTEM_FR
    prompt = lang_prefix + type_ctx + type_rules + _AB_PROMPT_TEMPLATE.format(idea=idea, lang_prefix="")

    message = _client().messages.create(
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


def generate_viral_script(idea: str, lang: str = "fr") -> dict:
    """Génère un script reel viral complet depuis une idée courte."""
    from utils.idea_classifier import classify_idea, build_type_context
    from utils.hook_templates import build_type_rules
    from utils.quality_validator import post_process_script

    classification = classify_idea(idea)
    type_ctx       = build_type_context(classification, lang=lang)
    type_rules     = build_type_rules(classification["type"], lang=lang)

    lang_prefix = "IMPORTANT: Generate ALL text values in English.\n\n" if lang == "en" else ""
    prompt = lang_prefix + type_ctx + VIRAL_SCRIPT_PROMPT.format(
        idea=idea,
        type_rules=type_rules,
    )

    message = _client().messages.create(
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

def generate_caption(sv: dict, montage: dict, idea: str, lang: str = "fr") -> str:
    """Génère un caption Instagram prêt à publier depuis le script viral."""
    script = sv.get("script", {})
    hook   = sv.get("best_hook", {}).get("text", script.get("hook", ""))
    cta    = script.get("cta", "")
    scenes = montage.get("scenes", [])
    scene_texts = " / ".join(s.get("text", "") for s in scenes if s.get("text"))

    if lang == "en":
        system  = _CAPTION_SYSTEM_EN
        prompt  = (
            f'Reel topic: "{idea}"\n'
            f'Hook: "{hook}"\n'
            f'Scene texts: "{scene_texts}"\n'
            f'CTA: "{cta}"\n\n'
            'Generate an Instagram caption. Return JSON:\n'
            '{"caption": "<2-4 punchy lines>\\n\\n<CTA line: Follow @ownyourtime.ai for more>\\n\\n<10-12 hashtags without line break>"}'
        )
    else:
        system  = _CAPTION_SYSTEM_FR
        prompt  = (
            f'Sujet du reel : "{idea}"\n'
            f'Hook : "{hook}"\n'
            f'Textes des scènes : "{scene_texts}"\n'
            f'CTA : "{cta}"\n\n'
            'Génère un caption Instagram. Retourne ce JSON :\n'
            '{"caption": "<2-4 lignes percutantes>\\n\\n<ligne CTA : Follow @ownyourtime.ai pour plus>\\n\\n<10-12 hashtags sans saut de ligne>"}'
        )

    message = _client().messages.create(
        model=MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    data = _parse_json(message.content[0].text)
    return data.get("caption", "")


def generate_variants(idea: str) -> list:
    """Génère 3 variantes de concept reel pour une même idée (un seul appel API)."""
    slug_base = re.sub(r"[^\w]", "_", idea.lower().strip())[:20]
    message = _client().messages.create(
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
