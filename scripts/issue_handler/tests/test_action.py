"""Tests for Stage 5: Action (T019)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from models import ClassificationResult, WebhookEvent
from stages.action import action_stage


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
        title="Test issue",
        body="Some body text.",
        existing_labels=[],
        is_discussion=False,
    )
    defaults.update(overrides)
    return WebhookEvent(**defaults)


class TestLabelMapping:
    @pytest.mark.asyncio
    async def test_bug_label(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="crash", is_clear_bug=True),
        }
        event = _make_event()
        decision = await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["bug"])
        assert decision.decision == "act"

    @pytest.mark.asyncio
    async def test_feature_label(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="feature", confidence=0.85, reasoning="request"),
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["enhancement"])

    @pytest.mark.asyncio
    async def test_support_label(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="support", confidence=0.88, reasoning="question"),
            "support_comment": "Here is the answer to your question.",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["support"])
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_unclear_label_needs_info(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.5, reasoning="vague"),
            "follow_up_questions": "Could you provide more details?",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["needs-info"])
        gh.post_comment.assert_called_once()


class TestConfidenceThreshold:
    @pytest.mark.asyncio
    async def test_high_confidence_no_triage(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="clear", is_clear_bug=True),
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["bug"])

    @pytest.mark.asyncio
    async def test_low_confidence_adds_triage(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="feature", confidence=0.5, reasoning="maybe"),
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["enhancement"])
        gh.add_labels.assert_any_call(42, ["needs-triage"])

    @pytest.mark.asyncio
    async def test_unclear_exempt_from_triage(self) -> None:
        """FR-018: unclear category should NOT get needs-triage even with low confidence."""
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.3, reasoning="vague"),
            "follow_up_questions": "Please provide more details.",
        }
        event = _make_event()
        await action_stage(event, context)
        # Should get needs-info but NOT needs-triage
        gh.add_labels.assert_called_once_with(42, ["needs-info"])


class TestBugDifferentiation:
    @pytest.mark.asyncio
    async def test_clear_bug_no_comment(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="clear", is_clear_bug=True),
        }
        event = _make_event()
        await action_stage(event, context)
        gh.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_unclear_bug_posts_template_link(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.8, reasoning="vague", is_clear_bug=False),
        }
        event = _make_event()
        await action_stage(event, context)
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "bug_report" in comment.lower() or "template" in comment.lower()


class TestRuleMatchActions:
    @pytest.mark.asyncio
    async def test_rule_match_with_close(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "rule_match": {"answer": "This setup is not supported.", "labels": ["support"], "close": True},
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["support"])
        gh.post_comment.assert_called_once()
        gh.close_issue.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_rule_match_without_close(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "rule_match": {"answer": "Here is how to install.", "labels": ["support"], "close": False},
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["support"])
        gh.post_comment.assert_called_once()
        gh.close_issue.assert_not_called()


class TestDiscussionActions:
    """Discussion events: comment-only, no labels (T049)."""

    @pytest.mark.asyncio
    async def test_discussion_skips_labels(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="support", confidence=0.9, reasoning="question"),
            "support_comment": "Here is the answer.",
        }
        event = _make_event(is_discussion=True)
        await action_stage(event, context)
        gh.add_labels.assert_not_called()
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_discussion_posts_comment(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.5, reasoning="vague"),
            "follow_up_questions": "Could you elaborate?",
        }
        event = _make_event(is_discussion=True)
        await action_stage(event, context)
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_comment_event_labels_parent_issue(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="crash", is_clear_bug=True),
        }
        event = _make_event(event_type="issue_comment", action="created")
        await action_stage(event, context)
        gh.add_labels.assert_called_once_with(42, ["bug"])
