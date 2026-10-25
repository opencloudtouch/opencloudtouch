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
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_discovery():
        entered.set()
        await release.wait()
        return [server]

    discovery.discover.side_effect = slow_discovery
    tasks = [
        asyncio.create_task(service.browse(server.id, folder))
        for folder in ("a", "b", "c")
    ]
    await asyncio.wait_for(entered.wait(), timeout=1)
    await asyncio.sleep(0)
    assert discovery.discover.await_count == 2
    release.set()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=1)
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

    discovery.discover.assert_awaited_once()  # Short retry backoff prevents scan storms.


@pytest.mark.asyncio
async def test_empty_scan_is_retried_and_server_becomes_available():
    server = DlnaServer(
        id="server-1",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    discovery = AsyncMock()
    discovery.discover.side_effect = [[], [server]]
    client = AsyncMock()
    client.browse.return_value = []
    clock = [100.0]
    service = DlnaService(discovery=discovery, client=client, clock=lambda: clock[0])

    with pytest.raises(LookupError, match="server-1"):
        await service.browse(server.id)
    clock[0] = 103.1
    assert await service.browse(server.id) == []
    assert discovery.discover.await_count == 2


@pytest.mark.asyncio
async def test_partial_refresh_keeps_previously_discovered_server():
    first = DlnaServer(
        id="first",
        name="First",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    second = DlnaServer(
        id="second",
        name="Second",
        location="http://192.0.2.11/device.xml",
        control_url="http://192.0.2.11/control",
    )
    discovery = AsyncMock()
    discovery.discover.side_effect = [[first, second], [first]]
    client = AsyncMock()
    client.browse.return_value = []
    service = DlnaService(discovery=discovery, client=client)

    await service.get_servers()
    assert len(await service.get_servers()) == 2
    assert await service.browse(second.id) == []
    assert discovery.discover.await_count == 2


@pytest.mark.asyncio
async def test_missing_id_is_retried_after_short_ttl():
    known = DlnaServer(
        id="known",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    clock = [100.0]
    discovery = AsyncMock()
    discovery.discover.return_value = [known]
    service = DlnaService(
        discovery=discovery,
        client=AsyncMock(),
        clock=lambda: clock[0],
        missing_ttl=3.0,
    )
    for _ in range(2):
        with pytest.raises(LookupError):
            await service.browse("unknown")
    assert discovery.discover.await_count == 1
    clock[0] = 103.1
    with pytest.raises(LookupError):
        await service.browse("unknown")
    assert discovery.discover.await_count == 2


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
async def test_stale_server_is_eventually_removed():
    server = DlnaServer(
        id="server-1",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    clock = [100.0]
    discovery = AsyncMock()
    discovery.discover.side_effect = [[server], [], []]
    service = DlnaService(
        discovery=discovery, client=AsyncMock(), clock=lambda: clock[0]
    )

    assert await service.get_servers() == [server]
    clock[0] = 161.0
    assert await service.get_servers() == [server]
    clock[0] = 281.0
    assert await service.get_servers() == []


@pytest.mark.asyncio
async def test_empty_scan_backoff_expires_and_retries():
    clock = [100.0]
    discovery = AsyncMock()
    discovery.discover.return_value = []
    service = DlnaService(
        discovery=discovery,
        client=AsyncMock(),
        clock=lambda: clock[0],
        missing_ttl=3.0,
    )
    for _ in range(3):
        with pytest.raises(LookupError):
            await service.browse("missing")
    discovery.discover.assert_awaited_once()
    clock[0] = 103.1
    with pytest.raises(LookupError):
        await service.browse("missing")
    assert discovery.discover.await_count == 2


@pytest.mark.asyncio
async def test_concurrent_unknown_ids_share_empty_discovery_backoff():
    known = DlnaServer(
        id="known",
        name="NAS",
        location="http://192.0.2.10/device.xml",
        control_url="http://192.0.2.10/control",
    )
    clock = [100.0]
    started = asyncio.Event()
    release = asyncio.Event()
    discovery = AsyncMock()
    service = DlnaService(
        discovery=discovery,
        client=AsyncMock(),
        clock=lambda: clock[0],
        missing_ttl=3.0,
    )
    discovery.discover.return_value = [known]
    await service.get_servers()

    async def empty_discovery():
        started.set()
        await release.wait()
        return []

    discovery.discover.side_effect = empty_discovery
    tasks = [
        asyncio.create_task(service.browse(server_id))
        for server_id in ("unknown-a", "unknown-b", "unknown-c")
    ]
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True), timeout=1
    )
    assert all(isinstance(result, LookupError) for result in results)
    assert discovery.discover.await_count == 2

    clock[0] = 103.1
    with pytest.raises(LookupError):
        await service.browse("unknown-d")
    assert discovery.discover.await_count == 3


@pytest.mark.asyncio
async def test_expired_missing_ids_are_pruned_on_refresh():
    clock = [100.0]
    discovery = AsyncMock()
    discovery.discover.return_value = []
    service = DlnaService(
        discovery=discovery,
        client=AsyncMock(),
        clock=lambda: clock[0],
        missing_ttl=3.0,
    )

    for server_id in ("unknown-a", "unknown-b"):
        with pytest.raises(LookupError):
            await service.browse(server_id)
    assert set(service._missing_ids) == {"unknown-a", "unknown-b"}

    clock[0] = 103.1
    await service.get_servers()
    assert service._missing_ids == {}

    with pytest.raises(LookupError):
        await service.browse("unknown-c")
    assert set(service._missing_ids) == {"unknown-c"}
