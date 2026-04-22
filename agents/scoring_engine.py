"""
agents/scoring_engine.py — Deterministic scoring for hooks and scripts.

Zero LLM calls. Wraps utils/hook_engine.py (score_hook, history_boost)
and adds script-level scoring. Used by PlannerAgent and OptimizationAgent
to rank variants without burning API budget.

Public API:
    engine = ScoringEngine(memory_manager)
    engine.score_hook(text, idea_type)           → float 0-10
    engine.score_script(script_dict)             → float 0-10
    engine.score_reel(hook, script, idea_type)   → dict with breakdown
    engine.rank_hooks(hooks_list)                → sorted list
    engine.rank_scripts(scripts_list)            → sorted list
    engine.select_top_hooks(hooks_list, n=3)     → top N hook dicts
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.memory_manager import MemoryManager

log = logging.getLogger(__name__)

# Weights for final reel score
_HOOK_WEIGHT = 0.45
_SCRIPT_WEIGHT = 0.55

# Script sub-score weights
_CLARITY_W = 0.30
_TENSION_W = 0.30
_CTA_W = 0.25
_STAT_W = 0.15

# Max words per scene type (from ScriptWriterAgent rules)
_MAX_WORDS = {"hook": 6, "pain": 6, "shift": 6, "solution": 6, "result": 6, "cta": 8}

# Patterns that signal a correctly-formed CTA
_CTA_GOOD_PATTERNS = [
    r"comment\s+\w+",          # "Comment GUIDE"
    r"save\s+this",            # "Save this"
    r"sauvegarde\s+",          # French save
    r"enregistre\s+",
    r"commente\s+\w+",         # French "Commente GUIDE"
    r"envoie\s+moi",
    r"dm\s+me",
    r"link\s+in\s+(bio|profile)",
    r"lien\s+en\s+bio",
]

# Tension arc: these transitions signal good narrative flow
_TENSION_SCENE_SIGNALS = {
    "pain":  ["perds", "lose", "encore", "still", "toujours", "perd", "fais"],
    "shift": ["mais", "but", "sauf", "except", "pourtant", "however", "seulement", "only"],
    "solution": ["claude", "chatgpt", "ia", "ai", "prompt", "outil", "tool", "système", "system"],
    "result": [
        r"\d",               # any digit = concrete result
        "min", "heure", "hour", "semaine", "week", "mois", "month",
        "€", "$", "chf", "fois", "time",
    ],
}


class ScoringEngine:
    """
    Deterministic scoring. Instantiate once, reuse across the pipeline.

    If a MemoryManager is provided, hook scores are boosted by historical
    pattern performance (via compute_style_boosts). Otherwise pure local scoring.
    """

    def __init__(self, memory_manager: "MemoryManager | None" = None):
        self._mem = memory_manager
        self._style_boosts: dict[str, float] = {}
        self._hook_texts: set[str] = set()

        if self._mem is not None:
            try:
                self._style_boosts = self._mem.compute_style_boosts()
                self._hook_texts = set(self._mem.get_all_hook_texts())
                log.debug(f"[scoring] Loaded {len(self._style_boosts)} pattern boosts, "
                          f"{len(self._hook_texts)} known hook texts")
            except Exception as e:
                log.warning(f"[scoring] Memory unavailable, running without boosts: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    def score_hook(self, text: str, idea_type: str = "") -> float:
        """
        Score a hook text 0–10. Uses hook_engine.score_hook() as base,
        adds memory pattern boost, penalises known weak hooks.
        """
        base = self._local_hook_score(text, idea_type)
        pattern = _detect_pattern(text)
        boost = self._style_boosts.get(pattern, 1.0)

        # Penalty: if identical to a known hook text (duplicate)
        dup_penalty = -0.5 if text in self._hook_texts else 0.0

        raw = base * boost + dup_penalty
        return round(max(0.0, min(10.0, raw)), 2)

    def score_script(self, script_dict: dict) -> float:
        """
        Score a script dict 0–10. Evaluates clarity, tension arc, CTA, stat presence.
        script_dict must have the structure from ScriptWriterAgent:
            {"hook": {"text": "..."}, "pain": {"text": "..."}, ...}
        """
        clarity = self._clarity_score(script_dict)
        tension = self._tension_arc_score(script_dict)
        cta = self._cta_score(script_dict)
        stat = self._stat_score(script_dict)

        raw = (
            clarity * _CLARITY_W
            + tension * _TENSION_W
            + cta * _CTA_W
            + stat * _STAT_W
        )
        return round(max(0.0, min(10.0, raw * 10)), 2)

    def score_reel(
        self,
        hook_text: str,
        script_dict: dict,
        idea_type: str = "",
    ) -> dict:
        """
        Full reel score with dimension breakdown.

        Returns:
            {
                "overall": 8.4,
                "hook_score": 9.1,
                "script_score": 7.9,
                "clarity": 8.0,
                "tension_arc": 8.5,
                "cta_quality": 7.0,
                "stat_presence": 9.0,
                "pattern": "loss",
                "pattern_boost": 1.2,
            }
        """
        hook_score = self.score_hook(hook_text, idea_type)
        script_score = self.score_script(script_dict)
        overall = round(hook_score * _HOOK_WEIGHT + script_score * _SCRIPT_WEIGHT, 2)

        # Sub-scores for the breakdown
        clarity = self._clarity_score(script_dict)
        tension = self._tension_arc_score(script_dict)
        cta = self._cta_score(script_dict)
        stat = self._stat_score(script_dict)
        pattern = _detect_pattern(hook_text)
        boost = self._style_boosts.get(pattern, 1.0)

        return {
            "overall": overall,
            "hook_score": hook_score,
            "script_score": script_score,
            "clarity": round(clarity * 10, 2),
            "tension_arc": round(tension * 10, 2),
            "cta_quality": round(cta * 10, 2),
            "stat_presence": round(stat * 10, 2),
            "pattern": pattern,
            "pattern_boost": boost,
        }

    def rank_hooks(self, hooks: list[dict]) -> list[dict]:
        """
        Score and sort a list of hook dicts in-place (desc).
        Each dict must have a "text" key. Adds "score" and "pattern" in-place.
        Returns sorted copy.
        """
        scored = []
        for h in hooks:
            text = h.get("text", "")
            idea_type = h.get("idea_type", "")
            s = self.score_hook(text, idea_type)
            scored.append({**h, "score": s, "pattern": _detect_pattern(text)})
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def rank_scripts(self, scripts: list[dict]) -> list[dict]:
        """
        Score and sort a list of script dicts (each has a "script" sub-dict + "hook_text").
        Returns sorted copy with "score" added.
        """
        scored = []
        for s in scripts:
            script_dict = s.get("script", {})
            hook_text = s.get("hook_text", "")
            idea_type = s.get("idea_type", "")
            breakdown = self.score_reel(hook_text, script_dict, idea_type)
            scored.append({**s, "score": breakdown["overall"], "score_breakdown": breakdown})
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def select_top_hooks(self, hooks: list[dict], n: int = 3) -> list[dict]:
        """Return the top N hooks by score."""
        return self.rank_hooks(hooks)[:n]

    # ── Private scoring sub-functions ─────────────────────────────────────────

    def _local_hook_score(self, text: str, idea_type: str) -> float:
        """Delegate to hook_engine.score_hook if available, else inline fallback."""
        try:
            from utils.hook_engine import score_hook
            return float(score_hook(text, idea_type))
        except ImportError:
            return self._inline_hook_score(text)

    def _inline_hook_score(self, text: str) -> float:
        """
        Lightweight inline fallback when hook_engine is unavailable.
        Mirrors the core logic from hook_engine.score_hook().
        """
        h = text.strip().lower()
        words = h.split()
        score = 5.0

        # Bonuses
        if re.search(r"\btu\b|\byou\b", h):
            score += 1.5
        if re.search(r"\d+", h):
            score += 1.5
        if any(kw in h for kw in ["perds", "lose", "losing", "fuit", "fuite"]):
            score += min(3.0, 1.5)
        if any(kw in h for kw in ["chf", "€", "$", "argent", "money", "salaire"]):
            score += 1.5
        if len(words) <= 6:
            score += 1.0
        elif len(words) <= 8:
            score += 0.5

        # Penalties
        _weak_starters = ["comment ", "voici ", "guide ", "astuce", "how to ", "here's ", "here is"]
        for starter in _weak_starters:
            if h.startswith(starter):
                score -= 3.0
                break
        if len(words) > 10:
            score -= 2.0

        return round(max(0.0, min(10.0, score)), 2)

    def _clarity_score(self, script: dict) -> float:
        """
        0.0–1.0 — penalises scenes with too many words, passive voice, jargon.
        """
        if not script:
            return 0.3

        total_penalty = 0.0
        scene_count = 0

        for scene_type, max_w in _MAX_WORDS.items():
            scene = script.get(scene_type, {})
            text = scene.get("text", "") if isinstance(scene, dict) else str(scene)
            if not text:
                continue
            scene_count += 1
            words = text.split()
            wc = len(words)

            # Over-length penalty (proportional)
            if wc > max_w:
                total_penalty += min(1.0, (wc - max_w) / max_w)

            # Passive voice signal (is/are/was/were + past participle)
            if re.search(r"\b(is|are|was|were|est|sont|était|étaient)\b.{1,30}\b\w+[eé]s?\b", text, re.I):
                total_penalty += 0.3

        if scene_count == 0:
            return 0.3

        avg_penalty = total_penalty / scene_count
        return round(max(0.0, 1.0 - avg_penalty), 3)

    def _tension_arc_score(self, script: dict) -> float:
        """
        0.0–1.0 — checks that pain/shift/solution/result form a narrative arc.
        Each scene scores 0.25 if it contains at least one arc signal.
        """
        score = 0.0
        for scene_type, signals in _TENSION_SCENE_SIGNALS.items():
            scene = script.get(scene_type, {})
            text = (scene.get("text", "") if isinstance(scene, dict) else str(scene)).lower()
            if any(re.search(sig, text) for sig in signals):
                score += 0.25
        return round(score, 3)

    def _cta_score(self, script: dict) -> float:
        """
        0.0–1.0 — checks CTA scene text matches a good engagement pattern.
        1.0 = strong action-trigger CTA
        0.5 = present but weak
        0.0 = missing or purely informational
        """
        cta = script.get("cta", {})
        text = (cta.get("text", "") if isinstance(cta, dict) else str(cta)).lower()
        if not text:
            return 0.0

        for pattern in _CTA_GOOD_PATTERNS:
            if re.search(pattern, text, re.I):
                return 1.0

        # Partial credit for containing a call word
        if any(w in text for w in ["follow", "save", "like", "share", "link", "guide",
                                    "suis", "abonne", "lien", "clique", "swipe"]):
            return 0.5

        return 0.2

    def _stat_score(self, script: dict) -> float:
        """
        0.0–1.0 — rewards concrete numbers anywhere in the script.
        Two or more scenes with a number → 1.0.
        One scene → 0.6. Zero → 0.1.
        """
        scenes_with_numbers = 0
        for scene_type in _MAX_WORDS:
            scene = script.get(scene_type, {})
            text = scene.get("text", "") if isinstance(scene, dict) else str(scene)
            if re.search(r"\d", text):
                scenes_with_numbers += 1

        if scenes_with_numbers >= 2:
            return 1.0
        elif scenes_with_numbers == 1:
            return 0.6
        return 0.1


# ── Module-level helpers ──────────────────────────────────────────────────────

def _detect_pattern(text: str) -> str:
    """
    Classify a hook text into one of the known PATTERN_TYPES.
    Used to look up style_boosts from memory.
    """
    h = text.strip().lower()

    # Tool-first detection
    _tool_prefixes = ["ce prompt", "chatgpt", "claude ", "l'ia", "this prompt", "the ai"]
    if any(h.startswith(p) for p in _tool_prefixes):
        return "generic"

    # Weak starters
    _weak = ["comment ", "voici ", "guide ", "astuce", "how to ", "here's "]
    if any(h.startswith(w) for w in _weak):
        return "generic"

    # Loss / perds
    if any(kw in h for kw in ["perds", "perd", "fuite", "fuit", "lose", "losing", "lost"]):
        return "loss"

    # Contrast (arrow or "avant/après" or "before/after")
    if any(kw in h for kw in ["→", "->", "avant", "before", "après", "after"]) or (
        "." in h and len(h.split(".")) >= 2
    ):
        return "contrast"

    # Social tension ("ton patron", "ils croient")
    if any(kw in h for kw in ["patron", "boss", "ils", "they", "croient", "think"]):
        return "social_tension"

    # User pain (interpellation + verb)
    if re.search(r"\btu\b|\byou\b", h):
        return "user_pain"

    # Transformation (first person + verb of change)
    if re.search(r"\bj'ai\b|\bi've\b|\bi\s+cut\b|\bj'ai\s+\w+é\b", h):
        return "transformation"

    # Discovery / hidden truth
    if any(kw in h for kw in ["sans le voir", "without", "caché", "hidden", "invisible"]):
        return "hidden_truth"

    # Number-led
    if re.match(r"^\d", h):
        return "time_contrast"

    return "generic"
