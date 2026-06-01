"""GitHub API wrapper using httpx (T009).

Uses BOT_PAT for mutations (labels, comments, close) and
GITHUB_TOKEN for search queries (rate limiting).
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
        # Safety net: check if bot already commented (prevent duplicate spam)
        bot_login = await self._get_bot_login()
        if bot_login:
            existing = await self._request_with_retry(
                self._search_client,
                "get",
                self._repo_url(f"/issues/{issue_number}/comments"),
                params={"per_page": 100},
            )
            if existing.status_code == 200:
                comments = existing.json()
                if any(c.get("user", {}).get("login") == bot_login for c in comments):
                    logger.warning(
                        "Duplicate comment blocked: bot '%s' already commented on #%d",
                        bot_login, issue_number,
                    )
                    return

        response = await self._request_with_retry(
            self._bot_client,
            "post",
            self._repo_url(f"/issues/{issue_number}/comments"),
            json={"body": body},
        )
        response.raise_for_status()

    async def _get_bot_login(self) -> str | None:
        """Get the authenticated bot's login name. Cached after first call."""
        if not hasattr(self, "_bot_login_cached"):
            try:
                response = await self._bot_client.get("/user")
                if response.status_code == 200:
                    self._bot_login_cached: str | None = response.json().get("login")
                else:
                    self._bot_login_cached = None
            except Exception:
                self._bot_login_cached = None
        return self._bot_login_cached

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

    async def set_assignee(self, issue_number: int, username: str) -> None:
        """Assign a user to an issue."""
        response = await self._request_with_retry(
            self._bot_client,
            "post",
            self._repo_url(f"/issues/{issue_number}/assignees"),
            json={"assignees": [username]},
        )
        response.raise_for_status()

    async def get_closed_issues_since(
        self, since_iso: str, labels: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get closed issues since a given ISO date, optionally filtered by labels."""
        params: dict[str, Any] = {
            "state": "closed",
            "since": since_iso,
            "per_page": 100,
        }
        if labels:
            params["labels"] = ",".join(labels)

        all_issues: list[dict[str, Any]] = []
        page = 1
        while True:
            params["page"] = page
            response = await self._request_with_retry(
                self._search_client,
                "get",
                self._repo_url("/issues"),
                params=params,
            )
            response.raise_for_status()
            issues = response.json()
            if not issues:
                break
            all_issues.extend(issues)
            if len(issues) < 100:
                break
            page += 1
        return all_issues

    async def bot_has_commented(self, issue_number: int, bot_username: str) -> bool:
        """Check if the bot has already commented on this issue."""
        response = await self._request_with_retry(
            self._search_client,
            "get",
            self._repo_url(f"/issues/{issue_number}/comments"),
            params={"per_page": 100},
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        comments = response.json()
        return any(
            c.get("user", {}).get("login") == bot_username for c in comments
        )

    async def get_issue_state(self, issue_number: int) -> str:
        """Get current issue state. Returns 'deleted' if 404/410."""
        response = await self._bot_client.get(self._repo_url(f"/issues/{issue_number}"))
        if response.status_code in (404, 410):
            return "deleted"
        response.raise_for_status()
        return response.json().get("state", "unknown")
