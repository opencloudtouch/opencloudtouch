"""Tests for the DLNA application service."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.models import DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService


@pytest.mark.asyncio
async def test_get_servers():
    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/content/control",
    )

    discovery = AsyncMock()
    discovery.discover.return_value = [server]

    service = DlnaService(discovery=discovery)

    result = await service.get_servers()

    assert result == [server]


@pytest.mark.asyncio
async def test_browse_server():
    server = DlnaServer(
        id="server-1",
        name="Test Server",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/content/control",
    )
    item = DlnaItem(
        id="track-1",
        parent_id="0",
        title="Track",
        is_container=False,
    )

    discovery = AsyncMock()
    discovery.discover.return_value = [server]

    client = AsyncMock()
    client.browse.return_value = [item]

    service = DlnaService(
        discovery=discovery,
        client=client,
    )

    result = await service.browse("server-1", "0")

    assert result == [item]
    client.browse.assert_awaited_once_with(server, "0")


@pytest.mark.asyncio
async def test_browse_unknown_server():
    discovery = AsyncMock()
    discovery.discover.return_value = []

    service = DlnaService(discovery=discovery)

    with pytest.raises(LookupError):
        await service.browse("missing-server")


@pytest.mark.asyncio
async def test_browse_reuses_discovered_server_without_new_ssdp():
    server = DlnaServer(
        id="server-1",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    discovery = AsyncMock()
    discovery.discover.return_value = [server]
    client = AsyncMock()
    client.browse.return_value = []
    service = DlnaService(discovery=discovery, client=client)

    assert await service.get_servers() == [server]
    await service.browse(server.id, "folder-a")
    await service.browse(server.id, "folder-b")
    discovery.discover.assert_awaited_once()
    assert client.browse.await_count == 2


@pytest.mark.asyncio
async def test_cache_expires_and_refreshes():
    server = DlnaServer(
        id="server-1",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    clock = [100.0]
    discovery = AsyncMock()
    discovery.discover.return_value = [server]
    service = DlnaService(
        discovery=discovery, client=AsyncMock(), cache_ttl=30.0, clock=lambda: clock[0]
    )

    await service.get_servers()
    clock[0] = 129.0
    await service.browse(server.id)
    assert discovery.discover.await_count == 1
    clock[0] = 131.0
    await service.browse(server.id)
    assert discovery.discover.await_count == 2


@pytest.mark.asyncio
async def test_missing_server_triggers_refresh_and_404():
    server = DlnaServer(
        id="server-1",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    discovery = AsyncMock()
    discovery.discover.side_effect = [[server], []]
    service = DlnaService(discovery=discovery, client=AsyncMock())
    await service.get_servers()

    with pytest.raises(LookupError, match="missing"):
        await service.browse("missing")
    assert discovery.discover.await_count == 2


@pytest.mark.asyncio
async def test_concurrent_browse_refreshes_expired_cache_only_once():
    server = DlnaServer(
        id="server-1",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    clock = [100.0]
    discovery = AsyncMock()
    discovery.discover.return_value = [server]
    client = AsyncMock()
    client.browse.return_value = []
    service = DlnaService(
        discovery=discovery, client=client, cache_ttl=30.0, clock=lambda: clock[0]
    )

    await service.get_servers()
    clock[0] = 131.0
    await asyncio.gather(
        service.browse(server.id, "a"),
        service.browse(server.id, "b"),
        service.browse(server.id, "c"),
    )
    assert discovery.discover.await_count == 2
    assert client.browse.await_count == 3


@pytest.mark.asyncio
async def test_repeated_missing_server_does_not_repeat_discovery():
    discovery = AsyncMock()
    discovery.discover.return_value = []
    service = DlnaService(discovery=discovery, client=AsyncMock())

    for _ in range(3):
        with pytest.raises(LookupError, match="missing"):
            await service.browse("missing")

    discovery.discover.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_refresh_clears_missing_server_cache():
    server = DlnaServer(
        id="missing",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    discovery = AsyncMock()
    discovery.discover.side_effect = [[], [server]]
    client = AsyncMock()
    client.browse.return_value = []
    service = DlnaService(discovery=discovery, client=client)

    with pytest.raises(LookupError):
        await service.browse(server.id)
    await service.get_servers()
    assert await service.browse(server.id) == []
    assert discovery.discover.await_count == 2


@pytest.mark.asyncio
async def test_play_uses_cached_server_and_closes_subscriptions():
    server = DlnaServer(
        id="server-1",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    item = DlnaItem(
        id="track-1",
        parent_id="folder",
        title="Song",
        is_container=False,
        resource_url="http://192.0.2.10/song.mp3",
    )
    discovery = AsyncMock()
    discovery.discover.return_value = [server]
    client = AsyncMock()
    client.browse.return_value = [item]
    playback = AsyncMock()
    playback.play.return_value = item
    service = DlnaService(discovery=discovery, client=client, playback=playback)
    service.subscriptions.ensure = AsyncMock()
    service.subscriptions.close = AsyncMock()

    await service.get_servers()
    result = await service.play(
        device_id="device-1",
        device_ip="192.0.2.20",
        server_id="server-1",
        parent_id="folder",
        object_id="track-1",
        callback_base_url="http://192.0.2.30:7777",
    )

    assert result == item
    discovery.discover.assert_awaited_once()
    service.subscriptions.ensure.assert_awaited_once_with(
        device_id="device-1",
        device_ip="192.0.2.20",
        callback_url="http://192.0.2.30:7777/api/dlna/events/device-1",
    )
    playback.play.assert_awaited_once()
    await service.close()
    service.subscriptions.close.assert_awaited_once()
