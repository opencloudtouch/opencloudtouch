"""Tests for Stage 0: Hard Exit (T015)."""

from __future__ import annotations

import pytest

from models import WebhookEvent
from stages.hard_exit import hard_exit_stage


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
        body="Some body text long enough for testing purposes.",
        existing_labels=[],
        is_discussion=False,
    )
    defaults.update(overrides)
    return WebhookEvent(**defaults)


class TestHardExitStage:
    @pytest.mark.asyncio
    async def test_skips_owner(self) -> None:
        event = _make_event(author_association="OWNER")
        decision = await hard_exit_stage(event, {})
        assert decision.short_circuit is True
        assert decision.decision == "skip"

    @pytest.mark.asyncio
    async def test_skips_member(self) -> None:
        event = _make_event(author_association="MEMBER")
        decision = await hard_exit_stage(event, {})
        assert decision.short_circuit is True

    @pytest.mark.asyncio
    async def test_skips_collaborator(self) -> None:
        event = _make_event(author_association="COLLABORATOR")
        decision = await hard_exit_stage(event, {})
        assert decision.short_circuit is True

    @pytest.mark.asyncio
    async def test_skips_bot_type(self) -> None:
        event = _make_event(sender_type="Bot")
        decision = await hard_exit_stage(event, {})
        assert decision.short_circuit is True

    @pytest.mark.asyncio
    async def test_skips_bot_username(self) -> None:
        event = _make_event(sender_login="oct-support-bot")
        decision = await hard_exit_stage(event, {"bot_username": "oct-support-bot"})
        assert decision.short_circuit is True

    @pytest.mark.asyncio
    async def test_passes_contributor(self) -> None:
        event = _make_event(author_association="CONTRIBUTOR")
        decision = await hard_exit_stage(event, {})
        assert decision.short_circuit is False
        assert decision.decision == "pass"

    @pytest.mark.asyncio
    async def test_passes_none_association(self) -> None:
        event = _make_event(author_association="NONE")
        decision = await hard_exit_stage(event, {})
        assert decision.short_circuit is False
