#!/usr/bin/env python3
"""
orchestrate.py — Multi-agent pipeline orchestrator for the Reel Generator.

Standard pipeline:
  [0] PlannerAgent      → 00_planner_decision.json   (strategy, angle, boosts)
  [1] TrendResearch     → 01_trends.json
  [2] HookGenerator     → 02_hooks.json
  [3] ScriptWriter      → 03_script.json
  [4] SceneBuilder      → 04_scene_config.yaml
  [5] VideoAssembler    → 05_video_result.json
  [6] CaptionGenerator  → 06_caption.json
  [7] Optimization      → 07_optimization.json
  [8] MemoryUpdate      → memory/*.json (learning loop)

News-mode pipeline (--news-mode):
  [0] PlannerAgent      → 00_planner_decision.json
  [N1] NewsAgent        → 00_news.json               (RSS fetch + Claude rank)
  [N2] HookFromNews     → 00_news_hook.json           (viral hooks from news)
  [N3] AIInsight        → 00_ai_insight.json          (AI angle on best news)
  [1–8] same as above, enriched with news context

Usage:
    python orchestrate.py "AI salary negotiation"
    python orchestrate.py "AI salary negotiation" --skip-video
    python orchestrate.py "AI salary negotiation" --lang fr
    python orchestrate.py "AI salary negotiation" --parallel
    python orchestrate.py "AI salary negotiation" --deep-plan
    python orchestrate.py "AI salary negotiation" --from-step script-writer
    python orchestrate.py --news-mode
    python orchestrate.py "intelligence artificielle emploi" --news-mode --skip-video
    python orchestrate.py --list-steps
    python orchestrate.py --memory-report
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── Phase B/C imports (graceful fallback if agents/ not yet present) ──────────
try:
    from agents.memory_manager import MemoryManager
    from agents.planner_agent import PlannerAgent
    from agents.scoring_engine import ScoringEngine
    from agents.parallel_runner import ParallelRunner
    _AGENTS_AVAILABLE = True
except ImportError as _agents_err:
    _AGENTS_AVAILABLE = False
    logging.getLogger(__name__).warning(f"agents/ modules not found: {_agents_err}")

# ── NewsAgent import (graceful fallback) ──────────────────────────────────────
try:
    from agents.news_agent import NewsAgent
    _NEWS_AGENT_AVAILABLE = True
except ImportError as _news_err:
    _NEWS_AGENT_AVAILABLE = False
    logging.getLogger(__name__).warning(f"agents/news_agent not found: {_news_err}")

# ── Trend-mode imports (graceful fallback) ────────────────────────────────────
try:
    from agents.social_trend_agent import SocialTrendAgent
    from agents.trend_fusion_agent import TrendFusionAgent
    from agents.trend_scoring_engine import TrendScoringEngine
    _TREND_AGENTS_AVAILABLE = True
except ImportError as _trend_err:
    _TREND_AGENTS_AVAILABLE = False
    logging.getLogger(__name__).warning(f"trend agents not found: {_trend_err}")

# ── Hook variant hints for parallel generation ────────────────────────────────
# Each of the 5 variants is biased toward a different copywriting framework.
# This guarantees hook diversity across the parallel batch.
HOOK_VARIANT_HINTS = [
    {
        "id": 0,
        "name": "pain_loss",
        "instruction": (
            "Focus EXCLUSIVELY on the PAIN/LOSS framework. "
            "Direct second-person interpellation ('Tu perds' / 'You're losing'). "
            "Quantify what they lose daily or weekly. Make the cost feel personal and immediate. "
            "Must contain a number or a specific cost signal."
        ),
    },
    {
        "id": 1,
        "name": "contrast",
        "instruction": (
            "Focus EXCLUSIVELY on the CONTRAST framework. "
            "Two states separated by a period, arrow (→), or 'before/after'. "
            "The contrast must be dramatic and specific (times, money, effort). "
            "E.g. '45 min → 4 minutes.' or 'Manual. Now automatic.'"
        ),
    },
    {
        "id": 2,
        "name": "curiosity",
        "instruction": (
            "Focus EXCLUSIVELY on the CURIOSITY framework. "
            "Create an open loop the viewer's brain cannot close without watching. "
            "Use 'sans le voir' / 'without knowing', hidden truth, or a statement that "
            "implies there is a secret the viewer doesn't have yet. "
            "Avoid question marks — tension, not interrogation."
        ),
    },
    {
        "id": 3,
        "name": "number_data",
        "instruction": (
            "Focus EXCLUSIVELY on the NUMBER/DATA framework. "
            "The hook must LEAD with or prominently feature a specific number: "
            "percentage, currency amount, hours saved, ratio, headcount. "
            "The number IS the scroll-stopper. No vague quantities."
        ),
    },
    {
        "id": 4,
        "name": "call_out",
        "instruction": (
            "Focus EXCLUSIVELY on the DIRECT CALL-OUT framework. "
            "Address a specific professional identity (manager, freelancer, data analyst, solopreneur). "
            "Challenge a belief they currently hold about themselves or their work. "
            "Pattern: '[identity] — [thing they think they're doing right] — [they're not].'"
        ),
    },
]

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
# NOTE: do NOT touch sys.stdout here — this module is imported by Streamlit,
# which replaces stdout with a proxy that has no .buffer and may be closed
# between reruns. stdout wrapping lives in main() only.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("orchestrate")

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
AGENTS_DIR = ROOT / ".claude" / "agents"
HANDOFF_DIR = ROOT / "output" / "agents"
HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

# ── Step registry ─────────────────────────────────────────────────────────────

STEPS = [
    "trend-research",
    "hook-generator",
    "script-writer",
    "scene-builder",
    "video-assembler",
    "caption-generator",
    "optimization",
]

# News-mode pre-processing steps (run before STEPS when --news-mode is active)
NEWS_STEPS = [
    "news-agent",
    "hook-from-news-agent",
    "ai-insight-agent",
]

# Trend-mode pre-processing steps (social + news fused)
TREND_STEPS = [
    "social-trend-agent",    # T1 — Reddit + Google Trends
    "news-agent",            # T2 — RSS news (reused from news-mode)
    "trend-fusion-agent",    # T3 — merge both signals
    "hook-from-trend-agent", # T4 — viral hooks from fused trends
    "ai-insight-agent",      # T5 — AI angle (reused)
]

# Social-only mode (no RSS news)
SOCIAL_STEPS = [
    "social-trend-agent",    # T1
    "hook-from-trend-agent", # T2 — hooks directly from social trends
    "ai-insight-agent",      # T3
]

STEP_OUTPUTS = {
    # Trend-mode steps
    "social-trend-agent":    HANDOFF_DIR / "00_social_trends.json",
    "trend-fusion-agent":    HANDOFF_DIR / "00_trend_intelligence.json",
    "hook-from-trend-agent": HANDOFF_DIR / "00_trend_hooks.json",
    # News-mode steps
    "news-agent":            HANDOFF_DIR / "00_news.json",
    "hook-from-news-agent":  HANDOFF_DIR / "00_news_hook.json",
    "ai-insight-agent":      HANDOFF_DIR / "00_ai_insight.json",
    # Standard steps (numbering unchanged)
    "trend-research":        HANDOFF_DIR / "01_trends.json",
    "hook-generator":        HANDOFF_DIR / "02_hooks.json",
    "script-writer":         HANDOFF_DIR / "03_script.json",
    "scene-builder":         HANDOFF_DIR / "04_scene_config.yaml",
    "video-assembler":       HANDOFF_DIR / "05_video_result.json",
    "caption-generator":     HANDOFF_DIR / "06_caption.json",
    "optimization":          HANDOFF_DIR / "07_optimization.json",
}

# Planner is step 0 — separate from the resumable STEPS list so --from-step still works
PLANNER_OUTPUT = HANDOFF_DIR / "00_planner_decision.json"

# Lazy singletons — initialised once per process
_memory: "MemoryManager | None" = None
_scoring: "ScoringEngine | None" = None


def _get_memory() -> "MemoryManager":
    global _memory
    if _memory is None and _AGENTS_AVAILABLE:
        _memory = MemoryManager()
    return _memory  # type: ignore[return-value]


def _get_scoring() -> "ScoringEngine":
    global _scoring
    if _scoring is None and _AGENTS_AVAILABLE:
        _scoring = ScoringEngine(_get_memory())
    return _scoring  # type: ignore[return-value]


# ── Claude API helpers ────────────────────────────────────────────────────────

def _claude_client():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")
    return anthropic.Anthropic(api_key=key)


def _call_agent(agent_name: str, task_prompt: str) -> str:
    """
    Runs a sub-agent by reading its .agent.md system prompt and calling Claude.
    Honors `model:` and `max_tokens:` frontmatter fields.
    Returns the agent's text response.
    """
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    if not agent_file.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_file}")

    content = agent_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Parse frontmatter key/value pairs + system prompt in one pass
    in_frontmatter = False
    frontmatter_done = False
    frontmatter: dict[str, str] = {}
    system_lines: list[str] = []

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            in_frontmatter = False
            frontmatter_done = True
            continue
        if in_frontmatter:
            if ":" in line:
                k, _, v = line.partition(":")
                frontmatter[k.strip()] = v.strip()
        elif frontmatter_done:
            system_lines.append(line)

    system_prompt = "\n".join(system_lines).strip()

    # Model: honour frontmatter, default to sonnet
    model = frontmatter.get("model", "claude-sonnet-4-6")

    # max_tokens: honour frontmatter, sensible per-agent defaults
    _DEFAULT_MAX: dict[str, int] = {
        "planner":             800,
        "social-trend":       1200,
        "trend-fusion":       1500,
        "news-agent":         1200,
        "hook-from-trend":    2000,
        "hook-from-news-agent": 1800,
        "ai-insight-agent":    500,
        "trend-research":     1000,
        "hook-generator":     1500,
        "script-writer":      2500,
        "scene-builder":      2800,
        "caption-generator":   900,
        "optimization":        700,
    }
    try:
        max_tokens = int(frontmatter.get("max_tokens", _DEFAULT_MAX.get(agent_name, 2048)))
    except ValueError:
        max_tokens = _DEFAULT_MAX.get(agent_name, 2048)

    import anthropic
    client = _claude_client()

    log.info(f"[{agent_name}] Calling {model} (max_tokens={max_tokens})…")
    t0 = time.time()

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": task_prompt}],
    )

    elapsed = time.time() - t0
    usage   = message.usage
    log.info(
        f"[{agent_name}] Done {elapsed:.1f}s — "
        f"in={usage.input_tokens} out={usage.output_tokens} "
        f"total={usage.input_tokens + usage.output_tokens}"
    )
    return message.content[0].text


# ── Step 0: Planner ───────────────────────────────────────────────────────────

def run_planner(
    idea: str,
    lang: str,
    run_id: str,
    parallel: bool = False,
    deep_plan: bool = False,
) -> dict:
    """
    Step 0 — runs before the main pipeline.
    Returns planner_decision dict. Never raises: falls back to safe defaults.
    """
    log.info("=== STEP 0: PlannerAgent ===")

    if not _AGENTS_AVAILABLE:
        log.warning("[planner] agents/ modules unavailable — using no-op defaults")
        return _default_planner_decision(run_id, idea)

    try:
        mem = _get_memory()
        planner = PlannerAgent(mem)
        decision = planner.plan(
            idea=idea,
            lang=lang,
            parallel=parallel,
            deep_plan=deep_plan,
            run_id=run_id,
        )
        return decision
    except Exception as e:
        log.warning(f"[planner] Failed ({e}) — falling back to defaults")
        return _default_planner_decision(run_id, idea)


def _default_planner_decision(run_id: str, idea: str) -> dict:
    """Safe fallback when PlannerAgent is unavailable or throws."""
    decision = {
        "run_id": run_id,
        "idea": idea,
        "strategy_mode": "single",
        "n_hook_variants": 5,
        "n_script_variants": 1,
        "idea_type": "educational_explainer",
        "topic_angle_hint": "",
        "hook_style_boost": {},
        "avoid_patterns": ["generic"],
        "reference_hooks": [],
        "force_rewrite": False,
        "content_calendar_note": None,
        "reasoning": "Fallback defaults (planner unavailable).",
    }
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    (HANDOFF_DIR / "00_planner_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return decision


# ── News-mode agent runners ───────────────────────────────────────────────────

def run_news_agent(idea: str, lang: str) -> dict:
    """
    Step N1 — Fetch RSS feeds and rank top 5 news by viral potential.
    Writes 00_news.json. Never raises: falls back to empty summary.
    """
    log.info("=== STEP N1: NewsAgent ===")

    if not _NEWS_AGENT_AVAILABLE:
        log.warning("[news-agent] agents/news_agent.py not found — skipping")
        result = {"date": datetime.today().strftime("%Y-%m-%d"), "topics": [],
                  "_error": "NewsAgent module unavailable"}
        _write_handoff("00_news.json", result)
        return result

    try:
        agent  = NewsAgent(call_agent_fn=_call_agent)
        result = agent.fetch_and_rank(idea=idea, lang=lang)
    except Exception as e:
        log.warning(f"[news-agent] Failed ({e}) — returning empty summary")
        result = {"date": datetime.today().strftime("%Y-%m-%d"), "topics": [],
                  "_error": str(e)}

    _write_handoff("00_news.json", result)
    topics = result.get("topics", [])
    if topics:
        log.info(f"[news-agent] Top news: '{topics[0].get('title', 'N/A')}' "
                 f"(virality={topics[0].get('virality_score', '?')})")
    return result


def run_hook_from_news_agent(
    news_summary: dict,
    lang: str,
    planner_decision: dict | None = None,
) -> dict:
    """
    Step N2 — Generate viral hooks from top news topics.
    Writes 00_news_hook.json.
    """
    log.info("=== STEP N2: HookFromNewsAgent ===")

    topics = news_summary.get("topics", [])
    if not topics:
        log.warning("[hook-from-news] No topics in news_summary — skipping")
        result = {"hooks": [], "best_hook": {}, "_error": "No news topics available"}
        _write_handoff("00_news_hook.json", result)
        return result

    # Build top-3 topics block
    top3 = topics[:3]
    topics_block = "\n\n".join(
        f"[{i+1}] {t.get('title', '')} ({t.get('region', '')})\n"
        f"    Impact: {t.get('impact', '')} | Virality: {t.get('virality_score', '?')}/10\n"
        f"    Summary: {t.get('summary', '')}\n"
        f"    Angle: {t.get('viral_angle', '')}"
        for i, t in enumerate(top3)
    )

    planner_hints = ""
    if planner_decision:
        boost = planner_decision.get("hook_style_boost", {})
        avoid = planner_decision.get("avoid_patterns", [])
        top_boost = [p for p, v in sorted(boost.items(), key=lambda x: -x[1]) if v > 1.0][:2]
        if top_boost:
            planner_hints += f"\nPRIORITY patterns (historically high-scoring): {', '.join(top_boost)}"
        if avoid:
            planner_hints += f"\nAVOID patterns: {', '.join(avoid)}"

    task = (
        f"Today: {datetime.today().strftime('%Y-%m-%d')} | Language: {lang}\n\n"
        f"Generate viral hooks for the following top news topics:\n\n"
        f"{topics_block}\n\n"
        f"Rules:\n"
        f"- Generate 3–5 hooks per topic (fear, curiosity, or contrast pattern)\n"
        f"- Max 12 words per hook\n"
        f"- Use second-person ('Tu', 'Ton') for French\n"
        f"- Include at least one concrete signal (number, price, %, time)\n"
        f"- Select the single best hook overall as best_hook\n"
        f"{planner_hints}\n\n"
        f"Return valid JSON matching your schema. No markdown. No extra text."
    )

    try:
        response = _call_agent("hook-from-news-agent", task)
        result   = _extract_json_from_response(response, "hook-from-news")
    except Exception as e:
        log.warning(f"[hook-from-news] Failed ({e}) — returning empty hooks")
        result = {"hooks": [], "best_hook": {}, "_error": str(e)}

    result.setdefault("hooks", [])
    result.setdefault("best_hook", result["hooks"][0] if result["hooks"] else {})

    _write_handoff("00_news_hook.json", result)
    best = result.get("best_hook", {})
    log.info(f"[hook-from-news] Best hook: '{best.get('hook', 'N/A')}' "
             f"(score={best.get('score', '?')})")
    return result


def run_ai_insight_agent(
    news_summary: dict,
    news_hook: dict,
    lang: str,
    planner_decision: dict | None = None,
) -> dict:
    """
    Step N3 — Transform best news + hook into an AI-angle insight.
    Writes 00_ai_insight.json.
    """
    log.info("=== STEP N3: AIInsightAgent ===")

    topics   = news_summary.get("topics", [])
    best_hook = news_hook.get("best_hook", {})

    if not topics and not best_hook:
        log.warning("[ai-insight] No news or hook available — skipping")
        result = {"insight": "", "angle_type": "automation", "example": "",
                  "cta": "", "_error": "No input data"}
        _write_handoff("00_ai_insight.json", result)
        return result

    # Pick the news item linked to the best hook
    hook_title = best_hook.get("news_title", "")
    top_topic  = next(
        (t for t in topics if hook_title and hook_title[:30] in t.get("title", "")),
        topics[0] if topics else {},
    )

    idea_type = (planner_decision or {}).get("idea_type", "educational_explainer")
    audience  = "des professionnels francophones (Suisse, France)" if lang == "fr" else "French-speaking professionals"

    task = (
        f"Today: {datetime.today().strftime('%Y-%m-%d')} | Language: {lang}\n\n"
        f"NEWS EVENT:\n"
        f"  Title: {top_topic.get('title', 'N/A')}\n"
        f"  Summary: {top_topic.get('summary', '')}\n"
        f"  Impact: {top_topic.get('impact', '')} | Region: {top_topic.get('region', '')}\n"
        f"  Viral angle: {top_topic.get('viral_angle', '')}\n\n"
        f"BEST HOOK FOR THIS NEWS:\n"
        f"  \"{best_hook.get('hook', 'N/A')}\" (pattern: {best_hook.get('pattern', '')})\n\n"
        f"CONTEXT:\n"
        f"  Target audience: {audience}\n"
        f"  Content type: {idea_type}\n\n"
        f"Your task: generate one sharp AI insight showing how AI predicts, automates, or optimizes "
        f"the situation described in this news.\n"
        f"The insight must be concrete, personal, and credible for the audience above.\n\n"
        f"Return valid JSON matching your schema. No markdown. No extra text."
    )

    try:
        response = _call_agent("ai-insight-agent", task)
        result   = _extract_json_from_response(response, "ai-insight")
    except Exception as e:
        log.warning(f"[ai-insight] Failed ({e}) — returning empty insight")
        result = {"insight": "", "angle_type": "automation", "example": "", "cta": "",
                  "_error": str(e)}

    for field in ("insight", "angle_type", "example", "cta"):
        result.setdefault(field, "")

    _write_handoff("00_ai_insight.json", result)
    log.info(f"[ai-insight] Insight: '{result.get('insight', 'N/A')[:80]}'")
    return result


# ── Trend-mode agent runners ──────────────────────────────────────────────────

def run_social_trend_agent(idea: str, lang: str) -> dict:
    """
    Step T1 — Fetch Reddit + Google Trends, score, rank top 10.
    Writes 00_social_trends.json. Never raises.
    """
    log.info("=== STEP T1: SocialTrendAgent ===")

    if not _TREND_AGENTS_AVAILABLE:
        log.warning("[social-trend] trend agents unavailable — skipping")
        result = {"date": datetime.today().strftime("%Y-%m-%d"), "trends": [],
                  "_error": "Trend agents module unavailable"}
        _write_handoff("00_social_trends.json", result)
        return result

    try:
        agent  = SocialTrendAgent(call_agent_fn=_call_agent)
        result = agent.fetch_and_rank(idea=idea, lang=lang)
    except Exception as e:
        log.warning(f"[social-trend] Failed ({e}) — returning empty result")
        result = {"date": datetime.today().strftime("%Y-%m-%d"), "trends": [],
                  "_error": str(e)}

    _write_handoff("00_social_trends.json", result)
    trends = result.get("trends", [])
    if trends:
        log.info(f"[social-trend] Top trend: '{trends[0].get('title','N/A')}' "
                 f"(score={trends[0].get('virality_score','?')})")
    return result


def run_trend_fusion_agent(
    social_trends: dict,
    news_summary: dict,
    lang: str,
    idea: str = "",
) -> dict:
    """
    Step T3 — Merge social + news into unified trend intelligence.
    Writes 00_trend_intelligence.json. Never raises.
    """
    log.info("=== STEP T3: TrendFusionAgent ===")

    if not _TREND_AGENTS_AVAILABLE:
        log.warning("[trend-fusion] trend agents unavailable — skipping")
        result = {"date": datetime.today().strftime("%Y-%m-%d"), "top_topics": [],
                  "_error": "Trend agents module unavailable"}
        _write_handoff("00_trend_intelligence.json", result)
        return result

    try:
        agent  = TrendFusionAgent(call_agent_fn=_call_agent)
        result = agent.fuse(social_trends, news_summary, lang=lang, idea=idea)
    except Exception as e:
        log.warning(f"[trend-fusion] Failed ({e}) — returning empty result")
        result = {"date": datetime.today().strftime("%Y-%m-%d"), "top_topics": [],
                  "_error": str(e)}

    _write_handoff("00_trend_intelligence.json", result)
    return result


def run_hook_from_trend_agent(
    trend_intelligence: dict,
    lang: str,
    planner_decision: dict | None = None,
    social_trends: dict | None = None,
) -> dict:
    """
    Step T4 — Generate viral hooks from fused trend intelligence.
    Also handles social-only mode (trend_intelligence may be empty, falls back to social_trends).
    Writes 00_trend_hooks.json. Never raises.
    """
    log.info("=== STEP T4: HookFromTrendAgent ===")

    # In social-only mode, build lightweight trend_intelligence from social_trends
    topics = trend_intelligence.get("top_topics", [])
    if not topics and social_trends:
        raw_trends = social_trends.get("trends", [])
        topics = [
            {
                "rank":           i + 1,
                "topic":          t.get("title", ""),
                "angle":          t.get("viral_angle", ""),
                "source_mix":     [t.get("source", "reddit")],
                "region":         t.get("region", "Global"),
                "category":       t.get("category", "social"),
                "virality_score": t.get("virality_score", 5),
                "evidence":       t.get("summary", ""),
            }
            for i, t in enumerate(raw_trends[:10])
        ]

    if not topics:
        log.warning("[hook-from-trend] No topics available — returning empty hooks")
        result = {"hooks": [], "best_hook": {}, "_error": "No trend topics available"}
        _write_handoff("00_trend_hooks.json", result)
        return result

    top5 = topics[:5]
    topics_block = "\n\n".join(
        f"[{i+1}] {t.get('topic','')} | score={t.get('virality_score','?')} "
        f"| sources={t.get('source_mix',[])} | region={t.get('region','')}\n"
        f"    ANGLE: {t.get('angle','')}\n"
        f"    EVIDENCE: {t.get('evidence','')[:150]}"
        for i, t in enumerate(top5)
    )

    planner_hints = ""
    if planner_decision:
        boost = planner_decision.get("hook_style_boost", {})
        avoid = planner_decision.get("avoid_patterns", [])
        top_boost = [p for p, v in sorted(boost.items(), key=lambda x: -x[1]) if v > 1.0][:2]
        if top_boost:
            planner_hints += f"\nPRIORITY patterns (high-scoring history): {', '.join(top_boost)}"
        if avoid:
            planner_hints += f"\nAVOID patterns: {', '.join(avoid)}"

    task = (
        f"Today: {datetime.today().strftime('%Y-%m-%d')} | Language: {lang}\n\n"
        f"Generate viral hooks for the top 5 trending topics below.\n"
        f"These trends are confirmed by real-time social + news signals.\n\n"
        f"TOP TRENDING TOPICS:\n{topics_block}\n\n"
        f"Rules:\n"
        f"- Generate 3–5 hooks per topic (fear, curiosity, or contrast pattern)\n"
        f"- Max 12 words per hook. Second-person ('Tu', 'Ton') for French.\n"
        f"- Include at least one concrete signal (number, %, price, time)\n"
        f"- Select the single best hook overall as best_hook\n"
        f"{planner_hints}\n\n"
        f"Return valid JSON matching your schema. No markdown. No extra text."
    )

    try:
        response = _call_agent("hook-from-trend", task)
        result   = _extract_json_from_response(response, "hook-from-trend")
    except Exception as e:
        log.warning(f"[hook-from-trend] Failed ({e}) — returning empty hooks")
        result = {"hooks": [], "best_hook": {}, "_error": str(e)}

    result.setdefault("hooks", [])
    result.setdefault("best_hook", result["hooks"][0] if result["hooks"] else {})

    _write_handoff("00_trend_hooks.json", result)
    best = result.get("best_hook", {})
    log.info(f"[hook-from-trend] Best hook: '{best.get('hook','N/A')}' "
             f"(score={best.get('score','?')})")
    return result


# ── Individual agent runners ──────────────────────────────────────────────────

def run_trend_research(idea: str, lang: str, ai_insight: dict | None = None) -> dict:
    log.info("=== STEP 1: TrendResearchAgent ===")

    # Build enrichment block from AI insight (news-mode only)
    insight_context = ""
    if ai_insight and ai_insight.get("insight"):
        insight_context = (
            f"\n\nNEWS-MODE CONTEXT (from AIInsightAgent):\n"
            f"  Insight: {ai_insight.get('insight', '')}\n"
            f"  Angle type: {ai_insight.get('angle_type', '')}\n"
            f"  Example: {ai_insight.get('example', '')}\n"
            f"  CTA hint: {ai_insight.get('cta', '')}\n"
            f"Use this AI angle as the primary recommendation signal.\n"
        )

    task = (
        f"Run trend research for today's reel. The idea hint is: '{idea}'. "
        f"Language preference: {lang}. "
        f"Execute the RSS fetch, analyze signals, and write output/agents/01_trends.json "
        f"with 3 ranked ideas. Mark the best one as recommended."
        f"{insight_context}"
    )

    # Try native pipeline first (faster, no extra API call)
    try:
        from utils.signals import fetch_signals
        from utils.stat_extractor import extract_stats
        from utils.source_scoring import score_source

        signals = fetch_signals()
        ideas = []
        for i, sig in enumerate(signals[:5], 1):
            src = getattr(sig, "source", "") or ""
            url = getattr(sig, "url", "") or ""
            title = getattr(sig, "title", "") or str(sig)
            score = getattr(sig, "relevance_score", 5)
            # In news-mode: use AI insight angle if available
            ai_angle_text = (
                ai_insight.get("insight", f"How AI can help with: {title}")
                if ai_insight else f"How AI can help with: {title}"
            )
            ideas.append({
                "id": i,
                "topic": title[:60],
                "signal_title": title,
                "signal_url": url,
                "signal_source": src,
                "core_stat": None,
                "ai_angle": ai_angle_text,
                "emotion": "curiosity",
                "idea_type": "educational_explainer",
                "viral_potential": min(10, int(score * 2)) if score else 5,
                "recommended": i == 1,
            })

        # Fallback to idea-based entry if no signals
        if not ideas:
            ideas = [{
                "id": 1,
                "topic": idea,
                "signal_title": None,
                "signal_url": None,
                "signal_source": None,
                "core_stat": None,
                "ai_angle": ai_insight.get("insight", idea) if ai_insight else idea,
                "emotion": "curiosity",
                "idea_type": "educational_explainer",
                "viral_potential": 7,
                "recommended": True,
            }]

        # Inject the user's idea (or news-derived idea) as top recommendation
        ideas.insert(0, {
            "id": 0,
            "topic": idea,
            "signal_title": None,
            "signal_url": None,
            "signal_source": None,
            "core_stat": None,
            "ai_angle": ai_insight.get("insight", idea) if ai_insight else idea,
            "emotion": "curiosity",
            "idea_type": "educational_explainer",
            "viral_potential": 8,
            "recommended": True,
        })
        # Renumber and mark only #0 as recommended
        for item in ideas:
            item["recommended"] = item["id"] == 0

        result = {
            "date": datetime.today().strftime("%Y-%m-%d"),
            "ideas": ideas[:4],
            "recommended_idea_id": 0,
        }
        # Attach AI insight metadata for downstream agents
        if ai_insight:
            result["news_mode"] = True
            result["ai_insight"] = ai_insight
    except Exception as e:
        log.warning(f"Native signal fetch failed ({e}), using Claude agent fallback")
        response = _call_agent("trend-research", task)
        result = _extract_json_from_response(response, "trend research")

    # Guarantee 'ideas' key is always present and non-empty
    if not result.get("ideas"):
        result["ideas"] = [{
            "id": 0, "topic": idea or "tendances IA",
            "signal_title": None, "signal_url": None, "signal_source": None,
            "core_stat": None,
            "ai_angle": (ai_insight or {}).get("insight", idea) if ai_insight else idea,
            "emotion": "curiosity", "idea_type": "educational_explainer",
            "viral_potential": 7, "recommended": True,
        }]
        result.setdefault("recommended_idea_id", 0)

    _write_handoff("01_trends.json", result)
    log.info(f"[trend-research] Recommended idea: {result['ideas'][0].get('topic', 'N/A')}")
    return result


def run_hook_generator(
    trends: dict,
    lang: str,
    planner_decision: dict | None = None,
    variant_hint: dict | None = None,
    write_handoff: bool = True,
) -> dict:
    """
    Single-call hook generation.
    variant_hint: if set (parallel mode), biases generation toward one framework.
    write_handoff: set False in parallel mode — the parallel wrapper handles file writes.
    """
    label = f"v{variant_hint['id']}:{variant_hint['name']}" if variant_hint else "single"
    log.info(f"=== STEP 2: HookGeneratorAgent [{label}] ===")

    rec_id = trends.get("recommended_idea_id", 0)
    rec_idea = next((i for i in trends["ideas"] if i["id"] == rec_id), trends["ideas"][0])

    task = (
        f"Generate 5 viral hook variants for this idea:\n"
        f"Topic: {rec_idea['topic']}\n"
        f"Core stat: {rec_idea.get('core_stat', 'N/A')}\n"
        f"AI angle: {rec_idea.get('ai_angle', '')}\n"
        f"Emotion: {rec_idea.get('emotion', 'curiosity')}\n"
        f"Language: {lang}\n\n"
        f"Use all 5 frameworks: curiosity, pain/call-out, contrast, number/data, direct call-out.\n"
        f"Score each hook and select the best one.\n"
        f"Write output to output/agents/02_hooks.json."
    )

    # ── Planner hints ─────────────────────────────────────────────────────────
    if planner_decision:
        hints: list[str] = []
        angle = planner_decision.get("topic_angle_hint", "")
        if angle:
            hints.append(f"Angle to target: {angle}")
        boosts = planner_decision.get("hook_style_boost", {})
        top_boost = sorted(boosts.items(), key=lambda x: x[1], reverse=True)[:2]
        if top_boost:
            top_names = [p for p, _ in top_boost if boosts[p] > 1.0]
            if top_names:
                hints.append(f"Prioritise these patterns (historically high-scoring): {', '.join(top_names)}")
        avoid = planner_decision.get("avoid_patterns", [])
        if avoid:
            hints.append(f"Avoid these patterns (historically low-scoring): {', '.join(avoid)}")
        refs = planner_decision.get("reference_hooks", [])
        if refs:
            hints.append(f"Top-performing reference hooks for this type (DO NOT copy, use as inspiration): {refs}")
        if hints:
            task += "\n\nPLANNER STRATEGY HINTS:\n" + "\n".join(f"- {h}" for h in hints)

    # ── Variant constraint (parallel mode only) ───────────────────────────────
    if variant_hint:
        task += (
            f"\n\nVARIANT CONSTRAINT (parallel generation — this call only):\n"
            f"You are Variant {variant_hint['id']} ({variant_hint['name'].upper()}).\n"
            f"{variant_hint['instruction']}\n"
            f"All 5 hooks you generate must follow this framework. "
            f"Do not mix frameworks in this variant."
        )

    response = _call_agent("hook-generator", task)
    result = _extract_json_from_response(response, "hook generator")

    # ── Normalise fields ──────────────────────────────────────────────────────
    if "hooks" not in result:
        result["hooks"] = []
    if "best_hook" not in result and result["hooks"]:
        best = max(result["hooks"], key=lambda h: h.get("total_score", 0))
        result["best_hook"] = best

    # Stamp variant metadata onto every hook for traceability
    if variant_hint:
        result["_variant_id"]   = variant_hint["id"]
        result["_variant_name"] = variant_hint["name"]
        for h in result.get("hooks", []):
            h.setdefault("variant", variant_hint["name"])

    if write_handoff:
        _write_handoff("02_hooks.json", result)

    best_text = result.get("best_hook", {}).get("text", "N/A")
    log.info(f"[hook-generator/{label}] Best hook: {best_text}")
    return result


def run_script_writer(
    trends: dict,
    hooks: dict,
    lang: str,
    hook_override: dict | None = None,
    write_handoff: bool = True,
) -> dict:
    """
    Single-call script generation.
    hook_override: if set (parallel mode), uses this specific hook instead of hooks["best_hook"].
    write_handoff: set False in parallel mode — the parallel wrapper handles file writes.
    """
    rec_id = trends.get("recommended_idea_id", 0)
    rec_idea = next((i for i in trends["ideas"] if i["id"] == rec_id), trends["ideas"][0])
    best_hook = hook_override or hooks.get("best_hook", {})
    hook_label = best_hook.get("text", "")[:30] if best_hook else "unknown"
    log.info(f"=== STEP 3: ScriptWriterAgent [hook: '{hook_label}'] ===")

    task = (
        f"Write a complete 6-scene reel script using:\n"
        f"Topic: {rec_idea['topic']}\n"
        f"Core stat: {rec_idea.get('core_stat', 'N/A')}\n"
        f"AI angle: {rec_idea.get('ai_angle', '')}\n"
        f"Best hook: {best_hook.get('text', '')}\n"
        f"Hook keyword highlight: {best_hook.get('keyword_highlight', '')}\n"
        f"Language: {lang}\n\n"
        f"Generate scenes: hook → pain → shift → solution → result → cta.\n"
        f"Max 6 words per scene (CTA: 8). Validate before writing.\n"
        f"Write output to output/agents/03_script.json."
    )
    response = _call_agent("script-writer", task)
    result = _extract_json_from_response(response, "script writer")

    # Stamp hook text for scoring pass
    result["hook_text"] = best_hook.get("text", "")
    result["hook_variant"] = best_hook.get("variant", "")

    if write_handoff:
        _write_handoff("03_script.json", result)

    script = result.get("script", {})
    for scene_type in ["hook", "pain", "shift", "solution", "result", "cta"]:
        text = script.get(scene_type, {}).get("text", "")
        log.info(f"  [{scene_type}] {text}")
    return result


# ── Phase C: Parallel execution ───────────────────────────────────────────────

def run_hook_generator_parallel(
    trends: dict,
    lang: str,
    planner_decision: dict,
    n: int = 5,
) -> dict:
    """
    Run N hook generation calls concurrently, one per variant hint.
    Collects all hooks, scores them with ScoringEngine, deduplicates,
    and returns a consolidated result dict (same schema as single-call version).
    Writes 02_hooks_v{i}.json per variant + 02_hooks.json as the consolidated winner.
    """
    log.info(f"=== STEP 2: HookGeneratorAgent [PARALLEL ×{n}] ===")

    runner = ParallelRunner() if _AGENTS_AVAILABLE else None

    # ── Build tasks ───────────────────────────────────────────────────────────
    tasks = [
        {
            "trends":          trends,
            "lang":            lang,
            "planner_decision": planner_decision,
            "variant_hint":    HOOK_VARIANT_HINTS[i % len(HOOK_VARIANT_HINTS)],
            "variant_idx":     i,
        }
        for i in range(n)
    ]

    def _task(t: dict) -> dict:
        result = run_hook_generator(
            t["trends"],
            t["lang"],
            planner_decision=t["planner_decision"],
            variant_hint=t["variant_hint"],
            write_handoff=False,
        )
        result["_variant_idx"] = t["variant_idx"]
        return result

    # ── Execute in parallel ───────────────────────────────────────────────────
    if runner:
        raw_results = runner.run_parallel(_task, tasks, max_workers=n, timeout=180.0)
    else:
        raw_results = [_task(t) for t in tasks]

    valid_results = [r for r in raw_results if r is not None]
    if not valid_results:
        log.warning("[parallel-hooks] All variants failed — falling back to single call")
        return run_hook_generator(trends, lang, planner_decision=planner_decision)

    # ── Save individual variant files ─────────────────────────────────────────
    for r in valid_results:
        idx = r.get("_variant_idx", 0)
        _write_handoff(f"02_hooks_v{idx}.json", r)

    # ── Collect and flatten all hooks from all variants ───────────────────────
    all_hooks: list[dict] = []
    for r in valid_results:
        for h in r.get("hooks", []):
            all_hooks.append(h)

    log.info(f"[parallel-hooks] {len(valid_results)}/{n} variants succeeded — {len(all_hooks)} hooks total")

    # ── Score with ScoringEngine + deduplicate ────────────────────────────────
    scoring = _get_scoring()
    if scoring and all_hooks:
        ranked = scoring.rank_hooks(all_hooks)
    else:
        ranked = sorted(all_hooks, key=lambda h: h.get("total_score", 0) or 0, reverse=True)

    ranked = _deduplicate_hooks(ranked)

    # ── Log comparison table ──────────────────────────────────────────────────
    log.info(f"[parallel-hooks] Top {min(5, len(ranked))} after dedup + scoring:")
    for i, h in enumerate(ranked[:5], 1):
        log.info(
            f"  {i}. [{h.get('score', h.get('total_score', 0)):.1f}] "
            f"({h.get('variant', '?')}) {h.get('text', '')}"
        )

    # ── Build consolidated output ─────────────────────────────────────────────
    best = ranked[0] if ranked else {}
    consolidated = {
        "variants_run":   n,
        "variants_ok":    len(valid_results),
        "hooks":          ranked,
        "best_hook":      best,
        "_parallel":      True,
    }
    _write_handoff("02_hooks.json", consolidated)
    log.info(f"[parallel-hooks] Winner: '{best.get('text', 'N/A')}' "
             f"(variant={best.get('variant', '?')}, score={best.get('score', 0):.2f})")
    return consolidated


def run_script_writer_parallel(
    trends: dict,
    lang: str,
    top_hooks: list[dict],
    planner_decision: dict,
) -> dict:
    """
    Run one script generation per hook in top_hooks, concurrently.
    Scores all scripts with ScoringEngine, returns the winner.
    Writes 03_script_v{i}.json per variant + 03_script.json as the winner
    (so --from-step still works correctly downstream).
    """
    n = len(top_hooks)
    log.info(f"=== STEP 3: ScriptWriterAgent [PARALLEL ×{n}] ===")

    runner = ParallelRunner() if _AGENTS_AVAILABLE else None

    tasks = [
        {
            "trends":       trends,
            "lang":         lang,
            "hook_override": hook,
            "variant_idx":  i,
        }
        for i, hook in enumerate(top_hooks)
    ]

    def _task(t: dict) -> dict:
        empty_hooks = {"best_hook": t["hook_override"], "hooks": [t["hook_override"]]}
        result = run_script_writer(
            t["trends"],
            empty_hooks,
            t["lang"],
            hook_override=t["hook_override"],
            write_handoff=False,
        )
        result["_variant_idx"] = t["variant_idx"]
        return result

    # ── Execute in parallel ───────────────────────────────────────────────────
    if runner:
        raw_results = runner.run_parallel(_task, tasks, max_workers=n, timeout=180.0)
    else:
        raw_results = [_task(t) for t in tasks]

    valid = [r for r in raw_results if r is not None]
    if not valid:
        log.warning("[parallel-scripts] All variants failed — falling back to single call")
        hooks_dict = {"best_hook": top_hooks[0]} if top_hooks else {}
        return run_script_writer(trends, hooks_dict, lang)

    # ── Save individual variant files ─────────────────────────────────────────
    for r in valid:
        _write_handoff(f"03_script_v{r.get('_variant_idx', 0)}.json", r)

    # ── Score all scripts ─────────────────────────────────────────────────────
    scoring = _get_scoring()
    if scoring:
        for r in valid:
            breakdown = scoring.score_reel(
                r.get("hook_text", ""),
                r.get("script", {}),
                planner_decision.get("idea_type", ""),
            )
            r["_score"]           = breakdown["overall"]
            r["_score_breakdown"] = breakdown
        valid.sort(key=lambda r: r.get("_score", 0), reverse=True)

    # ── Log comparison table ──────────────────────────────────────────────────
    log.info(f"[parallel-scripts] {len(valid)}/{n} variants succeeded:")
    for r in valid:
        idx   = r.get("_variant_idx", "?")
        score = r.get("_score", "n/a")
        hook  = r.get("hook_text", "")[:40]
        bd    = r.get("_score_breakdown", {})
        log.info(
            f"  v{idx}: score={score:.2f} | "
            f"hook={bd.get('hook_score', 0):.1f} flow={bd.get('tension_arc', 0):.1f} "
            f"cta={bd.get('cta_quality', 0):.1f} | hook: '{hook}'"
        )

    winner = valid[0]
    log.info(
        f"[parallel-scripts] WINNER: v{winner.get('_variant_idx')} "
        f"(score={winner.get('_score', 0):.2f})"
    )

    # ── Write winner to both 03_best_script.json and canonical 03_script.json ─
    _write_handoff("03_best_script.json", winner)
    _write_handoff("03_script.json", winner)   # keeps --from-step compatible

    return winner


def _deduplicate_hooks(hooks: list[dict], similarity_threshold: float = 0.75) -> list[dict]:
    """
    Remove near-duplicate hooks. Compares lowercased texts character by character.
    Keeps the higher-scored hook from any pair with similarity > threshold.
    Input must already be sorted descending by score (rank_hooks output).
    """
    if len(hooks) <= 1:
        return hooks

    kept: list[dict] = []
    kept_texts: list[str] = []

    for h in hooks:
        text = h.get("text", "").lower().strip()
        is_dup = False
        for existing in kept_texts:
            # Simple character overlap ratio (fast, no external dep)
            shared = sum(c in existing for c in text)
            ratio  = shared / max(len(text), len(existing), 1)
            if ratio >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(h)
            kept_texts.append(text)

    removed = len(hooks) - len(kept)
    if removed:
        log.debug(f"[dedup] Removed {removed} near-duplicate hooks (threshold={similarity_threshold})")
    return kept


# ── End parallel section ──────────────────────────────────────────────────────

def run_scene_builder(script: dict, lang: str) -> Path:
    log.info("=== STEP 4: SceneBuilderAgent ===")

    task = (
        f"Convert this script into a production-ready YAML for viral_text_centric_v1:\n"
        f"{json.dumps(script, ensure_ascii=False, indent=2)}\n\n"
        f"Apply timing rules, animation assignments, and Pexels queries.\n"
        f"Validate the YAML before writing to output/agents/04_scene_config.yaml.\n"
        f"Also write output/agents/04_meta.json with total_duration and pexels_queries."
    )
    response = _call_agent("scene-builder", task)

    # Extract YAML block from response
    yaml_config = _extract_yaml_from_response(response, script)
    config_path = HANDOFF_DIR / "04_scene_config.yaml"
    config_path.write_text(
        yaml.dump(yaml_config, allow_unicode=True, default_flow_style=False),
        encoding="utf-8"
    )

    # Write meta
    scenes = yaml_config.get("scenes", [])
    total_dur = sum(s.get("duration", 3.0) for s in scenes)
    queries = [v.get("query", "") for v in yaml_config.get("background", {}).get("videos", [])]
    meta = {
        "config_path": str(config_path),
        "total_duration": round(total_dur, 1),
        "scene_count": len(scenes),
        "pexels_queries": queries,
    }
    _write_handoff("04_meta.json", meta)
    log.info(f"[scene-builder] {len(scenes)} scenes, {total_dur:.1f}s total")
    return config_path


def run_video_assembler(config_path: Path, skip_video: bool = False) -> dict:
    log.info("=== STEP 5: VideoAssemblerAgent ===")

    if skip_video:
        log.info("[video-assembler] Skipping video render (--skip-video)")
        result = {
            "status": "skipped",
            "output_path": None,
            "file_size_mb": 0,
            "duration_seconds": 0,
            "render_time_seconds": 0,
            "preview_frames": [],
            "error": None,
            "retries": 0,
        }
        _write_handoff("05_video_result.json", result)
        return result

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = ROOT / "output" / f"reel_{timestamp}.mp4"

    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--config", str(config_path),
        "--output", str(output_path),
    ]

    log.info(f"[video-assembler] Running: {' '.join(cmd)}")
    t0 = time.time()

    for attempt in range(3):
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(ROOT), encoding="utf-8", errors="replace"
        )
        elapsed = time.time() - t0

        if proc.returncode == 0 and output_path.exists() and output_path.stat().st_size > 100_000:
            size_mb = output_path.stat().st_size / 1_048_576
            result = {
                "status": "success",
                "output_path": str(output_path),
                "file_size_mb": round(size_mb, 2),
                "duration_seconds": 0,
                "render_time_seconds": round(elapsed, 1),
                "preview_frames": [],
                "error": None,
                "retries": attempt,
            }
            log.info(f"[video-assembler] Success: {output_path} ({size_mb:.1f} MB, {elapsed:.0f}s)")
            break
        else:
            err = proc.stderr[-500:] if proc.stderr else proc.stdout[-500:]
            log.warning(f"[video-assembler] Attempt {attempt+1} failed: {err}")
            if attempt == 2:
                result = {
                    "status": "failed",
                    "output_path": None,
                    "file_size_mb": 0,
                    "duration_seconds": 0,
                    "render_time_seconds": round(elapsed, 1),
                    "preview_frames": [],
                    "error": err,
                    "retries": attempt + 1,
                }

    _write_handoff("05_video_result.json", result)
    return result


def run_caption_generator(trends: dict, script: dict, video_result: dict, lang: str) -> dict:
    log.info("=== STEP 6: CaptionGeneratorAgent ===")
    rec_id = trends.get("recommended_idea_id", 0)
    rec_idea = next((i for i in trends["ideas"] if i["id"] == rec_id), trends["ideas"][0])

    task = (
        f"Generate an Instagram caption for this reel.\n"
        f"Topic: {rec_idea['topic']}\n"
        f"Source URL: {rec_idea.get('signal_url', 'none')}\n"
        f"Core stat: {rec_idea.get('core_stat', 'none')}\n"
        f"Script CTA: {script.get('script', {}).get('cta', {}).get('text', '')}\n"
        f"CTA keyword: {script.get('cta_keyword', 'GUIDE')}\n"
        f"Viral angle: {script.get('viral_angle', '')}\n"
        f"Language: {lang}\n\n"
        f"Write the complete caption with hook line, body, CTA, and 10-12 hashtags.\n"
        f"Write output to output/agents/06_caption.json."
    )
    response = _call_agent("caption-generator", task)
    result = _extract_json_from_response(response, "caption generator")

    _write_handoff("06_caption.json", result)
    caption_preview = result.get("caption_full", "")[:100]
    log.info(f"[caption-generator] Caption preview: {caption_preview}...")
    return result


def run_optimization(trends: dict, hooks: dict, script: dict, caption: dict) -> dict:
    log.info("=== STEP 7: OptimizationAgent ===")

    task = (
        f"Analyze this complete reel and score it across 5 dimensions.\n\n"
        f"HOOK (best): {hooks.get('best_hook', {}).get('text', '')}\n"
        f"SCRIPT: {json.dumps(script.get('script', {}), ensure_ascii=False)}\n"
        f"CAPTION first line: {caption.get('caption_lines', {}).get('hook_line', '')}\n"
        f"CTA: {script.get('script', {}).get('cta', {}).get('text', '')}\n\n"
        f"Score each dimension 1-10. Identify 2-3 concrete improvements.\n"
        f"Write output to output/agents/07_optimization.json."
    )
    response = _call_agent("optimization", task)
    result = _extract_json_from_response(response, "optimization")

    _write_handoff("07_optimization.json", result)
    score = result.get("overall_score", 0)
    decision = result.get("decision", "unknown")
    log.info(f"[optimization] Score: {score}/10 — {decision}")

    improvements = result.get("improvements", [])
    for imp in improvements[:3]:
        log.info(f"  - [{imp.get('dimension')}] {imp.get('issue', '')}")
    return result


# ── Utility helpers ───────────────────────────────────────────────────────────

def _write_handoff(filename: str, data: dict):
    path = HANDOFF_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.debug(f"Handoff written: {path}")


def _extract_json_from_response(response: str, context: str) -> dict:
    """Extract the first JSON object or array from an agent response."""
    import re

    # Try to find JSON block in markdown code fences
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    match = re.search(r"(\{[\s\S]*\})", response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            # Try cleaning common issues
            cleaned = match.group(1)
            cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)  # trailing commas
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

    log.warning(f"[{context}] Could not parse JSON from response, returning raw text")
    return {"raw_response": response, "parse_error": True}


def _extract_yaml_from_response(response: str, script: dict) -> dict:
    """Extract YAML config from agent response or build from script."""
    import re

    # Try YAML code block
    match = re.search(r"```(?:yaml)?\s*([\s\S]*?)\s*```", response)
    if match:
        try:
            config = yaml.safe_load(match.group(1))
            if config and isinstance(config, dict) and "scenes" in config:
                return config
        except yaml.YAMLError:
            pass

    # Build config programmatically from script
    log.warning("[scene-builder] Building YAML from script data directly")
    return _build_yaml_from_script(script)


def _build_yaml_from_script(script: dict) -> dict:
    """Fallback: build a valid viral_text_centric_v1 YAML from script data."""
    scene_map = script.get("script", {})
    keyword_highlights = script.get("keyword_highlight", {})

    timing = {
        "hook": 3.2, "pain": 2.8, "shift": 2.8,
        "solution": 3.2, "result": 3.0, "cta": 3.5,
    }
    animations = {
        "hook": "impact_in", "pain": "slide_up", "shift": "slide_up",
        "solution": "typing", "result": "pop", "cta": "pop",
    }
    font_sizes = {
        "hook": "xl", "pain": "lg", "shift": "lg",
        "solution": "lg", "result": "lg", "cta": "xl",
    }
    emphasis = {
        "hook": True, "pain": False, "shift": True,
        "solution": False, "result": True, "cta": True,
    }

    scenes = []
    for scene_type in ["hook", "pain", "shift", "solution", "result", "cta"]:
        scene_data = scene_map.get(scene_type, {})
        text = scene_data.get("text", f"[{scene_type}]") if isinstance(scene_data, dict) else str(scene_data)
        word_count = len(text.split())
        base = timing[scene_type]
        extra = max(0, word_count - 5) * 0.4
        duration = round(base + extra, 1)

        scenes.append({
            "type": scene_type,
            "duration": duration,
            "text": text,
            "keyword_highlight": keyword_highlights.get(scene_type, ""),
            "text_animation": animations[scene_type],
            "font_size": font_sizes[scene_type],
            "emphasis": emphasis[scene_type],
        })

    return {
        "reel": {
            "template": "viral_text_centric_v1",
            "fps": 30,
            "width": 1080,
            "height": 1920,
        },
        "background": {
            "videos": [
                {"query": "person working alone laptop office calm", "path": ""},
                {"query": "minimal desk focus typing morning light", "path": ""},
                {"query": "professional thinking screen quiet workspace", "path": ""},
            ],
            "style": "slow ambient",
            "transitions": "smooth crossfade",
            "overlay_opacity": 0.55,
            "motion": "minimal",
        },
        "broll_video": "assets/video/typing_person.mp4",
        "audio": {
            "background_music": "assets/audio/lofi_beat.wav",
            "volume": 0.28,
            "voiceover": "",
            "voiceover_volume": 1.0,
        },
        "scenes": scenes,
    }


# ── Step 8: Memory update (self-improvement loop) ─────────────────────────────

def run_memory_update(
    run_id: str,
    trends: dict,
    hooks: dict,
    script: dict,
    video_result: dict,
    optimization: dict,
    planner_decision: dict,
) -> None:
    """
    Step 8 — runs after optimization. Saves everything to memory/*.json.
    Silent: logs warnings but never raises so a memory failure can't break the pipeline.
    """
    if not _AGENTS_AVAILABLE:
        return

    log.info("=== STEP 8: MemoryUpdate ===")
    try:
        mem = _get_memory()

        # ── Extract core data ─────────────────────────────────────────────────
        ideas = trends.get("ideas", [])
        rec_id = trends.get("recommended_idea_id", 0)
        rec_idea = next((i for i in ideas if i["id"] == rec_id), ideas[0] if ideas else {})
        topic = rec_idea.get("topic", planner_decision.get("idea", "unknown"))
        idea_type = planner_decision.get("idea_type", rec_idea.get("idea_type", "educational_explainer"))

        best_hook = hooks.get("best_hook", {})
        hook_text = best_hook.get("text", "")
        hook_pattern = best_hook.get("variant", "generic")
        hook_score = best_hook.get("total_score") or optimization.get("scores", {}).get("hook_strength", 0)

        opt_score: float = optimization.get("overall_score", 0)
        video_path: str = video_result.get("output_path") or ""
        strategy_mode: str = planner_decision.get("strategy_mode", "single")
        n_variants: int = planner_decision.get("n_hook_variants", 5)

        # ── Hook performance ──────────────────────────────────────────────────
        if hook_text:
            mem.update_hook_performance(
                hook_text=hook_text,
                score=float(hook_score) if hook_score else opt_score,
                idea_type=idea_type,
                pattern=hook_pattern,
                run_id=run_id,
                selected_as_best=True,
                language=planner_decision.get("lang", "fr"),
            )

        # ── Reel record ───────────────────────────────────────────────────────
        scores_breakdown = optimization.get("scores", {})
        mem.update_reel_record(run_id, {
            "topic": topic,
            "idea_type": idea_type,
            "best_hook": hook_text,
            "hook_pattern": hook_pattern,
            "optimization_score": opt_score,
            "hook_score": scores_breakdown.get("hook_strength", hook_score),
            "script_score": scores_breakdown.get("script_flow", 0),
            "video_path": video_path,
            "strategy_mode": strategy_mode,
            "n_variants_generated": n_variants,
            "video_status": video_result.get("status", "unknown"),
        })

        # ── Topic stats ───────────────────────────────────────────────────────
        angle = planner_decision.get("topic_angle_hint", "")
        emotion = rec_idea.get("emotion", "")
        mem.update_topic_stats(topic, opt_score, angle, emotion, idea_type)

        log.info(f"[memory] Updated: hook='{hook_text[:40]}' | score={opt_score} | topic='{topic[:40]}'")

    except Exception as e:
        log.warning(f"[memory] Update failed (non-fatal): {e}")


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_pipeline(
    idea: str,
    lang: str = "fr",
    skip_video: bool = False,
    from_step: str | None = None,
    parallel: bool = False,
    deep_plan: bool = False,
    news_mode: bool = False,
    trend_mode: bool = False,
    social_mode: bool = False,
    ideas_only: bool = False,
):
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info(
        f"Starting pipeline run_id={run_id} idea='{idea}' lang={lang} "
        f"skip_video={skip_video} parallel={parallel} deep_plan={deep_plan} "
        f"news_mode={news_mode} trend_mode={trend_mode} social_mode={social_mode}"
    )
    t_start = time.time()

    # ── Step 0: Planner (always runs, even when resuming from a later step) ───
    planner_decision = run_planner(idea, lang, run_id, parallel=parallel, deep_plan=deep_plan)

    # Determine pre-processing layer
    if trend_mode:
        pre_steps = TREND_STEPS
    elif social_mode:
        pre_steps = SOCIAL_STEPS
    elif news_mode:
        pre_steps = NEWS_STEPS
    else:
        pre_steps = []

    all_steps = pre_steps + STEPS

    steps_to_run = all_steps.copy()
    if from_step and from_step in all_steps:
        idx = all_steps.index(from_step)
        steps_to_run = all_steps[idx:]
        log.info(f"Resuming from step: {from_step}")

        # Load existing handoffs for skipped trend-mode steps
        social_trends      = _load_handoff("00_social_trends.json")      if "social-trend-agent"    not in steps_to_run else None
        trend_intelligence = _load_handoff("00_trend_intelligence.json") if "trend-fusion-agent"    not in steps_to_run else None
        trend_hooks        = _load_handoff("00_trend_hooks.json")        if "hook-from-trend-agent" not in steps_to_run else None
        # Load existing handoffs for skipped news-mode steps
        news_summary = _load_handoff("00_news.json")       if "news-agent"           not in steps_to_run else None
        news_hook    = _load_handoff("00_news_hook.json")  if "hook-from-news-agent" not in steps_to_run else None
        ai_insight   = _load_handoff("00_ai_insight.json") if "ai-insight-agent"     not in steps_to_run else None
        # Load existing handoffs for skipped standard steps
        trends       = _load_handoff("01_trends.json")       if "trend-research"    not in steps_to_run else None
        hooks        = _load_handoff("02_hooks.json")        if "hook-generator"    not in steps_to_run else None
        script       = _load_handoff("03_script.json")       if "script-writer"     not in steps_to_run else None
        config_path  = HANDOFF_DIR / "04_scene_config.yaml"  if "scene-builder"     not in steps_to_run else None
        video_result = _load_handoff("05_video_result.json") if "video-assembler"   not in steps_to_run else None
        caption      = _load_handoff("06_caption.json")      if "caption-generator" not in steps_to_run else None
    else:
        social_trends = trend_intelligence = trend_hooks = None
        news_summary = news_hook = ai_insight = None
        trends = hooks = script = config_path = video_result = caption = None

    optimization: dict = {}
    use_parallel = planner_decision.get("strategy_mode") == "ab_test"

    # ── Trend-mode: fetch social + news in parallel ────────────────────────────
    if trend_mode and (
        "social-trend-agent" in steps_to_run or "news-agent" in steps_to_run
    ):
        import concurrent.futures as _cf
        with _cf.ThreadPoolExecutor(max_workers=2) as pool:
            fut_social = (
                pool.submit(run_social_trend_agent, idea, lang)
                if "social-trend-agent" in steps_to_run else None
            )
            fut_news = (
                pool.submit(run_news_agent, idea, lang)
                if "news-agent" in steps_to_run else None
            )
            if fut_social:
                try:
                    social_trends = fut_social.result(timeout=60)
                except Exception as e:
                    log.warning(f"[pipeline] social-trend parallel fetch failed: {e}")
                    social_trends = {"trends": []}
            if fut_news:
                try:
                    news_summary = fut_news.result(timeout=60)
                except Exception as e:
                    log.warning(f"[pipeline] news parallel fetch failed: {e}")
                    news_summary = {"topics": []}

    # ── Social-only mode ───────────────────────────────────────────────────────
    if social_mode and "social-trend-agent" in steps_to_run:
        social_trends = run_social_trend_agent(idea=idea, lang=lang)

    # ── Trend fusion ───────────────────────────────────────────────────────────
    if "trend-fusion-agent" in steps_to_run:
        trend_intelligence = run_trend_fusion_agent(
            social_trends=social_trends or {},
            news_summary=news_summary or {},
            lang=lang,
            idea=idea,
        )

    # ── Hook from trend ────────────────────────────────────────────────────────
    if "hook-from-trend-agent" in steps_to_run:
        trend_hooks = run_hook_from_trend_agent(
            trend_intelligence=trend_intelligence or {},
            lang=lang,
            planner_decision=planner_decision,
            social_trends=social_trends,
        )

    # ── AI insight (trend-mode and social-mode use trend_hooks as input) ───────
    if "ai-insight-agent" in steps_to_run:
        # Choose the best available hook source
        if trend_mode or social_mode:
            hook_source = trend_hooks or {}
            news_source = trend_intelligence or {}
            # Normalise trend_hooks to news_summary-like structure for ai_insight_agent
            best_hook = hook_source.get("best_hook", {})
            top_news_equiv = {}
            if trend_intelligence and trend_intelligence.get("top_topics"):
                t = trend_intelligence["top_topics"][0]
                top_news_equiv = {
                    "title":   t.get("topic", ""),
                    "summary": t.get("evidence", ""),
                    "impact":  t.get("category", ""),
                    "region":  t.get("region", ""),
                    "viral_angle": t.get("angle", ""),
                }
            ai_insight = run_ai_insight_agent(
                news_summary={"topics": [top_news_equiv]} if top_news_equiv else {},
                news_hook={"best_hook": {
                    "hook": best_hook.get("hook", ""),
                    "pattern": best_hook.get("pattern", ""),
                    "news_title": best_hook.get("trend_topic", ""),
                }},
                lang=lang,
                planner_decision=planner_decision,
            )
        else:
            # news-mode path
            ai_insight = run_ai_insight_agent(
                news_summary=news_summary or {},
                news_hook=news_hook or {},
                lang=lang,
                planner_decision=planner_decision,
            )

    # ── Early exit for ideas_only mode (Ideas du jour — ~5 calls vs 13) ─────────
    if ideas_only:
        elapsed = time.time() - t_start
        log.info(f"[pipeline] ideas_only=True — skipping script/caption/video. elapsed={elapsed:.1f}s")
        return {
            "run_id":      run_id,
            "hooks":       [],
            "best_hook":   "",
            "script":      {},
            "caption":     "",
            "score":       0,
            "video_path":  None,
            "news":        news_summary,
            "social":      social_trends,
            "trends":      trend_intelligence,
            "trend_hooks": trend_hooks,
            "insight":     ai_insight,
            "error":       None,
        }

    # ── News-mode hook generation (unchanged) ─────────────────────────────────
    if "hook-from-news-agent" in steps_to_run:
        news_hook = run_hook_from_news_agent(
            news_summary=news_summary or {},
            lang=lang,
            planner_decision=planner_decision,
        )

    # News-only mode: run news-agent if not already done via trend parallel fetch
    if news_mode and "news-agent" in steps_to_run and news_summary is None:
        news_summary = run_news_agent(idea=idea, lang=lang)

    # ── Auto-derive idea from trends if none provided ──────────────────────────
    if not idea.strip():
        if trend_mode and trend_intelligence:
            topics = trend_intelligence.get("top_topics", [])
            if topics:
                idea = topics[0].get("topic", idea)
                log.info(f"[pipeline] Trend-mode: derived idea → '{idea}'")
        elif social_mode and social_trends:
            trends_list = social_trends.get("trends", [])
            if trends_list:
                idea = trends_list[0].get("title", idea)
                log.info(f"[pipeline] Social-mode: derived idea → '{idea}'")
        elif news_mode and news_summary:
            top_topics = news_summary.get("topics", [])
            if top_topics:
                idea = top_topics[0].get("title", idea)
                log.info(f"[pipeline] News-mode: derived idea → '{idea}'")

    # Run each step
    if "trend-research" in steps_to_run:
        trends = run_trend_research(idea, lang, ai_insight=ai_insight)

    if "hook-generator" in steps_to_run:
        if use_parallel and _AGENTS_AVAILABLE:
            n_hooks = planner_decision.get("n_hook_variants", 5)
            hooks = run_hook_generator_parallel(trends, lang, planner_decision, n=n_hooks)
        else:
            hooks = run_hook_generator(trends, lang, planner_decision=planner_decision)

    if "script-writer" in steps_to_run:
        n_scripts = planner_decision.get("n_script_variants", 1)
        if use_parallel and n_scripts > 1 and hooks and _AGENTS_AVAILABLE:
            all_hooks = hooks.get("hooks", [])
            scoring = _get_scoring()
            top_hooks = scoring.select_top_hooks(all_hooks, n=n_scripts) if scoring else all_hooks[:n_scripts]
            log.info(f"[pipeline] Parallel script mode — top {len(top_hooks)} hooks selected for script gen")
            script = run_script_writer_parallel(trends, lang, top_hooks, planner_decision)
        else:
            script = run_script_writer(trends, hooks, lang)

    if "scene-builder" in steps_to_run:
        config_path = run_scene_builder(script, lang)

    if "video-assembler" in steps_to_run:
        video_result = run_video_assembler(config_path, skip_video=skip_video)

    if "caption-generator" in steps_to_run:
        caption = run_caption_generator(trends, script, video_result, lang)

    if "optimization" in steps_to_run:
        optimization = run_optimization(trends, hooks, script, caption)

    # ── Step 8: Memory update (self-improvement loop) ─────────────────────────
    if trends and hooks and optimization:
        run_memory_update(
            run_id=run_id,
            trends=trends,
            hooks=hooks,
            script=script or {},
            video_result=video_result or {},
            optimization=optimization,
            planner_decision=planner_decision,
        )

    # ── Trend memory update (trend / social / news modes) ─────────────────────
    if (trend_mode or social_mode or news_mode) and _AGENTS_AVAILABLE:
        try:
            mem = _get_memory()
            best_trend_hook = (
                (trend_hooks or {}).get("best_hook", {})
                or (news_hook or {}).get("best_hook", {})
            )
            active_sources = (
                ["reddit", "news"] if trend_mode
                else ["reddit"] if social_mode
                else ["news"]
            )
            mem.update_trend_performance(run_id, {
                "topic":          idea,
                "sources":        active_sources,
                "virality_score": (
                    (trend_intelligence or {}).get("top_topics", [{}])[0].get("virality_score")
                    or (social_trends or {}).get("trends", [{}])[0].get("virality_score")
                    or (news_summary or {}).get("topics", [{}])[0].get("virality_score")
                    or 0
                ),
                "reel_score":     optimization.get("overall_score", 0),
                "hook_used":      best_trend_hook.get("hook") or best_trend_hook.get("text", ""),
                "angle_type":     (ai_insight or {}).get("angle_type", ""),
                "trend_mode":     "trend" if trend_mode else ("social" if social_mode else "news"),
            })
        except Exception as e:
            log.warning(f"[trend-memory] Update failed (non-fatal): {e}")

    # ── Final summary ──────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    try:
        _print_summary(trends, hooks, script, video_result, caption, optimization, elapsed, planner_decision)
    except (ValueError, OSError):
        pass  # stdout may be closed/unavailable when called from Streamlit

    return {
        "run_id":      run_id,
        "hooks":       (hooks or {}).get("hooks", []),
        "best_hook":   (hooks or {}).get("best_hook", {}).get("text", ""),
        "script":      (script or {}).get("script", {}),
        "caption":     (caption or {}).get("caption", ""),
        "score":       optimization.get("overall_score", 0),
        "video_path":  (video_result or {}).get("output_path"),
        "news":        news_summary,
        "social":      social_trends,
        "trends":      trend_intelligence,
        "trend_hooks": trend_hooks,
        "insight":     ai_insight,
        "error":       None,
    }


def run_full_pipeline(
    topic: str = "",
    trend_mode: bool = False,
    social_mode: bool = False,
    news_mode: bool = False,
    lang: str = "fr",
    parallel: bool = False,
    skip_video: bool = False,
    ideas_only: bool = False,
) -> dict:
    """
    Public Streamlit entry point — thin wrapper around run_pipeline().
    ideas_only=True: stops after hooks/insight (no script/caption/video). ~5 API calls vs 13.
    Never raises: all errors captured in result['error'].
    """
    try:
        return run_pipeline(
            idea=topic,
            lang=lang,
            skip_video=skip_video,
            parallel=parallel,
            news_mode=news_mode,
            trend_mode=trend_mode,
            social_mode=social_mode,
            ideas_only=ideas_only,
        )
    except Exception as exc:
        log.error(f"[run_full_pipeline] Fatal: {exc}", exc_info=True)
        return {
            "run_id":      datetime.now().strftime("%Y%m%d_%H%M%S"),
            "hooks":       [],
            "best_hook":   "",
            "script":      {},
            "caption":     "",
            "score":       0,
            "video_path":  None,
            "news":        None,
            "social":      None,
            "trends":      None,
            "trend_hooks": None,
            "insight":     None,
            "error":       str(exc),
        }


def _load_handoff(filename: str) -> dict:
    path = HANDOFF_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _print_summary(trends, hooks, script, video_result, caption, optimization, elapsed,
                   planner_decision=None):
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    if planner_decision:
        mode = planner_decision.get("strategy_mode", "?")
        idea_type = planner_decision.get("idea_type", "?")
        print(f"Plan:     {mode} | type={idea_type}")
        reasoning = planner_decision.get("reasoning", "")
        if reasoning:
            print(f"Reason:   {reasoning[:80]}{'...' if len(reasoning) > 80 else ''}")

    if trends:
        rec_id = trends.get("recommended_idea_id", 0)
        ideas = trends.get("ideas", [])
        rec = next((i for i in ideas if i["id"] == rec_id), ideas[0] if ideas else {})
        print(f"Topic:    {rec.get('topic', 'N/A')}")

    if hooks:
        best = hooks.get("best_hook", {})
        print(f"Hook:     {best.get('text', 'N/A')} (score: {best.get('total_score', 0)})")

    if script:
        scenes = script.get("script", {})
        print(f"Script:   {len(scenes)} scenes")

    if video_result:
        status = video_result.get("status", "unknown")
        path = video_result.get("output_path", "N/A")
        print(f"Video:    {status} → {path}")

    if caption:
        hook_line = caption.get("caption_lines", {}).get("hook_line", "")
        print(f"Caption:  {hook_line[:60]}...")

    if optimization:
        score = optimization.get("overall_score", 0)
        decision = optimization.get("decision", "unknown")
        print(f"Score:    {score}/10 — {decision}")

    print(f"Time:     {elapsed:.0f}s")
    print("=" * 60)
    print(f"\nHandoff files in: {HANDOFF_DIR}")
    print(f"Memory files in:  {Path('memory').resolve()}")
    print(f"Agent configs in: {AGENTS_DIR}")


def _print_memory_report() -> None:
    """Print a human-readable summary of everything in memory/."""
    if not _AGENTS_AVAILABLE:
        print("agents/ modules not available — memory report unavailable.")
        return

    mem = _get_memory()
    summary = mem.get_strategy_summary()

    print("\n" + "=" * 60)
    print(f"MEMORY REPORT — {datetime.today().strftime('%Y-%m-%d')}")
    print("=" * 60)

    import json as _json
    from pathlib import Path as _Path

    hooks_data = _json.loads((_Path("memory") / "hooks_performance.json").read_text(encoding="utf-8"))
    scores_data = _json.loads((_Path("memory") / "reel_scores.json").read_text(encoding="utf-8"))
    topics_data = _json.loads((_Path("memory") / "topic_performance.json").read_text(encoding="utf-8"))

    n_hooks = len(hooks_data.get("hooks", []))
    n_runs = len(scores_data.get("runs", []))
    n_topics = len(topics_data.get("topics", {}))
    last_run = scores_data["runs"][-1]["date"] if scores_data.get("runs") else "never"
    recent_avg = summary.get("recent_avg_score")

    print(f"Hooks tracked:    {n_hooks}")
    print(f"Topics tracked:   {n_topics}")
    print(f"Pipeline runs:    {n_runs} (last: {last_run})")
    print(f"Recent avg score: {recent_avg if recent_avg is not None else 'no data yet'}")
    print()

    print("Pattern boosts (history-derived):")
    boosts = summary.get("style_boosts", {})
    for pattern, boost in sorted(boosts.items(), key=lambda x: -x[1]):
        bar = "+" if boost > 1.0 else ("-" if boost < 1.0 else " ")
        print(f"  {bar} {pattern:<22} ×{boost:.2f}")
    print()

    print("Best hooks (all time):")
    best_data = _json.loads((_Path("memory") / "best_hooks.json").read_text(encoding="utf-8"))
    all_hooks = sorted(
        [h for hs in best_data.get("by_type", {}).values() for h in hs],
        key=lambda h: h.get("avg_score", 0),
        reverse=True,
    )
    for h in all_hooks[:5]:
        print(f"  [{h['avg_score']:.2f}] {h['text'][:50]} ({h.get('pattern','')})")
    print()

    if topics_data.get("topics"):
        print("Known topics:")
        for key, t in sorted(topics_data["topics"].items(), key=lambda x: -x[1].get("avg_score", 0)):
            print(f"  {key}: avg {t['avg_score']:.1f}, best_angle: {t.get('best_angle','?')[:40]}")

    print("=" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    # Fix Unicode output on Windows CLI only (NOT when imported by Streamlit)
    if sys.platform == "win32":
        try:
            import io as _io
            if hasattr(sys.stdout, "buffer"):
                sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "buffer"):
                sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    _all_resumable = list(dict.fromkeys(TREND_STEPS + SOCIAL_STEPS + NEWS_STEPS + STEPS))

    parser = argparse.ArgumentParser(
        description="Multi-agent reel pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrate.py "AI salary negotiation"
  python orchestrate.py "négocier son salaire avec l'IA" --lang fr
  python orchestrate.py "AI productivity tools" --skip-video
  python orchestrate.py "AI tools" --from-step caption-generator
  python orchestrate.py --news-mode
  python orchestrate.py --social-mode
  python orchestrate.py --trend-mode
  python orchestrate.py "intelligence artificielle" --trend-mode --skip-video
  python orchestrate.py --list-steps
        """,
    )
    parser.add_argument("idea", nargs="?", default="",
                        help="Reel idea or topic (optional in news/social/trend modes)")
    parser.add_argument("--lang", default="fr", choices=["fr", "en"],
                        help="Output language (default: fr)")
    parser.add_argument("--skip-video", action="store_true",
                        help="Skip video rendering (generate YAML + caption only)")
    parser.add_argument("--from-step", choices=_all_resumable, metavar="STEP",
                        help=f"Resume pipeline from this step. Choices: {', '.join(_all_resumable)}")
    parser.add_argument("--list-steps", action="store_true",
                        help="List all pipeline steps and exit")
    parser.add_argument("--parallel", action="store_true",
                        help="A/B test mode: 5 hook variants + 3 parallel scripts")
    parser.add_argument("--deep-plan", action="store_true",
                        help="Use Claude to enrich the planner decision (1 extra API call)")
    parser.add_argument("--memory-report", action="store_true",
                        help="Print a summary of all memory files and exit")
    parser.add_argument("--news-mode", action="store_true",
                        help=(
                            "Activate news-driven pipeline: "
                            "NewsAgent → HookFromNews → AIInsight → standard pipeline."
                        ))
    parser.add_argument("--social-mode", action="store_true",
                        help=(
                            "Activate social-trend pipeline: "
                            "SocialTrendAgent → HookFromTrend → AIInsight → standard pipeline."
                        ))
    parser.add_argument("--trend-mode", action="store_true",
                        help=(
                            "Activate full trend pipeline: "
                            "SocialTrendAgent + NewsAgent (parallel) → TrendFusion → HookFromTrend "
                            "→ AIInsight → standard pipeline."
                        ))

    args = parser.parse_args()

    if args.memory_report:
        _print_memory_report()
        return

    if args.list_steps:
        plan_exists = PLANNER_OUTPUT.exists()
        print("Pipeline steps (in order):")
        print(f"  0. [{'✓' if plan_exists else ' '}] planner              → 00_planner_decision.json")

        if args.trend_mode:
            print("  --- TREND-MODE pre-processing ---")
            for step in TREND_STEPS:
                output = STEP_OUTPUTS.get(step, "")
                exists = Path(output).exists() if output else False
                print(f"  T. [{'✓' if exists else ' '}] {step:<22} → {Path(output).name if output else 'N/A'}")
            print("  --- Standard pipeline ---")
        elif args.social_mode:
            print("  --- SOCIAL-MODE pre-processing ---")
            for step in SOCIAL_STEPS:
                output = STEP_OUTPUTS.get(step, "")
                exists = Path(output).exists() if output else False
                print(f"  S. [{'✓' if exists else ' '}] {step:<22} → {Path(output).name if output else 'N/A'}")
            print("  --- Standard pipeline ---")
        elif args.news_mode:
            print("  --- NEWS-MODE pre-processing ---")
            for step in NEWS_STEPS:
                output = STEP_OUTPUTS.get(step, "")
                exists = Path(output).exists() if output else False
                print(f"  N. [{'✓' if exists else ' '}] {step:<22} → {Path(output).name if output else 'N/A'}")
            print("  --- Standard pipeline ---")

        for i, step in enumerate(STEPS, 1):
            output = STEP_OUTPUTS.get(step, "")
            exists = Path(output).exists() if output else False
            status = "✓" if exists else " "
            print(f"  {i}. [{status}] {step:<22} → {Path(output).name if output else 'N/A'}")
        return

    idea = args.idea.strip() if args.idea else ""
    any_discovery_mode = args.news_mode or args.social_mode or args.trend_mode
    if not idea and not any_discovery_mode:
        idea = "AI productivity for professionals"

    run_pipeline(
        idea=idea,
        lang=args.lang,
        skip_video=args.skip_video,
        from_step=args.from_step,
        parallel=args.parallel,
        deep_plan=args.deep_plan,
        news_mode=args.news_mode,
        social_mode=args.social_mode,
        trend_mode=args.trend_mode,
    )


if __name__ == "__main__":
    main()
