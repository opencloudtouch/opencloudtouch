"""Retry policy of the GitHub client: transport errors, capped waits, no duplicate POSTs."""

from __future__ import annotations

import httpx
import pytest

from oct_status.api import DEFAULT_MAX_RETRY_WAIT, MAX_RETRIES, GitHubApi

REPO = "o/r"


def _client(handler, waits: list[float] | None = None, **kw) -> GitHubApi:
    async def sleep(seconds: float) -> None:
        if waits is not None:
            waits.append(seconds)

    return GitHubApi("t", REPO, transport=httpx.MockTransport(handler), sleep=sleep, **kw)


def _flaky(error: type[httpx.TransportError], failures: int, calls: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if len(calls) <= failures:
            raise error("boom", request=request)
        return httpx.Response(200, json={"ok": True})

    return handler


@pytest.mark.parametrize("error", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError])
async def test_get_retries_transport_errors_with_backoff(error):
    calls: list[str] = []
    waits: list[float] = []
    api = _client(_flaky(error, 2, calls), waits)
    resp = await api.request("GET", "/x")
    await api.aclose()
    assert resp.status_code == 200 and len(calls) == 3
    assert len(waits) == 2 and 1.0 <= waits[0] < 1.5 and 2.0 <= waits[1] < 2.5


async def test_transport_error_is_raised_after_the_last_attempt():
    calls: list[str] = []
    api = _client(_flaky(httpx.ReadTimeout, 99, calls))
    with pytest.raises(httpx.ReadTimeout):
        await api.request("PATCH", "/issues/1", json={"body": "x"})
    await api.aclose()
    assert len(calls) == MAX_RETRIES + 1


async def test_post_is_retried_when_the_connection_never_opened():
    calls: list[str] = []
    api = _client(_flaky(httpx.ConnectError, 1, calls))
    assert (await api.request("POST", "/issues/1/comments", json={"body": "x"})).status_code == 200
    await api.aclose()
    assert calls == ["POST", "POST"]


async def test_post_is_not_retried_after_a_read_timeout():
    """The server may have created the comment already: a retry could post it twice."""
    calls: list[str] = []
    api = _client(_flaky(httpx.ReadTimeout, 1, calls))
    with pytest.raises(httpx.ReadTimeout):
        await api.request("POST", "/issues/1/comments", json={"body": "x"})
    await api.aclose()
    assert calls == ["POST"]


async def test_post_is_not_retried_on_5xx():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(502)

    api = _client(handler)
    assert (await api.request("POST", "/issues/1/comments", json={"body": "x"})).status_code == 502
    await api.aclose()
    assert calls == ["POST"]


@pytest.mark.parametrize(
    "limited",
    [
        httpx.Response(429, headers={"retry-after": "3"}),
        httpx.Response(403, headers={"retry-after": "3"}),
        httpx.Response(403, headers={"x-ratelimit-remaining": "0"}),
    ],
)
async def test_post_is_retried_on_rate_limits(limited):
    """A rate-limited request was rejected before it was processed: retrying cannot duplicate it."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return limited if len(calls) == 1 else httpx.Response(201, json={})

    api = _client(handler)
    assert (await api.request("POST", "/issues/1/comments", json={"body": "x"})).status_code == 201
    await api.aclose()
    assert calls == ["POST", "POST"]


async def test_graphql_query_counts_as_idempotent_but_mutation_does_not():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.content.decode())
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json={"data": {}})

    api = _client(handler)
    assert await api.graphql("query { viewer { login } }", {}) == {}
    assert len(calls) == 2
    calls.clear()
    resp = await api.request("POST", "/graphql", json={"query": "mutation { x }", "variables": {}})
    await api.aclose()
    assert resp.status_code == 503 and len(calls) == 1


async def test_retry_after_is_capped_by_default():
    calls: list[str] = []
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(429, headers={"retry-after": str(int(DEFAULT_MAX_RETRY_WAIT) + 1)})

    api = _client(handler, waits)
    assert api.max_retry_wait == DEFAULT_MAX_RETRY_WAIT
    assert (await api.request("GET", "/x")).status_code == 429
    await api.aclose()
    assert calls == ["GET"] and waits == []  # returned to the caller instead of sleeping for minutes


async def test_retry_after_within_the_cap_is_honoured():
    waits: list[float] = []
    responses = [httpx.Response(429, headers={"retry-after": "120"}), httpx.Response(200, json={})]

    api = _client(lambda request: responses.pop(0), waits)
    assert (await api.request("GET", "/x")).status_code == 200
    await api.aclose()
    assert waits == [120.0]


async def test_rate_limit_reset_is_honoured_without_retry_after():
    """M-5: x-ratelimit-remaining 0 and no retry-after: wait until x-ratelimit-reset (epoch seconds), capped."""
    waits: list[float] = []
    limited = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1030"}
    responses = [httpx.Response(403, headers=limited), httpx.Response(200, json={})]
    api = _client(lambda request: responses.pop(0), waits, clock=lambda: 1000.0)
    assert (await api.request("GET", "/x")).status_code == 200
    await api.aclose()
    assert waits == [31.0]  # until the reset, plus one second
    calls: list[str] = []

    def far(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "999999"})

    api = _client(far, waits, clock=lambda: 1000.0)
    assert (await api.request("POST", "/x", json={})).status_code == 403
    await api.aclose()
    assert calls == ["POST"]  # beyond max_retry_wait: returned to the caller
    passed = [httpx.Response(429, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "900"})]
    passed.append(httpx.Response(200, json={}))
    waits.clear()
    api = _client(lambda request: passed.pop(0), waits, clock=lambda: 1000.0)
    assert (await api.request("GET", "/x")).status_code == 200
    await api.aclose()
    assert waits == [1.0]  # a reset in the past: retry right away (one second)
