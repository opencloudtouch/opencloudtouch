"""Tests for DlnaService.resolve_playable, get_cached_server and background refresh."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.client import DlnaBrowseError, DlnaTimeoutError
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer
from opencloudtouch.dlna.service import (
    PRESS_RESOLVE_BUDGET,
    DlnaNotPlayableError,
    DlnaService,
    ResolvedDlnaItem,
)

SERVER = DlnaServer(
    id="server-1",
    name="NAS",
    location="http://192.0.2.10/device.xml",
    control_url="http://192.0.2.10/control",
)
_AUDIO = "object.item.audioItem.musicTrack"


def _service(client, server=SERVER) -> tuple[DlnaService, AsyncMock]:
    discovery = AsyncMock()
    discovery.discover.return_value = [server]
    return DlnaService(discovery=discovery, client=client), discovery


def _track(item_id="t1", url="http://192.0.2.10/m/t1.mp3", cover=None, title="Song"):
    return DlnaItem(
        item_id,
        "0",
        title,
        False,
        resource_url=url,
        media_class=_AUDIO,
        album_art_url=cover,
    )


def _folder(item_id="f1"):
    return DlnaItem(item_id, "0", "Album", True, media_class="object.container")


async def _resolve(service, object_id="t1", server_id="server-1", cache_only=False):
    return await service.resolve_playable(
        server_id, object_id, cache_only=cache_only, deadline=5
    )


@pytest.mark.asyncio
async def test_resolve_track_returns_current_url_and_cover():
    client = AsyncMock()
    client.get_object.return_value = _track(cover="http://192.0.2.10/c.jpg")
    service, _ = _service(client)
    assert await _resolve(service) == ResolvedDlnaItem(
        "Song", "http://192.0.2.10/m/t1.mp3", "http://192.0.2.10/c.jpg"
    )


@pytest.mark.asyncio
async def test_resolve_container_skips_60_subfolders_to_first_audio():
    subfolders = [_folder(f"s{n}") for n in range(60)]
    pages = {
        0: BrowsePage(subfolders[:50], 50, 61),
        50: BrowsePage(subfolders[50:] + [_track("deep")], 11, 61),
    }
    client = AsyncMock()
    client.get_object.return_value = _folder()
    client.browse.side_effect = lambda s, o, start, count: pages[start]
    service, _ = _service(client)
    result = await _resolve(service, "f1")
    assert result.resource_url == "http://192.0.2.10/m/t1.mp3"
    assert result.title == "Album"
    assert client.browse.await_count == 2


@pytest.mark.asyncio
async def test_resolve_container_gives_up_after_5_pages():
    client = AsyncMock()
    client.get_object.return_value = _folder()
    client.browse.side_effect = lambda s, o, start, count: BrowsePage(
        [_folder(f"x{start + n}") for n in range(50)], 50, 1000
    )
    service, _ = _service(client)
    with pytest.raises(DlnaNotPlayableError):
        await _resolve(service, "f1")
    assert client.browse.await_count == 5


@pytest.mark.asyncio
async def test_resolve_empty_container_and_non_audio_are_not_playable():
    client = AsyncMock()
    client.get_object.return_value = _folder()
    client.browse.return_value = BrowsePage([], 0, 0)
    service, _ = _service(client)
    with pytest.raises(DlnaNotPlayableError):
        await _resolve(service, "f1")
    client.get_object.return_value = DlnaItem(
        "i",
        "0",
        "Pic",
        False,
        resource_url="http://192.0.2.10/p.jpg",
        media_class="object.item.imageItem",
    )
    with pytest.raises(DlnaNotPlayableError):
        await _resolve(service, "i")


@pytest.mark.asyncio
async def test_resolve_item_without_resource_is_not_playable():
    client = AsyncMock()
    client.get_object.return_value = _track(url=None)
    service, _ = _service(client)
    with pytest.raises(DlnaNotPlayableError):
        await _resolve(service)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,ok",
    [
        ("http://192.0.2.10:9000/m.mp3", True),
        ("https://192.0.2.10/m.mp3", True),
        ("http://192.0.2.11/m.mp3", False),
        ("ftp://192.0.2.10/m.mp3", False),
        ("file:///m.mp3", False),
        ("//192.0.2.10/m.mp3", False),
        ("http://nas.example/m.mp3", False),
        ("not a url", False),
    ],
)
async def test_resource_url_rule_for_ipv4_server(url, ok):
    client = AsyncMock()
    client.get_object.return_value = _track(url=url)
    service, _ = _service(client)
    if ok:
        assert (await _resolve(service)).resource_url == url
    else:
        with pytest.raises(DlnaNotPlayableError):
            await _resolve(service)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "control,url,ok",
    [
        ("http://NAS.Local:5000/c", "http://nas.local:8200/m.mp3", True),
        ("http://nas.local/c", "http://other.local/m.mp3", False),
        ("http://[fe80::1%25eth0]:5000/c", "http://[fe80::1]/m.mp3", True),
        ("http://[fe80::1]/c", "http://[FE80:0:0:0:0:0:0:1]/m.mp3", True),
        ("http://[fe80::1]/c", "http://[fe80::2]/m.mp3", False),
        ("http://nas.local/c", "http://192.0.2.10/m.mp3", False),
        ("http://192.0.2.10/c", "http://nas.local/m.mp3", False),
        ("http://[fe80::1]/c", "http://[bad/m.mp3", False),
    ],
)
async def test_resource_url_rule_for_names_ipv6_and_case(control, url, ok):
    client = AsyncMock()
    client.get_object.return_value = _track(url=url)
    service, _ = _service(client, DlnaServer("s", "NAS", "http://x/d.xml", control))
    if ok:
        await _resolve(service, server_id="s")
    else:
        with pytest.raises(DlnaNotPlayableError):
            await _resolve(service, server_id="s")


@pytest.mark.asyncio
async def test_cover_on_other_host_or_scheme_is_dropped_but_item_resolves():
    client = AsyncMock()
    service, _ = _service(client)
    for cover in ("http://evil.example/c.jpg", "file:///c.jpg", "http://192.0.2.99/c"):
        client.get_object.return_value = _track(cover=cover)
        assert (await _resolve(service)).album_art_url is None


@pytest.mark.asyncio
async def test_container_cover_falls_back_to_first_track_cover():
    client = AsyncMock()
    client.get_object.return_value = _folder()
    client.browse.return_value = BrowsePage(
        [_track(cover="http://192.0.2.10/t.jpg")], 1, 1
    )
    service, _ = _service(client)
    assert (await _resolve(service, "f1")).album_art_url == "http://192.0.2.10/t.jpg"


@pytest.mark.asyncio
async def test_unknown_server_on_normal_lookup_raises_lookup_error():
    service, _ = _service(AsyncMock())
    with pytest.raises(LookupError):
        await _resolve(service, server_id="forged")


@pytest.mark.asyncio
async def test_cache_only_never_scans_and_misses_schedule_one_refresh():
    client = AsyncMock()
    service, discovery = _service(client)
    assert service.get_cached_server("server-1") is None

    for _ in range(3):
        with pytest.raises(LookupError):
            await _resolve(service, cache_only=True)
    discovery.discover.assert_not_awaited()  # the press itself never scans
    await asyncio.sleep(0.05)
    assert discovery.discover.await_count == 1  # one de-duplicated refresh
    assert service.get_cached_server("server-1") == SERVER

    client.get_object.return_value = _track()
    assert (await _resolve(service, cache_only=True)).resource_url.endswith("t1.mp3")
    assert discovery.discover.await_count == 1


@pytest.mark.asyncio
async def test_cache_only_upstream_failure_schedules_refresh_but_701_does_not():
    client = AsyncMock()
    service, discovery = _service(client)
    await service.get_servers()
    discovery.discover.reset_mock()

    client.get_object.side_effect = DlnaBrowseError("gone", error_code="701")
    with pytest.raises(DlnaBrowseError):
        await _resolve(service, "x", cache_only=True)
    await asyncio.sleep(0.05)
    discovery.discover.assert_not_awaited()

    client.get_object.side_effect = DlnaBrowseError("down")
    with pytest.raises(DlnaBrowseError):
        await _resolve(service, "x", cache_only=True)
    await asyncio.sleep(0.05)
    assert discovery.discover.await_count == 1


@pytest.mark.asyncio
async def test_not_playable_does_not_schedule_a_refresh():
    client = AsyncMock()
    client.get_object.return_value = _track(url="http://evil.example/x.mp3")
    service, discovery = _service(client)
    await service.get_servers()
    discovery.discover.reset_mock()
    with pytest.raises(DlnaNotPlayableError):
        await _resolve(service, cache_only=True)
    await asyncio.sleep(0.05)
    discovery.discover.assert_not_awaited()


@pytest.mark.asyncio
async def test_press_budget_is_three_seconds_and_caps_the_operation():
    assert PRESS_RESOLVE_BUDGET == 3.0

    async def slow(*args):
        await asyncio.sleep(5)

    client = AsyncMock()
    client.get_object.side_effect = slow
    service, _ = _service(client)
    await service.get_servers()
    with pytest.raises(DlnaTimeoutError):
        await service.resolve_playable(
            "server-1", "t1", cache_only=True, deadline=0.05
        )


@pytest.mark.asyncio
async def test_background_refresh_swallows_discovery_errors_and_can_rerun():
    service, discovery = _service(AsyncMock())
    discovery.discover.side_effect = OSError("no network")
    service.schedule_refresh()
    await asyncio.sleep(0.05)
    assert discovery.discover.await_count == 1
    service.schedule_refresh()
    await asyncio.sleep(0.05)
    assert discovery.discover.await_count == 2
