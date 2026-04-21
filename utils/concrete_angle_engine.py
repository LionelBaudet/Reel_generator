# -*- coding: utf-8 -*-
"""
utils/concrete_angle_engine.py — Transforme un signal d'actualité en angle actionnable.

Mappe l'actu vers des cas d'usage métier concrets pour @ownyourtime.ai
et génère un bloc enrichi pour le prompt Claude.

Usage:
    from utils.concrete_angle_engine import turn_signal_into_actionable_angle
    angle = turn_signal_into_actionable_angle(summary, title)
    # → {"topic": "réunions", "use_cases": [...], "suggested_ai_tool": "Claude", ...}
"""
from __future__ import annotations
from dataclasses import dataclass, field

# ── Mapping topic → cas d'usage concrets ─────────────────────────────────────
# Priorité : premier match de keywords → angle retourné

_TOPIC_MAP: list[tuple[list[str], dict]] = [

    # Réunions / meetings
    (["meeting", "réunion", "conférence", "agenda", "compte-rendu",
      "compte rendu", "visioconférence", "standup", "stand-up"],
     {"topic": "réunions",
      "use_cases": [
          "Préparer une réunion en 2 min avec un prompt structuré",
          "Générer le compte-rendu automatiquement depuis les notes",
          "Résumer les décisions clés en 5 bullets pour le boss",
      ],
      "ai_tool": "Claude",
      "context": "pro"}),

    # Email / communication
    (["email", "e-mail", "mail", "courriel", "communication",
      "rédaction", "correspondance", "relance", "newsletter"],
     {"topic": "emails",
      "use_cases": [
          "Écrire un email difficile en 30 secondes",
          "Reformuler un message trop long ou trop agressif",
          "Générer une relance client professionnelle",
      ],
      "ai_tool": "ChatGPT",
      "context": "pro"}),

    # Rapports / présentations / slides
    (["report", "rapport", "slide", "présentation", "powerpoint",
      "deck", "synthèse", "résumé exécutif", "executive summary"],
     {"topic": "rapports",
      "use_cases": [
          "Résumer un deck de 20 slides en 5 bullets",
          "Générer un rapport hebdomadaire en 3 min",
          "Transformer des données brutes en narration claire",
      ],
      "ai_tool": "Claude",
      "context": "pro"}),

    # Excel / données / analyse
    (["excel", "spreadsheet", "tableur", "données", "data",
      "analyse", "csv", "base de données", "dashboard", "kpi",
      "power bi", "tableau", "reporting"],
     {"topic": "données",
      "use_cases": [
          "Analyser un fichier Excel sans formule complexe",
          "Nettoyer des données avec un prompt en langage naturel",
          "Créer un dashboard automatiquement depuis un CSV",
      ],
      "ai_tool": "ChatGPT + Code Interpreter",
      "context": "pro"}),

    # PDF / documents / veille
    (["pdf", "document", "contrat", "article", "veille", "lire",
      "résumer", "synthétiser", "note de synthèse"],
     {"topic": "documents",
      "use_cases": [
          "Résumer un PDF de 40 pages en 10 points clés",
          "Extraire les clauses importantes d'un contrat",
          "Faire une veille sectorielle automatique chaque semaine",
      ],
      "ai_tool": "Claude",
      "context": "pro"}),

    # CV / recrutement / carrière
    (["cv", "résumé", "recrutement", "embauche", "candidature",
      "entretien", "interview", "job", "poste", "négociation salariale",
      "lettre de motivation", "linkedin profile"],
     {"topic": "carrière",
      "use_cases": [
          "Réécrire son CV en 10 min avec Claude",
          "Préparer un entretien avec des questions simulées",
          "Rédiger une lettre de motivation ultra-ciblée en 5 min",
      ],
      "ai_tool": "Claude",
      "context": "pro"}),

    # Budget / finances personnelles
    (["budget", "argent", "dépenses", "finances", "pouvoir d'achat",
      "inflation", "salaire", "coût", "cost of living", "expense",
      "spending", "money", "épargne", "saving"],
     {"topic": "budget",
      "use_cases": [
          "Analyser ses dépenses du mois avec ChatGPT en 2 min",
          "Repérer 3 fuites d'argent récurrentes automatiquement",
          "Créer un budget familial personnalisé sans effort",
      ],
      "ai_tool": "ChatGPT",
      "context": "perso"}),

    # Productivité / temps / surcharge
    (["productivité", "productivity", "efficacité", "gain de temps",
      "time saving", "surcharge", "burn-out", "burnout", "tâches",
      "admin", "workflow", "automatisation", "automation",
      "routines", "organisation"],
     {"topic": "productivité",
      "use_cases": [
          "Planifier sa semaine entière en 5 min avec Claude",
          "Automatiser les tâches admin répétitives sans coder",
          "Créer un workflow qui absorbe 3h d'admin par semaine",
      ],
      "ai_tool": "Claude",
      "context": "mixte"}),

    # IA / outils / adoption
    (["ia", "intelligence artificielle", "ai ", "chatgpt", "claude", "gpt",
      "llm", "copilot", "gemini", "perplexity", "outil ia",
      "adoption ia", "déploiement ia"],
     {"topic": "IA",
      "use_cases": [
          "Adopter l'IA au quotidien en 7 jours avec 1 outil par jour",
          "Choisir le bon outil IA selon son métier",
          "Construire son premier workflow IA sans coder",
      ],
      "ai_tool": "Claude / ChatGPT",
      "context": "mixte"}),

    # Licenciements / emploi / reconversion
    (["licenciement", "layoff", "restructuration", "poste supprimé",
      "chômage", "plan social", "rupture conventionnelle", "reconversion"],
     {"topic": "reconversion",
      "use_cases": [
          "Réécrire son CV pour une reconversion rapide",
          "Trouver 5 opportunités cachées avec Perplexity",
          "Générer un pitch de reconversion en 15 min",
      ],
      "ai_tool": "Claude + Perplexity",
      "context": "pro"}),

    # Télétravail / bureau / hybride
    (["télétravail", "remote", "bureau", "hybrid", "hybride",
      "présentiel", "travail à distance", "back to office"],
     {"topic": "organisation",
      "use_cases": [
          "Créer un rituel productif matin en télétravail",
          "Organiser sa journée hybride sans réunions inutiles",
          "Automatiser son reporting quotidien à distance",
      ],
      "ai_tool": "ChatGPT",
      "context": "pro"}),

    # Formation / compétences / upskilling
    (["formation", "apprentissage", "upskill", "compétence", "learning",
      "formation continue", "diplôme", "certification", "mooc"],
     {"topic": "formation",
      "use_cases": [
          "Créer un plan de formation personnalisé avec Claude",
          "Résumer un livre professionnel en 10 min",
          "Apprendre une compétence clé en 30 jours avec un mentor IA",
      ],
      "ai_tool": "Claude + Perplexity",
      "context": "mixte"}),

    # Voyage / perso
    (["voyage", "travel", "vacances", "holiday", "trip",
      "planning voyage", "itinéraire"],
     {"topic": "voyage",
      "use_cases": [
          "Planifier un voyage complet avec Claude en 15 min",
          "Comparer les options et prix en 2 min",
          "Créer l'itinéraire parfait jour par jour",
      ],
      "ai_tool": "ChatGPT",
      "context": "perso"}),

    # Santé / bien-être
    (["santé", "health", "nutrition", "sport", "meal", "repas",
      "médecin", "ordonnance", "bien-être", "wellness"],
     {"topic": "santé",
      "use_cases": [
          "Créer un plan repas de la semaine en 5 min",
          "Comprendre une ordonnance ou un bilan médical",
          "Construire un plan sport personnalisé sans coach",
      ],
      "ai_tool": "Perplexity",
      "context": "perso"}),

    # Side hustle / revenu complémentaire
    (["side hustle", "revenu complémentaire", "freelance", "solopreneur",
      "entrepreneur", "startup", "business", "client", "mission"],
     {"topic": "side income",
      "use_cases": [
          "Valider une idée de business en 1 heure avec Claude",
          "Créer ses premiers contenus marketing automatiquement",
          "Générer sa proposition de valeur en 10 min",
      ],
      "ai_tool": "Claude",
      "context": "perso"}),

    # Négociation / salaire
    (["négociation", "negotiation", "augmentation", "salaire", "rémunération"],
     {"topic": "négociation",
      "use_cases": [
          "Préparer une négociation salariale avec les bons arguments",
          "Simuler la conversation avec Claude avant le vrai entretien",
          "Identifier sa valeur marché avec Perplexity",
      ],
      "ai_tool": "Claude",
      "context": "pro"}),
]

# Fallback si aucun topic détecté
_FALLBACK_ANGLE = {
    "topic": "productivité",
    "use_cases": [
        "Automatiser une tâche répétitive avec un prompt simple",
        "Gagner 30 min par jour avec un workflow IA",
        "Déléguer l'admin à l'IA pour se concentrer sur l'essentiel",
    ],
    "ai_tool": "ChatGPT / Claude",
    "context": "mixte",
}


def _match_topic(text: str) -> dict | None:
    text_l = text.lower()
    for keywords, angle in _TOPIC_MAP:
        if any(kw in text_l for kw in keywords):
            return angle
    return None


def turn_signal_into_actionable_angle(signal_text: str,
                                       signal_title: str = "") -> dict:
    """
    Mappe un signal d'actualité vers un angle concret et actionnable.

    Retourne un dict avec :
    - topic            : domaine détecté
    - use_cases        : liste de 3 cas d'usage concrets
    - best_use_case    : le meilleur cas d'usage (1er)
    - suggested_ai_tool: outil IA recommandé
    - context          : "pro" | "perso" | "mixte"
    """
    full_text = f"{signal_title} {signal_text}"
    angle = _match_topic(full_text) or _FALLBACK_ANGLE
    return {
        "topic":             angle["topic"],
        "use_cases":         angle["use_cases"][:3],
        "best_use_case":     angle["use_cases"][0],
        "suggested_ai_tool": angle.get("ai_tool", "ChatGPT / Claude"),
        "context":           angle.get("context", "mixte"),
    }


def generate_concrete_use_cases(signal_text: str,
                                  signal_title: str = "") -> list[str]:
    """Retourne la liste des cas d'usage concrets pour un signal."""
    angle = turn_signal_into_actionable_angle(signal_text, signal_title)
    return angle["use_cases"]


def enrich_signals_block(enriched_signals: list[dict], lang: str = "fr") -> str:
    """
    Sérialise des signaux enrichis en bloc prompt pour Claude.

    Chaque signal (dict) doit avoir :
    title, source, url, published, summary,
    source_score, best_stat, angle (dict)
    """
    if not enriched_signals:
        return ""

    header = (
        "REAL NEWS SIGNALS — pre-scored & enriched (use ONLY these, do NOT invent):\n"
        if lang == "en" else
        "SIGNAUX D'ACTUALITÉ RÉELS — pré-scorés et enrichis (utilise UNIQUEMENT ceux-ci) :\n"
    )
    lines = [header]

    for i, s in enumerate(enriched_signals, 1):
        score   = s.get("source_score", 5.0)
        stat    = s.get("best_stat", "")
        angle   = s.get("angle", {})
        pub     = s.get("published", "")
        summary = s.get("summary", "")

        date_str  = f" [{pub}]" if pub else ""
        score_str = f"{score:.1f}/10"

        lines.append(
            f"{i}. [{s.get('source', '?')}{date_str}] "
            f"[Fiabilité: {score_str}] "
            f"{s.get('title', '')}"
        )
        lines.append(f"   URL: {s.get('url', '')}")
        if stat:
            lines.append(f"   Stat détectée: \"{stat}\"")
        if angle.get("topic"):
            lines.append(
                f"   Angle suggéré: {angle['topic']} "
                f"→ \"{angle.get('best_use_case', '')}\""
            )
        if summary:
            lines.append(f"   Résumé: {summary[:130]}…")
        lines.append("")

    return "\n".join(lines)
