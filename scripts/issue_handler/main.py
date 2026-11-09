"""Entry point for the AI Issue Handler pipeline (T022).

Invoked by GitHub Actions workflow:
  python scripts/issue_handler/main.py

Environment variables:
  GITHUB_TOKEN     — auto-provided, used for search queries
  BOT_PAT          — bot account PAT for mutations
  OPENAI_API_KEY   — OpenAI fallback API key
  GITHUB_EVENT_PATH — path to event payload JSON
  GITHUB_EVENT_NAME — event type (issues, issue_comment, discussion)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from ai_context import make_ai_context
from close_prompt import handle_closed, handle_prompt_edit
from cost_tracker import report_cost, tracker_from_settings
from dry_run import DryRunClient
from github_client import GitHubClient
from knowledge_base import KnowledgeBase
from model_choice import pick_model
from models import WebhookEvent
from pipeline import Pipeline
from precheck import delay_seconds, early_skip_reason, recheck
from reply import handle_reply
from retrieval import find_sources
from stages.action import action_stage
from stages.classifier import classifier_stage
from stages.hard_exit import hard_exit_stage
from stages.heuristic import heuristic_stage
from stages.rate_limiter import rate_limiter_stage
from stages.rule_engine import rule_engine_stage


def _load_settings() -> dict:
    """Load settings from rules.yml if available."""
    import yaml

    rules_path = Path(__file__).parent / "rules.yml"
    if rules_path.exists():
        with open(rules_path) as f:
            config = yaml.safe_load(f) or {}
        return config.get("settings", {})
    return {}


async def run() -> int:
    """Main pipeline execution. Returns exit code."""
    try:
        _start_time = time.monotonic()
        # Parse environment variables
        github_token = os.environ.get("GITHUB_TOKEN", "")
        bot_pat = os.environ.get("BOT_PAT", "")
        event_path = os.environ.get("GITHUB_EVENT_PATH", "")
        event_name = os.environ.get("GITHUB_EVENT_NAME", "issues")

        if not event_path:
            print("[ERROR] GITHUB_EVENT_PATH not set", file=sys.stderr)
            return 1

        # Load event payload
        with open(event_path) as f:
            payload = json.load(f)

        event = WebhookEvent.from_payload(event_name, payload)

        # Load settings
        settings = _load_settings()

        # Create GitHub client
        github_client = GitHubClient(
            bot_pat=bot_pat,
            github_token=github_token,
            repo_owner=event.repo_owner,
            repo_name=event.repo_name,
        )

        if os.environ.get("OCT_BOT_DRY_RUN", "true").lower() != "false":
            # Dry-run is the default: writes are only logged until it is switched off explicitly.
            github_client = DryRunClient(github_client)

        # Every exit path reports the cost: this view reads the counter even on runs that never call the AI
        cost_file = Path("/tmp/ai-cost-tracker/cost.json")
        cost_file.parent.mkdir(parents=True, exist_ok=True)
        tracker = tracker_from_settings(cost_file, settings)
        try:
            bot = settings.get("bot_username", "oct-support-bot")
            routed: dict | None = None
            if event.event_type == "issues" and event.action == "closed":
                # The maintainer closed an issue: ask what the outcome was
                ai = await make_ai_context(settings)
                tracker = ai["cost_tracker"]
                routed = await handle_closed(event, github_client, ai, bot)
            elif event.event_type == "issue_comment" and event.action == "edited":
                # A box in the bot's close prompt was ticked
                routed = await handle_prompt_edit(event, github_client, bot)
            elif event.event_type in ("issue_comment", "discussion_comment"):
                # A reply of the thread starter to the follow-up question
                ai = await make_ai_context(settings)
                tracker = ai["cost_tracker"]
                routed = await handle_reply(event, github_client, ai, bot)
            if routed is not None:
                print(json.dumps({"stage": "routed", **routed}))
                return 0

            skip = early_skip_reason(event)
            if skip is None:
                # Answer a few minutes later, not instantly, and only if nothing changed meanwhile.
                await asyncio.sleep(delay_seconds(settings))
                skip = await recheck(event, github_client, settings.get("bot_username", "oct-support-bot"))
            if skip is not None:
                print(json.dumps({"stage": "pre_check", "decision": "skip", "reason": skip, "short_circuit": True}))
                return 0

            # Check issue state (skip if deleted/closed)
            if event.issue_number is not None and not event.is_discussion:
                state = await github_client.get_issue_state(event.issue_number)
                if state in ("deleted", "closed"):
                    print(json.dumps({
                        "stage": "pre_check",
                        "decision": "skip",
                        "reason": f"issue state is {state}",
                        "short_circuit": True,
                    }))
                    return 0

            # Skip if bot already commented on this issue (prevent duplicate responses)
            # Must run for ALL events (issues, issue_comment) to prevent loops
            bot_username = settings.get("bot_username", "oct-support-bot")
            if event.issue_number is not None and not event.is_discussion:
                if await github_client.bot_has_commented(event.issue_number, bot_username):
                    print(json.dumps({
                        "stage": "pre_check",
                        "decision": "skip",
                        "reason": f"bot ({bot_username}) already commented on issue #{event.issue_number}",
                        "short_circuit": True,
                    }))
                    return 0

            # Load rules from rules.yml
            import yaml

            rules_path = Path(__file__).parent / "rules.yml"
            rules = []
            if rules_path.exists():
                with open(rules_path) as rf:
                    config = yaml.safe_load(rf) or {}
                rules = config.get("rules", [])

            # Load knowledge base
            kb_dir = str(Path(__file__).parent / "knowledge_base" / "approved_answers")
            kb = KnowledgeBase(kb_dir)
            kb_answers = kb.select_relevant_answers(event.title, event.body)

            # Load README.md and CONTRIBUTING.md from repo root
            repo_root = Path(__file__).parent.parent.parent
            readme_content = ""
            contributing_content = ""
            readme_path = repo_root / "README.md"
            if readme_path.exists():
                try:
                    readme_content = readme_path.read_text(encoding="utf-8")
                except Exception:
                    pass
            contributing_path = repo_root / "CONTRIBUTING.md"
            if contributing_path.exists():
                try:
                    contributing_content = contributing_path.read_text(encoding="utf-8")
                except Exception:
                    pass

            # Build pipeline context
            context = {
                "github_client": github_client,
                "bot_username": settings.get("bot_username", "oct-support-bot"),
                "min_text_length": settings.get("min_text_length", 50),
                "rate_limit_threshold": settings.get("rate_limit_threshold", 2),
                "monthly_budget_usd": settings.get("monthly_budget_usd", 0.90),
                "rules": rules,
                "kb_dir": kb_dir,
                "kb_answers": kb_answers,
                "readme_content": readme_content,
                "contributing_content": contributing_content,
                "openai_client": None,
                "cost_tracker": None,
            }

            # Sources for the answer: approved answers, docs and verified solved threads
            context["sources"] = await find_sources(
                github_client,
                event.title,
                event.body,
                kb_answers,
                repo_root,
                f"{event.repo_owner}/{event.repo_name}",
                min_relevance=settings.get("min_relevance", 0.3),
            )

            # Initialize AI clients if API keys available
            openai_api_key = os.environ.get("OPENAI_API_KEY", "")
            if openai_api_key:
                try:
                    from openai import AsyncOpenAI

                    context["openai_client"] = AsyncOpenAI(api_key=openai_api_key)
                except ImportError:
                    pass

            # Initialize cost tracker

            cost_file = Path("/tmp/ai-cost-tracker/cost.json")
            cost_file.parent.mkdir(parents=True, exist_ok=True)
            choice = await pick_model(context["openai_client"], settings)
            context["cost_tracker"] = tracker_from_settings(cost_file, settings, choice)
            context["openai_model"] = choice.id
            tracker = context["cost_tracker"]

            # Build and run pipeline
            pipeline = Pipeline()
            pipeline.add_stage("hard_exit", hard_exit_stage)
            pipeline.add_stage("rule_engine", rule_engine_stage)
            pipeline.add_stage("rate_limiter", rate_limiter_stage)
            pipeline.add_stage("heuristic", heuristic_stage)
            pipeline.add_stage("classifier", classifier_stage)
            pipeline.add_stage("action", action_stage)

            await pipeline.run(event, context)

            # T039: Structured logging
            classification = context.get("classification")
            duration_ms = int((time.monotonic() - _start_time) * 1000)
            log_entry = {
                "issue_number": event.issue_number,
                "category": classification.category if classification else "none",
                "confidence": classification.confidence if classification else 0.0,
                "kb_match": classification.kb_match if classification else None,
                "ai_call_count": context.get("ai_call_count", 1 if classification else 0),
                "processing_duration_ms": duration_ms,
            }
            print(json.dumps(log_entry))

            # T040: GitHub Actions Job Summary
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                response_type = "static"
                if classification and classification.category == "support" and classification.kb_match:
                    response_type = "kb_match"
                elif context.get("support_comment"):
                    response_type = "ai_generated"
                elif context.get("follow_up_questions"):
                    response_type = "ai_generated"

                summary = (
                    "| Issue | Category | Confidence | Response Type |\n"
                    "|-------|----------|------------|---------------|\n"
                    f"| #{event.issue_number} | {log_entry['category']} | "
                    f"{log_entry['confidence']:.2f} | {response_type} |\n"
                )
                with open(summary_path, "a") as sf:
                    sf.write(summary)

            return 0

        finally:
            report_cost(tracker)
            await github_client.close()

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


def main() -> None:
    exit_code = asyncio.run(run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
