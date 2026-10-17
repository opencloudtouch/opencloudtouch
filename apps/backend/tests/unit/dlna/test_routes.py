"""Tests for DLNA API routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_dlna_service
from opencloudtouch.dlna import routes
from opencloudtouch.dlna.models import DlnaItem, DlnaServer


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


@pytest.mark.asyncio
async def test_browse_dlna_server():
    item = DlnaItem(
        id="track-1",
        parent_id="0",
        title="Test Track",
        is_container=False,
        resource_url="http://192.0.2.10/track.mp3",
        media_class="object.item.audioItem.musicTrack",
    )

    service = AsyncMock()
    service.browse.return_value = [item]

    result = await routes.browse_dlna_server(
        service=service,
        server_id="server-1",
        object_id="music",
    )

    assert result == {
        "server_id": "server-1",
        "object_id": "music",
        "items": [
            {
                "id": "track-1",
                "parent_id": "0",
                "title": "Test Track",
                "is_container": False,
                "resource_url": "http://192.0.2.10/track.mp3",
                "media_class": "object.item.audioItem.musicTrack",
                "artist": None,
                "album": None,
                "genre": None,
                "creator": None,
                "album_art_url": None,
                "duration": None,
                "size": None,
                "bitrate": None,
                "sample_frequency": None,
                "audio_channels": None,
                "protocol_info": None,
            }
        ],
    }

    service.browse.assert_awaited_once_with("server-1", "music")


@pytest.mark.asyncio
async def test_browse_unknown_dlna_server():
    service = AsyncMock()
    service.browse.side_effect = LookupError("DLNA server not found: missing")

    with pytest.raises(HTTPException) as exc_info:
        await routes.browse_dlna_server(
            service=service,
            server_id="missing",
            object_id="0",
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "DLNA server not found: missing"


@pytest.mark.asyncio
async def test_browse_missing_dlna_object():
    from opencloudtouch.dlna.client import DlnaBrowseError

    service = AsyncMock()
    service.browse.side_effect = DlnaBrowseError(
        "No Such Object",
        error_code="701",
    )

    with pytest.raises(HTTPException) as exc_info:
        await routes.browse_dlna_server(
            service=service,
            server_id="server-1",
            object_id="does-not-exist",
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "DLNA object not found: does-not-exist"


@pytest.mark.asyncio
async def test_browse_dlna_server_error():
    from opencloudtouch.dlna.client import DlnaBrowseError

    service = AsyncMock()
    service.browse.side_effect = DlnaBrowseError(
        "DLNA server unavailable",
    )

    with pytest.raises(HTTPException) as exc_info:
        await routes.browse_dlna_server(
            service=service,
            server_id="server-1",
            object_id="0",
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "DLNA server unavailable"


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
