"""Route tests for GET /api/dlna/servers/{id}/objects/path (mock media server)."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_dlna_service
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.dlna import routes
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.mock import MOCK_UUID_SERVER, MockDlnaClient, MockDlnaDiscovery
from opencloudtouch.dlna.service import DlnaService


@pytest.fixture
def app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    service = DlnaService(MockDlnaDiscovery(), MockDlnaClient())
    app.dependency_overrides[get_dlna_service] = lambda: service
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _url(server: str = "mock-media-server") -> str:
    return f"/api/dlna/servers/{server}/objects/path"


def test_four_level_path_of_a_track(client):
    body = client.get(_url(), params={"object_id": "albums-a-b-c-1"}).json()
    assert [p["object_id"] for p in body["path"]] == [
        "albums",
        "albums-a",
        "albums-a-b",
        "albums-a-b-c",
    ]
    assert body["path"][0] == {"object_id": "albums", "title": "Albums"}
    assert body["object_id"] == "albums-a-b-c-1"
    assert body["server_id"] == "mock-media-server"
    assert body["server_name"] and body["is_container"] is False


def test_second_mock_server_answers_too(client):
    body = client.get(
        _url(MOCK_UUID_SERVER.id), params={"object_id": "albums-a-b-c-1"}
    ).json()
    assert len(body["path"]) == 4


def test_folder_below_root_and_root_itself(client):
    top = client.get(_url(), params={"object_id": "albums"}).json()
    assert top["path"] == [] and top["is_container"] is True
    root = client.get(_url(), params={"object_id": "0"}).json()
    assert root["path"] == [] and root["title"] == root["server_name"]


def test_errors(client):
    r = client.get(_url("unknown"), params={"object_id": "albums"})
    assert (r.status_code, r.json()["code"]) == (404, "dlna_server_not_found")
    r = client.get(_url(), params={"object_id": "nope"})
    assert (r.status_code, r.json()["code"]) == (404, "dlna_object_not_found")


def test_object_id_bounds(client):
    for value in ("", "x" * 513):
        r = client.get(_url(), params={"object_id": value})
        assert (r.status_code, r.json()["code"]) == (422, "validation_error")
    assert client.get(_url()).status_code == 422
    r = client.get(_url(), params={"object_id": "x" * 512})
    assert r.status_code == 404  # accepted, just unknown


def test_upstream_failure_timeout_and_no_leak(app, client, caplog):
    service = AsyncMock()
    app.dependency_overrides[get_dlna_service] = lambda: service
    caplog.set_level("DEBUG")
    service.get_object_path.side_effect = DlnaBrowseError("boom http://192.0.2.10/x")
    r = client.get(_url(), params={"object_id": "secret-id"})
    assert (r.status_code, r.json()["code"]) == (502, "dlna_upstream_error")
    service.get_object_path.side_effect = DlnaTimeoutError("slow")
    r = client.get(_url(), params={"object_id": "secret-id"})
    assert (r.status_code, r.json()["code"]) == (504, "dlna_server_timeout")
    ours = " ".join(
        r.getMessage() for r in caplog.records if r.name.startswith("opencloudtouch")
    )
    assert ours and "secret-id" not in ours and "192.0.2.10" not in ours
