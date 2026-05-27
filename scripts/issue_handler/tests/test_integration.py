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
        gh.add_labels.assert_any_call(42, ["bug"])

    @pytest.mark.asyncio
    async def test_owner_issue_hard_exits(self) -> None:
        """Owner opens issue → hard exit, no processing (when SKIP_ASSOCIATIONS is active)."""
        from stages.hard_exit import SKIP_ASSOCIATIONS

        payload = _load_fixture("issue_opened.json")
        payload["issue"]["author_association"] = "OWNER"
        event = WebhookEvent.from_payload("issues", payload)

        pipeline = _build_pipeline()
        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=0)
        context = {"github_client": gh, "bot_username": "oct-support-bot"}

        decisions = await pipeline.run(event, context)

        if "OWNER" in SKIP_ASSOCIATIONS:
            assert decisions[0].stage == "hard_exit"
            assert decisions[0].decision == "skip"
        else:
            # Owner filter disabled — pipeline processes normally
            assert decisions[0].stage == "hard_exit"
            assert decisions[0].decision == "pass"

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


class TestCategoryIntegration:
    """T042: Full classifier → action flow for each category with 3-signal check."""

    def _mock_classify_response(self, category: str, confidence: float = 0.9, **extra) -> MagicMock:
        data = {
            "category": category, "confidence": confidence, "reasoning": "test",
            "is_clear_bug": extra.get("is_clear_bug", False),
            "kb_match": extra.get("kb_match"), "is_on_topic": extra.get("is_on_topic", True),
        }
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(data)
        resp.usage = MagicMock()
        resp.usage.prompt_tokens = 50
        resp.usage.completion_tokens = 20
        return resp

    def _make_event(self, **kw) -> WebhookEvent:
        defaults = dict(
            event_type="issues", action="opened", sender_login="user", sender_type="User",
            author_association="NONE", repo_owner="opencloudtouch", repo_name="opencloudtouch",
            issue_number=42, title="Test", body="Body text with enough content here.", existing_labels=[], is_discussion=False,
        )
        defaults.update(kw)
        return WebhookEvent(**defaults)

    @pytest.mark.asyncio
    async def test_off_topic_integration(self) -> None:
        gh = AsyncMock()
        mock_ai = MagicMock()
        mock_ai.chat.completions.create = AsyncMock(
            return_value=self._mock_classify_response("off-topic", 0.85, is_on_topic=False)
        )
        context = {
            "github_models_client": mock_ai, "openai_client": None, "cost_tracker": None,
            "kb_answers": [], "readme_content": "", "contributing_content": "",
        }
        event = self._make_event(title="How to cook pasta", body="Recipe please")
        await classifier_stage(event, context)
        context["github_client"] = gh
        context["bot_username"] = "oct-support"
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["off-topic"])
        gh.set_assignee.assert_called_once()
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_spam_integration(self) -> None:
        gh = AsyncMock()
        mock_ai = MagicMock()
        mock_ai.chat.completions.create = AsyncMock(
            return_value=self._mock_classify_response("spam", 0.95, is_on_topic=False)
        )
        context = {
            "github_models_client": mock_ai, "openai_client": None, "cost_tracker": None,
            "kb_answers": [], "readme_content": "", "contributing_content": "",
        }
        event = self._make_event(title="Buy watches", body="Visit spam site")
        await classifier_stage(event, context)
        context["github_client"] = gh
        context["bot_username"] = "oct-support"
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["spam"])
        gh.set_assignee.assert_called_once()
        gh.post_comment.assert_called_once()


class TestEdgeCaseIntegration:
    """T043: Edge case integration tests — AI unavailable, budget, API failure."""

    @pytest.mark.asyncio
    async def test_ai_unavailable_fallback(self) -> None:
        gh = AsyncMock()
        mock_ai = MagicMock()
        mock_ai.chat.completions.create = AsyncMock(side_effect=Exception("AI down"))
        context = {
            "github_models_client": mock_ai, "openai_client": None, "cost_tracker": None,
            "kb_answers": [], "readme_content": "", "contributing_content": "",
        }
        event = WebhookEvent(
            event_type="issues", action="opened", sender_login="user", sender_type="User",
            author_association="NONE", repo_owner="opencloudtouch", repo_name="opencloudtouch",
            issue_number=99, title="Test", body="Test body content", existing_labels=[],
        )
        decision = await classifier_stage(event, context)
        assert decision.decision == "fallback"

        context["github_client"] = gh
        context["bot_username"] = "oct-support"
        await action_stage(event, context)
        gh.add_labels.assert_called()

    @pytest.mark.asyncio
    async def test_api_failure_retry_fallback(self) -> None:
        from models import ClassificationResult
        gh = AsyncMock()
        gh.add_labels = AsyncMock(return_value=None)
        gh.set_assignee = AsyncMock(side_effect=Exception("API down"))
        gh.post_comment = AsyncMock(return_value=None)
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="crash", is_clear_bug=True),
            "bot_username": "oct-support",
        }
        event = WebhookEvent(
            event_type="issues", action="opened", sender_login="user", sender_type="User",
            author_association="NONE", repo_owner="opencloudtouch", repo_name="opencloudtouch",
            issue_number=99, title="Bug", body="Crash", existing_labels=[],
        )
        decision = await action_stage(event, context)
        assert decision.decision == "act"
        label_calls = [str(c) for c in gh.add_labels.call_args_list]
        assert any("needs-triage" in c for c in label_calls)
