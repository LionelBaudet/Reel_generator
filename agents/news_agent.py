"""
agents/news_agent.py — RSS fetcher + Claude ranker for the NewsAgent step.

Phase 1: concurrent urllib fetch across 4 RSS feeds (stdlib only, no feedparser).
Phase 2: Claude scores and filters to top 5, returns structured news_summary dict.
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("news_agent")

# ── RSS feed registry ─────────────────────────────────────────────────────────
# Stdlib-only fetch: no feedparser, no BS4, no scraping.
# Format: { "region": "...", "url": "...", "label": "..." }

RSS_FEEDS = [
    {
        "region": "Switzerland",
        "url": "https://www.srf.ch/news/bnf/rss/1646.rss",
        "label": "SRF News",
    },
    {
        "region": "France",
        "url": "https://www.francetvinfo.fr/titres.rss",
        "label": "France Info",
    },
    {
        "region": "Global",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "label": "BBC World",
    },
    {
        "region": "Tech/AI",
        "url": "https://techcrunch.com/feed/",
        "label": "TechCrunch",
    },
]

_FETCH_TIMEOUT  = 15   # seconds per feed
_MAX_ITEMS_FEED = 12   # articles to collect per feed before scoring
_MAX_TOKENS     = 2048 # Claude call for scoring


# ── RSS parser ────────────────────────────────────────────────────────────────

def _fetch_feed(feed: dict) -> list[dict]:
    """
    Fetch one RSS feed and return a list of raw article dicts.
    Returns [] on any network/parse error (never raises).
    """
    region  = feed["region"]
    label   = feed["label"]
    url     = feed["url"]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "fr,en;q=0.9",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            raw = resp.read()
    except Exception as e:
        log.warning(f"[news_agent] Feed fetch failed ({label}): {e}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log.warning(f"[news_agent] XML parse error ({label}): {e}")
        return []

    # Handle both RSS 2.0 (<channel><item>) and Atom (<entry>)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)

    articles = []
    for item in items[:_MAX_ITEMS_FEED]:
        def _text(tag: str, fallback: str = "") -> str:
            # NOTE: cannot use `or` — XML elements with no children are falsy
            el = item.find(tag)
            if el is None:
                el = item.find(f"atom:{tag}", ns)
            return (el.text or "").strip() if el is not None else fallback

        title   = _text("title")
        summary = _text("description") or _text("summary") or _text("content")
        link    = _text("link") or _text("atom:link", ns)
        pub     = _text("pubDate") or _text("published") or _text("updated")

        if not title:
            continue

        # Strip HTML tags from summary (simple regex-free approach)
        if summary and "<" in summary:
            import re
            summary = re.sub(r"<[^>]+>", " ", summary)
            summary = " ".join(summary.split())[:300]

        articles.append({
            "region":  region,
            "source":  label,
            "title":   title[:120],
            "summary": summary[:300],
            "url":     link[:200],
            "pub_date": pub[:40],
        })

    log.info(f"[news_agent] {label} → {len(articles)} articles fetched")
    return articles


def fetch_all_feeds(max_workers: int = 4) -> list[dict]:
    """
    Fetch all RSS feeds in parallel.
    Returns flat list of raw article dicts sorted by feed order.
    """
    all_articles: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_feed, feed): feed for feed in RSS_FEEDS}
        for fut in concurrent.futures.as_completed(futures):
            try:
                all_articles.extend(fut.result())
            except Exception as e:
                log.warning(f"[news_agent] Unexpected error in feed worker: {e}")

    log.info(f"[news_agent] Total raw articles collected: {len(all_articles)}")
    return all_articles


# ── NewsAgent class ───────────────────────────────────────────────────────────

class NewsAgent:
    """
    Hybrid agent: Python RSS fetcher → Claude scorer/ranker.

    Usage:
        agent = NewsAgent(call_agent_fn)
        result = agent.fetch_and_rank(idea="AI et emploi", lang="fr")
        # result: news_summary dict matching 00_news.json schema
    """

    def __init__(self, call_agent_fn):
        """
        call_agent_fn: the orchestrate._call_agent(name, prompt) -> str function.
        Injected to avoid circular imports.
        """
        self._call = call_agent_fn

    def fetch_and_rank(self, idea: str = "", lang: str = "fr") -> dict:
        """
        1. Fetch RSS feeds in parallel.
        2. Ask Claude to rank, filter to top 5, and return structured JSON.
        Returns news_summary dict (00_news.json schema).
        """
        t0 = time.time()

        raw_articles = fetch_all_feeds()
        if not raw_articles:
            log.warning("[news_agent] No articles fetched — returning empty summary")
            return self._empty_summary()

        # Build the scoring prompt
        idea_context = (
            f"The content creator is building a reel about: '{idea}'. "
            f"Prioritise news that is directly or tangentially related."
            if idea.strip()
            else "Select the most universally viral news regardless of topic."
        )

        lang_instruction = (
            "Write summaries and titles in French."
            if lang == "fr"
            else "Write summaries and titles in English."
        )

        articles_block = "\n\n".join(
            f"[{i+1}] [{a['region']} / {a['source']}]\n"
            f"TITLE: {a['title']}\n"
            f"SUMMARY: {a['summary'] or '(no summary)'}\n"
            f"URL: {a['url']}"
            for i, a in enumerate(raw_articles[:15])
        )

        task = f"""Today is {datetime.today().strftime('%Y-%m-%d')}.
{idea_context}
{lang_instruction}

Below are {len(raw_articles[:15])} raw news articles fetched from RSS feeds.
Your job: select the TOP 5 most virally relevant articles for a social media reel creator.

Scoring criteria (weight each equally):
- controversy / provocation (makes people react)
- economic / financial impact on individuals
- fear OR opportunity (personal stakes)
- AI / tech disruption angle
- recency and surprise factor

ARTICLES:
{articles_block}

Return ONLY a valid JSON object matching this exact schema (no markdown, no extra text):
{{
  "date": "{datetime.today().strftime('%Y-%m-%d')}",
  "topics": [
    {{
      "rank": 1,
      "region": "Switzerland | France | Global | Tech/AI",
      "title": "rewritten punchy title (max 12 words)",
      "original_title": "exact original title",
      "summary": "2-sentence summary focusing on impact (max 200 chars)",
      "url": "source url",
      "impact": "economic | social | tech | political",
      "virality_score": 8,
      "viral_angle": "one sentence: why this is viral for a content creator"
    }}
  ]
}}

Select exactly 5 articles. Rank 1 = most viral. No trailing commas."""

        try:
            response = self._call("news-agent", task)
            result   = self._parse_json(response)
        except Exception as e:
            log.warning(f"[news_agent] Claude scoring failed ({e}) — using heuristic fallback")
            result = self._heuristic_rank(raw_articles[:5])

        # Validate and patch missing fields
        result.setdefault("date", datetime.today().strftime("%Y-%m-%d"))
        result.setdefault("topics", [])

        elapsed = time.time() - t0
        log.info(f"[news_agent] Done in {elapsed:.1f}s — {len(result['topics'])} topics selected")
        return result

    # ── Private helpers ────────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> dict:
        import json, re
        # Try markdown code fence first
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try raw JSON object
        m = re.search(r"(\{[\s\S]*\})", text)
        if m:
            raw = m.group(1)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Fix trailing commas
                cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
                return json.loads(cleaned)
        raise ValueError("No JSON found in Claude response")

    def _heuristic_rank(self, articles: list[dict]) -> dict:
        """Simple keyword-based fallback when Claude call fails."""
        HIGH_VALUE_KEYWORDS = {
            "AI", "intelligence artificielle", "emploi", "job", "money", "argent",
            "crise", "crisis", "croissance", "growth", "chômage", "unemployment",
            "salaire", "salary", "tech", "robot", "automation", "ChatGPT", "GPT",
        }
        def _score(article: dict) -> int:
            text = (article["title"] + " " + article["summary"]).lower()
            return sum(1 for kw in HIGH_VALUE_KEYWORDS if kw.lower() in text)

        ranked = sorted(articles, key=_score, reverse=True)
        topics = []
        for i, a in enumerate(ranked[:5]):
            topics.append({
                "rank": i + 1,
                "region": a["region"],
                "title": a["title"],
                "original_title": a["title"],
                "summary": a["summary"],
                "url": a["url"],
                "impact": "tech" if a["region"] == "Tech/AI" else "social",
                "virality_score": max(5, 9 - i),
                "viral_angle": "Direct relevance to AI/productivity niche.",
            })
        return {
            "date": datetime.today().strftime("%Y-%m-%d"),
            "topics": topics,
        }

    def _empty_summary(self) -> dict:
        return {
            "date": datetime.today().strftime("%Y-%m-%d"),
            "topics": [],
            "_error": "All RSS feeds failed — no articles fetched.",
        }
