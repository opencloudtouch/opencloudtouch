"""Tests for DLNA API routes."""

import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_dlna_service
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.dlna import routes
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer, page_cursor


@pytest.mark.asyncio
async def test_get_dlna_servers():
    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/content/control",
    )

    service = AsyncMock()
    service.get_servers.return_value = [server]

    result = await routes.get_dlna_servers(service=service)

    assert result == [
        {
            "id": "server-1",
            "name": "Test Server",
            "location": "http://192.0.2.10/device.xml",
            "control_url": "http://192.0.2.10/content/control",
        }
    ]


def _client(service) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[get_dlna_service] = lambda: service
    return TestClient(app)


def _track(n: int) -> DlnaItem:
    return DlnaItem(
        id=f"t{n}",
        parent_id="music",
        title=f"Track {n}",
        is_container=False,
        resource_url=f"http://192.0.2.10/{n}.mp3",
        media_class="object.item.audioItem.musicTrack",
    )


def test_browse_default_paging_and_response_shape():
    service = AsyncMock()
    service.browse.return_value = BrowsePage([_track(n) for n in range(50)], 50, 120)

    response = _client(service).get("/api/dlna/servers/server-1/browse?object_id=music")

    body = response.json()
    assert response.status_code == 200
    assert {k: v for k, v in body.items() if k != "items"} == {
        "server_id": "server-1",
        "object_id": "music",
        "starting_index": 0,
        "number_returned": 50,
        "total_matches": 120,
        "next_index": 50,
        "has_more": True,
    }
    assert len(body["items"]) == 50
    assert body["items"][0]["title"] == "Track 0"
    assert body["items"][0]["album_art_url"] is None
    service.browse.assert_awaited_once_with("server-1", "music", 0, 50)


def test_browse_last_page_has_no_more():
    service = AsyncMock()
    service.browse.return_value = BrowsePage([_track(n) for n in range(20)], 20, 120)

    body = (
        _client(service)
        .get("/api/dlna/servers/s/browse?starting_index=100&requested_count=50")
        .json()
    )

    assert (body["next_index"], body["has_more"]) == (120, False)
    service.browse.assert_awaited_once_with("s", "0", 100, 50)


@pytest.mark.parametrize(
    ("page", "start", "count", "expected"),
    [
        (BrowsePage([], 50, None), 0, 50, (50, True)),
        (BrowsePage([], 49, None), 0, 50, (49, False)),
        (BrowsePage([], 0, None), 0, 50, (0, False)),
        (BrowsePage([], 0, 120), 0, 50, (0, False)),
        (BrowsePage([], 50, 100), 50, 50, (100, False)),
        (BrowsePage([], 50, 101), 50, 50, (100, True)),
        (BrowsePage([], 60, 120), 0, 50, (60, True)),  # trust number_returned
    ],
)
def test_page_cursor_truth_table(page, start, count, expected):
    assert page_cursor(page, start, count) == expected


def test_filtered_page_still_advances_by_number_returned():
    service = AsyncMock()
    service.browse.return_value = BrowsePage([_track(n) for n in range(40)], 50, 120)

    body = _client(service).get("/api/dlna/servers/s/browse").json()

    assert len(body["items"]) == 40
    assert (body["number_returned"], body["next_index"]) == (50, 50)


@pytest.mark.parametrize(
    "query",
    ["requested_count=0", "requested_count=201", "starting_index=-1"],
)
def test_browse_rejects_out_of_range_paging(query):
    service = AsyncMock()

    response = _client(service).get(f"/api/dlna/servers/s/browse?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    service.browse.assert_not_awaited()


def test_browse_empty_object_id_means_root():
    service = AsyncMock()
    service.browse.return_value = BrowsePage([], 0, 0)

    body = _client(service).get("/api/dlna/servers/s/browse?object_id=").json()

    assert body["object_id"] == "0"
    service.browse.assert_awaited_once_with("s", "0", 0, 50)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (
            LookupError("DLNA server not found: http://192.0.2.10/x"),
            404,
            "dlna_server_not_found",
        ),
        (
            DlnaBrowseError("No Such Object", error_code="701"),
            404,
            "dlna_object_not_found",
        ),
        (DlnaBrowseError("boom http://192.0.2.10/x"), 502, "dlna_upstream_error"),
        (DlnaTimeoutError("slow http://192.0.2.10/x"), 504, "dlna_server_timeout"),
    ],
)
def test_browse_errors_are_coded_and_leak_no_url(error, status, code, caplog):
    service = AsyncMock()
    service.browse.side_effect = error

    with caplog.at_level(logging.DEBUG):
        response = _client(service).get("/api/dlna/servers/s/browse")

    body = response.json()
    assert (response.status_code, body["code"]) == (status, code)
    assert "http" not in response.text
    assert "192.0.2.10" not in caplog.text
    assert not body.get("params")


def test_dlna_route_dependency_override():
    app = FastAPI()
    app.include_router(routes.router)
    service = AsyncMock()
    service.get_servers.return_value = []
    app.dependency_overrides[get_dlna_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/dlna/servers")

    assert response.status_code == 200
    assert response.json() == []
    service.get_servers.assert_awaited_once()
