"""Minimal async GitHub REST/GraphQL client with retry and backoff."""

from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

API_ROOT = "https://api.github.com"
MAX_RETRIES = 3
BASE_DELAY = 1.0
FACTOR = 2.0
MAX_JITTER = 0.5
DEFAULT_MAX_RETRY_WAIT = 120.0  # seconds; a rate limit asking for longer is returned to the caller
_IDEMPOTENT = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE"})
# The connection never opened, so the server cannot have processed the request.
_NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


def _is_mutation(kw: dict[str, Any]) -> bool:
    query = (kw.get("json") or {}).get("query", "")
    return not isinstance(query, str) or bool(re.search(r"\bmutation\b", query, re.IGNORECASE))


class ReadOnlyError(RuntimeError):
    """A write was attempted through a read-only API."""


class GitHubApi:
    """Thin wrapper around httpx.AsyncClient.

    Retry policy (``MAX_RETRIES`` retries, exponential backoff with jitter, or the server's
    ``retry-after``):

    - A rate limit (429, or 403 with ``retry-after`` or ``x-ratelimit-remaining: 0``) is retried for
      every method: GitHub rejected the request before processing it. Without ``retry-after`` the wait
      runs until ``x-ratelimit-reset`` when the remaining quota is 0 (still capped by ``max_retry_wait``).
    - A 5xx answer and a transport error (connect or read timeout, broken connection) are retried only
      for idempotent requests: GET, HEAD, OPTIONS, PUT, PATCH (we only ever PATCH to a target state),
      DELETE and GraphQL queries. A POST (comment, label add, commit status) or a GraphQL mutation is
      not retried on 5xx or after the request may have reached the server, so it is never duplicated;
      a POST whose connection never opened (``ConnectError``, ``ConnectTimeout``) is retried.
    - A wait longer than ``max_retry_wait`` (default ``DEFAULT_MAX_RETRY_WAIT``) is not slept through:
      the response is returned to the caller. After the last attempt the response is returned, or the
      transport error raised.

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
        max_retry_wait: float | None = DEFAULT_MAX_RETRY_WAIT,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.repo = repo
        self.read_only = read_only
        # A rate limit asking for a longer wait than this is returned to the caller instead of slept
        # through (the backfill stops and resumes later); ``None`` waits as long as asked (tests only).
        self.max_retry_wait = max_retry_wait
        self._sleep = sleep
        self._clock = clock
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
    def _rate_limited(resp: httpx.Response) -> bool:
        if resp.status_code == 429:
            return True
        if resp.status_code == 403:
            return "retry-after" in resp.headers or resp.headers.get("x-ratelimit-remaining") == "0"
        return False

    def _until_reset(self, resp: httpx.Response) -> str | None:
        """Seconds until ``x-ratelimit-reset`` (plus one) when the primary limit is used up, as a string."""
        reset = resp.headers.get("x-ratelimit-reset", "")
        if resp.headers.get("x-ratelimit-remaining") != "0" or not reset.isdigit():
            return None
        return str(max(0, int(reset) - int(self._clock())) + 1)

    @staticmethod
    def _idempotent(method: str, url: str, kw: dict[str, Any]) -> bool:
        if method.upper() in _IDEMPOTENT:
            return True
        return url == "/graphql" and not _is_mutation(kw)

    def _guard(self, method: str, url: str, kw: dict[str, Any]) -> None:
        """Read-only mode (shadow mode): only GET and GraphQL queries may leave the process."""
        if method.upper() == "GET":
            return
        if url == "/graphql" and method.upper() == "POST" and not _is_mutation(kw):
            return
        raise ReadOnlyError(f"{method.upper()} {url} refused: API is read-only")

    async def request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        url = self._url(path)
        if self.read_only:
            self._guard(method, url, kw)
        idempotent = self._idempotent(method, url, kw)
        delay = BASE_DELAY
        for attempt in range(MAX_RETRIES + 1):
            last = attempt == MAX_RETRIES
            try:
                resp = await self._client.request(method, url, **kw)
            except httpx.TransportError as exc:
                if last or not (idempotent or isinstance(exc, _NOT_SENT)):
                    raise
                retry_after = None
            else:
                retryable = self._rate_limited(resp) or (idempotent and resp.status_code >= 500)
                if not retryable or last:
                    return resp
                retry_after = resp.headers.get("retry-after") or self._until_reset(resp)
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
