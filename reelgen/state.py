"""
reelgen/state.py — Global AppState for the Reflex app.
All pipeline calls go through generate() background event.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import reflex as rx

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class AppState(rx.State):

    # ── Navigation ─────────────────────────────────────────────────────────────
    page: str = "generator"

    # ── Form ───────────────────────────────────────────────────────────────────
    topic: str = ""
    language: str = "fr"
    mode: str = "trend"

    # ── UI ─────────────────────────────────────────────────────────────────────
    loading: bool = False
    error: str = ""

    # ── Results ────────────────────────────────────────────────────────────────
    hooks: list[dict[str, Any]] = []
    best_hook: str = ""
    script: dict[str, Any] = {}
    caption: str = ""
    quality_score: float = 0.0
    viral_prediction: dict[str, Any] = {}
    run_id: str = ""

    # ── Computed vars (script scenes) ──────────────────────────────────────────

    @rx.var
    def has_results(self) -> bool:
        return bool(self.script or self.hooks)

    @rx.var
    def script_hook(self) -> str:
        return self.script.get("hook", "")

    @rx.var
    def script_tension(self) -> str:
        return self.script.get("tension", "")

    @rx.var
    def script_shift(self) -> str:
        return self.script.get("shift", "")

    @rx.var
    def script_proof(self) -> str:
        return self.script.get("proof", "")

    @rx.var
    def script_solution(self) -> str:
        return self.script.get("solution", "")

    @rx.var
    def script_result(self) -> str:
        return self.script.get("result", "")

    @rx.var
    def script_cta(self) -> str:
        return self.script.get("cta", "")

    @rx.var
    def viral_scroll_stop(self) -> int:
        return int(self.viral_prediction.get("scroll_stop", 0))

    @rx.var
    def viral_watch_time(self) -> int:
        return int(self.viral_prediction.get("watch_time", 0))

    @rx.var
    def viral_shareability(self) -> int:
        return int(self.viral_prediction.get("shareability", 0))

    @rx.var
    def viral_comment(self) -> int:
        return int(self.viral_prediction.get("comment_trigger", 0))

    @rx.var
    def viral_relevance(self) -> int:
        return int(self.viral_prediction.get("relevance", 0))

    @rx.var
    def viral_global(self) -> float:
        return float(self.viral_prediction.get("global_score", 0))

    @rx.var
    def score_color(self) -> str:
        if self.quality_score >= 8:
            return "#10B981"
        if self.quality_score >= 6:
            return "#F59E0B"
        return "#EF4444"

    @rx.var
    def mode_label(self) -> str:
        return {
            "trend":    "Tendances (Reddit + RSS)",
            "social":   "Social only (Reddit)",
            "news":     "News only (RSS)",
            "standard": "Standard",
        }.get(self.mode, self.mode)

    # ── Setters ────────────────────────────────────────────────────────────────

    def set_topic(self, value: str):
        self.topic = value

    def set_language(self, value: str):
        self.language = value

    def set_mode(self, value: str):
        self.mode = value

    def nav(self, page: str):
        self.page = page

    def reset(self):
        self.hooks = []
        self.best_hook = ""
        self.script = {}
        self.caption = ""
        self.quality_score = 0.0
        self.viral_prediction = {}
        self.error = ""
        self.page = "generator"

    # ── Pipeline ───────────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def generate(self):
        async with self:
            self.loading = True
            self.error = ""
            self.hooks = []
            self.script = {}
            self.caption = ""
            self.viral_prediction = {}

        try:
            from orchestrate import run_full_pipeline

            t, l, m = self.topic, self.language, self.mode

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_full_pipeline(
                    topic=t,
                    trend_mode=(m == "trend"),
                    social_mode=(m == "social"),
                    news_mode=(m == "news"),
                    lang=l,
                    skip_video=True,
                    ideas_only=False,
                ),
            )

            async with self:
                self.hooks = result.get("hooks") or []
                self.best_hook = result.get("best_hook") or ""
                raw = result.get("script") or {}
                # Unwrap nested {"script": {...}} if present
                self.script = raw.get("script", raw) if isinstance(raw, dict) else {}
                self.caption = result.get("caption") or ""
                self.quality_score = float(result.get("score") or 0)
                self.run_id = result.get("run_id") or ""
                self.error = result.get("error") or ""
                # Viral prediction may come from script JSON via sv_result
                self.viral_prediction = (
                    result.get("viral_prediction") or {}
                )
                if not self.error:
                    self.page = "results"

        except Exception as exc:
            async with self:
                self.error = str(exc)
        finally:
            async with self:
                self.loading = False
