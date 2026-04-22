"""
agents/planner_agent.py — Strategic planning agent for the reel pipeline.

Two modes:
  Core (default): Pure Python decision tree. Zero LLM calls. Always fast.
  Deep  (--deep-plan): Claude-augmented. Enriches the core plan with
                       nuanced angle selection. One extra API call.

Public API:
    planner = PlannerAgent(memory_manager)
    decision = planner.plan(idea, lang, parallel=False, deep_plan=False)
    # → writes output/agents/00_planner_decision.json
    # → logs to memory/strategy_log.json
    # → returns decision dict
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.memory_manager import MemoryManager

log = logging.getLogger(__name__)

HANDOFF_DIR = Path(__file__).parent.parent / "output" / "agents"
AGENTS_DIR  = Path(__file__).parent.parent / ".claude" / "agents"

# ── Defaults ──────────────────────────────────────────────────────────────────

# Threshold: if recent avg score < this, switch to ab_test mode
_LOW_SCORE_THRESHOLD = 6.5

# Topic is "proven" above this score → stick to single mode, reuse best angle
_PROVEN_TOPIC_THRESHOLD = 8.0

# Per idea_type: default angle hint when no topic history exists
_ANGLE_DEFAULTS: dict[str, str] = {
    "before_after_time":     "concrete time savings — use specific numbers (e.g. '45 min → 4 min')",
    "prompt_reveal":         "the exact prompt as the value prop — show the output, not just the tool",
    "tool_demo":             "side-by-side: old manual way vs AI way, same task",
    "comparison":            "clear winner with one specific, measurable advantage",
    "data_workflow":         "eliminate the most painful manual data step with one AI action",
    "budget_finance":        "name a specific money amount saved or lost — make it feel real",
    "career_work":           "leverage AI to get a concrete career outcome (salary, promotion, time freed)",
    "controversial_opinion": "challenge a commonly held professional belief — back it with data",
    "build_in_public":       "real numbers from an ongoing project — month 1, week 3, etc.",
    "storytelling_personal": "personal transformation from a specific problem to a specific outcome",
    "educational_explainer": "simplify one complex concept to a single actionable step",
    "reactive_reply":        "direct response to trending news — add the AI productivity angle",
}

# Content calendar pairing notes per idea_type
_CALENDAR_NOTES: dict[str, str] = {
    "before_after_time":  "Pairs well after a 'tool demo' reel — audience already knows the tool.",
    "prompt_reveal":      "Best posted Monday–Wednesday when professionals are looking for work shortcuts.",
    "career_work":        "Post before salary review season (Oct–Nov, Feb–Mar) for max resonance.",
    "budget_finance":     "Post start or end of month — aligns with budget review cycles.",
    "controversial_opinion": "Best as a standalone — do not pair back-to-back with other opinions.",
    "tool_demo":          "Good series opener — introduces a tool before deeper prompt_reveal content.",
    "educational_explainer": "Use as recovery content after a low-engagement reel.",
}


class PlannerAgent:
    """
    Decides content strategy before the pipeline runs.

    Reads from MemoryManager. Writes 00_planner_decision.json.
    Logs every decision to memory/strategy_log.json for full traceability.
    """

    def __init__(self, memory_manager: "MemoryManager"):
        self._mem = memory_manager

    # ── Public API ────────────────────────────────────────────────────────────

    def plan(
        self,
        idea: str,
        lang: str = "fr",
        parallel: bool = False,
        deep_plan: bool = False,
        run_id: str | None = None,
    ) -> dict:
        """
        Run the planner and return the decision dict.
        Writes to 00_planner_decision.json and strategy_log.json.
        """
        run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        log.info(f"[planner] Planning run {run_id} | idea='{idea}' | parallel={parallel} | deep={deep_plan}")

        # ── 1. Gather memory context ──────────────────────────────────────────
        memory_summary = self._mem.get_strategy_summary()
        idea_type = _classify_idea(idea)
        topic_data = self._mem.read_topic_performance(idea)

        log.debug(f"[planner] idea_type={idea_type} | recent_avg={memory_summary.get('recent_avg_score')} "
                  f"| topic_runs={topic_data.get('runs', 0)}")

        # ── 2. Core (deterministic) plan ──────────────────────────────────────
        decision = self._core_plan(
            idea=idea,
            lang=lang,
            parallel=parallel,
            idea_type=idea_type,
            memory_summary=memory_summary,
            topic_data=topic_data,
        )
        decision["run_id"] = run_id
        decision["idea"] = idea
        decision["lang"] = lang

        # ── 3. Deep-plan enrichment (optional) ───────────────────────────────
        if deep_plan:
            try:
                decision = self._deep_plan(decision, memory_summary, idea, lang)
            except Exception as e:
                log.warning(f"[planner] Deep-plan failed ({e}), using core plan")

        # ── 4. Write handoff + log ────────────────────────────────────────────
        HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
        handoff_path = HANDOFF_DIR / "00_planner_decision.json"
        handoff_path.write_text(
            json.dumps(decision, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._mem.log_strategy_decision(run_id, {k: v for k, v in decision.items()
                                                  if k not in ("run_id", "idea", "lang")})

        log.info(
            f"[planner] mode={decision['strategy_mode']} | "
            f"n_hooks={decision['n_hook_variants']} | "
            f"n_scripts={decision['n_script_variants']} | "
            f"idea_type={decision['idea_type']}"
        )
        log.info(f"[planner] Reasoning: {decision['reasoning']}")
        return decision

    # ── Core decision tree ────────────────────────────────────────────────────

    def _core_plan(
        self,
        idea: str,
        lang: str,
        parallel: bool,
        idea_type: str,
        memory_summary: dict,
        topic_data: dict,
    ) -> dict:
        recent_avg: float | None = memory_summary.get("recent_avg_score")
        recent_count: int = memory_summary.get("recent_run_count", 0)
        style_boosts: dict = memory_summary.get("style_boosts", {})
        best_patterns: list = memory_summary.get("best_patterns", [])
        failed_patterns: list = memory_summary.get("failed_patterns", [])
        worst_patterns: list = memory_summary.get("worst_patterns", [])

        # ── Determine strategy mode + variant counts ──────────────────────────
        force_rewrite = False

        if parallel:
            strategy_mode = "ab_test"
            n_hook_variants = 5
            n_script_variants = 3
            reasoning = (
                f"Parallel mode requested. Running A/B test with {5} hook variants "
                f"and {3} scripts for maximum variant coverage."
            )

        elif recent_count == 0:
            # First run — no data, use safe defaults
            strategy_mode = "single"
            n_hook_variants = 5
            n_script_variants = 1
            reasoning = (
                "No prior run data. Single mode with 5 hook variants. "
                "Defaulting to loss/user_pain patterns — highest scoring from seed data. "
                "Run 3 reels to unlock data-driven angle selection."
            )

        elif recent_avg is not None and recent_avg < _LOW_SCORE_THRESHOLD:
            # Recent runs performing poorly — broaden search
            strategy_mode = "ab_test"
            n_hook_variants = 5
            n_script_variants = 3
            force_rewrite = True
            gap = round(_LOW_SCORE_THRESHOLD - recent_avg, 1)
            reasoning = (
                f"Recent avg score {recent_avg:.1f} is {gap} pts below threshold {_LOW_SCORE_THRESHOLD}. "
                f"Switching to A/B test mode ({5} hooks, {3} scripts) to find a higher-scoring variant. "
                f"force_rewrite=True to break out of low-scoring hook patterns."
            )

        elif topic_data and topic_data.get("best_score", 0) >= _PROVEN_TOPIC_THRESHOLD:
            # Known winning topic — don't over-engineer
            strategy_mode = "single"
            n_hook_variants = 5
            n_script_variants = 1
            best_angle = topic_data.get("best_angle", "unknown")
            best_score = topic_data.get("best_score", 0)
            reasoning = (
                f"Topic '{idea[:40]}' has a proven best score of {best_score}. "
                f"Reusing best angle: '{best_angle}'. "
                f"Single mode to maintain consistency with what worked."
            )

        else:
            strategy_mode = "single"
            n_hook_variants = 5
            n_script_variants = 1
            if recent_avg is not None:
                reasoning = (
                    f"Recent avg score {recent_avg:.1f} is acceptable. "
                    f"Single mode with 5 hook variants. "
                    f"Boosting {best_patterns[:2]} patterns based on historical data."
                )
            else:
                reasoning = (
                    "No recent score data. Single mode with standard 5 hook variants. "
                    "Pattern boosts derived from seed engagement data."
                )

        # ── Topic angle hint ──────────────────────────────────────────────────
        if topic_data and topic_data.get("best_angle"):
            topic_angle_hint = topic_data["best_angle"]
        else:
            topic_angle_hint = _ANGLE_DEFAULTS.get(idea_type, "concrete, specific, actionable outcome")

        # ── Reference hooks (best performers for this idea type) ──────────────
        ref_hook_data = self._mem.read_best_hooks(idea_type, top_n=3)
        reference_hooks = [
            h["text"] for h in ref_hook_data
            if h.get("avg_score", 0) >= 7.5
        ]

        # ── Avoid patterns list ───────────────────────────────────────────────
        # Combine explicitly failed + worst-performing, deduplicated
        avoid = list(dict.fromkeys(failed_patterns + worst_patterns[:2]))
        # Always avoid generic unless it's the only option
        if "generic" not in avoid and style_boosts.get("generic", 1.0) < 0.7:
            avoid.append("generic")

        # ── Content calendar note ─────────────────────────────────────────────
        calendar_note = _CALENDAR_NOTES.get(idea_type)

        return {
            "strategy_mode": strategy_mode,
            "n_hook_variants": n_hook_variants,
            "n_script_variants": n_script_variants,
            "idea_type": idea_type,
            "topic_angle_hint": topic_angle_hint,
            "hook_style_boost": style_boosts,
            "avoid_patterns": avoid,
            "reference_hooks": reference_hooks,
            "force_rewrite": force_rewrite,
            "content_calendar_note": calendar_note,
            "reasoning": reasoning,
        }

    # ── Deep-plan (Claude-augmented) ──────────────────────────────────────────

    def _deep_plan(self, core_decision: dict, memory_summary: dict, idea: str, lang: str) -> dict:
        """
        Call Claude to enrich the core plan. Reads .claude/agents/planner.md for system prompt.
        Falls back to core_decision if anything fails.
        """
        import anthropic

        agent_file = AGENTS_DIR / "planner.md"
        if not agent_file.exists():
            log.warning("[planner] planner.md not found, skipping deep-plan")
            return core_decision

        # Extract system prompt from agent file
        raw = agent_file.read_text(encoding="utf-8")
        lines = raw.split("\n")
        in_front, done_front, sys_lines = False, False, []
        for i, line in enumerate(lines):
            if i == 0 and line.strip() == "---":
                in_front = True; continue
            if in_front and line.strip() == "---":
                in_front = False; done_front = True; continue
            if done_front:
                sys_lines.append(line)
        system_prompt = "\n".join(sys_lines).strip()

        user_message = (
            f"Enrich this core plan.\n\n"
            f"IDEA: {idea}\n"
            f"LANGUAGE: {lang}\n\n"
            f"CORE PLAN:\n{json.dumps(core_decision, ensure_ascii=False, indent=2)}\n\n"
            f"MEMORY SUMMARY:\n{json.dumps(memory_summary, ensure_ascii=False, indent=2)}\n\n"
            f"Return the enriched plan as JSON. All fields from the schema are required."
        )

        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            log.warning("[planner] ANTHROPIC_API_KEY not set, skipping deep-plan")
            return core_decision

        log.info("[planner] Calling Claude for deep-plan enrichment...")
        t0 = time.time()
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        elapsed = time.time() - t0
        log.info(f"[planner] Deep-plan done in {elapsed:.1f}s")

        # Parse response — merge into core_decision
        response = msg.content[0].text
        enriched = _parse_json_response(response)
        if enriched and isinstance(enriched, dict):
            # Merge: enriched values override core values for allowed keys
            _ENRICHABLE = {
                "topic_angle_hint", "hook_style_boost", "avoid_patterns",
                "content_calendar_note", "reasoning"
            }
            for key in _ENRICHABLE:
                if key in enriched and enriched[key]:
                    core_decision[key] = enriched[key]
            log.debug("[planner] Deep-plan enrichment applied successfully")
        else:
            log.warning("[planner] Deep-plan response could not be parsed, using core plan")

        return core_decision


# ── Module-level helpers ──────────────────────────────────────────────────────

def _classify_idea(idea: str) -> str:
    """
    Classify idea into one of 12 content types.
    Delegates to hook_engine_v3 if available, else uses inline fallback.
    """
    try:
        from utils.hook_engine_v3 import classify_idea_type
        return classify_idea_type(idea)
    except ImportError:
        pass

    i = idea.lower()
    if any(k in i for k in ["prompt", "chatgpt", "claude", "gpt"]):
        return "prompt_reveal"
    if any(k in i for k in ["budget", "chf", "argent", "money", "finance", "depenses", "salaire", "salary", "salary"]):
        return "budget_finance"
    if any(k in i for k in ["excel", "vlookup", "data", "dax", "python", "script", "tableau"]):
        return "data_workflow"
    if any(k in i for k in ["vs ", "versus", "comparaison", "compare", "vs."]):
        return "comparison"
    if any(k in i for k in ["augmentation", "salaire", "cv", "job", "carriere", "career", "salary", "negotiate"]):
        return "career_work"
    if any(k in i for k in ["→", "h →", "min →", "heures", "minutes", "passe de", "from", "to ", "cut"]):
        return "before_after_time"
    if any(k in i for k in ["fail", "build in public", "semaine 1", "mois 1", "week 1", "month 1"]):
        return "build_in_public"
    if any(k in i for k in ["opinion", "faux", "personne ne", "controversial", "unpopular", "contre"]):
        return "controversial_opinion"
    if any(k in i for k in ["revenus", "income", "side", "passive", "freelance", "client"]):
        return "budget_finance"
    return "educational_explainer"


def _parse_json_response(response: str) -> dict | None:
    """Extract first JSON object from a text response."""
    import re
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"(\{[\s\S]*\})", response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            cleaned = re.sub(r",\s*([}\]])", r"\1", match.group(1))
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
    return None
