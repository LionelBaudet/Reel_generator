# -*- coding: utf-8 -*-
"""
utils/hook_engine.py — Moteur local d'optimisation de hooks Instagram Reels.

Pipeline :
  1. Détection des hooks faibles (is_weak_hook)
  2. Scoring local (score_hook) — rapide, sans API
  3. Boost historique (history_boost) — récompense les patterns qui ont performé
  4. Classification A/B/C (classify_abc)
  5. Réécriture des hooks faibles via Claude (rewrite_weak_hooks_api) — optionnel
  6. Pipeline complet (optimize_hooks)
  7. Enregistrement des performances (save_hook_result)

Aucune dépendance obligatoire sur l'API — tout sauf rewrite_weak_hooks_api
fonctionne 100% localement.
"""
from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

HISTORY_PATH = Path("assets/hook_history.json")

# ─────────────────────────────────────────────────────────────────────────────
# Détection des hooks faibles
# ─────────────────────────────────────────────────────────────────────────────

# Mots de départ qui signalent un hook de type blog/tuto
_WEAK_STARTERS = [
    "comment ", "voici ", "astuce", "guide", "c'est quoi", "comment faire",
    "how to ", "here's ", "here is", "tip:", "what is ", "learn how",
    "découvrez", "apprenez", "saviez-vous", "did you know",
    "dans cette vidéo", "in this video", "today i ", "let me show",
    "je vais vous", "je vous montre",
]

# Mots qui signalent un copywriting artificiel ou trop "marketing"
_WEAK_WORDS = [
    "stratégie ultime", "méthode révolutionnaire", "technique secrète",
    "ultime guide", "incroyable", "fascinant", "impressionnant",
    "boost", "optimiser votre", "maximiser votre",
    "ultimate guide", "revolutionary", "incredible", "amazing",
    "secret method", "proven strategy",
]


def is_weak_hook(hook: str) -> bool:
    """
    Retourne True si le hook est probablement sous-performant sur Instagram Reels.
    Règles : trop long, démarrage faible, mots marketing, absence de signal fort.
    """
    h = hook.strip().lower()
    words = h.split()

    # Trop long
    if len(words) > 10:
        return True

    # Commence par un mot faible
    for starter in _WEAK_STARTERS:
        if h.startswith(starter):
            return True

    # Contient des mots marketing/copywriter
    for word in _WEAK_WORDS:
        if word in h:
            return True

    # Question trop longue (blog-style)
    if h.endswith("?") and len(words) > 7:
        return True

    # Aucun signal fort présent pour un hook > 5 mots
    _strong_signals = [
        "tu ", "vous ", "you ", "perds", "perd", "fuis", "fuite",
        "coûte", "coste", "lose", "losing", "gagne", "earn", "argent",
        "money", "chf", "$", "€", "erreur", "mistake", "faux",
        "already", "déjà", "sans le voir", "without",
    ]
    if len(words) > 5 and not any(sig in h for sig in _strong_signals):
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Scoring local
# ─────────────────────────────────────────────────────────────────────────────

def score_hook(hook: str, idea_type: str = "") -> float:
    """
    Score local d'un hook (0–10).
    Rapide, sans API, facilement modifiable.
    Base 5.0, bonus/malus selon les signaux.
    idea_type : si fourni, ajoute des bonus/malus type-spécifiques.
    """
    h = hook.strip().lower()
    words = h.split()
    score = 5.0

    # ── Bonus ────────────────────────────────────────────────────────────────

    # Signal de perte (cumulable jusqu'à +3)
    _loss_bonus = 0.0
    for kw in ["perds", "perd", "perdre", "fuit", "fuite", "perte",
               "lose", "losing", "lost", "leak", "leaking"]:
        if kw in h:
            _loss_bonus = min(_loss_bonus + 1.5, 3.0)
    score += _loss_bonus

    # Argent / montant (+1.5, une seule fois)
    if any(kw in h for kw in ["chf", "€", "$", "argent", "money", "budget",
                               "dépenses", "expenses", "salaire", "salary"]):
        score += 1.5

    # Interpellation directe "tu" / "you"
    if re.search(r"\btu\b|\byou\b", h):
        score += 1.5

    # Problème invisible ("sans le voir", "without knowing"…)
    if any(kw in h for kw in ["sans le voir", "without seeing", "sans savoir",
                               "without knowing", "invisible", "sans y penser",
                               "without realizing", "sans remarquer"]):
        score += 2.0

    # Chiffre concret (400, 1h, 20%)
    if re.search(r"\d+", h):
        score += 1.5

    # Longueur idéale ≤6 mots
    if len(words) <= 6:
        score += 1.0
    elif len(words) <= 8:
        score += 0.5

    # Langage parlé / contractions
    if any(kw in h for kw in ["t'es", "c'est", "j'ai", "y'a", "nan",
                               "you're", "don't", "it's", "there's", "i've"]):
        score += 0.5

    # Erreur / faux / mauvais
    if any(kw in h for kw in ["erreur", "faux", "mauvais", "raté",
                               "mistake", "wrong", "bad", "failed"]):
        score += 1.0

    # ── Malus ────────────────────────────────────────────────────────────────

    # Démarrage faible
    for starter in _WEAK_STARTERS:
        if h.startswith(starter):
            score -= 3.0
            break

    # Mots marketing
    for word in _WEAK_WORDS:
        if word in h:
            score -= 1.5
            break

    # Trop long
    if len(words) > 10:
        score -= 2.0

    # Question faible (longue)
    if h.endswith("?") and len(words) > 7:
        score -= 1.5

    # Abstrait / philosophique
    for kw in ["liberté", "freedom", "succès", "success", "bonheur", "happiness",
               "transformation", "journey", "voyage", "parcours", "mindset"]:
        if kw in h:
            score -= 1.5
            break

    # Motivationnel
    for kw in ["prouve", "prove", "ose", "dare", "prêt à", "ready to",
               "time to", "commence", "start your", "begins with",
               "crois en", "believe in"]:
        if kw in h:
            score -= 1.5
            break

    # ── Bonus type-spécifiques ───────────────────────────────────────────────
    if idea_type:
        try:
            from utils.hook_templates import get_type_score_bonuses, is_tool_first
            for signal, bonus in get_type_score_bonuses(idea_type):
                if signal in h:
                    score += bonus
            # Pénalité si hook outil-first pour un type viewer-first
            if is_tool_first(hook, idea_type):
                score -= 2.0
        except ImportError:
            pass

    return round(max(0.0, min(10.0, score)), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Classification A / B / C
# ─────────────────────────────────────────────────────────────────────────────

def classify_abc(hook: str) -> str:
    """
    Assigne un hook à la variante A (simple), B (intrigue) ou C (interruption).
    Retourne 'A', 'B' ou 'C'.
    """
    h = hook.strip().lower()
    words = h.split()

    # C — interruption directe : perte, erreur, formulation brutale courte
    _c_signals = [
        "perds", "perd", "fuite", "coûte", "erreur", "faux",
        "lose", "losing", "costs you", "mistake", "wrong",
        "sans le voir", "without seeing", "déjà", "already",
    ]
    c_count = sum(1 for sig in _c_signals if sig in h)

    # B — intrigue : gap d'information, question, mystère
    _b_signals = [
        "?", "secret", "vraiment", "réel", "vrai", "real", "actually",
        "really", "pourquoi", "why", "et si", "imagine", "personne ne",
        "nobody", "personne n'", "they don't", "what if",
    ]
    b_count = sum(1 for sig in _b_signals if sig in h)

    # C si signal fort de perte/erreur (surtout si court)
    if c_count >= 2 or (c_count >= 1 and len(words) <= 6):
        return "C"
    # B si signal d'intrigue
    if b_count >= 2:
        return "B"
    if c_count >= 1:
        return "C"
    if b_count >= 1:
        return "B"
    return "A"


# ─────────────────────────────────────────────────────────────────────────────
# Historique de performances
# ─────────────────────────────────────────────────────────────────────────────

def load_history(path: str | Path | None = None) -> list[dict]:
    """Charge l'historique des hooks depuis un fichier JSON local."""
    p = Path(path) if path else HISTORY_PATH
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("hooks", [])
    except Exception:
        return []


def performance_score(entry: dict) -> float:
    """
    Score d'engagement pour une entrée d'historique.
    Poids : commentaires ×5 > likes ×2 > vues ×0.1
    Les commentaires sont le signal le plus fort (reach organique).
    """
    views    = float(entry.get("views", 0) or 0)
    likes    = float(entry.get("likes", 0) or 0)
    comments = float(entry.get("comments", 0) or 0)
    return comments * 5.0 + likes * 2.0 + views * 0.1


def learn_best_patterns(history: list[dict], top_n: int = 10) -> list[str]:
    """
    Retourne les top_n hooks les plus performants de l'historique.
    Triés par performance_score décroissant.
    """
    if not history:
        return []
    ranked = sorted(history, key=performance_score, reverse=True)
    return [e["text"] for e in ranked[:top_n] if e.get("text")]


def history_boost(hook: str, top_hooks: list[str],
                  boost_factor: float = 1.0) -> float:
    """
    Retourne un bonus (0–2.0) si le hook ressemble aux meilleurs hooks historiques.
    Basé sur le chevauchement de mots clés (pas du ML, simple et explicable).
    """
    if not top_hooks:
        return 0.0

    hook_words = set(hook.lower().split())
    if not hook_words:
        return 0.0

    max_overlap = 0.0
    for top in top_hooks[:5]:
        top_words = set(top.lower().split())
        if not top_words:
            continue
        overlap = len(hook_words & top_words) / max(len(hook_words), len(top_words))
        max_overlap = max(max_overlap, overlap)

    return round(min(2.0, max_overlap * boost_factor * 3.0), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Réécriture via Claude (optionnel — nécessite ANTHROPIC_API_KEY)
# ─────────────────────────────────────────────────────────────────────────────

_REWRITE_SYSTEM = """\
Tu réécris des hooks Instagram faibles en versions plus performantes.
Règles strictes :
- Max 8 mots
- Langage parlé, pas rédigé
- Concret : perte visible, argent, erreur, problème direct
- Commence de préférence par "Tu" pour interpeller
- Jamais : "Voici", "Comment", "Astuce", "Guide", "Découvrez"
- Modèles préférés :
  "Tu perds X sans le voir"
  "Ton argent fuit déjà"
  "Tu bosses. L'argent part."
Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après.
"""

_REWRITE_PROMPT = """\
Réécris ces hooks faibles. Pour chaque hook original, donne une version améliorée.

Hooks à réécrire :
{hooks_list}

Retourne ce JSON exact :
{{
  "rewrites": [
    {{"original": "<texte original>", "improved": "<nouvelle version, max 8 mots>"}},
    ...
  ]
}}
"""


def rewrite_weak_hooks_api(weak_hooks: list[str]) -> dict[str, str]:
    """
    Réécrit les hooks faibles via Claude en un seul appel API.
    Retourne {original_text: improved_text}.
    Retourne {} si pas de clé API ou si appel échoue.
    """
    if not weak_hooks:
        return {}

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {}

    try:
        import anthropic  # import lazy — pas obligatoire pour le reste du module

        hooks_list = "\n".join(f'- "{h}"' for h in weak_hooks)
        prompt = _REWRITE_PROMPT.format(hooks_list=hooks_list)

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=_REWRITE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Nettoyage robuste
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = re.sub(r",\s*\]", "]", raw)
        raw = re.sub(r",\s*\}", "}", raw)
        data = json.loads(raw)

        result = {}
        for item in data.get("rewrites", []):
            orig = item.get("original", "")
            improved = item.get("improved", "")
            if orig and improved and improved != orig:
                result[orig] = improved
        return result

    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline complet
# ─────────────────────────────────────────────────────────────────────────────

def optimize_hooks(
    hooks: list[dict],
    history_path: str | Path | None = None,
    use_api_rewrite: bool = False,
    idea_type: str = "",
) -> dict:
    """
    Pipeline complet d'optimisation des hooks.

    Input  : liste de dicts {"text": str, "score": int, ...} (format generate_viral_script)
    Output : {
        "ranked":      liste triée par total_score,
        "best":        meilleur hook,
        "variants":    {"A": hook_dict, "B": hook_dict, "C": hook_dict},
        "weak_count":  nb hooks faibles détectés,
        "rewritten":   nb hooks réécrits,
        "top_history": liste des 3 meilleurs hooks historiques,
    }

    use_api_rewrite : si True, appelle rewrite_weak_hooks_api pour les hooks faibles
    """
    # Chargement de l'historique
    history   = load_history(history_path)
    top_hooks = learn_best_patterns(history)

    # Réécriture des hooks faibles (batch, 1 appel API)
    rewrites: dict[str, str] = {}
    weak_texts = [h.get("text", "").strip() for h in hooks
                  if h.get("text") and is_weak_hook(h.get("text", ""))]
    if use_api_rewrite and weak_texts:
        rewrites = rewrite_weak_hooks_api(weak_texts)

    results = []
    weak_count    = 0
    rewrite_count = 0

    for h in hooks:
        original_text = h.get("text", "").strip()
        if not original_text:
            continue

        weak = is_weak_hook(original_text)
        if weak:
            weak_count += 1

        # Appliquer réécriture si disponible
        text = original_text
        if weak and original_text in rewrites:
            text = rewrites[original_text]
            rewrite_count += 1

        local_sc  = score_hook(text, idea_type=idea_type)
        boost     = history_boost(text, top_hooks)
        total_sc  = round(min(10.0, local_sc + boost), 1)
        variant   = classify_abc(text)

        results.append({
            "text":          text,
            "original_text": original_text,
            "local_score":   local_sc,
            "history_boost": boost,
            "total_score":   total_sc,
            "variant":       variant,
            "is_weak":       weak,
            "was_rewritten": (text != original_text),
            "api_score":     h.get("score", 0),
        })

    # Trier par score total décroissant
    results.sort(key=lambda x: x["total_score"], reverse=True)

    # Assigner le meilleur hook à chaque variante A/B/C
    variants: dict[str, dict | None] = {"A": None, "B": None, "C": None}
    for r in results:
        v = r["variant"]
        if variants[v] is None:
            variants[v] = r

    # Fallback : remplir les variantes vides avec le meilleur global
    for v in ("A", "B", "C"):
        if variants[v] is None and results:
            variants[v] = results[0]

    return {
        "ranked":      results,
        "best":        results[0] if results else None,
        "variants":    variants,
        "weak_count":  weak_count,
        "rewritten":   rewrite_count,
        "top_history": top_hooks[:3],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Enregistrement des performances
# ─────────────────────────────────────────────────────────────────────────────

def save_hook_result(
    text: str,
    views: int = 0,
    likes: int = 0,
    comments: int = 0,
    path: str | Path | None = None,
) -> None:
    """
    Ajoute un résultat de performance à l'historique JSON local.
    Crée le fichier si inexistant.
    """
    p = Path(path) if path else HISTORY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {"hooks": []}
    else:
        data = {"hooks": []}

    # Éviter les doublons exacts
    existing_texts = {e.get("text", "") for e in data["hooks"]}
    if text in existing_texts:
        # Mettre à jour l'entrée existante
        for e in data["hooks"]:
            if e.get("text") == text:
                e["views"]    = views
                e["likes"]    = likes
                e["comments"] = comments
                break
    else:
        data["hooks"].append({
            "text":     text,
            "views":    views,
            "likes":    likes,
            "comments": comments,
        })

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
