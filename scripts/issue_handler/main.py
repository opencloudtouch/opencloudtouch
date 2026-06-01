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

from github_client import GitHubClient
from knowledge_base import KnowledgeBase
from models import WebhookEvent
from pipeline import Pipeline
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

        try:
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
                "github_models_client": None,
                "openai_client": None,
                "cost_tracker": None,
            }

            # Initialize AI clients if API keys available
            openai_api_key = os.environ.get("OPENAI_API_KEY", "")
            if github_token:
                try:
                    from openai import AsyncOpenAI

                    context["github_models_client"] = AsyncOpenAI(
                        base_url="https://models.inference.ai.azure.com",
                        api_key=github_token,
                    )
                except ImportError:
                    pass

            if openai_api_key:
                try:
                    from openai import AsyncOpenAI

                    context["openai_client"] = AsyncOpenAI(api_key=openai_api_key)
                except ImportError:
                    pass

            # Initialize cost tracker
            from cost_tracker import CostTracker

            cost_file = Path("/tmp/ai-cost-tracker/cost.json")
            cost_file.parent.mkdir(parents=True, exist_ok=True)
            context["cost_tracker"] = CostTracker(
                cost_file=cost_file,
                budget_usd=settings.get("monthly_budget_usd", 0.90),
            )

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
            await github_client.close()

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


def main() -> None:
    exit_code = asyncio.run(run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
