"""Minimal async GitHub REST/GraphQL client with retry and backoff."""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

API_ROOT = "https://api.github.com"
MAX_RETRIES = 3
BASE_DELAY = 1.0
FACTOR = 2.0
MAX_JITTER = 0.5


class ReadOnlyError(RuntimeError):
    """A write was attempted through a read-only API."""


class GitHubApi:
    """Thin wrapper around httpx.AsyncClient.

    Path convention for ``request``: a path starting with ``/repos/`` (or equal to
    ``/graphql``) is absolute on the API host; every other path is relative to the
    repository API root, so ``request("GET", "/labels")`` calls ``/repos/{repo}/labels``.
    """

    def __init__(
        self,
        token: str,
        repo: str,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        read_only: bool = False,
        max_retry_wait: float | None = None,
    ) -> None:
        self.repo = repo
        self.read_only = read_only
        # A rate limit asking for a longer wait than this is returned to the caller instead of slept
        # through (the backfill stops and resumes later); ``None`` waits as long as asked.
        self.max_retry_wait = max_retry_wait
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=API_ROOT,
            transport=transport,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def _url(self, path: str) -> str:
        if path.startswith("/repos/") or path == "/graphql":
            return path
        return f"/repos/{self.repo}{path}"

    @staticmethod
    def _retryable(resp: httpx.Response) -> bool:
        if resp.status_code == 429 or resp.status_code >= 500:
            return True
        if resp.status_code == 403:
            return "retry-after" in resp.headers or resp.headers.get("x-ratelimit-remaining") == "0"
        return False

    def _guard(self, method: str, url: str, kw: dict[str, Any]) -> None:
        """Read-only mode (shadow mode): only GET and GraphQL queries may leave the process."""
        if method.upper() == "GET":
            return
        if url == "/graphql" and method.upper() == "POST":
            query = (kw.get("json") or {}).get("query", "")
            if isinstance(query, str) and not re.search(r"\bmutation\b", query, re.IGNORECASE):
                return
        raise ReadOnlyError(f"{method.upper()} {url} refused: API is read-only")

    async def request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        url = self._url(path)
        if self.read_only:
            self._guard(method, url, kw)
        delay = BASE_DELAY
        for attempt in range(MAX_RETRIES + 1):
            resp = await self._client.request(method, url, **kw)
            if not self._retryable(resp) or attempt == MAX_RETRIES:
                return resp
            retry_after = resp.headers.get("retry-after")
            wait = (
                float(retry_after) if retry_after and retry_after.isdigit() else delay + random.uniform(0, MAX_JITTER)
            )
            if self.max_retry_wait is not None and wait > self.max_retry_wait:
                return resp
            await self._sleep(wait)
            delay *= FACTOR
        raise AssertionError("unreachable")  # pragma: no cover

    async def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        resp = await self.request("POST", "/graphql", json={"query": query, "variables": variables})
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL errors: {payload['errors']}")
        return payload["data"]

    async def aclose(self) -> None:
        await self._client.aclose()
