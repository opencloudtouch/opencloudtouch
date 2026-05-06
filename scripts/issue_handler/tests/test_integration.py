"""Full pipeline integration test (T052)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from models import WebhookEvent
from pipeline import Pipeline
from stages.action import action_stage
from stages.classifier import classifier_stage
from stages.hard_exit import hard_exit_stage
from stages.heuristic import heuristic_stage
from stages.rate_limiter import rate_limiter_stage
from stages.rule_engine import rule_engine_stage
from tests.conftest import FIXTURES_DIR


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _build_pipeline() -> Pipeline:
    pipeline = Pipeline()
    pipeline.add_stage("hard_exit", hard_exit_stage)
    pipeline.add_stage("rule_engine", rule_engine_stage)
    pipeline.add_stage("rate_limiter", rate_limiter_stage)
    pipeline.add_stage("heuristic", heuristic_stage)
    pipeline.add_stage("classifier", classifier_stage)
    pipeline.add_stage("action", action_stage)
    return pipeline


class TestFullPipelineIntegration:
    @pytest.mark.asyncio
    async def test_issue_opened_community_user(self) -> None:
        """Community user opens issue → full pipeline processes it."""
        payload = _load_fixture("issue_opened.json")
        event = WebhookEvent.from_payload("issues", payload)

        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=0)

        mock_ai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "category": "bug", "confidence": 0.92, "reasoning": "crash report", "is_clear_bug": True
        })
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 20
        mock_ai.chat.completions.create = AsyncMock(return_value=mock_response)

        pipeline = _build_pipeline()
        context = {
            "github_client": gh,
            "bot_username": "oct-support-bot",
            "min_text_length": 50,
            "rate_limit_threshold": 2,
            "rules": [],
            "kb_dir": str(FIXTURES_DIR),
            "github_models_client": mock_ai,
            "openai_client": None,
            "cost_tracker": None,
            "kb_answers": [],
            "readme_content": "",
            "contributing_content": "",
        }

        # Override pipeline run to inject context
        decisions = []
        for name, func in pipeline._stages:
            decision = await func(event, context)
            decisions.append(decision)
            if decision.short_circuit:
                break

        # Should reach action stage and apply bug label
        assert any(d.stage == "action" and d.decision == "act" for d in decisions)
        gh.add_labels.assert_called_with(42, ["bug"])

    @pytest.mark.asyncio
    async def test_owner_issue_hard_exits(self) -> None:
        """Owner opens issue → hard exit, no processing."""
        payload = _load_fixture("issue_opened.json")
        payload["issue"]["author_association"] = "OWNER"
        event = WebhookEvent.from_payload("issues", payload)

        pipeline = _build_pipeline()
        context = {"github_client": AsyncMock(), "bot_username": "oct-support-bot"}

        decisions = []
        for name, func in pipeline._stages:
            decision = await func(event, context)
            decisions.append(decision)
            if decision.short_circuit:
                break

        assert len(decisions) == 1
        assert decisions[0].stage == "hard_exit"
        assert decisions[0].short_circuit is True

    @pytest.mark.asyncio
    async def test_discussion_created(self) -> None:
        """Discussion created → pipeline processes with comment-only (no labels)."""
        payload = _load_fixture("discussion_created.json")
        event = WebhookEvent.from_payload("discussion", payload)

        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=0)

        mock_ai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "category": "support", "confidence": 0.88, "reasoning": "question", "is_clear_bug": False
        })
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 20
        mock_ai.chat.completions.create = AsyncMock(return_value=mock_response)

        context = {
            "github_client": gh,
            "bot_username": "oct-support-bot",
            "min_text_length": 50,
            "rate_limit_threshold": 2,
            "rules": [],
            "kb_dir": str(FIXTURES_DIR),
            "github_models_client": mock_ai,
            "openai_client": None,
            "cost_tracker": None,
            "kb_answers": [],
            "readme_content": "",
            "contributing_content": "",
            "support_comment": "Here is help for multi-room setup.",
        }

        decisions = []
        for name, func in _build_pipeline()._stages:
            decision = await func(event, context)
            decisions.append(decision)
            if decision.short_circuit:
                break

        # Discussion: no labels applied, but comment should be posted
        action_decisions = [d for d in decisions if d.stage == "action"]
        assert len(action_decisions) == 1
        gh.add_labels.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limited_user(self) -> None:
        """User with too many issues → rate limited."""
        payload = _load_fixture("issue_opened.json")
        event = WebhookEvent.from_payload("issues", payload)

        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=5)

        context = {
            "github_client": gh,
            "bot_username": "oct-support-bot",
            "min_text_length": 50,
            "rate_limit_threshold": 2,
            "rules": [],
            "kb_dir": str(FIXTURES_DIR),
        }

        decisions = []
        for name, func in _build_pipeline()._stages:
            decision = await func(event, context)
            decisions.append(decision)
            if decision.short_circuit:
                break

        rate_decision = next(d for d in decisions if d.stage == "rate_limiter")
        assert rate_decision.decision == "block"
        assert rate_decision.short_circuit is True
