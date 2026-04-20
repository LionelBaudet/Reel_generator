# -*- coding: utf-8 -*-
"""
utils/signals.py — Fetch & filter real news signals for daily reel ideas.

No hallucination: every signal has a real title, source name, and URL
fetched from public RSS feeds at call time.

Usage:
    from utils.signals import fetch_daily_signals, filter_relevant_signals
    signals = fetch_daily_signals()
    relevant = filter_relevant_signals(signals)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Signal dataclass ──────────────────────────────────────────────────────────

@dataclass
class Signal:
    title:     str
    source:    str          # publication name (e.g. "Le Monde", "TechCrunch")
    url:       str
    published: str          # ISO date string
    summary:   str = ""
    relevance: float = 0.0  # filled by filter_relevant_signals()

    def short(self) -> str:
        """One-line summary for prompt injection."""
        return f"[{self.source}] {self.title} — {self.url}"


# ── RSS feeds ─────────────────────────────────────────────────────────────────
# Google News RSS (no API key, public) + a few direct feeds.
# Queries cover: IA au travail, productivité, layoffs, burn-out, remote work,
# no-code, compétences, salaires, semaine 4 jours.

_GOOGLE_RSS = "https://news.google.com/rss/search?hl=fr&gl=FR&ceid=FR:fr&q={query}"
_GOOGLE_RSS_EN = "https://news.google.com/rss/search?hl=en&gl=US&ceid=US:en&q={query}"

_FR_QUERIES = [
    "intelligence+artificielle+entreprise+travail",
    "IA+productivité+emploi+2025",
    "burn-out+travail+salariés",
    "layoffs+licenciements+tech+2025",
    "télétravail+remote+work+entreprise",
    "no-code+automatisation+métier",
    "semaine+4+jours+travail",
    "ChatGPT+Claude+travail+bureau",
]

_EN_QUERIES = [
    "AI+workplace+productivity+2025",
    "AI+replacing+jobs+workers+2025",
    "workforce+AI+adoption+enterprise",
]

# Direct RSS feeds (supplement Google News)
_DIRECT_FEEDS = [
    ("Numerama",   "https://www.numerama.com/feed/"),
    ("01net",      "https://www.01net.com/rss/"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
]

_FETCH_TIMEOUT = 8    # seconds per feed
_MAX_PER_FEED  = 5    # items to keep per feed
_MAX_TOTAL     = 40   # max signals before filtering


# ── Relevance keywords ────────────────────────────────────────────────────────

_RELEVANCE_HIGH = [
    "ia", "intelligence artificielle", "ai", "chatgpt", "claude", "gpt",
    "automatisation", "automation", "productivité", "productivity",
    "emploi", "job", "travail", "work", "licenci", "layoff", "burn-out",
    "burnout", "télétravail", "remote", "compétence", "skill",
    "no-code", "nocode", "semaine 4 jours", "four-day week",
    "manager", "entreprise", "salarié", "cadre", "bureau",
]

_RELEVANCE_MEDIUM = [
    "tech", "numérique", "digital", "startup", "revenus", "salaire",
    "inflation", "coût", "gain de temps", "time-saving", "outil",
    "microsoft", "google", "apple", "meta", "openai", "anthropic",
]

_RELEVANCE_BLACKLIST = [
    "sport", "football", "rugby", "élection", "politique", "guerre", "meteo",
    "recette", "cuisine", "mode", "beauté", "people", "célébrité",
    "horoscope", "cinéma", "musique", "concert",
]


# ── Fetch ─────────────────────────────────────────────────────────────────────

def _parse_rss(url: str, source_name: str) -> list[Signal]:
    """Fetch and parse a single RSS feed. Returns list of Signal."""
    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser not installed — pip install feedparser")
        return []

    try:
        resp = requests.get(url, timeout=_FETCH_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ReelsGenerator/1.0)"
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        logger.debug(f"Feed fetch failed ({source_name}): {e}")
        return []

    signals = []
    for entry in feed.entries[:_MAX_PER_FEED]:
        title   = entry.get("title", "").strip()
        link    = entry.get("link", "").strip()
        summary = entry.get("summary", entry.get("description", "")).strip()
        # Strip HTML tags from summary
        import re
        summary = re.sub(r"<[^>]+>", "", summary)[:300]

        # Published date
        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6],
                                     tzinfo=timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                published = ""

        if title and link:
            signals.append(Signal(
                title=title,
                source=source_name,
                url=link,
                published=published,
                summary=summary,
            ))

    return signals


def fetch_daily_signals(include_en: bool = True) -> list[Signal]:
    """
    Fetch fresh signals from Google News RSS + direct feeds.
    Returns up to _MAX_TOTAL signals (unfiltered).
    """
    all_signals: list[Signal] = []

    # French Google News queries
    for query in _FR_QUERIES:
        url = _GOOGLE_RSS.format(query=query)
        signals = _parse_rss(url, _source_from_query(query))
        all_signals.extend(signals)
        if len(all_signals) >= _MAX_TOTAL:
            break
        time.sleep(0.15)  # polite crawling

    # English queries
    if include_en and len(all_signals) < _MAX_TOTAL:
        for query in _EN_QUERIES:
            url = _GOOGLE_RSS_EN.format(query=query)
            signals = _parse_rss(url, _source_from_query(query))
            all_signals.extend(signals)
            time.sleep(0.15)

    # Direct feeds (supplement)
    if len(all_signals) < _MAX_TOTAL:
        for name, feed_url in _DIRECT_FEEDS:
            signals = _parse_rss(feed_url, name)
            all_signals.extend(signals)
            time.sleep(0.15)

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[Signal] = []
    for s in all_signals:
        if s.url not in seen:
            seen.add(s.url)
            unique.append(s)

    logger.info(f"fetch_daily_signals: {len(unique)} unique signals fetched")
    return unique[:_MAX_TOTAL]


def _source_from_query(query: str) -> str:
    """Derive a readable source label from a query string."""
    return "Google News"


# ── Filter ────────────────────────────────────────────────────────────────────

def _score_signal(signal: Signal) -> float:
    """Score a signal for relevance to @ownyourtime.ai content (0.0 – 1.0)."""
    text = (signal.title + " " + signal.summary).lower()

    # Blacklist check
    for kw in _RELEVANCE_BLACKLIST:
        if kw in text:
            return 0.0

    score = 0.0
    for kw in _RELEVANCE_HIGH:
        if kw in text:
            score += 0.15
    for kw in _RELEVANCE_MEDIUM:
        if kw in text:
            score += 0.05

    # Boost for recent articles
    if signal.published:
        try:
            pub = datetime.strptime(signal.published, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - pub).days
            if age_days <= 1:
                score += 0.2
            elif age_days <= 3:
                score += 0.1
            elif age_days <= 7:
                score += 0.05
        except Exception:
            pass

    return min(1.0, score)


def filter_relevant_signals(signals: list[Signal],
                             top_n: int = 12) -> list[Signal]:
    """
    Score and rank signals by relevance.
    Returns the top_n most relevant, with relevance field populated.
    """
    for s in signals:
        s.relevance = _score_signal(s)

    ranked = sorted(signals, key=lambda s: s.relevance, reverse=True)
    relevant = [s for s in ranked if s.relevance > 0.0][:top_n]

    logger.info(
        f"filter_relevant_signals: {len(relevant)}/{len(signals)} signals kept "
        f"(min score: {relevant[-1].relevance:.2f})" if relevant else
        f"filter_relevant_signals: 0 relevant signals found"
    )
    return relevant


def signals_to_prompt_block(signals: list[Signal], lang: str = "fr") -> str:
    """
    Serialize signals into a prompt block for Claude.
    Each signal is a numbered line with title, source, url.
    """
    if not signals:
        return ""

    if lang == "en":
        header = "REAL NEWS SIGNALS (use these to anchor ideas — do not invent other sources):\n"
    else:
        header = "SIGNAUX D'ACTUALITÉ RÉELS (ancre tes idées sur ces sources — n'invente rien d'autre) :\n"

    lines = [header]
    for i, s in enumerate(signals, 1):
        date_str = f" [{s.published}]" if s.published else ""
        lines.append(f"{i}. [{s.source}{date_str}] {s.title}")
        lines.append(f"   URL: {s.url}")
        if s.summary:
            lines.append(f"   Résumé: {s.summary[:150]}…")
        lines.append("")

    return "\n".join(lines)
