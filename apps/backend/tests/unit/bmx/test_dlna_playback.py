"""Orion press path for DLNA presets (AC-B4..B7, B18)."""

import dataclasses
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.bmx.routes import router
from opencloudtouch.core.dlna_reference import DlnaReference, build_orion_data
from opencloudtouch.dlna.client import DlnaBrowseError
from opencloudtouch.dlna.mock import MOCK_SERVER, MockDlnaClient
from opencloudtouch.dlna.service import DlnaService

URL = "/core02/svc-bmx-adapter-orion/prod/orion/station"
SECRET_TITLE = "Secret Title Do Not Leak"


class SecretClient(MockDlnaClient):
    """Every item carries a title and cover that must never appear in logs."""

    async def get_object(self, server, object_id):
        item = await super().get_object(server, object_id)
        return dataclasses.replace(
            item,
            title=SECRET_TITLE,
            album_art_url="http://mock-media.invalid/c.jpg?token=SECRETTOKEN",
        )


@pytest.fixture
def discovery():
    d = AsyncMock()
    d.discover.return_value = [MOCK_SERVER]
    return d


def _client(discovery, dlna_client=None, cached=True):
    service = DlnaService(discovery, dlna_client or MockDlnaClient())
    if cached:
        service._servers[MOCK_SERVER.id] = MOCK_SERVER
    service.schedule_refresh = MagicMock()
    app = FastAPI()
    app.include_router(router)
    app.state.dlna_service = service
    return TestClient(app), service


def _press(client, object_id="music-001", server_id=MOCK_SERVER.id):
    data = build_orion_data(DlnaReference(server_id, object_id), "Stored Name")
    return client.get(f"{URL}?data={data}")


def test_track_returns_current_url(discovery):
    client, _ = _client(discovery)
    r = _press(client)
    assert r.status_code == 200
    body = r.json()
    assert body["audio"]["streamUrl"] == "http://mock-media.invalid/media/music-001.mp3"
    assert body["name"] == "Track 001"


def test_server_ip_change_returns_new_url(discovery):
    moved = dataclasses.replace(MOCK_SERVER, control_url="http://192.0.2.7/control")

    class Moved(MockDlnaClient):
        async def get_object(self, server, object_id):
            item = await super().get_object(server, object_id)
            return dataclasses.replace(item, resource_url="http://192.0.2.7/a.mp3")

    client, service = _client(discovery, Moved(), cached=False)
    service._servers[MOCK_SERVER.id] = moved
    assert _press(client).json()["audio"]["streamUrl"] == "http://192.0.2.7/a.mp3"


def test_container_plays_first_audio_item(discovery):
    client, _ = _client(discovery)
    body = _press(client, "subfolders").json()
    assert body["audio"]["streamUrl"].endswith("/media/sub-track-1.mp3")


def test_cover_becomes_image_url(discovery):
    client, _ = _client(discovery)
    body = _press(client, "mixed-http").json()
    assert body["imageUrl"] == "http://mock-media.invalid/cover.jpg"


@pytest.mark.parametrize("server_id", ["forged-server", MOCK_SERVER.id])
def test_cache_miss_is_503_without_scan(discovery, server_id):
    client, service = _client(discovery, cached=False)
    r = _press(client, server_id=server_id)
    assert r.status_code == 503
    assert r.json()["code"] == "dlna_server_not_found"
    discovery.discover.assert_not_awaited()
    service.schedule_refresh.assert_called_once()


def test_unknown_object_and_not_playable_are_404(discovery):
    client, _ = _client(discovery)
    gone = _press(client, "nope")
    assert (gone.status_code, gone.json()["code"]) == (404, "dlna_object_not_found")
    no_audio = _press(client, "albums")
    assert (no_audio.status_code, no_audio.json()["code"]) == (404, "dlna_not_playable")


def test_upstream_error_is_503(discovery):
    class Broken(MockDlnaClient):
        async def get_object(self, server, object_id):
            raise DlnaBrowseError("boom http://secret.invalid/x")

    client, service = _client(discovery, Broken())
    r = _press(client)
    assert (r.status_code, r.json()["code"]) == (503, "dlna_upstream_error")
    assert "secret.invalid" not in r.text
    service.schedule_refresh.assert_called_once()


def test_no_title_or_url_in_logs_or_error_bodies(discovery, caplog):
    caplog.set_level(logging.DEBUG)
    client, _ = _client(discovery, SecretClient())
    ok = _press(client)
    assert ok.status_code == 200
    failed = _press(client, "albums")
    for text in (caplog.text, failed.text):
        assert SECRET_TITLE not in text
        assert "SECRETTOKEN" not in text
        assert "mock-media.invalid" not in text
    assert "Stored Name" not in caplog.text
