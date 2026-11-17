"""Mock-mode integration: the browse cache end to end over HTTP, without network."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_dlna_service
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.dlna import routes
from opencloudtouch.dlna.browse_cache import BrowseCache
from opencloudtouch.dlna.mock import MockDlnaClient, MockDlnaDiscovery
from opencloudtouch.dlna.service import DlnaService

BASE = "/api/dlna/servers/mock-media-server/browse"


class Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def env():
    clock = Clock()
    mock_client = MockDlnaClient()
    service = DlnaService(
        MockDlnaDiscovery(),
        mock_client,
        clock=clock,
        browse_cache=BrowseCache(900, 604800, 20000, clock=clock),
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[get_dlna_service] = lambda: service
    with TestClient(app) as client:
        yield client, mock_client, clock, service


def test_cold_warm_stale_and_refresh(env):
    client, mock, clock, service = env
    cold = client.get(BASE).json()
    assert (cold["cached"], cold["stale"], mock.browse_calls) == (False, False, 1)

    warm = client.get(BASE).json()
    assert (warm["cached"], warm["stale"], mock.browse_calls) == (True, False, 1)
    assert warm["items"] == cold["items"] and warm["cached_at"]

    clock.now += 1000
    stale = client.get(BASE).json()
    assert (stale["cached"], stale["stale"]) == (True, True)
    assert stale["items"] == cold["items"]

    forced = client.get(f"{BASE}?refresh=true").json()
    assert forced["cached"] is False and forced["items"] == cold["items"]


def test_latency_hook_and_counter(env):
    _, mock, _, _ = env
    assert mock.browse_calls == 0 and mock.latency == 0.0


def test_unknown_object_is_not_cached(env):
    client, mock, _, _ = env
    assert client.get(f"{BASE}?object_id=nope").status_code == 404
    assert client.get(f"{BASE}?object_id=nope").status_code == 404
    assert mock.browse_calls == 2


def test_press_path_reads_live_with_a_warm_cache(env):
    import asyncio

    client, mock, _, service = env
    client.get(BASE)
    warm_calls = mock.browse_calls
    resolved = asyncio.run(
        service.resolve_playable(
            "mock-media-server", "music-001", cache_only=False, deadline=5
        )
    )
    assert resolved.title == "Track 001"
    assert mock.browse_calls == warm_calls  # get_object, not a cached browse
