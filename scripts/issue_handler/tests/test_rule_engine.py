"""Tests for Stage 1: Rule Engine (T025)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from models import WebhookEvent
from stages.rule_engine import rule_engine_stage


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


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "approved_answers"
    kb.mkdir()
    (kb / "unsupported_setups.md").write_text(
        "---\ntags: [proxmox, lxc]\n---\n# Unsupported\n\nProxmox LXC is not supported."
    )
    (kb / "installation.md").write_text(
        "---\ntags: [docker, install]\n---\n# Installation\n\nUse docker pull."
    )
    return kb


class TestRuleEngineKeywordMatch:
    @pytest.mark.asyncio
    async def test_any_mode_matches_single_keyword(self, kb_dir: Path) -> None:
        rules = [
            {"name": "proxmox", "keywords": ["proxmox", "proxmox ve"], "match_mode": "any",
             "answer_file": "unsupported_setups.md", "labels": ["support"], "close": True},
        ]
        event = _make_event(body="I'm running on Proxmox and having issues")
        context: dict[str, Any] = {"rules": rules, "kb_dir": str(kb_dir)}
        decision = await rule_engine_stage(event, context)
        assert decision.short_circuit is True
        assert decision.decision == "match"
        assert "rule_match" in context

    @pytest.mark.asyncio
    async def test_all_mode_requires_all_keywords(self, kb_dir: Path) -> None:
        rules = [
            {"name": "docker-install", "keywords": ["docker", "install"], "match_mode": "all",
             "answer_file": "installation.md", "labels": ["support"], "close": False},
        ]
        event = _make_event(body="How do I install Docker on my Raspberry Pi?")
        context: dict[str, Any] = {"rules": rules, "kb_dir": str(kb_dir)}
        decision = await rule_engine_stage(event, context)
        assert decision.short_circuit is True

    @pytest.mark.asyncio
    async def test_all_mode_fails_partial_match(self, kb_dir: Path) -> None:
        rules = [
            {"name": "docker-install", "keywords": ["docker", "install"], "match_mode": "all",
             "answer_file": "installation.md", "labels": ["support"], "close": False},
        ]
        event = _make_event(body="I want to use Docker")
        context: dict[str, Any] = {"rules": rules, "kb_dir": str(kb_dir)}
        decision = await rule_engine_stage(event, context)
        assert decision.short_circuit is False

    @pytest.mark.asyncio
    async def test_first_match_wins(self, kb_dir: Path) -> None:
        rules = [
            {"name": "rule1", "keywords": ["docker"], "match_mode": "any",
             "answer_file": "unsupported_setups.md", "labels": ["support"], "close": True},
            {"name": "rule2", "keywords": ["docker"], "match_mode": "any",
             "answer_file": "installation.md", "labels": ["support"], "close": False},
        ]
        event = _make_event(body="Docker question")
        context: dict[str, Any] = {"rules": rules, "kb_dir": str(kb_dir)}
        decision = await rule_engine_stage(event, context)
        assert "rule1" in decision.reason

    @pytest.mark.asyncio
    async def test_no_match_passes(self, kb_dir: Path) -> None:
        rules = [
            {"name": "proxmox", "keywords": ["proxmox"], "match_mode": "any",
             "answer_file": "unsupported_setups.md", "labels": ["support"], "close": True},
        ]
        event = _make_event(body="My speaker is not working correctly")
        context: dict[str, Any] = {"rules": rules, "kb_dir": str(kb_dir)}
        decision = await rule_engine_stage(event, context)
        assert decision.short_circuit is False
        assert decision.decision == "pass"


class TestRuleEngineMissingAnswer:
    @pytest.mark.asyncio
    async def test_missing_answer_file_needs_triage(self, kb_dir: Path) -> None:
        rules = [
            {"name": "broken-rule", "keywords": ["test"], "match_mode": "any",
             "answer_file": "nonexistent.md", "labels": ["support"], "close": False},
        ]
        event = _make_event(body="test keyword here")
        context: dict[str, Any] = {"rules": rules, "kb_dir": str(kb_dir)}
        decision = await rule_engine_stage(event, context)
        assert decision.short_circuit is True
        assert "needs-triage" in decision.reason
