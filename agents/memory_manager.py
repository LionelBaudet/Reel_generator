"""
agents/memory_manager.py — Persistent memory layer for the reel pipeline.

Single class MemoryManager handles all reads/writes to memory/*.json.
Deterministic — zero LLM calls. Thread-safe via threading.Lock per file.

Files managed:
    memory/hooks_performance.json   All hooks + engagement + local scores
    memory/best_hooks.json          Top hooks per idea_type (auto-rebuilt)
    memory/reel_scores.json         Per-run records
    memory/failed_reels.json        Failures with error context
    memory/topic_performance.json   Per-topic aggregates
    memory/strategy_log.json        Full planner decision audit trail
    memory/trend_performance.json   Trend-mode run history (sources, scores, hooks)
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent.parent / "memory"

_FILES = {
    "hooks":    "hooks_performance.json",
    "best":     "best_hooks.json",
    "scores":   "reel_scores.json",
    "failures": "failed_reels.json",
    "topics":   "topic_performance.json",
    "strategy": "strategy_log.json",
    "trends":   "trend_performance.json",
}

# Number of top hooks stored per idea_type in best_hooks.json
_TOP_N = 5


class MemoryManager:
    """
    Central memory layer. Instantiate once per pipeline run.

    Usage:
        mem = MemoryManager()
        best = mem.read_best_hooks("career_work", top_n=3)
        mem.update_hook_performance("Tu perds 1h", 8.8, "before_after_time", "user_pain", "run_123")
    """

    def __init__(self, memory_dir: Path | None = None):
        self._dir = Path(memory_dir) if memory_dir else MEMORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {k: threading.Lock() for k in _FILES}
        self._cache: dict[str, dict] = {}

    # ── Public read API ───────────────────────────────────────────────────────

    def read_best_hooks(self, idea_type: str, top_n: int = 5) -> list[dict]:
        """
        Return top N hooks for a given idea_type, sorted by avg_score desc.
        Falls back to cross-type top hooks if the type has < top_n entries.
        """
        data = self._load("best")
        by_type: dict = data.get("by_type", {})
        hooks = list(by_type.get(idea_type, []))

        if len(hooks) < top_n:
            # Supplement with high-scoring hooks from other types
            all_hooks = self._get_all_hooks_sorted()
            seen = {h["text"] for h in hooks}
            for h in all_hooks:
                if h["text"] not in seen:
                    hooks.append(h)
                    seen.add(h["text"])
                if len(hooks) >= top_n:
                    break

        return hooks[:top_n]

    def read_topic_performance(self, topic: str) -> dict:
        """
        Return aggregated performance data for a topic.
        Returns empty dict if topic not seen before.
        """
        data = self._load("topics")
        key = _normalize_topic(topic)
        return data.get("topics", {}).get(key, {})

    def get_failed_patterns(self) -> list[str]:
        """
        Return list of hook patterns that consistently failed (avg_score < 4.0
        with at least 3 samples). Used by PlannerAgent to inject 'avoid' hints.
        """
        data = self._load("hooks")
        pattern_scores: dict[str, list[float]] = defaultdict(list)
        for h in data.get("hooks", []):
            if h.get("pattern") and h.get("avg_score") is not None:
                pattern_scores[h["pattern"]].append(h["avg_score"])

        failed = []
        for pattern, scores in pattern_scores.items():
            if len(scores) >= 3 and (sum(scores) / len(scores)) < 4.0:
                failed.append(pattern)
        return failed

    def get_recent_scores(self, n: int = 10) -> list[float]:
        """Return the last N overall optimization scores, oldest first."""
        data = self._load("scores")
        runs = data.get("runs", [])
        return [r["optimization_score"] for r in runs[-n:] if "optimization_score" in r]

    def compute_style_boosts(self) -> dict[str, float]:
        """
        Analyze hooks_performance to derive pattern boost multipliers.

        Returns a dict like:
            {"contrast": 1.3, "loss": 1.2, "user_pain": 1.1, "generic": 0.6}

        Boost = (pattern_avg_score / global_avg_score).
        Clamped to [0.5, 1.5]. Patterns with < 2 samples get boost = 1.0.
        """
        data = self._load("hooks")
        hooks = data.get("hooks", [])
        if not hooks:
            return {}

        pattern_scores: dict[str, list[float]] = defaultdict(list)
        for h in hooks:
            pattern = h.get("pattern", "generic")
            score = h.get("avg_score")
            if score is not None:
                pattern_scores[pattern].append(score)

        all_scores = [s for scores in pattern_scores.values() for s in scores]
        global_avg = sum(all_scores) / len(all_scores) if all_scores else 5.0

        boosts: dict[str, float] = {}
        for pattern, scores in pattern_scores.items():
            if len(scores) < 2:
                boosts[pattern] = 1.0
            else:
                raw = (sum(scores) / len(scores)) / global_avg
                boosts[pattern] = round(max(0.5, min(1.5, raw)), 3)

        return boosts

    def get_all_hook_texts(self) -> list[str]:
        """Return all known hook texts (for deduplication in generation)."""
        data = self._load("hooks")
        return [h["text"] for h in data.get("hooks", [])]

    def get_strategy_summary(self) -> dict:
        """
        Return a compact summary for PlannerAgent consumption:
            recent_avg_score, best_patterns, worst_patterns, topic_count
        """
        recent = self.get_recent_scores(5)
        boosts = self.compute_style_boosts()
        failed = self.get_failed_patterns()
        topics = self._load("topics").get("topics", {})

        sorted_boosts = sorted(boosts.items(), key=lambda x: x[1], reverse=True)
        best_patterns = [p for p, _ in sorted_boosts[:3] if boosts.get(p, 1.0) > 1.05]
        worst_patterns = [p for p, _ in sorted_boosts[-3:] if boosts.get(p, 1.0) < 0.95]

        return {
            "recent_avg_score": round(sum(recent) / len(recent), 2) if recent else None,
            "recent_run_count": len(recent),
            "best_patterns": best_patterns,
            "worst_patterns": worst_patterns,
            "failed_patterns": failed,
            "style_boosts": boosts,
            "known_topic_count": len(topics),
        }

    # ── Public write API ──────────────────────────────────────────────────────

    def update_hook_performance(
        self,
        hook_text: str,
        score: float,
        idea_type: str,
        pattern: str,
        run_id: str,
        selected_as_best: bool = False,
        language: str = "fr",
    ) -> None:
        """
        Record a hook generation event. Upserts by hook text.
        Updates avg_score as running weighted average (recent runs weighted 1.5x).
        Rebuilds best_hooks.json after every update.
        """
        with self._locks["hooks"]:
            data = self._load("hooks", bypass_cache=True)
            hooks: list[dict] = data.get("hooks", [])

            # Find existing entry or create new one
            existing = next((h for h in hooks if h["text"] == hook_text), None)
            if existing is None:
                entry: dict[str, Any] = {
                    "text": hook_text,
                    "idea_type": idea_type,
                    "pattern": pattern,
                    "language": language,
                    "raw_engagement": None,
                    "engagement_score": None,
                    "local_score": None,
                    "avg_score": score,
                    "times_generated": 1,
                    "times_selected": 1 if selected_as_best else 0,
                    "runs": [{"run_id": run_id, "score": score, "selected_as_best": selected_as_best}],
                }
                hooks.append(entry)
            else:
                # Weighted running average: give recent runs 1.5x weight
                existing_runs = existing.get("runs", [])
                all_scores = [r["score"] for r in existing_runs]
                # New score counts as 1.5 samples
                total_weight = len(all_scores) + 1.5
                weighted_sum = sum(all_scores) + score * 1.5
                existing["avg_score"] = round(weighted_sum / total_weight, 3)
                existing["times_generated"] = existing.get("times_generated", 0) + 1
                if selected_as_best:
                    existing["times_selected"] = existing.get("times_selected", 0) + 1
                existing["runs"].append(
                    {"run_id": run_id, "score": score, "selected_as_best": selected_as_best}
                )
                # Cap run history at 50 entries to keep file size bounded
                if len(existing["runs"]) > 50:
                    existing["runs"] = existing["runs"][-50:]

            data["hooks"] = hooks
            self._save("hooks", data)
            self._invalidate_cache("hooks")

        # Rebuild best_hooks index
        self._rebuild_best_hooks()

    def update_reel_record(self, run_id: str, record: dict) -> None:
        """
        Append a completed run record to reel_scores.json.

        record should include at minimum:
            topic, idea_type, best_hook, optimization_score, video_path
        """
        with self._locks["scores"]:
            data = self._load("scores", bypass_cache=True)
            runs: list = data.get("runs", [])
            runs.append({
                "run_id": run_id,
                "date": datetime.today().strftime("%Y-%m-%d"),
                **record,
            })
            data["runs"] = runs
            self._save("scores", data)
            self._invalidate_cache("scores")

    def update_topic_stats(
        self,
        topic: str,
        score: float,
        angle: str = "",
        emotion: str = "",
        idea_type: str = "",
    ) -> None:
        """
        Update aggregated stats for a topic. Computes running averages.
        """
        with self._locks["topics"]:
            data = self._load("topics", bypass_cache=True)
            topics: dict = data.get("topics", {})
            key = _normalize_topic(topic)

            if key not in topics:
                topics[key] = {
                    "runs": 1,
                    "avg_score": score,
                    "best_score": score,
                    "best_angle": angle,
                    "best_emotion": emotion,
                    "best_idea_type": idea_type,
                    "score_history": [score],
                }
            else:
                t = topics[key]
                t["runs"] = t.get("runs", 0) + 1
                history = t.get("score_history", [t.get("avg_score", score)])
                history.append(score)
                if len(history) > 20:
                    history = history[-20:]
                t["score_history"] = history
                t["avg_score"] = round(sum(history) / len(history), 3)
                if score > t.get("best_score", 0):
                    t["best_score"] = score
                    t["best_angle"] = angle
                    t["best_emotion"] = emotion
                    t["best_idea_type"] = idea_type

            data["topics"] = topics
            self._save("topics", data)
            self._invalidate_cache("topics")

    def log_failure(self, run_id: str, error: str, context: dict | None = None) -> None:
        """Record a failed pipeline run for diagnostic and avoidance purposes."""
        with self._locks["failures"]:
            data = self._load("failures", bypass_cache=True)
            failures: list = data.get("failures", [])
            failures.append({
                "run_id": run_id,
                "date": datetime.today().strftime("%Y-%m-%d"),
                "error": error[:500],
                "context": context or {},
            })
            # Keep last 50 failures only
            data["failures"] = failures[-50:]
            self._save("failures", data)
            self._invalidate_cache("failures")

    def update_trend_performance(self, run_id: str, record: dict) -> None:
        """
        Append a trend-mode run record to trend_performance.json.

        Expected record fields (all optional except topic):
            topic, sources, virality_score, reel_score, hook_used, angle_type,
            trend_mode (trend | news | social), date
        """
        with self._locks["trends"]:
            data = self._load("trends", bypass_cache=True)
            entries: list = data.get("trends", [])
            entries.append({
                "run_id":         run_id,
                "date":           datetime.today().strftime("%Y-%m-%d"),
                **record,
            })
            # Keep last 100 trend runs
            data["trends"] = entries[-100:]
            self._save("trends", data)
            self._invalidate_cache("trends")

    def get_top_trend_topics(self, n: int = 5) -> list[dict]:
        """Return top N trend topics by reel_score from trend_performance.json."""
        data = self._load("trends")
        entries = data.get("trends", [])
        scored = [e for e in entries if e.get("reel_score") is not None]
        scored.sort(key=lambda x: x.get("reel_score", 0), reverse=True)
        return scored[:n]

    def log_strategy_decision(self, run_id: str, decision: dict) -> None:
        """Append a PlannerAgent decision to the strategy audit log."""
        with self._locks["strategy"]:
            data = self._load("strategy", bypass_cache=True)
            decisions: list = data.get("decisions", [])
            decisions.append({
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                **decision,
            })
            data["decisions"] = decisions
            self._save("strategy", data)
            self._invalidate_cache("strategy")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load(self, key: str, bypass_cache: bool = False) -> dict:
        """Load a memory file. Returns empty skeleton if file missing."""
        if not bypass_cache and key in self._cache:
            return self._cache[key]

        path = self._dir / _FILES[key]
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not bypass_cache:
                    self._cache[key] = data
                return data
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"[memory] Failed to load {path.name}: {e}")

        # Return minimal skeleton
        skeletons = {
            "hooks":    {"_meta": {}, "hooks": []},
            "best":     {"_meta": {}, "by_type": {}, "top_patterns": []},
            "scores":   {"_meta": {}, "runs": []},
            "failures": {"_meta": {}, "failures": []},
            "topics":   {"_meta": {}, "topics": {}},
            "strategy": {"_meta": {}, "decisions": []},
            "trends":   {"_meta": {}, "trends": []},
        }
        return skeletons.get(key, {})

    def _save(self, key: str, data: dict) -> None:
        path = self._dir / _FILES[key]
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            log.error(f"[memory] Failed to save {path.name}: {e}")

    def _invalidate_cache(self, key: str) -> None:
        self._cache.pop(key, None)

    def _get_all_hooks_sorted(self) -> list[dict]:
        """All hooks from hooks_performance, sorted by avg_score desc."""
        data = self._load("hooks")
        hooks = [
            {"text": h["text"], "pattern": h.get("pattern", ""), "avg_score": h.get("avg_score", 0)}
            for h in data.get("hooks", [])
            if h.get("avg_score") is not None
        ]
        return sorted(hooks, key=lambda h: h["avg_score"], reverse=True)

    def _rebuild_best_hooks(self) -> None:
        """
        Rebuild best_hooks.json from hooks_performance.json.
        Called automatically after every update_hook_performance().
        """
        with self._locks["best"]:
            data = self._load("hooks", bypass_cache=True)
            hooks = data.get("hooks", [])

            # Group by idea_type
            by_type: dict[str, list[dict]] = defaultdict(list)
            for h in hooks:
                idea_type = h.get("idea_type", "educational_explainer")
                by_type[idea_type].append({
                    "text": h["text"],
                    "pattern": h.get("pattern", ""),
                    "avg_score": h.get("avg_score", 0),
                })

            # Sort each bucket and keep top _TOP_N
            best_by_type = {
                t: sorted(hs, key=lambda h: h["avg_score"], reverse=True)[:_TOP_N]
                for t, hs in by_type.items()
            }

            # Also rebuild top_patterns
            pattern_scores: dict[str, list[float]] = defaultdict(list)
            for h in hooks:
                p = h.get("pattern", "generic")
                s = h.get("avg_score")
                if s is not None:
                    pattern_scores[p].append(s)

            top_patterns = sorted(
                [
                    {
                        "pattern": p,
                        "avg_score": round(sum(scores) / len(scores), 2),
                        "sample_count": len(scores),
                    }
                    for p, scores in pattern_scores.items()
                ],
                key=lambda x: x["avg_score"],
                reverse=True,
            )

            best_data = self._load("best", bypass_cache=True)
            best_data["by_type"] = best_by_type
            best_data["top_patterns"] = top_patterns
            best_data["_meta"] = {
                **best_data.get("_meta", {}),
                "last_rebuilt": datetime.today().strftime("%Y-%m-%d"),
            }
            self._save("best", best_data)
            self._invalidate_cache("best")


# ── Module-level helpers ──────────────────────────────────────────────────────

def _normalize_topic(topic: str) -> str:
    """
    Normalize a topic string for use as a dict key.
    'AI Salary Negotiation' → 'ai_salary_negotiation'
    """
    topic = topic.lower().strip()
    topic = re.sub(r"[^\w\s]", "", topic)
    topic = re.sub(r"\s+", "_", topic)
    return topic[:80]
