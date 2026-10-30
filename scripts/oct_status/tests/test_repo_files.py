"""Repository instruction files for Gitar and Claude agents (spec sections 7 and 8)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_gitar_rules_explain_status_system():
    text = _read(".gitar/rules/oct-status.md")
    for needle in (
        "<!-- oct-status:v1 -->",
        "<!-- /oct-status -->",
        "<!-- oct-next:v1 -->",
        "phase:",
        "wait:",
        "resolution:",
        "Conventional Commits",
        "/oct accept-paths",
        "@gitar-bot",
    ):
        assert needle in text, needle
    for path in (".github/", ".claude/", ".gitar/", "scripts/oct_status/"):
        assert path in text, path


def test_gitar_apply_criteria_skip_sensitive_areas():
    text = _read(".gitar/config/apply.md").lower()
    for needle in (
        "unused import",
        "formatting",
        "typo",
        "documentation",
        "authentication",
        "ssh",
        "setup wizard",
        "device protocol",
        ".github/",
        ".claude/",
        ".gitar/",
        "scripts/oct_status/",
    ):
        assert needle in text, needle


def test_claude_md_status_section():
    text = _read("CLAUDE.md")
    assert "## Status system" in text
    assert "docs/WORKFLOW.md" in text
    section = text.split("## Status system", 1)[1].split("\n## ", 1)[0]
    assert len([ln for ln in section.strip().splitlines() if ln.strip()]) <= 10
    for needle in ("/oct", "oct-status", "phase", "wait", "resolution", "guide comment", "subagent"):
        assert needle in section, needle
    assert "Never bypass hooks" in text
