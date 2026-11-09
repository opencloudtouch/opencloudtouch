"""The read-only support thread scan."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backfill_scan import markdown, scan_thread
from followup import Comment, Thread

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


def _thread(comments: list[Comment]) -> Thread:
    return Thread("issue", 7, "", "Speaker offline", "https://x/7", "starter", NOW - timedelta(days=30), labels={"support"}, comments=comments)


def _c(cid: str, author: str, body: str = "a long enough comment body") -> Comment:
    return Comment(cid, author, "User", body, f"https://x/{cid}", NOW)


@pytest.mark.asyncio
async def test_thread_without_replies_is_unsolved_and_costs_no_ai_call() -> None:
    with patch("backfill_scan._ai_json", new=AsyncMock()) as ai:
        out = await scan_thread({}, _thread([_c("1", "starter")]), "open")
    assert out["status"] == "unsolved" and ai.await_count == 0


@pytest.mark.asyncio
async def test_solved_needs_a_comment_and_a_quote() -> None:
    t = _thread([_c("1", "helper"), _c("2", "starter", "that fixed it")])
    ok = {"status": "solved", "solution_comment": "c1", "solution": "Use host networking", "evidence": "that fixed it", "confidence": 0.9}
    with patch("backfill_scan._ai_json", new=AsyncMock(return_value=ok)):
        solved = await scan_thread({}, t, "closed")
    assert solved["status"] == "solved" and solved["solution_url"] == "https://x/1"
    with patch("backfill_scan._ai_json", new=AsyncMock(return_value={**ok, "evidence": None})):
        assert (await scan_thread({}, t, "closed"))["status"] == "unclear"
    with patch("backfill_scan._ai_json", new=AsyncMock(return_value={**ok, "solution_comment": "c9"})):
        assert (await scan_thread({}, t, "closed"))["status"] == "unclear"


@pytest.mark.asyncio
async def test_unusable_ai_answer_is_reported_as_error() -> None:
    with patch("backfill_scan._ai_json", new=AsyncMock(return_value=None)):
        out = await scan_thread({}, _thread([_c("1", "helper")]), "open")
    assert out["status"] == "error"


def test_markdown_groups_by_status() -> None:
    text = markdown([
        {"status": "solved", "kind": "issue", "title": "A", "url": "u", "state": "closed", "solution": "fix", "solution_url": "s", "confidence": 0.9},
        {"status": "unsolved", "kind": "issue", "title": "B", "url": "v", "state": "open", "reason": "nobody replied"},
    ])
    assert "## Looks solved (1)" in text and "## Not solved (1)" in text and "[solution comment](s)" in text
