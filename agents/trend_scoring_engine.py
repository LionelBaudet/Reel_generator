"""
agents/trend_scoring_engine.py — Deterministic trend scorer. Zero LLM calls.

Scores raw articles / Reddit posts / Google Trends items on viral potential.
Used as a pre-filter before any Claude call to reduce tokens and latency.

Score formula (0–10):
    keyword_score   (0–4)   — keyword density: AI, crise, prix, emploi, argent…
    engagement_score (0–3)  — log-scaled upvotes + weighted comments
    novelty_score   (0–2)   — recency: <4h=2, <24h=1.5, <72h=0.5, else 0
    category_boost  (0–1)   — tech/economy=1, politics=0.5, other=0
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any


# ── Keyword scoring ────────────────────────────────────────────────────────────

# High-value keywords by weight (1 = strong, 0.5 = moderate)
_KEYWORDS: dict[str, float] = {
    # AI / tech (weight 1.0)
    "artificial intelligence": 1.0, "intelligence artificielle": 1.0,
    "chatgpt": 1.0, "gpt": 1.0, "openai": 1.0, "claude": 1.0, "llm": 1.0,
    "automation": 1.0, "automatisation": 1.0, "robot": 0.8,
    # Economy / money (weight 1.0)
    "crise": 1.0, "crisis": 1.0, "crash": 1.0, "effondrement": 1.0, "collapse": 1.0,
    "hausse": 0.9, "rise": 0.8, "surge": 0.9, "spike": 0.9,
    "baisse": 0.8, "fall": 0.7, "drop": 0.7, "chute": 0.8,
    "récession": 1.0, "recession": 1.0, "inflation": 0.9,
    "salaire": 0.8, "salary": 0.8, "wage": 0.8, "revenu": 0.8, "income": 0.7,
    "argent": 0.8, "money": 0.8, "prix": 0.8, "price": 0.7, "coût": 0.7, "cost": 0.6,
    "licenciement": 1.0, "layoff": 1.0, "fired": 0.9, "chômage": 1.0, "unemployment": 1.0,
    # Fear / opportunity
    "risque": 0.8, "risk": 0.7, "danger": 0.9, "menace": 0.9, "threat": 0.8,
    "opportunité": 0.8, "opportunity": 0.7, "profit": 0.7, "gain": 0.6,
    "perte": 0.8, "loss": 0.7, "faillite": 1.0, "bankruptcy": 1.0,
    # Controversy / social
    "scandale": 0.9, "scandal": 0.9, "fraude": 0.9, "fraud": 0.9,
    "coupure": 0.7, "grève": 0.8, "strike": 0.8, "manifestation": 0.7,
    "censure": 0.8, "censorship": 0.8, "interdit": 0.7, "banned": 0.8,
    # Swiss / France specific
    "suisse": 0.6, "switzerland": 0.6, "bns": 0.8, "snb": 0.8,
    "france": 0.5, "macron": 0.7, "élection": 0.7, "election": 0.7,
    "ubs": 0.8, "crédit suisse": 1.0, "credit suisse": 1.0,
}

_CATEGORY_BOOST = {
    "tech":      1.0,
    "Tech/AI":   1.0,
    "economy":   1.0,
    "economic":  1.0,
    "finance":   1.0,
    "politics":  0.5,
    "political": 0.5,
    "social":    0.4,
    "global":    0.3,
    "Global":    0.3,
    "Switzerland": 0.5,
    "France":    0.4,
}

# Max accumulated keyword weight before we cap at 4.0
_KW_CAP = 4.0

# Penalty keywords — subtract from score after keyword boost
# US-only political content with no European impact
_US_POLITICAL: list[str] = [
    "maga", "trump", "gop", "republican party", "democrat party",
    "congress", "senate", "white house", "biden", "harris",
]
# Celebrity/gossip without structural stakes
_CELEBRITY_GOSSIP: list[str] = [
    "unmasked", "exposed as", "fake persona", "influencer drama",
    "kardashian", "celebrity", "viral meme", "tiktok drama",
]
_US_ONLY_PENALTY      = -1.5
_CELEBRITY_PENALTY    = -1.0
_LOCAL_ACCIDENT_PENALTY = -2.0   # local fait-divers: no creator angle possible

# German/Italian language signals (hard derank)
_NON_FRENCH_LANG: list[str] = [
    "unfall", "arbeitsunfall", "verkehrsunfall", "tödlich",
    "der ", "die ", "das ", "und ", "von ", "mit ", "wurde",
    "incidente", "morto", "ferito",
]


class TrendScoringEngine:
    """
    Pure Python scorer. No I/O, no external deps, no LLM.

    Usage:
        scorer = TrendScoringEngine()
        scored = scorer.score_batch(articles)   # adds "virality_score" to each
        top10  = scorer.top_n(scored, 10)
    """

    def score_item(self, item: dict[str, Any]) -> float:
        """
        Score a single trend/article item.

        Accepts any dict with common fields from RSS / Reddit / Google Trends:
            title, summary/description/selftext, pub_date/created_utc,
            upvotes/score, comments/num_comments, category/region/flair
        Returns float 0.0–10.0
        """
        text = self._extract_text(item)

        kw_score   = min(self._keyword_score(text), _KW_CAP)
        eng_score  = self._engagement_score(item)
        nov_score  = self._novelty_score(item)
        cat_boost  = self._category_boost(item)

        penalty   = self._penalty_score(text)
        raw = kw_score + eng_score + nov_score + cat_boost + penalty
        return round(max(min(raw, 10.0), 0.0), 2)

    def score_batch(self, items: list[dict]) -> list[dict]:
        """
        Add 'virality_score' field to each item in-place.
        Returns the same list (mutated), sorted by score descending.
        """
        for item in items:
            item["virality_score"] = self.score_item(item)
        return sorted(items, key=lambda x: x.get("virality_score", 0), reverse=True)

    def top_n(self, items: list[dict], n: int = 20) -> list[dict]:
        """Return top N items by virality_score."""
        scored = self.score_batch(items)
        return scored[:n]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _extract_text(self, item: dict) -> str:
        """Combine all text fields into one lowercase string for keyword matching."""
        parts = [
            item.get("title", ""),
            item.get("summary", ""),
            item.get("description", ""),
            item.get("selftext", ""),
            item.get("flair", ""),
            item.get("viral_angle", ""),
            item.get("category", ""),
        ]
        return " ".join(p for p in parts if p).lower()

    def _keyword_score(self, text: str) -> float:
        """Accumulate keyword weights. Capped at _KW_CAP."""
        total = 0.0
        for kw, weight in _KEYWORDS.items():
            if kw in text:
                total += weight
                if total >= _KW_CAP:
                    break
        return total

    def _engagement_score(self, item: dict) -> float:
        """
        Log-scaled engagement. Max 3.0.
        Works for Reddit (score/num_comments) and news (no engagement = 0).
        """
        upvotes  = float(item.get("upvotes", item.get("score", 0)) or 0)
        comments = float(item.get("comments", item.get("num_comments", 0)) or 0)
        combined = upvotes + comments * 2.0
        if combined <= 0:
            return 0.0
        # log10(100)=2, log10(1000)=3, log10(10000)=4 → cap at 3
        return min(math.log10(combined + 1), 3.0)

    def _novelty_score(self, item: dict) -> float:
        """
        Age-based score. Max 2.0.
        Accepts ISO strings, RFC 2822 (RSS pubDate), Unix timestamps.
        Returns 0 if date unparseable.
        """
        raw = item.get("pub_date") or item.get("created_utc") or item.get("published", "")
        if not raw:
            return 0.0

        try:
            if isinstance(raw, (int, float)):
                # Unix timestamp (Reddit)
                pub = datetime.fromtimestamp(float(raw), tz=timezone.utc)
            elif "T" in str(raw) or "Z" in str(raw):
                # ISO 8601
                pub = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            else:
                # RFC 2822 (RSS pubDate: "Mon, 21 Apr 2026 08:00:00 +0000")
                pub = parsedate_to_datetime(str(raw))

            now_utc = datetime.now(tz=timezone.utc)
            # Make pub offset-aware if naive
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)

            age_hours = (now_utc - pub).total_seconds() / 3600

            if age_hours < 4:    return 2.0
            if age_hours < 24:   return 1.5
            if age_hours < 72:   return 0.5
            return 0.0

        except Exception:
            return 0.0

    def _category_boost(self, item: dict) -> float:
        """Category/region-based bonus. Max 1.0."""
        for field in ("category", "region", "impact", "flair"):
            val = item.get(field, "")
            if val in _CATEGORY_BOOST:
                return _CATEGORY_BOOST[val]
        return 0.0

    def _penalty_score(self, text: str) -> float:
        """
        Subtract points for:
        - US-only political content
        - Celebrity gossip without structural stakes
        - Non-French language (German/Italian topics)
        - Local accident/fait-divers with no creator angle
        """
        penalty = 0.0

        # Non-French language → hard derank
        if any(kw in text for kw in _NON_FRENCH_LANG):
            penalty -= 3.0

        # US-only politics (rescue if EU context present)
        if any(kw in text for kw in _US_POLITICAL):
            has_eu = any(eu in text for eu in ("europe", "france", "suisse", "switzerland", "belgium", "uk", "global"))
            if not has_eu:
                penalty += _US_ONLY_PENALTY

        # Celebrity gossip (rescue if structural tech/economy angle)
        if any(kw in text for kw in _CELEBRITY_GOSSIP):
            has_stakes = any(s in text for s in ("ai", "intelligence artificielle", "licenciement", "layoff", "économie", "economy", "data"))
            if not has_stakes:
                penalty += _CELEBRITY_PENALTY

        # Local accident/fait-divers (rescue if systemic angle)
        _accident_kw = ["unfall", "accident à", "accident mortel", "incendie à", "crime à", "arbeitsunfall"]
        if any(kw in text for kw in _accident_kw):
            has_angle = any(s in text for s in ("ia", "politique", "emploi", "économie", "santé", "tech"))
            if not has_angle:
                penalty += _LOCAL_ACCIDENT_PENALTY

        return penalty

    def filter_noise(self, items: list[dict], min_score: float = 3.0) -> list[dict]:
        """Remove items scoring below min_score. Assumes score_batch already called."""
        return [i for i in items if i.get("virality_score", 0) >= min_score]
