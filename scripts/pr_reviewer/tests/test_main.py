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
    get_ci_status,
    has_bot_reviewed_commit,
    wait_for_ci,
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


# =============================================================================
# CI Status Check Tests
# =============================================================================


class TestGetCiStatus:
    @pytest.mark.asyncio
    async def test_all_checks_passing(self):
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "CI/Backend Tests", "status": "completed", "conclusion": "success"},
                {"name": "CI/Frontend Tests", "status": "completed", "conclusion": "success"},
                {"name": "CI/Lint Code", "status": "completed", "conclusion": "success"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is True
        assert failures == []

    @pytest.mark.asyncio
    async def test_failing_check_run(self):
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "CI/Backend Tests", "status": "completed", "conclusion": "failure"},
                {"name": "CI/Frontend Tests", "status": "completed", "conclusion": "success"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is False
        assert "CI/Backend Tests (failure)" in failures

    @pytest.mark.asyncio
    async def test_pending_check_run(self):
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "CI/Backend Tests", "status": "in_progress", "conclusion": None},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is False
        assert "CI/Backend Tests (still in_progress)" in failures

    @pytest.mark.asyncio
    async def test_skipped_and_neutral_pass(self):
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "CI/SonarCloud", "status": "completed", "conclusion": "skipped"},
                {"name": "CI/Optional", "status": "completed", "conclusion": "neutral"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is True
        assert failures == []

    @pytest.mark.asyncio
    async def test_pr_review_checks_skipped(self):
        """PR Review checks should be excluded to avoid circular dependency."""
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "PR Review (oct-support)/AI Review", "status": "completed", "conclusion": "success"},
                {"name": "PR Review (oct-support)/Approve Check", "status": "queued", "conclusion": None},
                {"name": "CI/Backend Tests", "status": "completed", "conclusion": "success"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is True
        assert failures == []

    @pytest.mark.asyncio
    async def test_own_job_names_skipped_without_workflow_prefix(self):
        """Job names without workflow prefix (AI Review, Approve Check, Comment Trigger) must be skipped."""
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
{"name": "PR Review", "status": "in_progress", "conclusion": None},
                {"name": "Approve Check", "status": "completed", "conclusion": "skipped"},
                {"name": "Comment Trigger", "status": "completed", "conclusion": "skipped"},
                {"name": "CI/Backend Tests", "status": "completed", "conclusion": "success"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is True
        assert failures == []

    @pytest.mark.asyncio
    async def test_legacy_ai_review_name_skipped(self):
        """Legacy 'AI Review' job name (from old runs) must be filtered to avoid false CI failures."""
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "AI Review", "status": "completed", "conclusion": "cancelled"},
                {"name": "CI/Backend Tests", "status": "completed", "conclusion": "success"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is True
        assert failures == []

    @pytest.mark.asyncio
    async def test_legacy_commit_status_failure(self):
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {"check_runs": []}
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {
            "statuses": [
                {"context": "external-ci/build", "state": "failure"},
            ],
        }
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await get_ci_status(client, "owner/repo", "abc123")
        assert passed is False
        assert "external-ci/build (failure)" in failures


# =============================================================================
# check_and_approve with CI Check Tests
# =============================================================================


class TestCheckAndApproveCiGate:
    @pytest.mark.asyncio
    async def test_approve_blocked_when_ci_failing(self):
        """When threads resolved but CI failing, should NOT approve."""
        client = AsyncMock()

        # GraphQL: all threads resolved
        graphql_resp = MagicMock()
        graphql_resp.status_code = 200
        graphql_resp.json.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "t1",
                                    "isResolved": True,
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
        graphql_resp.raise_for_status = MagicMock()

        # Reviews: no existing approval
        reviews_resp = MagicMock()
        reviews_resp.status_code = 200
        reviews_resp.json.return_value = [
            {"user": {"login": BOT_USERNAME}, "state": "COMMENTED"},
        ]
        reviews_resp.raise_for_status = MagicMock()

        # PR details
        pr_resp = MagicMock()
        pr_resp.status_code = 200
        pr_resp.json.return_value = {"head": {"sha": "abc123"}}
        pr_resp.raise_for_status = MagicMock()

        # CI: check runs failing
        ci_resp = MagicMock()
        ci_resp.status_code = 200
        ci_resp.json.return_value = {
            "check_runs": [
                {"name": "CI/Backend Tests", "status": "completed", "conclusion": "failure"},
            ],
        }
        ci_resp.raise_for_status = MagicMock()

        # Commit status: empty
        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        # Comment post response
        comment_resp = MagicMock()
        comment_resp.status_code = 200
        comment_resp.raise_for_status = MagicMock()

        # post calls: GraphQL, then CI-blocked comment
        client.post = AsyncMock(side_effect=[graphql_resp, comment_resp])
        # get calls: reviews, PR details, check-runs, commit status
        client.get = AsyncMock(side_effect=[reviews_resp, pr_resp, ci_resp, status_resp])

        await check_and_approve(client, "owner/repo", 1)

        # Should post a COMMENT (CI-blocked), NOT an APPROVE
        last_post = client.post.call_args_list[-1]
        posted_payload = last_post.kwargs.get("json") or last_post[1].get("json")
        assert posted_payload["event"] == "COMMENT"
        assert "CI checks not passing" in posted_payload["body"]


# =============================================================================
# wait_for_ci Tests
# =============================================================================


class TestWaitForCi:
    @pytest.mark.asyncio
    async def test_returns_immediately_when_all_complete(self):
        """When all checks are already complete, should not poll."""
        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "CI/Tests", "status": "completed", "conclusion": "success"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await wait_for_ci(client, "owner/repo", "abc123")
        assert passed is True
        assert failures == []
        # Only 2 GET calls (check-runs + status), no polling
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_polls_until_complete(self, monkeypatch):
        """When checks are in_progress, should poll until complete."""
        import main as main_mod

        # Speed up polling for test
        monkeypatch.setattr(main_mod, "CI_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(main_mod, "CI_POLL_MAX_WAIT_SECONDS", 10)

        client = AsyncMock()

        # First poll: in_progress
        resp1_cr = MagicMock()
        resp1_cr.status_code = 200
        resp1_cr.json.return_value = {
            "check_runs": [
                {"name": "CI/Tests", "status": "in_progress", "conclusion": None},
            ],
        }
        resp1_cr.raise_for_status = MagicMock()

        resp1_st = MagicMock()
        resp1_st.status_code = 200
        resp1_st.json.return_value = {"statuses": []}
        resp1_st.raise_for_status = MagicMock()

        # Second poll: complete
        resp2_cr = MagicMock()
        resp2_cr.status_code = 200
        resp2_cr.json.return_value = {
            "check_runs": [
                {"name": "CI/Tests", "status": "completed", "conclusion": "success"},
            ],
        }
        resp2_cr.raise_for_status = MagicMock()

        resp2_st = MagicMock()
        resp2_st.status_code = 200
        resp2_st.json.return_value = {"statuses": []}
        resp2_st.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[resp1_cr, resp1_st, resp2_cr, resp2_st])

        passed, failures = await wait_for_ci(client, "owner/repo", "abc123")
        assert passed is True
        assert client.get.call_count == 4  # 2 calls per poll × 2 polls

    @pytest.mark.asyncio
    async def test_returns_failures_after_ci_complete(self, monkeypatch):
        """When CI completes with failures, returns them."""
        import main as main_mod
        monkeypatch.setattr(main_mod, "CI_POLL_INTERVAL_SECONDS", 0)

        client = AsyncMock()
        check_runs_resp = MagicMock()
        check_runs_resp.status_code = 200
        check_runs_resp.json.return_value = {
            "check_runs": [
                {"name": "CI/Backend", "status": "completed", "conclusion": "failure"},
                {"name": "CI/Frontend", "status": "completed", "conclusion": "success"},
            ],
        }
        check_runs_resp.raise_for_status = MagicMock()

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"statuses": []}
        status_resp.raise_for_status = MagicMock()

        client.get = AsyncMock(side_effect=[check_runs_resp, status_resp])

        passed, failures = await wait_for_ci(client, "owner/repo", "abc123")
        assert passed is False
        assert "CI/Backend (failure)" in failures
