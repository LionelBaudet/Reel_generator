"""
agents/trend_fusion_agent.py — Merges social trends + news into unified intelligence.

Detects semantic overlap between Reddit/Google and RSS news.
Ranks by combined virality: engagement × coverage × emotional intensity.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime

log = logging.getLogger("trend_fusion_agent")


class TrendFusionAgent:
    """
    Merges social_trends.json + news_summary.json into trend_intelligence.json.

    Usage:
        agent = TrendFusionAgent(call_agent_fn)
        result = agent.fuse(social_trends, news_summary, lang="fr")
    """

    def __init__(self, call_agent_fn):
        self._call = call_agent_fn

    def fuse(
        self,
        social_trends: dict,
        news_summary: dict,
        lang: str = "fr",
        idea: str = "",
    ) -> dict:
        """
        Fuse social + news signals into ranked trend intelligence.
        Returns trend_intelligence dict (00_trend_intelligence.json schema).
        """
        t0 = time.time()

        s_trends = social_trends.get("trends", [])
        n_topics = news_summary.get("topics", [])

        if not s_trends and not n_topics:
            log.warning("[trend_fusion] No input data — returning empty result")
            return self._empty_result()

        # Build compact representation for Claude
        social_block = self._format_social(s_trends[:10])
        news_block   = self._format_news(n_topics[:5])

        idea_ctx = (
            f"The creator is building a reel about: '{idea}'. "
            f"Boost topics related to this theme."
            if idea.strip()
            else ""
        )
        lang_instruction = "Write all output in French." if lang == "fr" else "Write all output in English."

        task = (
            f"Today: {datetime.today().strftime('%Y-%m-%d')} | Language: {lang}\n"
            f"{idea_ctx}\n"
            f"{lang_instruction}\n\n"
            f"You are a trend intelligence analyst for a viral content studio.\n"
            f"Your job: fuse these two signal streams into a unified TOP 10 trend ranking.\n\n"
            f"FUSION RULES:\n"
            f"1. Topics appearing in BOTH sources get +3 coverage bonus (strongest signal)\n"
            f"2. High-engagement social trends (upvotes >1000) get priority\n"
            f"3. News with high virality_score (8+) are must-include\n"
            f"4. Detect semantic overlap — same event may have different wording\n"
            f"5. Discard pure celebrity/entertainment unless extreme cultural impact\n\n"
            f"SOCIAL TRENDS (Reddit + Google Trends):\n{social_block}\n\n"
            f"NEWS TOPICS (RSS):\n{news_block}\n\n"
            f"Return ONLY valid JSON (no markdown, no extra text):\n"
            f'{{\n'
            f'  "date": "{datetime.today().strftime("%Y-%m-%d")}",\n'
            f'  "top_topics": [\n'
            f'    {{\n'
            f'      "rank": 1,\n'
            f'      "topic": "punchy topic name (max 8 words)",\n'
            f'      "angle": "specific content angle for a reel creator (1 sentence)",\n'
            f'      "source_mix": ["reddit", "news"],\n'
            f'      "region": "France | Switzerland | Global | Tech/AI",\n'
            f'      "category": "economy | tech | politics | social",\n'
            f'      "virality_score": 9,\n'
            f'      "coverage_bonus": true,\n'
            f'      "evidence": "why this is viral right now (1 sentence)"\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n\n'
            f'Return exactly 10 topics. Rank 1 = most viral. No trailing commas.'
        )

        try:
            response = self._call("trend-fusion", task)
            result   = self._parse_json(response)
        except Exception as e:
            log.warning(f"[trend_fusion] Claude failed ({e}) — using heuristic merge")
            result = self._heuristic_merge(s_trends, n_topics)

        result.setdefault("date", datetime.today().strftime("%Y-%m-%d"))
        result.setdefault("top_topics", [])

        elapsed = time.time() - t0
        n = len(result["top_topics"])
        log.info(f"[trend_fusion] Done in {elapsed:.1f}s — {n} fused topics")
        if n:
            top = result["top_topics"][0]
            log.info(f"[trend_fusion] #1: '{top.get('topic','')}' (score={top.get('virality_score','?')})")
        return result

    # ── Formatting helpers ─────────────────────────────────────────────────────

    def _format_social(self, trends: list[dict]) -> str:
        lines = []
        for i, t in enumerate(trends):
            eng = t.get("engagement", {})
            up  = eng.get("upvotes", t.get("upvotes", 0))
            cmt = eng.get("comments", t.get("comments", 0))
            lines.append(
                f"[S{i+1}] {t.get('source','reddit').upper()} / {t.get('region','')} "
                f"| score={t.get('virality_score',0):.1f} | {up} upvotes {cmt} comments\n"
                f"    TOPIC: {t.get('title','')}\n"
                f"    ANGLE: {t.get('viral_angle','')}"
            )
        return "\n\n".join(lines)

    def _format_news(self, topics: list[dict]) -> str:
        lines = []
        for i, t in enumerate(topics):
            lines.append(
                f"[N{i+1}] {t.get('region','')} | score={t.get('virality_score',0)} | {t.get('impact','')}\n"
                f"    TITLE: {t.get('title','')}\n"
                f"    SUMMARY: {t.get('summary','')[:150]}"
            )
        return "\n\n".join(lines)

    # ── Heuristic fallback (no LLM) ────────────────────────────────────────────

    def _heuristic_merge(self, social: list[dict], news: list[dict]) -> dict:
        """Simple merge: interleave top social + news, deduplicate by keyword overlap."""
        seen_words: set[str] = set()
        merged = []

        def _words(t: dict) -> set[str]:
            text = (t.get("title") or t.get("topic") or "").lower()
            return set(re.findall(r"\w{4,}", text))

        def _is_dup(t: dict) -> bool:
            w = _words(t)
            if w & seen_words:
                return True
            seen_words.update(w)
            return False

        candidates = []
        for t in social[:10]:
            candidates.append(("reddit", t))
        for t in news[:5]:
            candidates.append(("news", t))

        rank = 1
        for source, t in candidates:
            if _is_dup(t) or rank > 10:
                continue
            title = t.get("title") or t.get("topic") or ""
            merged.append({
                "rank":           rank,
                "topic":          title[:60],
                "angle":          t.get("viral_angle") or t.get("summary", "")[:100],
                "source_mix":     [source],
                "region":         t.get("region", "Global"),
                "category":       t.get("category", "social"),
                "virality_score": t.get("virality_score", 5),
                "coverage_bonus": False,
                "evidence":       t.get("summary", "")[:100],
            })
            rank += 1

        return {"date": datetime.today().strftime("%Y-%m-%d"), "top_topics": merged}

    def _parse_json(self, text: str) -> dict:
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.search(r"(\{[\s\S]*\})", text)
        if m:
            raw = m.group(1)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
                return json.loads(cleaned)
        raise ValueError("No JSON found in response")

    def _empty_result(self) -> dict:
        return {
            "date":       datetime.today().strftime("%Y-%m-%d"),
            "top_topics": [],
            "_error":     "No input data for fusion.",
        }
