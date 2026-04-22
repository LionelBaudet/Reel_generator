"""
agents/social_trend_agent.py — Reddit JSON + Google Trends RSS fetcher.

Phase 1: Concurrent fetch — Reddit hot.json (5 subreddits) + Google Trends RSS
Phase 2: TrendScoringEngine pre-filter (no LLM) → top 25 items
Phase 3: Optional Claude ranking → top 10 with viral angles + rewritten titles

No API key required. Reddit uses JSON endpoints with User-Agent.
Google Trends uses public RSS (no auth).
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from agents.trend_scoring_engine import TrendScoringEngine

log = logging.getLogger("social_trend_agent")

# ── Source registry ────────────────────────────────────────────────────────────

REDDIT_SUBREDDITS = [
    {"subreddit": "worldnews",  "category": "global",    "region": "Global"},
    {"subreddit": "technology", "category": "tech",      "region": "Tech/AI"},
    {"subreddit": "finance",    "category": "economy",   "region": "Global"},
    {"subreddit": "france",     "category": "politics",  "region": "France"},
    {"subreddit": "europe",     "category": "politics",  "region": "Global"},
]

GOOGLE_TRENDS_FEEDS = [
    {"geo": "FR", "region": "France",      "label": "Google Trends FR"},
    {"geo": "CH", "region": "Switzerland", "label": "Google Trends CH"},
]

_FETCH_TIMEOUT   = 15   # seconds
_MAX_REDDIT_POSTS = 15  # per subreddit before scoring
_MAX_TRENDS_ITEMS = 10  # per Google Trends feed
_PRE_FILTER_N    = 12  # items passed to Claude after scoring


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, application/rss+xml, text/xml, */*",
    "Accept-Language": "fr,en;q=0.9",
}


# ── Reddit fetcher ─────────────────────────────────────────────────────────────

def _fetch_reddit(sub_config: dict) -> list[dict]:
    """
    Fetch /hot.json from one subreddit.
    Returns normalised list of post dicts. Never raises.
    """
    subreddit = sub_config["subreddit"]
    category  = sub_config["category"]
    region    = sub_config["region"]

    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={_MAX_REDDIT_POSTS}"
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        log.warning(f"[social_trend] Reddit r/{subreddit} failed: {e}")
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        if p.get("stickied") or p.get("is_meta"):
            continue

        title    = (p.get("title") or "").strip()
        selftext = (p.get("selftext") or "")[:200].strip()
        if not title:
            continue

        posts.append({
            "source":       "reddit",
            "subreddit":    subreddit,
            "region":       region,
            "category":     category,
            "title":        title[:150],
            "summary":      selftext or f"Reddit r/{subreddit}: {title[:100]}",
            "url":          f"https://reddit.com{p.get('permalink', '')}",
            "upvotes":      int(p.get("score", 0)),
            "comments":     int(p.get("num_comments", 0)),
            "created_utc":  p.get("created_utc", 0),
            "flair":        p.get("link_flair_text") or "",
        })

    log.info(f"[social_trend] r/{subreddit} → {len(posts)} posts")
    return posts


# ── Google Trends fetcher ──────────────────────────────────────────────────────

def _fetch_google_trends(feed_config: dict) -> list[dict]:
    """
    Fetch Google Trends RSS for a given geo.
    Returns normalised list of trend dicts. Never raises.
    """
    geo    = feed_config["geo"]
    region = feed_config["region"]
    label  = feed_config["label"]

    url = f"https://trends.google.com/trending/rss?geo={geo}"
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            raw = resp.read()
    except Exception as e:
        log.warning(f"[social_trend] Google Trends {geo} failed: {e}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log.warning(f"[social_trend] Google Trends {geo} XML parse error: {e}")
        return []

    # Google Trends RSS uses custom namespace for traffic
    ns = {"ht": "https://trends.google.com/trending/rss"}

    items = []
    for item in root.findall(".//item")[:_MAX_TRENDS_ITEMS]:
        title_el   = item.find("title")
        traffic_el = item.find("ht:approx_traffic", ns)
        pub_el     = item.find("pubDate")
        news_el    = item.find("ht:news_item_title", ns)

        title   = title_el.text.strip()   if title_el   is not None else ""
        traffic = traffic_el.text.strip() if traffic_el is not None else "0"
        pub_date = pub_el.text.strip()    if pub_el     is not None else ""
        news     = news_el.text.strip()   if news_el    is not None else ""

        if not title:
            continue

        # Parse traffic string like "500K+" or "1M+"
        traffic_num = _parse_traffic(traffic)

        items.append({
            "source":    "google_trends",
            "region":    region,
            "category":  "social",
            "title":     title,
            "summary":   news or f"Trending on Google {geo}: {title}",
            "url":       f"https://trends.google.com/trending?geo={geo}",
            "upvotes":   traffic_num,
            "comments":  0,
            "pub_date":  pub_date,
        })

    log.info(f"[social_trend] {label} → {len(items)} trending topics")
    return items


def _parse_traffic(s: str) -> int:
    """'500K+' → 500000, '1M+' → 1000000, '10K' → 10000."""
    s = s.replace("+", "").strip().upper()
    try:
        if s.endswith("M"):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith("K"):
            return int(float(s[:-1]) * 1_000)
        return int(s)
    except (ValueError, AttributeError):
        return 0


# ── Parallel fetch ─────────────────────────────────────────────────────────────

def fetch_all_social(max_workers: int = 7) -> list[dict]:
    """
    Fetch Reddit + Google Trends in parallel.
    Returns flat list of raw items.
    """
    all_items: list[dict] = []
    tasks = (
        [("reddit", cfg) for cfg in REDDIT_SUBREDDITS]
        + [("google", cfg) for cfg in GOOGLE_TRENDS_FEEDS]
    )

    def _run(task):
        kind, cfg = task
        if kind == "reddit":
            return _fetch_reddit(cfg)
        return _fetch_google_trends(cfg)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_run, t) for t in tasks]
        for fut in concurrent.futures.as_completed(futures):
            try:
                all_items.extend(fut.result())
            except Exception as e:
                log.warning(f"[social_trend] Worker error: {e}")

    log.info(f"[social_trend] Total raw items: {len(all_items)}")
    return all_items


# ── SocialTrendAgent class ─────────────────────────────────────────────────────

class SocialTrendAgent:
    """
    Hybrid agent: Python fetcher → TrendScoringEngine pre-filter → Claude ranker.

    Usage:
        agent = SocialTrendAgent(call_agent_fn)
        result = agent.fetch_and_rank(idea="hausse des prix", lang="fr")
        # result: social_trends dict (00_social_trends.json schema)
    """

    def __init__(self, call_agent_fn):
        self._call   = call_agent_fn
        self._scorer = TrendScoringEngine()

    def fetch_and_rank(self, idea: str = "", lang: str = "fr") -> dict:
        """
        1. Fetch Reddit + Google Trends in parallel (no LLM)
        2. TrendScoringEngine pre-filter → top 25
        3. Claude rank → top 10 with viral angles
        """
        t0 = time.time()

        raw = fetch_all_social()
        if not raw:
            log.warning("[social_trend] No items fetched — returning empty result")
            return self._empty_result()

        # Pre-filter with scoring engine (no LLM)
        top_raw = self._scorer.top_n(raw, n=_PRE_FILTER_N)
        top_raw = self._scorer.filter_noise(top_raw, min_score=2.0)

        if not top_raw:
            log.warning("[social_trend] All items scored below threshold")
            return self._empty_result()

        # Build Claude prompt
        idea_ctx = (
            f"The content creator is building a reel about: '{idea}'. "
            f"Prioritise trends directly or tangentially related."
            if idea.strip()
            else "Select the most universally viral social trends."
        )
        lang_instruction = (
            "Write summaries and titles in French."
            if lang == "fr"
            else "Write summaries and titles in English."
        )

        items_block = "\n\n".join(
            f"[{i+1}] [{a['source'].upper()} / {a['region']}] pre-score={a.get('virality_score',0):.1f}\n"
            f"TITLE: {a['title']}\n"
            f"SUMMARY: {a['summary'][:200]}\n"
            f"ENGAGEMENT: {a.get('upvotes',0)} upvotes | {a.get('comments',0)} comments\n"
            f"URL: {a['url']}"
            for i, a in enumerate(top_raw[:30])
        )

        task = (
            f"Today: {datetime.today().strftime('%Y-%m-%d')} | Language: {lang}\n"
            f"{idea_ctx}\n"
            f"{lang_instruction}\n\n"
            f"Below are pre-scored social trends from Reddit and Google Trends.\n"
            f"Select TOP 10 most relevant for a viral reel creator.\n\n"
            f"Scoring criteria:\n"
            f"- Personal financial/career impact\n"
            f"- Emotional intensity (fear, anger, surprise, excitement)\n"
            f"- AI/tech disruption angle\n"
            f"- Controversy or strong opinion potential\n"
            f"- Recency and cultural relevance (French/Swiss audience)\n\n"
            f"SOCIAL TRENDS:\n{items_block}\n\n"
            f"Return ONLY valid JSON (no markdown, no extra text):\n"
            f'{{\n'
            f'  "date": "{datetime.today().strftime("%Y-%m-%d")}",\n'
            f'  "trends": [\n'
            f'    {{\n'
            f'      "rank": 1,\n'
            f'      "source": "reddit | google_trends",\n'
            f'      "subreddit": "worldnews | (empty for google)",\n'
            f'      "region": "France | Global | Switzerland | Tech/AI",\n'
            f'      "title": "punchy rewritten title (max 12 words)",\n'
            f'      "original_title": "exact original title",\n'
            f'      "summary": "2-sentence summary (max 200 chars)",\n'
            f'      "engagement": {{"upvotes": 1000, "comments": 200}},\n'
            f'      "category": "politics | tech | economy | social",\n'
            f'      "virality_score": 8,\n'
            f'      "viral_angle": "one sentence hook angle for a content creator"\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n\n'
            f'Select exactly 10 trends. Rank 1 = highest viral potential.'
        )

        try:
            response = self._call("social-trend", task)
            result   = self._parse_json(response)
        except Exception as e:
            log.warning(f"[social_trend] Claude ranking failed ({e}) — using heuristic top 10")
            result = self._heuristic_result(top_raw[:10])

        result.setdefault("date", datetime.today().strftime("%Y-%m-%d"))
        result.setdefault("trends", [])

        elapsed = time.time() - t0
        log.info(f"[social_trend] Done in {elapsed:.1f}s — {len(result['trends'])} trends selected")
        return result

    # ── Private helpers ────────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> dict:
        import re
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

    def _heuristic_result(self, items: list[dict]) -> dict:
        trends = []
        for i, a in enumerate(items[:10]):
            trends.append({
                "rank":           i + 1,
                "source":         a.get("source", "reddit"),
                "subreddit":      a.get("subreddit", ""),
                "region":         a.get("region", "Global"),
                "title":          a["title"],
                "original_title": a["title"],
                "summary":        a.get("summary", ""),
                "engagement":     {"upvotes": a.get("upvotes", 0), "comments": a.get("comments", 0)},
                "category":       a.get("category", "social"),
                "virality_score": a.get("virality_score", 5),
                "viral_angle":    f"Trending on {a.get('source','social media')}: {a['title'][:60]}",
            })
        return {"date": datetime.today().strftime("%Y-%m-%d"), "trends": trends}

    def _empty_result(self) -> dict:
        return {
            "date":   datetime.today().strftime("%Y-%m-%d"),
            "trends": [],
            "_error": "All social feeds returned no data.",
        }
