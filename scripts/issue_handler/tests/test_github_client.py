"""Tests for GitHub client wrapper (T008)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from github_client import GitHubClient


def _resp(status: int, json: dict | list, method: str = "POST", url: str = "http://test") -> httpx.Response:
    """Create an httpx.Response with a request attached (required for raise_for_status)."""
    return httpx.Response(status, json=json, request=httpx.Request(method, url))


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(
        bot_pat="fake-bot-pat",
        github_token="fake-gh-token",
        repo_owner="scheilch",
        repo_name="opencloudtouch",
    )


class TestAddLabels:
    @pytest.mark.asyncio
    async def test_adds_labels(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "post", new_callable=AsyncMock, return_value=_resp(200, [{"name": "bug"}])):
            await client.add_labels(42, ["bug", "needs-triage"])
            client._bot_client.post.assert_called_once()


class TestPostComment:
    @pytest.mark.asyncio
    async def test_posts_comment(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "post", new_callable=AsyncMock, return_value=_resp(201, {"id": 1})):
            await client.post_comment(42, "Hello, thanks for reporting!")
            client._bot_client.post.assert_called_once()


class TestCloseIssue:
    @pytest.mark.asyncio
    async def test_closes_issue(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "patch", new_callable=AsyncMock, return_value=_resp(200, {"state": "closed"}, "PATCH")):
            await client.close_issue(42)
            client._bot_client.patch.assert_called_once()


class TestSetAssignee:
    """T010: Tests for set_assignee()."""

    @pytest.mark.asyncio
    async def test_assigns_user(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "post", new_callable=AsyncMock, return_value=_resp(200, {"assignees": [{"login": "oct-support"}]})):
            await client.set_assignee(42, "oct-support")
            client._bot_client.post.assert_called_once()
            call_args = client._bot_client.post.call_args
            assert call_args[0][0] == "/repos/scheilch/opencloudtouch/issues/42/assignees"
            assert call_args[1]["json"] == {"assignees": ["oct-support"]}

    @pytest.mark.asyncio
    async def test_set_assignee_retries_on_429(self, client: GitHubClient) -> None:
        with patch.object(
            client._bot_client,
            "post",
            new_callable=AsyncMock,
            side_effect=[_resp(429, {"message": "rate limit"}), _resp(200, {"assignees": []})],
        ):
            with patch("github_client.asyncio.sleep", new_callable=AsyncMock):
                await client.set_assignee(42, "oct-support")
                assert client._bot_client.post.call_count == 2


class TestGetClosedIssuesSince:
    """T033: Tests for get_closed_issues_since()."""

    @pytest.mark.asyncio
    async def test_returns_closed_issues(self, client: GitHubClient) -> None:
        issues = [{"number": 1, "title": "Bug fix", "state": "closed"}]
        with patch.object(client._search_client, "get", new_callable=AsyncMock, return_value=_resp(200, issues, "GET")):
            result = await client.get_closed_issues_since("2026-01-01T00:00:00Z")
            assert len(result) == 1
            assert result[0]["number"] == 1

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, client: GitHubClient) -> None:
        with patch.object(client._search_client, "get", new_callable=AsyncMock, return_value=_resp(200, [], "GET")):
            result = await client.get_closed_issues_since("2026-01-01T00:00:00Z")
            assert result == []

    @pytest.mark.asyncio
    async def test_with_label_filter(self, client: GitHubClient) -> None:
        issues = [{"number": 5, "title": "Support Q", "state": "closed"}]
        with patch.object(client._search_client, "get", new_callable=AsyncMock, return_value=_resp(200, issues, "GET")) as mock_get:
            result = await client.get_closed_issues_since("2026-01-01T00:00:00Z", labels=["support"])
            assert len(result) == 1
            call_params = mock_get.call_args[1]["params"]
            assert "support" in call_params["labels"]


class TestSearchIssuesByAuthor:
    @pytest.mark.asyncio
    async def test_returns_count(self, client: GitHubClient) -> None:
        with patch.object(client._search_client, "get", new_callable=AsyncMock, return_value=_resp(200, {"total_count": 3, "items": []}, "GET")):
            count = await client.search_issues_by_author("some-user")
            assert count == 3


class TestRetryOnRateLimit:
    @pytest.mark.asyncio
    async def test_retries_on_403(self, client: GitHubClient) -> None:
        with patch.object(
            client._bot_client,
            "post",
            new_callable=AsyncMock,
            side_effect=[_resp(403, {"message": "rate limit exceeded"}), _resp(200, [{"name": "bug"}])],
        ):
            with patch("github_client.asyncio.sleep", new_callable=AsyncMock):
                await client.add_labels(42, ["bug"])
                assert client._bot_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_429(self, client: GitHubClient) -> None:
        with patch.object(
            client._bot_client,
            "post",
            new_callable=AsyncMock,
            side_effect=[_resp(429, {"message": "too many requests"}), _resp(200, [{"name": "bug"}])],
        ):
            with patch("github_client.asyncio.sleep", new_callable=AsyncMock):
                await client.add_labels(42, ["bug"])
                assert client._bot_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, client: GitHubClient) -> None:
        with patch.object(
            client._bot_client,
            "post",
            new_callable=AsyncMock,
            side_effect=[_resp(429, {"message": "too many requests"})] * 4,
        ):
            with patch("github_client.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(httpx.HTTPStatusError):
                    await client.add_labels(42, ["bug"])


class TestIssueStateCheck:
    @pytest.mark.asyncio
    async def test_get_issue_state_open(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "get", new_callable=AsyncMock, return_value=_resp(200, {"state": "open"}, "GET")):
            state = await client.get_issue_state(42)
            assert state == "open"

    @pytest.mark.asyncio
    async def test_get_issue_state_deleted(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "get", new_callable=AsyncMock, return_value=_resp(404, {"message": "Not Found"}, "GET")):
            state = await client.get_issue_state(42)
            assert state == "deleted"

    @pytest.mark.asyncio
    async def test_get_issue_state_gone(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "get", new_callable=AsyncMock, return_value=_resp(410, {"message": "Gone"}, "GET")):
            state = await client.get_issue_state(42)
            assert state == "deleted"

    @pytest.mark.asyncio
    async def test_get_issue_state_closed(self, client: GitHubClient) -> None:
        with patch.object(client._bot_client, "get", new_callable=AsyncMock, return_value=_resp(200, {"state": "closed"}, "GET")):
            state = await client.get_issue_state(42)
            assert state == "closed"
