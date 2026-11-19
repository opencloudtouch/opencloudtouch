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


class TestKnowledgeBasePath:
    """Regression: kb_dir must point to approved_answers subdir, not knowledge_base root."""

    def test_kb_dir_resolves_to_approved_answers(self) -> None:
        """Verify main.py builds kb_dir pointing to knowledge_base/approved_answers/."""
        main_py = Path(__file__).parent.parent / "main.py"
        source = main_py.read_text(encoding="utf-8")
        # The kb_dir assignment must include approved_answers
        assert '"knowledge_base" / "approved_answers"' in source or \
               "'knowledge_base' / 'approved_answers'" in source or \
               "knowledge_base/approved_answers" in source, \
            "kb_dir in main.py must point to knowledge_base/approved_answers, not knowledge_base root"

    def test_approved_answers_dir_exists(self) -> None:
        """Verify the approved_answers directory exists with answer files."""
        answers_dir = Path(__file__).parent.parent / "knowledge_base" / "approved_answers"
        assert answers_dir.exists(), f"approved_answers directory missing: {answers_dir}"
        md_files = list(answers_dir.glob("*.md"))
        assert len(md_files) > 0, "approved_answers directory must contain at least one .md file"


class TestCostReportOnEveryRun:
    @pytest.mark.asyncio
    async def test_an_early_exit_run_still_reports_the_cost(self, tmp_path: Path) -> None:
        """An edited event exits before the AI is touched; the cost line must still be reported."""
        event_file = tmp_path / "event.json"
        payload = json.loads((FIXTURES_DIR / "issue_edited.json").read_text())
        event_file.write_text(json.dumps(payload))
        env = {
            "GITHUB_TOKEN": "t", "BOT_PAT": "p", "GITHUB_EVENT_PATH": str(event_file), "GITHUB_EVENT_NAME": "issues",
        }
        with patch.dict(os.environ, env):
            with patch("main.GitHubClient") as MockClient, patch("main.report_cost") as report:
                MockClient.return_value = AsyncMock()
                from main import run

                assert await run() == 0
        report.assert_called_once()
        assert report.call_args.args[0] is not None
