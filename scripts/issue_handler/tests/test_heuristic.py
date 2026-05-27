"""Tests for Stage 3: Heuristic Check (T017)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from models import WebhookEvent
from stages.heuristic import heuristic_stage


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
        title="Test",
        body="",
        existing_labels=[],
        is_discussion=False,
    )
    defaults.update(overrides)
    return WebhookEvent(**defaults)


class TestHeuristicStage:
    @pytest.mark.asyncio
    async def test_below_threshold_needs_info(self) -> None:
        gh = AsyncMock()
        gh.add_labels = AsyncMock()
        event = _make_event(title="Bug", body="short")
        decision = await heuristic_stage(event, {"min_text_length": 50, "github_client": gh})
        assert decision.short_circuit is True
        assert decision.decision == "block"
        assert "needs-info" in decision.reason
        gh.add_labels.assert_awaited_once_with(42, ["needs-info"])

    @pytest.mark.asyncio
    async def test_at_threshold_passes(self) -> None:
        event = _make_event(title="A" * 50, body="")
        decision = await heuristic_stage(event, {"min_text_length": 50})
        assert decision.short_circuit is False
        assert decision.decision == "pass"

    @pytest.mark.asyncio
    async def test_above_threshold_passes(self) -> None:
        event = _make_event(title="Bug report", body="A" * 100)
        decision = await heuristic_stage(event, {"min_text_length": 50})
        assert decision.short_circuit is False

    @pytest.mark.asyncio
    async def test_default_min_text_length(self) -> None:
        gh = AsyncMock()
        gh.add_labels = AsyncMock()
        event = _make_event(title="Bug", body="short")
        decision = await heuristic_stage(event, {"github_client": gh})
        assert decision.short_circuit is True

    @pytest.mark.asyncio
    async def test_configurable_threshold(self) -> None:
        event = _make_event(title="B" * 20, body="")
        decision = await heuristic_stage(event, {"min_text_length": 10})
        assert decision.short_circuit is False

    @pytest.mark.asyncio
    async def test_discussion_skips_label(self) -> None:
        """Discussions have no label API, so needs-info should NOT be applied."""
        gh = AsyncMock()
        gh.add_labels = AsyncMock()
        event = _make_event(title="Bug", body="short", is_discussion=True)
        decision = await heuristic_stage(event, {"min_text_length": 50, "github_client": gh})
        assert decision.short_circuit is True
        gh.add_labels.assert_not_called()
