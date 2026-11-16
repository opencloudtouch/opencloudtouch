"""Tests for the DLNA application service."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer
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
    client.browse.return_value = BrowsePage([item], 1, 1)

    service = DlnaService(
        discovery=discovery,
        client=client,
    )

    result = await service.browse("server-1", "0")

    assert result == BrowsePage([], 1, 1) or result.items == []
    client.browse.assert_awaited_once_with(server, "0", 0, 50)


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
    client.browse.return_value = BrowsePage([], 0, 0)
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
    client.browse.return_value = BrowsePage([], 0, 0)
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
    client.browse.return_value = BrowsePage([], 0, 0)
    clock = [100.0]
    service = DlnaService(discovery=discovery, client=client, clock=lambda: clock[0])

    with pytest.raises(LookupError, match="server-1"):
        await service.browse(server.id)
    clock[0] = 103.1
    assert (await service.browse(server.id)).items == []
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
    client.browse.return_value = BrowsePage([], 0, 0)
    service = DlnaService(discovery=discovery, client=client)

    await service.get_servers()
    assert len(await service.get_servers()) == 2
    assert (await service.browse(second.id)).items == []
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
    client.browse.return_value = BrowsePage([], 0, 0)
    service = DlnaService(discovery=discovery, client=client)

    with pytest.raises(LookupError):
        await service.browse(server.id)
    await service.get_servers()
    assert (await service.browse(server.id)).items == []
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


SERVER = DlnaServer(
    id="server-1",
    name="NAS",
    location="http://192.0.2.10/device.xml",
    control_url="http://192.0.2.10/control",
)


def _service(client, **kwargs) -> DlnaService:
    discovery = AsyncMock()
    discovery.discover.return_value = [SERVER]
    return DlnaService(discovery=discovery, client=client, **kwargs)


@pytest.mark.asyncio
async def test_browse_filters_non_audio_but_keeps_number_returned():
    folder = DlnaItem("f", "0", "Folder", True)
    track = DlnaItem("t", "0", "T", False, media_class="object.item.audioItem")
    by_proto = DlnaItem("p", "0", "P", False, protocol_info="http-get:*:audio/flac:*")
    image = DlnaItem("i", "0", "I", False, media_class="object.item.imageItem")
    client = AsyncMock()
    client.browse.return_value = BrowsePage([folder, track, by_proto, image], 50, 120)

    page = await _service(client).browse("server-1", "0", 100, 50)

    assert [i.id for i in page.items] == ["f", "t", "p"]
    assert (page.number_returned, page.total_matches) == (50, 120)
    client.browse.assert_awaited_once_with(SERVER, "0", 100, 50)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cover", "expected"),
    [
        ("http://192.0.2.10/c.jpg", "http://192.0.2.10/c.jpg"),
        ("https://192.0.2.10/c.jpg", "https://192.0.2.10/c.jpg"),
        ("/c.jpg", None),
        ("c.jpg", None),
        ("file:///c.jpg", None),
        ("ftp://192.0.2.10/c.jpg", None),
        ("http:///c.jpg", None),
        (None, None),
    ],
)
async def test_cover_is_kept_only_if_absolute_http(cover, expected):
    item = DlnaItem("f", "0", "F", True, album_art_url=cover)
    client = AsyncMock()
    client.browse.return_value = BrowsePage([item], 1, 1)
    client.get_object.return_value = item

    service = _service(client)
    assert (await service.browse("server-1")).items[0].album_art_url == expected
    assert (await service.get_object("server-1", "f")).album_art_url == expected


@pytest.mark.asyncio
async def test_get_object_uses_shared_lookup():
    item = DlnaItem("f", "0", "F", True)
    client = AsyncMock()
    client.get_object.return_value = item

    assert await _service(client).get_object("server-1", "f") == item
    client.get_object.assert_awaited_once_with(SERVER, "f")
    with pytest.raises(LookupError):
        await _service(client).get_object("other", "f")


@pytest.mark.asyncio
async def test_total_deadline_ends_operation_with_timeout_error():
    async def slow(*args):
        await asyncio.sleep(5)

    client = AsyncMock()
    client.browse.side_effect = slow
    client.get_object.side_effect = slow
    service = _service(client, timeout=0.05)

    with pytest.raises(DlnaTimeoutError):
        await service.browse("server-1")
    with pytest.raises(DlnaTimeoutError):
        await service.get_object("server-1", "x")


@pytest.mark.asyncio
async def test_caller_may_pass_a_shorter_deadline_but_not_a_longer_one():
    async def slow(*args):
        await asyncio.sleep(0.2)
        return BrowsePage([], 0, 0)

    client = AsyncMock()
    client.browse.side_effect = slow
    with pytest.raises(DlnaTimeoutError):
        await _service(client, timeout=5).browse("server-1", deadline=0.05)
    with pytest.raises(DlnaTimeoutError):
        await _service(client, timeout=0.05).browse("server-1", deadline=30)


@pytest.mark.asyncio
async def test_client_errors_pass_through_the_deadline():
    client = AsyncMock()
    client.browse.side_effect = DlnaBrowseError("x", error_code="701")
    with pytest.raises(DlnaBrowseError) as exc:
        await _service(client).browse("server-1")
    assert exc.value.error_code == "701"


def test_service_passes_timeout_to_default_client():
    assert DlnaService(discovery=AsyncMock(), timeout=30).client.timeout.read == 30
