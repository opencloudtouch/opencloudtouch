"""Tests for Stage 2: Rate Limiter (T035)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from models import WebhookEvent
from stages.rate_limiter import rate_limiter_stage


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


class TestRateLimiterStage:
    @pytest.mark.asyncio
    async def test_blocks_user_above_threshold(self) -> None:
        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=3)
        gh.post_comment = AsyncMock()
        context = {"github_client": gh, "rate_limit_threshold": 2}
        event = _make_event()
        decision = await rate_limiter_stage(event, context)
        assert decision.short_circuit is True
        assert decision.decision == "block"
        gh.post_comment.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_blocks_user_at_threshold(self) -> None:
        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=2)
        gh.post_comment = AsyncMock()
        context = {"github_client": gh, "rate_limit_threshold": 2}
        event = _make_event()
        decision = await rate_limiter_stage(event, context)
        assert decision.short_circuit is True

    @pytest.mark.asyncio
    async def test_passes_user_below_threshold(self) -> None:
        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=1)
        gh.post_comment = AsyncMock()
        context = {"github_client": gh, "rate_limit_threshold": 2}
        event = _make_event()
        decision = await rate_limiter_stage(event, context)
        assert decision.short_circuit is False
        assert decision.decision == "pass"
        gh.post_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_configurable_threshold(self) -> None:
        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=5)
        gh.post_comment = AsyncMock()
        context = {"github_client": gh, "rate_limit_threshold": 10}
        event = _make_event()
        decision = await rate_limiter_stage(event, context)
        assert decision.short_circuit is False

    @pytest.mark.asyncio
    async def test_default_threshold(self) -> None:
        gh = AsyncMock()
        gh.search_issues_by_author = AsyncMock(return_value=3)
        gh.post_comment = AsyncMock()
        context = {"github_client": gh}
        event = _make_event()
        decision = await rate_limiter_stage(event, context)
        assert decision.short_circuit is True
