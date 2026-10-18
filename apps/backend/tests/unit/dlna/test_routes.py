"""Tests for DLNA API routes."""

from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.asyncio
async def test_play_dlna_item(monkeypatch):
    item = DlnaItem(
        id="track-1",
        parent_id="folder-1",
        title="Track",
        is_container=False,
        resource_url="http://server/track.mp3",
        media_class="object.item.audioItem.musicTrack",
    )

    service = AsyncMock()
    service.play.return_value = item

    monkeypatch.setattr(
        routes,
        "_get_callback_base_url",
        lambda request, device_ip: "http://192.0.2.20:7778",
    )

    class Device:
        ip = "192.168.1.10"

    class DeviceService:
        async def get_device_by_id(self, device_id):
            return Device()

    class App:
        class State:
            device_service = DeviceService()

        state = State()

    class Request:
        app = App()

    result = await routes.play_dlna_item(
        request=Request(),
        server_id="server-1",
        object_id="track-1",
        device_id="device-1",
        parent_id="folder-1",
        service=service,
    )

    assert result["device_id"] == "device-1"
    assert result["item"]["id"] == "track-1"
    assert result["item"]["title"] == "Track"

    service.play.assert_awaited_once_with(
        device_id="device-1",
        device_ip="192.168.1.10",
        server_id="server-1",
        parent_id="folder-1",
        object_id="track-1",
        callback_base_url="http://192.0.2.20:7778",
    )


@pytest.mark.asyncio
async def test_dlna_playback_controls(monkeypatch):
    item = DlnaItem(
        id="track-1",
        parent_id="folder-1",
        title="Track",
        is_container=False,
        resource_url="http://server/track.mp3",
        media_class="object.item.audioItem.musicTrack",
    )

    service = AsyncMock()
    service.next.return_value = item
    service.previous.return_value = item

    class Device:
        ip = "192.168.1.10"

    class DeviceService:
        async def get_device_by_id(self, device_id):
            return Device()

    class App:
        class State:
            device_service = DeviceService()

        state = State()

    class Request:
        app = App()

    request = Request()

    await routes.pause_dlna(request=request, device_id="device-1", service=service)
    await routes.resume_dlna(request=request, device_id="device-1", service=service)
    await routes.next_dlna(request=request, device_id="device-1", service=service)
    await routes.previous_dlna(request=request, device_id="device-1", service=service)

    service.pause.assert_awaited_once_with("device-1", "192.168.1.10")
    service.resume.assert_awaited_once_with("device-1", "192.168.1.10")
    service.next.assert_awaited_once_with("device-1", "192.168.1.10")
    service.previous.assert_awaited_once_with("device-1", "192.168.1.10")


@pytest.mark.asyncio
async def test_play_dlna_missing_device(monkeypatch):
    service = AsyncMock()

    class DeviceService:
        async def get_device_by_id(self, device_id):
            return None

    class App:
        class State:
            device_service = DeviceService()

        state = State()

    class Request:
        app = App()

    with pytest.raises(HTTPException) as exc_info:
        await routes.play_dlna_item(
            request=Request(),
            server_id="server-1",
            object_id="track-1",
            device_id="missing",
            parent_id="folder-1",
            service=service,
        )

    assert exc_info.value.status_code == 404


class MockNotifyRequest:
    """Minimal request object for AVTransport NOTIFY tests."""

    def __init__(self, body: bytes):
        self._body = body

    async def body(self) -> bytes:
        return self._body


@pytest.mark.asyncio
async def test_avtransport_notify(monkeypatch):
    service = AsyncMock()
    service.playback.handle_transport_state = AsyncMock()

    body = b"""<?xml version="1.0"?>
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
  <e:property>
    <LastChange>&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;&lt;InstanceID val="0"&gt;&lt;TransportState val="PLAYING"/&gt;&lt;/InstanceID&gt;&lt;/Event&gt;</LastChange>
  </e:property>
</e:propertyset>"""

    response = await routes.dlna_avtransport_event(
        MockNotifyRequest(body),
        "device-1",
        service,
    )

    assert response.status_code == 200
    service.playback.handle_transport_state.assert_awaited_once_with(
        "device-1",
        "PLAYING",
    )


@pytest.mark.asyncio
async def test_avtransport_notify_ignores_malformed_xml(monkeypatch):
    service = AsyncMock()
    service.playback.handle_transport_state = AsyncMock()

    response = await routes.dlna_avtransport_event(
        MockNotifyRequest(b"<not-valid"),
        "device-1",
        service,
    )

    assert response.status_code == 200
    service.playback.handle_transport_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_dlna_item(monkeypatch):
    item = DlnaItem(
        id="track-1",
        parent_id="0",
        title="Current Track",
        is_container=False,
        resource_url="http://server/track.mp3",
        media_class="object.item.audioItem.musicTrack",
        artist="Artist",
        album="Album",
    )

    service = AsyncMock()
    service.playback.current = MagicMock(return_value=item)

    result = await routes.get_current_dlna_item("device-1", service)

    assert result["device_id"] == "device-1"
    assert result["item"]["title"] == "Current Track"
    assert result["item"]["artist"] == "Artist"
    assert result["item"]["album"] == "Album"


@pytest.mark.asyncio
async def test_get_current_dlna_item_when_idle(monkeypatch):
    service = AsyncMock()
    service.playback.current = MagicMock(return_value=None)

    result = await routes.get_current_dlna_item("device-1", service)

    assert result == {
        "device_id": "device-1",
        "item": None,
    }


@pytest.mark.asyncio
async def test_avtransport_notify_ignores_malformed_bose_lastchange():
    """Ignore the malformed initial LastChange sent by SoundTouch."""
    service = AsyncMock()
    service.playback.handle_transport_state = AsyncMock()

    body = b"""<?xml version="1.0"?>
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
  <e:property>
    <LastChange>&lt;/InstanceID&gt;&lt;/Event&gt;</LastChange>
  </e:property>
</e:propertyset>"""

    response = await routes.dlna_avtransport_event(
        MockNotifyRequest(body),
        "device-1",
        service,
    )

    assert response.status_code == 200
    service.playback.handle_transport_state.assert_not_awaited()
