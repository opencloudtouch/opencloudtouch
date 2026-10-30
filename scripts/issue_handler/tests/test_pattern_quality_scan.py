"""Tests for the KB pattern & quality scan."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from knowledge_base import KnowledgeBase
from knowledge_base.pattern_quality_scan import PATTERNS, scan_open_issues

SCAN_DIR = Path(".local/agent-work/knowledge-kai/scans")


def _make_kb(answers: list | None = None) -> KnowledgeBase:
    kb = MagicMock(spec=KnowledgeBase)
    kb.get_all_answers.return_value = answers or []
    return kb


def _iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _make_issue(number: int, title: str, body: str = "", days_ago: float = 1) -> dict:
    return {
        "number": number,
        "title": title,
        "body": body,
        "updated_at": _iso_days_ago(days_ago),
        "created_at": _iso_days_ago(days_ago),
    }


async def _scan(issues: list[dict], answers: list | None = None) -> tuple[list, dict, dict]:
    gh = AsyncMock()
    gh.get_open_issues_since = AsyncMock(return_value=issues)
    await scan_open_issues(gh, _make_kb(answers))
    threads = yaml.safe_load((SCAN_DIR / "pattern_quality_threads.yaml").read_text(encoding="utf-8"))
    coverage = yaml.safe_load((SCAN_DIR / "pattern_quality_coverage.yaml").read_text(encoding="utf-8"))
    quality = yaml.safe_load((SCAN_DIR / "pattern_quality_quality.yaml").read_text(encoding="utf-8"))
    return threads["threads"], coverage["coverage"], quality["quality"]


def test_patterns_match_how_and_why_questions() -> None:
    assert any(re.search(p, "how do i pair a speaker") for p in PATTERNS)
    assert any(re.search(p, "why is the volume low") for p in PATTERNS)


@pytest.mark.asyncio
async def test_scan_records_patterns_for_how_question(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    threads, _, _ = await _scan([_make_issue(1, "How do I reset my speaker")])
    assert threads[0]["patterns"]


@pytest.mark.asyncio
async def test_stale_after_seven_days(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    threads, _, _ = await _scan([
        _make_issue(1, "Speaker offline", days_ago=8),
        _make_issue(2, "Speaker offline", days_ago=6),
    ])
    by_id = {t["id"]: t for t in threads}
    assert by_id[1]["stale"] is True
    assert by_id[2]["stale"] is False


@pytest.mark.asyncio
async def test_feedback_counters(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _, _, quality = await _scan([
        _make_issue(1, "Report A", "solved"),
        _make_issue(2, "Report B", "still broken"),
        _make_issue(3, "Report C", "no answer yet", days_ago=10),
    ])
    assert quality["solved"] == 1
    assert quality["didn’t_work"] == 1
    assert quality["no_response"] == 1


@pytest.mark.asyncio
async def test_coverage_map_marks_covered_topic(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    answer = SimpleNamespace(title="wizard", tags=["wizard"], filename="wizard.md")
    _, coverage, _ = await _scan([_make_issue(1, "Setup wizard crashes")], [answer])
    assert coverage["wizard"]["covered_by_kb"] is True


@pytest.mark.asyncio
async def test_thanks_counts_as_solved(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    threads, _, quality = await _scan([_make_issue(1, "Report", "thanks")])
    assert quality["solved"] == 1
    assert threads[0]["bot_response"]["score"] == 2
