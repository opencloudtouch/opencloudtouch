"""Tests for DLNA API routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_dlna_service
from opencloudtouch.dlna import routes
from opencloudtouch.core.exception_handlers import coded_api_error_handler
from opencloudtouch.core.exceptions import CodedApiError
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer


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


def _client(service):
    app = FastAPI()
    app.include_router(routes.router)
    app.add_exception_handler(CodedApiError, coded_api_error_handler)
    app.dependency_overrides[get_dlna_service] = lambda: service
    return TestClient(app)


def _track(i=1):
    return DlnaItem(id=f"t{i}", parent_id="0", title="T", is_container=False)


def test_has_more_with_total():
    service = AsyncMock()
    service.browse_page.return_value = BrowsePage([_track()], 2, 5)
    res = _client(service).get(
        "/api/dlna/servers/s1/browse",
        params={"object_id": "m", "starting_index": 2, "requested_count": 2},
    )
    body = res.json()
    assert res.status_code == 200
    assert (body["next_index"], body["has_more"], body["total_matches"]) == (4, True, 5)
    assert body["number_returned"] == 2 and len(body["items"]) == 1
    service.browse_page.assert_awaited_once_with("s1", "m", 2, 2)


def test_has_more_without_total():
    service = AsyncMock()
    service.browse_page.return_value = BrowsePage([], 3, None)
    c = _client(service)
    assert c.get("/api/dlna/servers/s1/browse?requested_count=3").json()["has_more"]
    assert not c.get("/api/dlna/servers/s1/browse?requested_count=4").json()["has_more"]


def _browse_error(exc):
    service = AsyncMock()
    service.browse_page.side_effect = exc
    return _client(service).get("/api/dlna/servers/s1/browse")


def test_unknown_server_404_code():
    res = _browse_error(LookupError("x"))
    assert (res.status_code, res.json()["code"]) == (404, "dlna_server_not_found")


def test_701_maps_404_object_code():
    res = _browse_error(DlnaBrowseError("x", error_code="701"))
    assert (res.status_code, res.json()["code"]) == (404, "dlna_object_not_found")


def test_timeout_maps_504_code():
    res = _browse_error(DlnaTimeoutError("x"))
    assert (res.status_code, res.json()["code"]) == (504, "dlna_server_timeout")


def test_upstream_502_code():
    res = _browse_error(DlnaBrowseError("http://192.0.2.10/secret"))
    assert (res.status_code, res.json()["code"]) == (502, "dlna_upstream_error")
    assert "secret" not in res.text


def test_request_limits_422():
    c = _client(AsyncMock())
    assert c.get("/api/dlna/servers/s1/browse?requested_count=201").status_code == 422
    assert c.get("/api/dlna/servers/s1/browse?starting_index=-1").status_code == 422


def test_first_child_audio_route():
    service = AsyncMock()
    service.first_child_is_audio.return_value = True
    res = _client(service).get("/api/dlna/servers/s1/first-child-audio?object_id=f")
    assert res.json() == {"first_child_is_audio": True}
    service.first_child_is_audio.side_effect = LookupError("x")
    res = _client(service).get("/api/dlna/servers/s1/first-child-audio?object_id=f")
    assert res.status_code == 404


def test_object_path_route():
    from opencloudtouch.dlna.models import ObjectPath

    service = AsyncMock()
    folder = DlnaItem(id="f", parent_id="p", title="Folder", is_container=True)
    parent = DlnaItem(id="p", parent_id="0", title="Parent", is_container=True)
    service.get_object_path.return_value = ObjectPath("NAS", folder, [parent])
    res = _client(service).get("/api/dlna/servers/s1/objects/path?object_id=f")
    assert res.status_code == 200
    assert res.json() == {
        "server_id": "s1",
        "server_name": "NAS",
        "object_id": "f",
        "title": "Folder",
        "is_container": True,
        "path": [{"object_id": "p", "title": "Parent"}],
    }
    service.get_object_path.assert_awaited_once_with("s1", "f")


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (DlnaBrowseError("x", error_code="701"), 404, "dlna_object_not_found"),
        (DlnaBrowseError("cycle"), 502, "dlna_upstream_error"),
        (LookupError("x"), 404, "dlna_server_not_found"),
    ],
)
def test_object_path_route_errors(exc, status, code):
    service = AsyncMock()
    service.get_object_path.side_effect = exc
    res = _client(service).get("/api/dlna/servers/s1/objects/path?object_id=f")
    assert (res.status_code, res.json()["code"]) == (status, code)


def test_object_path_route_requires_object_id():
    c = _client(AsyncMock())
    assert c.get("/api/dlna/servers/s1/objects/path").status_code == 422
    assert c.get("/api/dlna/servers/s1/objects/path?object_id=").status_code == 422


def test_album_root_route():
    service = AsyncMock()
    service.find_album_root.return_value = "albums"
    res = _client(service).get("/api/dlna/servers/s1/album-root")
    assert res.json() == {"object_id": "albums"}
    service.find_album_root.return_value = None
    res = _client(service).get("/api/dlna/servers/s1/album-root")
    assert res.json() == {"object_id": None}


def test_album_root_route_errors():
    service = AsyncMock()
    service.find_album_root.side_effect = DlnaTimeoutError("x")
    res = _client(service).get("/api/dlna/servers/s1/album-root")
    assert (res.status_code, res.json()["code"]) == (504, "dlna_server_timeout")
