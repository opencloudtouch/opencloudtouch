"""GitHub API wrapper using httpx (T009).

Uses BOT_PAT for mutations (labels, comments, close) and
GITHUB_TOKEN for search queries (rate limiting).
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

# Retry configuration per spec: base 1s, factor 2×, max 3, jitter ±500ms
MAX_RETRIES = 3
BASE_DELAY = 1.0
BACKOFF_FACTOR = 2.0
JITTER_MS = 500

API_BASE = "https://api.github.com"


class GitHubClient:
    """Wrapper around GitHub REST API with retry and state checking."""

    def __init__(
        self,
        bot_pat: str,
        github_token: str,
        repo_owner: str,
        repo_name: str,
    ) -> None:
        self._repo_owner = repo_owner
        self._repo_name = repo_name
        headers_common = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self._bot_client = httpx.AsyncClient(
            base_url=API_BASE,
            headers={**headers_common, "Authorization": f"Bearer {bot_pat}"},
        )
        self._search_client = httpx.AsyncClient(
            base_url=API_BASE,
            headers={**headers_common, "Authorization": f"Bearer {github_token}"},
        )

    async def close(self) -> None:
        await self._bot_client.aclose()
        await self._search_client.aclose()

    def _repo_url(self, path: str) -> str:
        return f"/repos/{self._repo_owner}/{self._repo_name}{path}"

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute request with exponential backoff on 403/429."""
        last_response: httpx.Response | None = None
        for attempt in range(MAX_RETRIES + 1):
            response = await getattr(client, method)(url, **kwargs)
            if response.status_code not in (403, 429):
                return response
            last_response = response
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (BACKOFF_FACTOR ** attempt)
                jitter = random.uniform(-JITTER_MS / 1000, JITTER_MS / 1000)
                await asyncio.sleep(max(0, delay + jitter))

        assert last_response is not None
        last_response.raise_for_status()
        return last_response  # unreachable, but satisfies type checker

    async def add_labels(self, issue_number: int, labels: list[str]) -> None:
        response = await self._request_with_retry(
            self._bot_client,
            "post",
            self._repo_url(f"/issues/{issue_number}/labels"),
            json=labels,
        )
        response.raise_for_status()

    async def post_comment(self, issue_number: int, body: str) -> None:
        response = await self._request_with_retry(
            self._bot_client,
            "post",
            self._repo_url(f"/issues/{issue_number}/comments"),
            json={"body": body},
        )
        response.raise_for_status()

    async def close_issue(self, issue_number: int) -> None:
        response = await self._request_with_retry(
            self._bot_client,
            "patch",
            self._repo_url(f"/issues/{issue_number}"),
            json={"state": "closed"},
        )
        response.raise_for_status()

    async def search_issues_by_author(self, username: str, since_hours: int = 24) -> int:
        """Count issues opened by user in the last N hours using GitHub Search API."""
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime("%Y-%m-%dT%H:%M:%S")
        query = f"author:{username} type:issue repo:{self._repo_owner}/{self._repo_name} created:>={since}"
        response = await self._request_with_retry(
            self._search_client,
            "get",
            "/search/issues",
            params={"q": query},
        )
        response.raise_for_status()
        return response.json().get("total_count", 0)

    async def get_issue_state(self, issue_number: int) -> str:
        """Get current issue state. Returns 'deleted' if 404."""
        response = await self._bot_client.get(self._repo_url(f"/issues/{issue_number}"))
        if response.status_code == 404:
            return "deleted"
        response.raise_for_status()
        return response.json().get("state", "unknown")
