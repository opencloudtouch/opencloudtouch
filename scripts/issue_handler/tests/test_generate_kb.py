"""Tests for KB article generator (T036)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge_base.generate_kb_article import (
    generate_article,
    sanitize_filename,
    validate_frontmatter,
    write_draft,
)

VALID_ARTICLE = """---
tags: [docker, install, setup]
title: "Docker Installation Guide"
---
# Docker Installation Guide

## Problem
User needed help installing Docker for OpenCloudTouch.

## Solution
1. Install Docker
2. Run the container

## See Also
- [README](https://github.com/opencloudtouch/opencloudtouch#readme)
"""


class TestValidateFrontmatter:
    def test_valid_frontmatter(self) -> None:
        assert validate_frontmatter(VALID_ARTICLE) is True

    def test_missing_tags(self) -> None:
        content = '---\ntitle: "Test"\n---\n# Content'
        assert validate_frontmatter(content) is False

    def test_missing_title(self) -> None:
        content = "---\ntags: [test]\n---\n# Content"
        assert validate_frontmatter(content) is False

    def test_no_frontmatter(self) -> None:
        assert validate_frontmatter("# Just content") is False

    def test_invalid_yaml(self) -> None:
        content = "---\n[invalid yaml\n---\n# Content"
        assert validate_frontmatter(content) is False


class TestSanitizeFilename:
    def test_simple_title(self) -> None:
        assert sanitize_filename("Docker Setup") == "docker-setup"

    def test_special_chars(self) -> None:
        assert sanitize_filename("How to install? (Guide)") == "how-to-install-guide"

    def test_long_title_truncated(self) -> None:
        long_title = "A" * 100
        assert len(sanitize_filename(long_title)) <= 60


class TestGenerateArticle:
    @pytest.mark.asyncio
    async def test_generates_valid_article(self) -> None:
        mock_ai = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = VALID_ARTICLE
        mock_ai.chat.completions.create = AsyncMock(return_value=resp)

        result = await generate_article(
            mock_ai,
            {"number": 42, "title": "Docker help", "body": "How to install Docker?"},
        )
        assert result is not None
        assert "Docker Installation Guide" in result

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_frontmatter(self) -> None:
        mock_ai = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "# No frontmatter"
        mock_ai.chat.completions.create = AsyncMock(return_value=resp)

        result = await generate_article(
            mock_ai,
            {"number": 42, "title": "Test", "body": "Test body"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_ai_error(self) -> None:
        mock_ai = MagicMock()
        mock_ai.chat.completions.create = AsyncMock(side_effect=Exception("AI down"))

        result = await generate_article(
            mock_ai,
            {"number": 42, "title": "Test", "body": "Test body"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_includes_comments_in_prompt(self) -> None:
        mock_ai = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = VALID_ARTICLE
        mock_ai.chat.completions.create = AsyncMock(return_value=resp)

        comments = [{"user": {"login": "maintainer"}, "body": "Fixed by updating config"}]
        await generate_article(
            mock_ai,
            {"number": 42, "title": "Config issue", "body": "Config broken"},
            comments=comments,
        )
        call_args = mock_ai.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "maintainer" in user_msg
        assert "Fixed by updating config" in user_msg


class TestWriteDraft:
    def test_writes_draft_file(self, tmp_path: Path) -> None:
        import knowledge_base.generate_kb_article as mod
        original = mod.OUTPUT_DIR
        mod.OUTPUT_DIR = tmp_path
        try:
            path = write_draft(VALID_ARTICLE, "Docker Setup Guide")
            assert path.exists()
            assert path.name.startswith("_draft_")
            assert path.name.endswith(".md")
            content = path.read_text(encoding="utf-8")
            assert "Docker Installation Guide" in content
        finally:
            mod.OUTPUT_DIR = original
