"""Tests for main.py entry point (T021)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import FIXTURES_DIR


class TestMainEntryPoint:
    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, tmp_path: Path) -> None:
        """Full pipeline run with mocked stages, verify exit code 0."""
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(json.loads((FIXTURES_DIR / "issue_opened.json").read_text())))

        env = {
            "GITHUB_TOKEN": "fake-token",
            "BOT_PAT": "fake-pat",
            "OPENAI_API_KEY": "fake-key",
            "GITHUB_EVENT_PATH": str(event_file),
            "GITHUB_EVENT_NAME": "issues",
        }

        with patch.dict(os.environ, env):
            with patch("main.GitHubClient") as MockClient:
                mock_gh = AsyncMock()
                mock_gh.get_issue_state = AsyncMock(return_value="open")
                mock_gh.add_labels = AsyncMock()
                mock_gh.post_comment = AsyncMock()
                mock_gh.close_issue = AsyncMock()
                mock_gh.search_issues_by_author = AsyncMock(return_value=0)
                mock_gh.close = AsyncMock()
                MockClient.return_value = mock_gh

                from main import run

                exit_code = await run()
                assert exit_code == 0

    @pytest.mark.asyncio
    async def test_skips_deleted_issue(self, tmp_path: Path) -> None:
        """Pipeline should skip deleted issues."""
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(json.loads((FIXTURES_DIR / "issue_opened.json").read_text())))

        env = {
            "GITHUB_TOKEN": "fake-token",
            "BOT_PAT": "fake-pat",
            "OPENAI_API_KEY": "fake-key",
            "GITHUB_EVENT_PATH": str(event_file),
            "GITHUB_EVENT_NAME": "issues",
        }

        with patch.dict(os.environ, env):
            with patch("main.GitHubClient") as MockClient:
                mock_gh = AsyncMock()
                mock_gh.get_issue_state = AsyncMock(return_value="deleted")
                mock_gh.close = AsyncMock()
                MockClient.return_value = mock_gh

                from main import run

                exit_code = await run()
                assert exit_code == 0
                mock_gh.add_labels.assert_not_called()
