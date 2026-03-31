#!/usr/bin/env python3
"""
generate.py — Générateur FULL AUTONOME de reels Instagram
Usage:
    python generate.py "automatiser reporting"
    python generate.py "gagner du temps emails" --run
    python generate.py "relancer clients automatiquement" --preview
"""

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
    """Parse JSON en nettoyant les virgules trailing (habitude de Claude)."""
    raw = re.sub(r",\s*\]", "]", raw.strip())
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
