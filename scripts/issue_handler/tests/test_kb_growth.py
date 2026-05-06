"""Tests for KB growth scan (T030, T031)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge_base import ApprovedAnswer, KnowledgeBase
from knowledge_base.kb_growth import generate_digest, scan_closed_issues


def _make_kb(answers: list[ApprovedAnswer] | None = None) -> KnowledgeBase:
    """Create a mock KnowledgeBase."""
    kb = MagicMock(spec=KnowledgeBase)
    kb.get_all_answers.return_value = answers or []
    return kb


def _make_issue(number: int, title: str, body: str = "", labels: list[str] | None = None) -> dict:
    """Create a mock GitHub issue dict."""
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": "closed",
        "labels": [{"name": lbl} for lbl in (labels or [])],
    }


class TestScanClosedIssues:
    """T030: Tests for KB growth scan."""

    @pytest.mark.asyncio
    async def test_identifies_candidates(self) -> None:
        gh = AsyncMock()
        gh.get_closed_issues_since = AsyncMock(return_value=[
            _make_issue(1, "How to configure Home Assistant", "I want to integrate HA"),
        ])
        kb = _make_kb([
            ApprovedAnswer(filename="docker.md", tags=["docker", "install"], content="Docker setup"),
        ])
        result = await scan_closed_issues(gh, kb, since_days=7)
        assert result["candidate_count"] == 1
        assert result["candidates"][0]["number"] == 1

    @pytest.mark.asyncio
    async def test_identifies_covered_issues(self) -> None:
        gh = AsyncMock()
        gh.get_closed_issues_since = AsyncMock(return_value=[
            _make_issue(2, "Docker install question", "How to install docker for setup"),
        ])
        kb = _make_kb([
            ApprovedAnswer(filename="docker.md", tags=["docker", "install"], content="Docker setup"),
        ])
        result = await scan_closed_issues(gh, kb, since_days=7)
        assert result["covered_count"] == 1
        assert result["candidate_count"] == 0

    @pytest.mark.asyncio
    async def test_filters_kb_scanned_issues(self) -> None:
        gh = AsyncMock()
        gh.get_closed_issues_since = AsyncMock(return_value=[
            _make_issue(3, "Old question", labels=["support", "kb-scanned"]),
            _make_issue(4, "New question about something"),
        ])
        kb = _make_kb()
        result = await scan_closed_issues(gh, kb, since_days=7)
        assert result["support_count"] == 1
        assert result["total_scanned"] == 2

    @pytest.mark.asyncio
    async def test_produces_digest_markdown(self) -> None:
        gh = AsyncMock()
        gh.get_closed_issues_since = AsyncMock(return_value=[
            _make_issue(5, "Speaker setup help"),
        ])
        kb = _make_kb()
        result = await scan_closed_issues(gh, kb, since_days=7)
        digest = generate_digest(result)
        assert "KB Growth Digest" in digest
        assert "#5" in digest


class TestEdgeCases:
    """T031: Edge case tests for KB growth."""

    @pytest.mark.asyncio
    async def test_no_closed_issues(self) -> None:
        gh = AsyncMock()
        gh.get_closed_issues_since = AsyncMock(return_value=[])
        kb = _make_kb()
        result = await scan_closed_issues(gh, kb, since_days=7)
        assert result["total_scanned"] == 0
        assert result["candidate_count"] == 0
        digest = generate_digest(result)
        assert "No new KB candidates" in digest

    @pytest.mark.asyncio
    async def test_all_covered_by_kb(self) -> None:
        gh = AsyncMock()
        gh.get_closed_issues_since = AsyncMock(return_value=[
            _make_issue(10, "Docker install help", "docker install setup"),
        ])
        kb = _make_kb([
            ApprovedAnswer(filename="docker.md", tags=["docker", "install", "setup"], content="..."),
        ])
        result = await scan_closed_issues(gh, kb, since_days=7)
        assert result["candidate_count"] == 0
        assert result["covered_count"] == 1
        digest = generate_digest(result)
        assert "No new KB candidates" in digest

    def test_digest_format(self) -> None:
        result = {
            "total_scanned": 5,
            "support_count": 3,
            "covered_count": 1,
            "candidate_count": 2,
            "candidates": [
                {"number": 42, "title": "Test issue"},
                {"number": 43, "title": "Another issue"},
            ],
        }
        digest = generate_digest(result)
        assert "**Scanned**: 5" in digest
        assert "**Support issues**: 3" in digest
        assert "#42" in digest
        assert "#43" in digest
