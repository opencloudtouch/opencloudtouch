"""Tests for Knowledge Base loader (T023)."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_base import KnowledgeBase


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    """Create a temporary knowledge base directory with sample files."""
    kb = tmp_path / "approved_answers"
    kb.mkdir()

    (kb / "installation.md").write_text(
        "---\ntags: [docker, install, setup, raspberry-pi]\n---\n"
        "# Installation Guide\n\nUse `docker pull` to get started."
    )
    (kb / "discovery.md").write_text(
        "---\ntags: [discovery, ssdp, multicast, not-found, network]\n---\n"
        "# Device Discovery\n\nTroubleshoot SSDP discovery issues."
    )
    return kb


class TestKnowledgeBaseLoader:
    def test_loads_approved_answers(self, kb_dir: Path) -> None:
        kb = KnowledgeBase(kb_dir)
        answers = kb.get_all_answers()
        assert len(answers) == 2

    def test_parses_frontmatter_tags(self, kb_dir: Path) -> None:
        kb = KnowledgeBase(kb_dir)
        answers = kb.get_all_answers()
        tags = {a.filename: a.tags for a in answers}
        assert "docker" in tags["installation.md"]
        assert "ssdp" in tags["discovery.md"]

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "empty"
        kb_dir.mkdir()
        kb = KnowledgeBase(kb_dir)
        assert kb.get_all_answers() == []

    def test_handles_missing_directory(self, tmp_path: Path) -> None:
        kb = KnowledgeBase(tmp_path / "nonexistent")
        assert kb.get_all_answers() == []

    def test_handles_file_without_frontmatter(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "plain.md").write_text("# Just a title\n\nNo frontmatter here.")
        kb = KnowledgeBase(kb_dir)
        answers = kb.get_all_answers()
        assert len(answers) == 1
        assert answers[0].tags == []

    def test_extracts_content(self, kb_dir: Path) -> None:
        kb = KnowledgeBase(kb_dir)
        answers = kb.get_all_answers()
        install = next(a for a in answers if a.filename == "installation.md")
        assert "docker pull" in install.content


class TestTagMatching:
    """Tests for tag-based answer selection (T030)."""

    @pytest.fixture
    def full_kb_dir(self, tmp_path: Path) -> Path:
        kb = tmp_path / "full_kb"
        kb.mkdir()
        (kb / "installation.md").write_text(
            "---\ntags: [docker, install, setup, raspberry-pi]\n---\n# Installation"
        )
        (kb / "discovery.md").write_text(
            "---\ntags: [discovery, ssdp, multicast, not-found, network]\n---\n# Discovery"
        )
        (kb / "presets.md").write_text(
            "---\ntags: [preset, presets, radio, station, favorite]\n---\n# Presets"
        )
        (kb / "bug_report.md").write_text(
            "---\ntags: [bug, crash, error, broken]\n---\n# Bug Report Required"
        )
        (kb / "unsupported.md").write_text(
            "---\ntags: [proxmox, lxc, vm, virtualization]\n---\n# Unsupported"
        )
        (kb / "zones.md").write_text(
            "---\ntags: [zone, multi-room, group, speaker]\n---\n# Zones"
        )
        return kb

    def test_matches_relevant_answers(self, full_kb_dir: Path) -> None:
        kb = KnowledgeBase(full_kb_dir)
        results = kb.select_relevant_answers("How to install docker", "I need help with docker setup")
        assert len(results) > 0
        assert results[0].filename == "installation.md"

    def test_ranking_by_match_count(self, full_kb_dir: Path) -> None:
        kb = KnowledgeBase(full_kb_dir)
        results = kb.select_relevant_answers(
            "Docker install setup", "I want to install docker and setup raspberry-pi"
        )
        # installation.md has most tag matches (docker, install, setup, raspberry-pi)
        assert results[0].filename == "installation.md"

    def test_top_5_selection(self, full_kb_dir: Path) -> None:
        kb = KnowledgeBase(full_kb_dir)
        results = kb.select_relevant_answers(
            "docker install ssdp discovery preset radio bug crash zone speaker",
            "All keywords from all files"
        )
        assert len(results) <= 5

    def test_tie_breaking_by_filename(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "tie"
        kb_dir.mkdir()
        (kb_dir / "b_file.md").write_text("---\ntags: [test]\n---\n# B")
        (kb_dir / "a_file.md").write_text("---\ntags: [test]\n---\n# A")
        kb = KnowledgeBase(kb_dir)
        results = kb.select_relevant_answers("test", "test keyword")
        assert results[0].filename == "a_file.md"

    def test_empty_kb_returns_empty(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "empty_kb"
        kb_dir.mkdir()
        kb = KnowledgeBase(kb_dir)
        results = kb.select_relevant_answers("anything", "any text")
        assert results == []

    def test_no_matching_tags(self, full_kb_dir: Path) -> None:
        kb = KnowledgeBase(full_kb_dir)
        results = kb.select_relevant_answers("xyz123", "completely unrelated text")
        assert results == []
