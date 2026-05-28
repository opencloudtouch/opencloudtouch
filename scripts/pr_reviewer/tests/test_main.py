"""Tests for PR Reviewer — cost tracker, rate limiter, review logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add scripts/pr_reviewer to sys.path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import (
    BOT_USERNAME,
    CostTracker,
    ReviewRateLimiter,
    _build_valid_lines_map,
    _parse_diff_lines,
    _should_skip,
    build_review_prompt,
    check_and_approve,
    has_bot_reviewed_commit,
)


# =============================================================================
# CostTracker Tests
# =============================================================================


class TestCostTracker:
    def test_new_tracker_starts_at_zero(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "cost.json")
        assert tracker.total_cost_usd == 0.0
        assert tracker.call_count == 0

    def test_record_call_accumulates(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "cost.json")
        tracker.record_call(1000, 500)
        assert tracker.call_count == 1
        assert tracker.total_cost_usd > 0

    def test_save_and_load(self, tmp_path: Path) -> None:
        cost_file = tmp_path / "cost.json"
        tracker = CostTracker(cost_file)
        tracker.record_call(10000, 5000)
        tracker.save()

        tracker2 = CostTracker(cost_file)
        assert tracker2.call_count == 1
        assert tracker2.total_cost_usd == tracker.total_cost_usd

    def test_budget_exceeded(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "cost.json", budget_usd=0.001)
        tracker.record_call(100000, 50000)
        assert tracker.is_budget_exceeded()

    def test_budget_not_exceeded(self, tmp_path: Path) -> None:
        tracker = CostTracker(tmp_path / "cost.json", budget_usd=100.0)
        tracker.record_call(100, 50)
        assert not tracker.is_budget_exceeded()

    def test_different_month_resets(self, tmp_path: Path) -> None:
        cost_file = tmp_path / "cost.json"
        old_data = {
            "month": "2020-01",
            "total_cost_usd": 99.99,
            "call_count": 999,
            "last_updated": "2020-01-01T00:00:00",
        }
        cost_file.write_text(json.dumps(old_data))

        tracker = CostTracker(cost_file)
        assert tracker.total_cost_usd == 0.0
        assert tracker.call_count == 0

    def test_corrupted_file_handled(self, tmp_path: Path) -> None:
        cost_file = tmp_path / "cost.json"
        cost_file.write_text("not json")

        tracker = CostTracker(cost_file)
        assert tracker.total_cost_usd == 0.0


# =============================================================================
# ReviewRateLimiter Tests
# =============================================================================


class TestReviewRateLimiter:
    def test_first_review_allowed(self, tmp_path: Path) -> None:
        limiter = ReviewRateLimiter(tmp_path / "rate.json")
        assert limiter.check_and_record("repo#1") is True

    def test_second_review_within_cooldown_blocked(self, tmp_path: Path) -> None:
        state_file = tmp_path / "rate.json"
        limiter = ReviewRateLimiter(state_file)
        limiter.check_and_record("repo#1")
        limiter.save()

        limiter2 = ReviewRateLimiter(state_file)
        assert limiter2.check_and_record("repo#1") is False

    def test_different_pr_not_blocked(self, tmp_path: Path) -> None:
        state_file = tmp_path / "rate.json"
        limiter = ReviewRateLimiter(state_file)
        limiter.check_and_record("repo#1")
        limiter.save()

        limiter2 = ReviewRateLimiter(state_file)
        assert limiter2.check_and_record("repo#2") is True

    def test_review_after_cooldown_allowed(self, tmp_path: Path) -> None:
        state_file = tmp_path / "rate.json"
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        state_file.write_text(json.dumps({"repo#1": old_time}))

        limiter = ReviewRateLimiter(state_file)
        assert limiter.check_and_record("repo#1") is True

    def test_corrupted_file_handled(self, tmp_path: Path) -> None:
        state_file = tmp_path / "rate.json"
        state_file.write_text("not json")

        limiter = ReviewRateLimiter(state_file)
        assert limiter.check_and_record("repo#1") is True


# =============================================================================
# _should_skip Tests
# =============================================================================


class TestShouldSkip:
    def test_skip_lock_files(self) -> None:
        assert _should_skip("package-lock.json") is True
        assert _should_skip("yarn.lock") is True
        assert _should_skip("poetry.lock") is True

    def test_skip_generated_dirs(self) -> None:
        assert _should_skip("node_modules/foo.js") is True
        assert _should_skip("__pycache__/bar.pyc") is True
        assert _should_skip(".local/something") is True

    def test_skip_map_files(self) -> None:
        assert _should_skip("bundle.js.map") is True

    def test_allow_normal_files(self) -> None:
        assert _should_skip("src/main.py") is False
        assert _should_skip("README.md") is False
        assert _should_skip("apps/frontend/src/App.tsx") is False


# =============================================================================
# build_review_prompt Tests
# =============================================================================


class TestBuildReviewPrompt:
    def test_basic_prompt_structure(self) -> None:
        pr = {
            "title": "Fix bug",
            "body": "Fixes #123",
            "base": {"ref": "main"},
            "head": {"ref": "fix/bug"},
        }
        files = [
            {"filename": "src/main.py", "status": "modified", "patch": "+fix"},
        ]
        prompt = build_review_prompt(pr, files)
        assert "Fix bug" in prompt
        assert "fix/bug" in prompt
        assert "src/main.py" in prompt

    def test_skips_lock_files(self) -> None:
        pr = {
            "title": "Update deps",
            "body": "",
            "base": {"ref": "main"},
            "head": {"ref": "chore/deps"},
        }
        files = [
            {"filename": "package-lock.json", "status": "modified", "patch": "+stuff"},
        ]
        prompt = build_review_prompt(pr, files)
        assert "package-lock.json" not in prompt

    def test_truncates_large_diffs(self) -> None:
        pr = {
            "title": "Big change",
            "body": None,
            "base": {"ref": "main"},
            "head": {"ref": "feat/big"},
        }
        files = [
            {"filename": "big.py", "status": "modified", "patch": "x" * 10000},
        ]
        prompt = build_review_prompt(pr, files)
        assert "[truncated]" in prompt


# =============================================================================
# check_and_approve Tests
# =============================================================================


class TestCheckAndApprove:
    @pytest.mark.asyncio
    async def test_no_threads_skips(self) -> None:
        """When no bot threads exist, should not approve."""
        client = AsyncMock()
        # GraphQL returns empty threads
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {"nodes": []},
                    },
                },
            },
        }
        mock_response.raise_for_status = MagicMock()
        client.post = AsyncMock(return_value=mock_response)

        await check_and_approve(client, "owner/repo", 1)
        # Should not submit any review (only the GraphQL call)
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_unresolved_threads_no_approve(self) -> None:
        """When bot threads are unresolved, should not approve."""
        client = AsyncMock()
        mock_graphql = MagicMock()
        mock_graphql.status_code = 200
        mock_graphql.json.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "t1",
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [
                                            {"author": {"login": BOT_USERNAME}, "body": "Fix this"},
                                        ],
                                    },
                                },
                            ],
                        },
                    },
                },
            },
        }
        mock_graphql.raise_for_status = MagicMock()
        client.post = AsyncMock(return_value=mock_graphql)

        await check_and_approve(client, "owner/repo", 1)
        # Only GraphQL call, no approval
        assert client.post.call_count == 1


# =============================================================================
# Diff Line Parsing Tests
# =============================================================================


class TestParseDiffLines:
    def test_simple_addition(self):
        patch = "@@ -10,3 +10,5 @@\n context\n+added1\n+added2\n context\n context"
        result = _parse_diff_lines(patch)
        assert 10 in result  # context
        assert 11 in result  # added1
        assert 12 in result  # added2
        assert 13 in result  # context
        assert 14 in result  # context

    def test_deletion_not_included(self):
        patch = "@@ -10,4 +10,3 @@\n context\n-deleted\n context\n context"
        result = _parse_diff_lines(patch)
        assert 10 in result
        assert 11 in result
        assert 12 in result
        # Only 3 new-side lines (deletion doesn't count)
        assert len(result) == 3

    def test_multiple_hunks(self):
        patch = "@@ -1,3 +1,3 @@\n-old\n+new\n ctx\n ctx\n@@ -20,3 +20,3 @@\n-old2\n+new2\n ctx\n ctx"
        result = _parse_diff_lines(patch)
        assert 1 in result   # new (from first hunk)
        assert 2 in result   # ctx
        assert 3 in result   # ctx
        assert 20 in result  # new2 (from second hunk)
        assert 21 in result  # ctx
        assert 22 in result  # ctx

    def test_empty_patch(self):
        assert _parse_diff_lines("") == set()


class TestBuildValidLinesMap:
    def test_builds_map(self):
        files = [
            {"filename": "a.py", "patch": "@@ -1,2 +1,3 @@\n ctx\n+new\n ctx"},
            {"filename": "b.py", "patch": ""},
            {"filename": "c.py"},
        ]
        result = _build_valid_lines_map(files)
        assert "a.py" in result
        assert 1 in result["a.py"]
        assert 2 in result["a.py"]
        assert 3 in result["a.py"]
        assert "b.py" not in result
        assert "c.py" not in result


# =============================================================================
# Duplicate Review Detection Tests
# =============================================================================


class TestHasBotReviewedCommit:
    @pytest.mark.asyncio
    async def test_returns_true_when_already_reviewed(self):
        client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"user": {"login": "oct-support"}, "commit_id": "abc123", "state": "COMMENTED"},
        ]
        mock_resp.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_resp)

        result = await has_bot_reviewed_commit(client, "owner/repo", 1, "abc123")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_different_commit(self):
        client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"user": {"login": "oct-support"}, "commit_id": "abc123", "state": "COMMENTED"},
        ]
        mock_resp.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_resp)

        result = await has_bot_reviewed_commit(client, "owner/repo", 1, "def456")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_different_user(self):
        client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"user": {"login": "other-user"}, "commit_id": "abc123", "state": "COMMENTED"},
        ]
        mock_resp.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_resp)

        result = await has_bot_reviewed_commit(client, "owner/repo", 1, "abc123")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_dismissed_review(self):
        client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"user": {"login": "oct-support"}, "commit_id": "abc123", "state": "DISMISSED"},
        ]
        mock_resp.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_resp)

        result = await has_bot_reviewed_commit(client, "owner/repo", 1, "abc123")
        assert result is False
