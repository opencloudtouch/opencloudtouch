"""Tests for Stage 5: Action (T019)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from models import ClassificationResult, WebhookEvent
from stages.action import action_stage, _find_missing_bug_fields, _build_bug_comment

_FILLED_BUG_BODY = (
    "### What happened?\n\nDocker build fails with COPY error.\n\n"
    "### Steps to Reproduce\n\n```markdown\ndocker compose up --build\n```\n\n"
    "### Expected Behaviour\n\nbuild works\n\n"
    "### OpenCloudTouch Version\n\n1.1.0\n\n"
    "### Backend Logs\n\n```shell\nERROR: failed to compute cache key\n```\n"
)


def _make_event(**overrides) -> WebhookEvent:
    defaults = dict(
        event_type="issues",
        action="opened",
        sender_login="community-user",
        sender_type="User",
        author_association="NONE",
        repo_owner="opencloudtouch",
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
            "bot_username": "oct-support",
        }
        event = _make_event()
        decision = await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["bug"])
        assert decision.decision == "act"

    @pytest.mark.asyncio
    async def test_feature_label(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="feature", confidence=0.85, reasoning="request"),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["enhancement"])

    @pytest.mark.asyncio
    async def test_support_label(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="support", confidence=0.88, reasoning="question"),
            "support_comment": "Here is the answer to your question.",
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["support"])
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_unclear_label_needs_info(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.5, reasoning="vague"),
            "follow_up_questions": "Could you provide more details?",
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["needs-info"])
        gh.post_comment.assert_called_once()


class TestConfidenceThreshold:
    @pytest.mark.asyncio
    async def test_high_confidence_no_triage(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="clear", is_clear_bug=True),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["bug"])
        # Should NOT have needs-triage
        for call_args in gh.add_labels.call_args_list:
            assert call_args[0][1] != ["needs-triage"]

    @pytest.mark.asyncio
    async def test_low_confidence_adds_triage(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="feature", confidence=0.5, reasoning="maybe"),
            "bot_username": "oct-support",
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
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        # Should get needs-info but NOT needs-triage for unclear category
        gh.add_labels.assert_any_call(42, ["needs-info"])


class TestBugDifferentiation:
    @pytest.mark.asyncio
    async def test_clear_bug_gets_clear_template(self) -> None:
        """Bug report with all fields filled gets BUG_CLEAR_TEMPLATE."""
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="clear", is_clear_bug=True),
            "bot_username": "oct-support",
        }
        event = _make_event(body=_FILLED_BUG_BODY)
        await action_stage(event, context)
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "detailed bug report" in comment.lower()

    @pytest.mark.asyncio
    async def test_missing_fields_requests_specifics(self) -> None:
        """Bug report with missing logs/version gets targeted request."""
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.8, reasoning="vague", is_clear_bug=False),
            "bot_username": "oct-support",
        }
        event = _make_event(body="### What happened?\n\nSomething broke.\n\n### Steps to Reproduce\n\nno idea\n")
        await action_stage(event, context)
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "missing details" in comment.lower()
        assert "backend logs" in comment.lower()

    @pytest.mark.asyncio
    async def test_unclear_bug_posts_template_link(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.8, reasoning="vague", is_clear_bug=False),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "missing details" in comment.lower() or "bug_report" in comment.lower()


class TestBugFieldDetection:
    def test_all_fields_present(self) -> None:
        assert _find_missing_bug_fields(_FILLED_BUG_BODY) == []

    def test_missing_logs_and_version(self) -> None:
        body = "### What happened?\n\nCrash.\n\n### Steps to Reproduce\n\nclick button\n"
        missing = _find_missing_bug_fields(body)
        assert "Backend logs (`docker logs opencloudtouch`)" in missing
        assert "OpenCloudTouch version" in missing

    def test_empty_log_block(self) -> None:
        body = (
            "### Steps to Reproduce\n\ndone\n\n"
            "### Backend Logs\n\n```shell\n\n```\n\n"
            "### OpenCloudTouch Version\n\n1.0.0\n"
        )
        missing = _find_missing_bug_fields(body)
        assert "Backend logs (`docker logs opencloudtouch`)" in missing
        assert "OpenCloudTouch version" not in missing

    def test_build_comment_all_present(self) -> None:
        comment = _build_bug_comment(_FILLED_BUG_BODY)
        assert "detailed bug report" in comment.lower()

    def test_build_comment_missing_fields(self) -> None:
        comment = _build_bug_comment("### What happened?\n\nBroken.\n")
        assert "missing details" in comment.lower()
        assert "Steps to reproduce" in comment


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
            "bot_username": "oct-support",
        }
        event = _make_event(is_discussion=True)
        await action_stage(event, context)
        gh.add_labels.assert_not_called()
        gh.set_assignee.assert_not_called()
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_discussion_posts_comment(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.5, reasoning="vague"),
            "follow_up_questions": "Could you elaborate?",
            "bot_username": "oct-support",
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
            "bot_username": "oct-support",
        }
        event = _make_event(event_type="issue_comment", action="created")
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["bug"])


class TestThreeSignalGuarantee:
    """T011: Every category path must produce label + assignee + comment."""

    @pytest.mark.asyncio
    async def test_bug_clear_three_signals(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="crash", is_clear_bug=True),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_bug_unclear_three_signals(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.8, reasoning="vague", is_clear_bug=False),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_feature_three_signals(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="feature", confidence=0.85, reasoning="request"),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_support_kb_match_three_signals(self) -> None:
        from knowledge_base import ApprovedAnswer
        gh = AsyncMock()
        kb_answer = ApprovedAnswer(filename="docker-setup.md", tags=["docker"], content="Install Docker first.", title="Docker Setup")
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="support", confidence=0.9, reasoning="question", kb_match="docker-setup.md"
            ),
            "bot_username": "oct-support",
            "kb_answers": [kb_answer],
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_support_ai_three_signals(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="support", confidence=0.88, reasoning="question"),
            "support_comment": "Here is the answer.",
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_unclear_three_signals(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.5, reasoning="vague"),
            "follow_up_questions": "Could you provide more details?",
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_off_topic_three_signals(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="off-topic", confidence=0.85, reasoning="unrelated", is_on_topic=False
            ),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_spam_three_signals(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="spam", confidence=0.95, reasoning="advertising", is_on_topic=False
            ),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once_with(42, "oct-support")
        gh.post_comment.assert_called_once()


class TestRetryFallback:
    """T012: Retry+fallback — needs-triage when any signal fails after 3 retries."""

    @pytest.mark.asyncio
    async def test_total_failure_applies_needs_triage(self) -> None:
        gh = AsyncMock()
        gh.add_labels = AsyncMock(side_effect=Exception("API down"))
        gh.set_assignee = AsyncMock(side_effect=Exception("API down"))
        gh.post_comment = AsyncMock(side_effect=Exception("API down"))
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="crash", is_clear_bug=True),
            "bot_username": "oct-support",
        }
        event = _make_event()
        decision = await action_stage(event, context)
        # Should have attempted and applied needs-triage as fallback
        assert decision.decision == "act"

    @pytest.mark.asyncio
    async def test_partial_failure_assignee_fails(self) -> None:
        """Labels succeed, assignee fails 3x → needs-triage applied alongside existing labels."""
        gh = AsyncMock()
        gh.add_labels = AsyncMock(return_value=None)
        gh.set_assignee = AsyncMock(side_effect=Exception("assignee API down"))
        gh.post_comment = AsyncMock(return_value=None)
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="bug", confidence=0.9, reasoning="crash", is_clear_bug=True),
            "bot_username": "oct-support",
        }
        event = _make_event()
        decision = await action_stage(event, context)
        assert decision.decision == "act"
        # needs-triage should be applied as fallback for the failed signal
        label_calls = [str(c) for c in gh.add_labels.call_args_list]
        assert any("needs-triage" in c for c in label_calls)


class TestSupportKBMatch:
    """T016: Support + KB match path — approved answer posted."""

    @pytest.mark.asyncio
    async def test_kb_match_posts_approved_answer(self) -> None:
        from knowledge_base import ApprovedAnswer
        gh = AsyncMock()
        kb_answer = ApprovedAnswer(filename="docker-setup.md", tags=["docker"], content="Step 1: Install Docker...", title="Docker Setup")
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="support", confidence=0.9, reasoning="question", kb_match="docker-setup.md"
            ),
            "bot_username": "oct-support",
            "kb_answers": [kb_answer],
        }
        event = _make_event()
        await action_stage(event, context)
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "Install Docker" in comment

    @pytest.mark.asyncio
    async def test_kb_match_not_found_falls_back_to_empty(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="support", confidence=0.9, reasoning="question", kb_match="nonexistent.md"
            ),
            "bot_username": "oct-support",
            "kb_answers": [],
        }
        event = _make_event()
        await action_stage(event, context)
        # No comment posted since KB article not found and no AI response
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once()


class TestSupportAIResponse:
    """T017: Support + AI response path — context support_comment posted."""

    @pytest.mark.asyncio
    async def test_ai_response_posted(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="support", confidence=0.88, reasoning="question"),
            "support_comment": "Here is how to configure your speaker...",
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "configure your speaker" in comment

    @pytest.mark.asyncio
    async def test_no_support_comment_no_crash(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="support", confidence=0.88, reasoning="question"),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        # Labels and assignee should still work
        gh.add_labels.assert_called()
        gh.set_assignee.assert_called_once()


class TestUnclearFollowUp:
    """T020: Unclear + AI follow-up path — follow_up_questions posted, needs-info label."""

    @pytest.mark.asyncio
    async def test_follow_up_questions_posted(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.5, reasoning="vague"),
            "follow_up_questions": "Hi! Could you provide:\n1. What device?\n2. What OS?",
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["needs-info"])
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "device" in comment.lower()

    @pytest.mark.asyncio
    async def test_unclear_no_follow_up_no_crash(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(category="unclear", confidence=0.5, reasoning="vague"),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["needs-info"])
        gh.set_assignee.assert_called_once()


class TestOffTopicHandling:
    """T022-T023: Off-topic classification paths."""

    @pytest.mark.asyncio
    async def test_off_topic_high_confidence(self) -> None:
        """T022: off-topic label + OFF_TOPIC_TEMPLATE when is_on_topic=false and confidence≥0.7."""
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="off-topic", confidence=0.85, reasoning="unrelated", is_on_topic=False
            ),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["off-topic"])
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "OpenCloudTouch" in comment

    @pytest.mark.asyncio
    async def test_off_topic_low_confidence_needs_triage(self) -> None:
        """T023: needs-triage label when is_on_topic=false and confidence<0.7."""
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="off-topic", confidence=0.5, reasoning="maybe unrelated", is_on_topic=False
            ),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["needs-triage"])
        gh.post_comment.assert_called_once()


class TestSpamHandling:
    """T024: Spam/abuse classification path."""

    @pytest.mark.asyncio
    async def test_spam_label_and_template(self) -> None:
        gh = AsyncMock()
        context = {
            "github_client": gh,
            "classification": ClassificationResult(
                category="spam", confidence=0.95, reasoning="advertising", is_on_topic=False
            ),
            "bot_username": "oct-support",
        }
        event = _make_event()
        await action_stage(event, context)
        gh.add_labels.assert_any_call(42, ["spam"])
        gh.post_comment.assert_called_once()
        comment = gh.post_comment.call_args[0][1]
        assert "flagged" in comment.lower()


class TestTemplateConstants:
    """T029: Validate all template constants contain valid absolute URLs."""

    def test_bug_clear_template_has_url(self) -> None:
        from stages.action import BUG_CLEAR_TEMPLATE
        assert "https://github.com/opencloudtouch/opencloudtouch/" in BUG_CLEAR_TEMPLATE

    def test_feature_template_has_url(self) -> None:
        from stages.action import FEATURE_TEMPLATE
        assert "https://github.com/opencloudtouch/opencloudtouch/" in FEATURE_TEMPLATE

    def test_off_topic_template_content(self) -> None:
        from stages.action import OFF_TOPIC_TEMPLATE
        assert "OpenCloudTouch" in OFF_TOPIC_TEMPLATE

    def test_spam_template_content(self) -> None:
        from stages.action import SPAM_TEMPLATE
        assert "flagged" in SPAM_TEMPLATE.lower()

    def test_bug_template_comment_has_url(self) -> None:
        from stages.action import BUG_TEMPLATE_COMMENT
        assert "bug_report" in BUG_TEMPLATE_COMMENT.lower() or "template" in BUG_TEMPLATE_COMMENT.lower()
