"""Tests for Stage 4: AI Classifier (T037, T041)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from models import WebhookEvent
from stages.classifier import _build_prompt_messages, classifier_stage


def _make_event(**overrides) -> WebhookEvent:
    defaults = dict(
        event_type="issues",
        action="opened",
        sender_login="community-user",
        sender_type="User",
        author_association="NONE",
        repo_owner="scheilch",
        repo_name="opencloudtouch",
        issue_number=42,
        title="Speaker crashes on play",
        body="When I press play, the speaker freezes and needs a restart. Device: SoundTouch 300, OS: Android 14.",
        existing_labels=[],
        is_discussion=False,
    )
    defaults.update(overrides)
    return WebhookEvent(**defaults)


class TestAIClassification:
    @pytest.mark.asyncio
    async def test_github_models_primary(self) -> None:
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "category": "bug", "confidence": 0.92, "reasoning": "crash report", "is_clear_bug": True
        })
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 20
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

        context = {
            "github_models_client": mock_openai,
            "openai_client": None,
            "cost_tracker": None,
            "kb_answers": [],
            "readme_content": "# Test",
            "contributing_content": "",
        }
        event = _make_event()
        decision = await classifier_stage(event, context)
        assert decision.decision == "classify"
        assert "classification" in context
        assert context["classification"].category == "bug"

    @pytest.mark.asyncio
    async def test_openai_fallback_on_failure(self) -> None:
        mock_gh_client = MagicMock()
        mock_gh_client.chat.completions.create = AsyncMock(side_effect=Exception("GitHub Models down"))

        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "category": "feature", "confidence": 0.85, "reasoning": "request", "is_clear_bug": False
        })
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 20
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_cost = MagicMock()
        mock_cost.is_budget_exceeded.return_value = False
        mock_cost.record_call = MagicMock()
        mock_cost.save = MagicMock()

        context = {
            "github_models_client": mock_gh_client,
            "openai_client": mock_openai,
            "cost_tracker": mock_cost,
            "kb_answers": [],
            "readme_content": "# Test",
            "contributing_content": "",
        }
        event = _make_event()
        await classifier_stage(event, context)
        assert context["classification"].category == "feature"
        mock_cost.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_json_retry(self) -> None:
        mock_openai = MagicMock()
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "Not valid JSON at all"
        bad_response.usage.prompt_tokens = 50
        bad_response.usage.completion_tokens = 10

        good_response = MagicMock()
        good_response.choices = [MagicMock()]
        good_response.choices[0].message.content = json.dumps({
            "category": "support", "confidence": 0.75, "reasoning": "question", "is_clear_bug": False
        })
        good_response.usage.prompt_tokens = 50
        good_response.usage.completion_tokens = 10

        mock_openai.chat.completions.create = AsyncMock(side_effect=[bad_response, good_response])

        context = {
            "github_models_client": mock_openai,
            "openai_client": None,
            "cost_tracker": None,
            "kb_answers": [],
            "readme_content": "# Test",
            "contributing_content": "",
        }
        event = _make_event()
        await classifier_stage(event, context)
        assert context["classification"].category == "support"

    @pytest.mark.asyncio
    async def test_ai_unavailable_needs_triage(self) -> None:
        mock_gh = MagicMock()
        mock_gh.chat.completions.create = AsyncMock(side_effect=Exception("down"))

        context = {
            "github_models_client": mock_gh,
            "openai_client": None,
            "cost_tracker": None,
            "kb_answers": [],
            "readme_content": "",
            "contributing_content": "",
        }
        event = _make_event()
        decision = await classifier_stage(event, context)
        assert decision.decision == "fallback"
        assert "needs-triage" in decision.reason

    @pytest.mark.asyncio
    async def test_budget_exhausted_needs_triage(self) -> None:
        mock_gh = MagicMock()
        mock_gh.chat.completions.create = AsyncMock(side_effect=Exception("down"))

        mock_cost = MagicMock()
        mock_cost.is_budget_exceeded.return_value = True

        context = {
            "github_models_client": mock_gh,
            "openai_client": MagicMock(),
            "cost_tracker": mock_cost,
            "kb_answers": [],
            "readme_content": "",
            "contributing_content": "",
        }
        event = _make_event()
        decision = await classifier_stage(event, context)
        assert "needs-triage" in decision.reason

    @pytest.mark.asyncio
    async def test_clear_bug_detection(self) -> None:
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "category": "bug", "confidence": 0.95, "reasoning": "clear bug", "is_clear_bug": True
        })
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 20
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

        context = {
            "github_models_client": mock_openai,
            "openai_client": None,
            "cost_tracker": None,
            "kb_answers": [],
            "readme_content": "",
            "contributing_content": "",
        }
        event = _make_event()
        await classifier_stage(event, context)
        assert context["classification"].is_clear_bug is True


class TestPromptConstruction:
    def test_includes_readme(self) -> None:
        messages = _build_prompt_messages("Bug title", "Bug body", "# README", "", [])
        system_msg = messages[0]["content"]
        assert "README" in system_msg

    def test_includes_approved_answers(self) -> None:
        from knowledge_base import ApprovedAnswer
        answers = [ApprovedAnswer(filename="test.md", tags=["test"], content="Answer content", title="Test")]
        messages = _build_prompt_messages("title", "body", "", "", answers)
        system_msg = messages[0]["content"]
        assert "Answer content" in system_msg

    def test_user_message_has_delimiters(self) -> None:
        messages = _build_prompt_messages("My Title", "My Body", "", "", [])
        user_msg = messages[1]["content"]
        assert "<user_issue_title>" in user_msg
        assert "<user_issue_body>" in user_msg
