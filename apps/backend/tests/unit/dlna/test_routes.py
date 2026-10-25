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
        device_id="device-1",
        payload=routes.DlnaPlayRequest(
            server_id="server-1", object_id="track-1", parent_id="folder-1"
        ),
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
            device_id="missing",
            payload=routes.DlnaPlayRequest(
                server_id="server-1", object_id="track-1", parent_id="folder-1"
            ),
            service=service,
        )

    assert exc_info.value.status_code == 404


class MockNotifyRequest:
    """Minimal request object for AVTransport NOTIFY tests."""

    def __init__(self, body: bytes):
        self._body = body

    headers = {"sid": "uuid:test"}
    client = MagicMock(host="192.168.1.10")

    async def stream(self):
        yield self._body


@pytest.mark.asyncio
async def test_avtransport_notify(monkeypatch):
    service = AsyncMock()
    service.playback.handle_transport_state = AsyncMock()
    service.subscriptions.get = MagicMock(
        return_value=MagicMock(sid="uuid:test", device_ip="192.168.1.10")
    )

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
    service.subscriptions.get = MagicMock(
        return_value=MagicMock(
            sid="uuid:test",
            device_ip="192.168.1.10",
        )
    )
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
    service.subscriptions.get = MagicMock(
        return_value=MagicMock(
            sid="uuid:test",
            device_ip="192.168.1.10",
        )
    )
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


def test_http_play_route_with_slash_object_id(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    service = AsyncMock()
    service.play.return_value = DlnaItem(
        id="folder/track$1",
        parent_id="folder",
        title="Track",
        is_container=False,
        resource_url="http://server/track.mp3",
    )
    app.state.device_service = MagicMock()
    app.state.device_service.get_device_by_id = AsyncMock(
        return_value=MagicMock(ip="192.168.1.10")
    )
    app.dependency_overrides[get_dlna_service] = lambda: service
    monkeypatch.setattr(
        routes, "_get_callback_base_url", lambda *_: "http://192.0.2.20:7777"
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/dlna/devices/device-1/play",
            json={
                "server_id": "server-1",
                "object_id": "folder/track$1",
                "parent_id": "folder",
            },
        )
    assert response.status_code == 200
    assert response.json()["item"]["id"] == "folder/track$1"
    assert service.play.await_args.kwargs["object_id"] == "folder/track$1"


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (LookupError("missing"), 404),
        (routes.DlnaPlaybackError("inactive"), 409),
        (routes.DlnaRendererError("unavailable"), 502),
    ],
)
def test_http_play_error_mappings(monkeypatch, failure, expected):
    app = FastAPI()
    app.include_router(routes.router)
    service = AsyncMock()
    service.play.side_effect = failure
    app.state.device_service = MagicMock()
    app.state.device_service.get_device_by_id = AsyncMock(
        return_value=MagicMock(ip="192.168.1.10")
    )
    app.dependency_overrides[get_dlna_service] = lambda: service
    monkeypatch.setattr(
        routes, "_get_callback_base_url", lambda *_: "http://192.0.2.20:7777"
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/dlna/devices/device-1/play",
            json={
                "server_id": "server-1",
                "object_id": "folder/track",
                "parent_id": "folder",
            },
        )
    assert response.status_code == expected


def test_http_notify_dispatch_and_xml_hardening():
    app = FastAPI()
    app.include_router(routes.router)
    service = MagicMock()
    service.playback.handle_transport_state = AsyncMock()
    service.subscriptions.get.return_value = MagicMock(
        sid="uuid:test", device_ip="testclient"
    )
    app.dependency_overrides[get_dlna_service] = lambda: service
    body = (
        '<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">'
        '<e:property><LastChange>&lt;Event&gt;&lt;TransportState val="PLAYING"/&gt;&lt;/Event&gt;'
        "</LastChange></e:property></e:propertyset>"
    )
    headers = {"sid": "uuid:test"}
    with TestClient(app) as client:
        good = client.request(
            "NOTIFY", "/api/dlna/events/device-1", content=body, headers=headers
        )
        forbidden = client.request(
            "NOTIFY",
            "/api/dlna/events/device-1",
            content='<!DOCTYPE foo [<!ENTITY x "bad">]><foo>&x;</foo>',
            headers=headers,
        )
        oversized = client.request(
            "NOTIFY", "/api/dlna/events/device-1", content="X" * 65537, headers=headers
        )
        bad_sid = client.request(
            "NOTIFY",
            "/api/dlna/events/device-1",
            content=body,
            headers={"sid": "wrong"},
        )
    assert good.status_code == 200
    assert forbidden.status_code == 200
    assert oversized.status_code == 413
    assert bad_sid.status_code == 200
    service.playback.handle_transport_state.assert_awaited_once_with(
        "device-1", "PLAYING"
    )
