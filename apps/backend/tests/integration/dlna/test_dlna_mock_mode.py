"""Mock-mode integration: DLNA browse against the fake media server."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_dlna_service
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.dlna import routes
from opencloudtouch.dlna.mock import MockDlnaClient, MockDlnaDiscovery
from opencloudtouch.dlna.service import DlnaService

BASE = "/api/dlna/servers/mock-media-server/browse"


@pytest.fixture
def client():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    service = DlnaService(MockDlnaDiscovery(), MockDlnaClient())
    app.dependency_overrides[get_dlna_service] = lambda: service
    return TestClient(app)


def test_paging_over_120_items(client):
    seen, index, pages = [], 0, 0
    while True:
        body = client.get(f"{BASE}?object_id=music&starting_index={index}").json()
        seen += [i["id"] for i in body["items"]]
        pages += 1
        if not body["has_more"]:
            break
        index = body["next_index"]
    assert (len(seen), len(set(seen)), pages) == (120, 120, 3)


def test_root_filter_cover_and_errors(client):
    assert len(client.get(BASE).json()["items"]) == 4
    mixed = client.get(f"{BASE}?object_id=mixed").json()
    assert mixed["number_returned"] == 3 and len(mixed["items"]) == 2
    assert mixed["items"][1]["album_art_url"] is None
    missing = client.get(f"{BASE}?object_id=nope").json()
    assert missing["code"] == "dlna_object_not_found"
    other = client.get("/api/dlna/servers/unknown/browse")
    assert other.json()["code"] == "dlna_server_not_found"


def test_app_in_mock_mode_serves_the_fake_server():
    from opencloudtouch.main import app

    with TestClient(app) as http:
        assert http.get(BASE).status_code == 200
