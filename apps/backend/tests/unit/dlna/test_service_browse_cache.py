"""Tests for DlnaService.browse with the browse cache (stale-while-revalidate)."""

import asyncio
import gc
import logging
import tracemalloc
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.dlna.browse_cache import BrowseCache
from opencloudtouch.dlna.client import DlnaBrowseError, DlnaClient, DlnaTimeoutError
from opencloudtouch.dlna.models import BrowsePage, DlnaItem, DlnaServer
from opencloudtouch.dlna.service import DlnaService


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _server(server_id: str = "srv", host: str = "192.0.2.10") -> DlnaServer:
    return DlnaServer(server_id, "Name", f"http://{host}/d.xml", f"http://{host}/c")


class FakeClient(DlnaClient):
    """Counts browse calls; content per server; optional gate and error."""

    def __init__(self) -> None:
        self.calls = 0
        self.hosts: list[str] = []
        self.content: dict[str, list[str]] = {}
        self.gate: asyncio.Event | None = None
        self.error: Exception | None = None
        self.object_calls = 0

    async def browse(self, server, object_id="0", starting_index=0, requested_count=50):
        self.calls += 1
        self.hosts.append(server.control_url)
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        titles = self.content.get(server.id, ["A"])
        items = [
            DlnaItem(id=t, parent_id=object_id, title=t, is_container=True)
            for t in titles
        ]
        return BrowsePage(items, len(items), len(items))

    async def get_object(self, server, object_id):
        self.object_calls += 1
        return DlnaItem(id=object_id, parent_id="0", title="Live", is_container=True)


class Setup:
    def __init__(self, ttl=10.0, stale_ttl=100.0, max_items=1000) -> None:
        self.clock = Clock()
        self.client = FakeClient()
        self.servers = [_server()]
        self.discovery = AsyncMock()
        self.discovery.discover.side_effect = lambda: list(self.servers)
        self.cache = BrowseCache(
            ttl,
            stale_ttl,
            max_items,
            clock=self.clock,
            wall_clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.service = DlnaService(
            self.discovery,
            self.client,
            clock=self.clock,
            browse_cache=self.cache,
        )

    async def drain(self) -> None:
        while self.service._tasks:
            await asyncio.gather(*self.service._tasks, return_exceptions=True)
            await asyncio.sleep(0)


async def _yield(times: int = 5) -> None:
    for _ in range(times):
        await asyncio.sleep(0)


@pytest.fixture
def env() -> Setup:
    return Setup()


@pytest.mark.asyncio
async def test_fresh_hit_makes_no_client_call(env):
    first = await env.service.browse("srv")
    second = await env.service.browse("srv")
    assert env.client.calls == 1
    assert (first.cached, first.cached_at, first.stale, first.revalidating) == (
        False,
        None,
        False,
        False,
    )
    assert (second.cached, second.stale, second.revalidating) == (True, False, False)
    assert second.cached_at is not None
    assert second.items == first.items


@pytest.mark.asyncio
async def test_stale_hit_answers_at_once_and_revalidates_once(env):
    await env.service.browse("srv")
    env.client.content["srv"] = ["B"]
    env.clock.now += 20
    env.client.gate = asyncio.Event()
    results = [await env.service.browse("srv") for _ in range(3)]
    assert all(r.cached and r.stale and r.items[0].id == "A" for r in results)
    assert results[0].revalidating
    await _yield()
    assert env.client.calls == 2  # one revalidation for three stale hits
    env.client.gate.set()
    await env.drain()
    fresh = await env.service.browse("srv")
    assert (fresh.stale, fresh.items[0].id) == (False, "B")
    assert env.client.calls == 2


@pytest.mark.asyncio
async def test_expired_entry_is_a_miss(env):
    await env.service.browse("srv")
    env.clock.now += 200
    page = await env.service.browse("srv")
    assert env.client.calls == 2 and not page.cached


@pytest.mark.asyncio
async def test_coalescing_shares_one_call_and_survives_cancelled_waiter(env):
    env.client.gate = asyncio.Event()
    tasks = [asyncio.create_task(env.service.browse("srv")) for _ in range(4)]
    other = asyncio.create_task(env.service.browse("srv", "other"))
    await _yield()
    tasks[0].cancel()  # a waiter leaving must not cancel the shared fetch
    await _yield()
    env.client.gate.set()
    results = await asyncio.gather(*tasks[1:], other)
    assert env.client.calls == 2
    assert all(r.items[0].id == "A" for r in results)
    assert (
        await env.service.browse("srv")
    ).cached  # the cancelled waiter's fetch filled it
    assert env.cache.stats()["coalesced"] == 3
    await env.drain()
    assert not env.service._tasks and not env.service._inflight


@pytest.mark.asyncio
async def test_waiter_timeout_keeps_the_shared_fetch(env):
    env.client.gate = asyncio.Event()
    with pytest.raises(DlnaTimeoutError):
        await env.service.browse("srv", deadline=0.01)
    env.client.gate.set()
    await env.drain()
    assert (await env.service.browse("srv")).cached


@pytest.mark.asyncio
async def test_error_reaches_all_waiters_is_not_cached_and_frees_key(env, caplog):
    env.client.gate = asyncio.Event()
    env.client.error = DlnaBrowseError("boom", error_code="500")
    tasks = [asyncio.create_task(env.service.browse("srv")) for _ in range(3)]
    await _yield()
    env.client.gate.set()
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(o, DlnaBrowseError) for o in outcomes)
    await env.drain()
    assert not env.service._inflight and env.cache.stats()["entries"] == 0
    env.client.error = None
    assert not (await env.service.browse("srv")).cached
    assert env.client.calls == 2


@pytest.mark.asyncio
async def test_unknown_server_miss_is_404_style_lookup_error():
    env = Setup()
    env.servers.clear()
    with pytest.raises(LookupError):
        await env.service.browse("srv")


@pytest.mark.asyncio
async def test_failed_revalidation_keeps_stale_and_backs_off_for_30s(env):
    await env.service.browse("srv")
    env.clock.now += 20
    env.client.error = DlnaBrowseError("down", error_code="500")
    first = await env.service.browse("srv")
    assert first.stale and first.revalidating
    await env.drain()
    calls = env.client.calls
    during = await env.service.browse("srv")
    assert (during.cached, during.stale, during.revalidating) == (True, True, False)
    await env.drain()
    assert env.client.calls == calls
    env.clock.now += 31
    await env.service.browse("srv")
    await env.drain()
    assert env.client.calls == calls + 1
    stats = env.cache.stats()
    assert stats["revalidations_failed"] == 2 and stats["entries"] == 1


@pytest.mark.asyncio
async def test_701_on_revalidation_drops_the_entry(env):
    await env.service.browse("srv")
    env.clock.now += 20
    env.client.error = DlnaBrowseError("gone", error_code="701")
    await env.service.browse("srv")
    await env.drain()
    assert env.cache.stats()["entries"] == 0
    with pytest.raises(DlnaBrowseError):
        await env.service.browse("srv")


@pytest.mark.asyncio
async def test_servers_do_not_share_entries(env):
    env.servers.append(_server("other", "192.0.2.11"))
    env.client.content = {"srv": ["A"], "other": ["Z"]}
    one = await env.service.browse("srv")
    two = await env.service.browse("other")
    assert (one.items[0].id, two.items[0].id) == ("A", "Z")
    assert (await env.service.browse("other")).items[0].id == "Z"


@pytest.mark.asyncio
async def test_weighted_bound_through_the_service():
    env = Setup(max_items=5)
    env.client.content["srv"] = ["a", "b", "c"]
    await env.service.browse("srv", "f1")
    await env.service.browse("srv", "f2")
    stats = env.cache.stats()
    assert stats["items"] <= 5 and stats["evictions"] == 1


@pytest.mark.asyncio
async def test_entries_survive_discovery_eviction_and_answer_stale(env):
    await env.service.browse("srv")
    env.servers.clear()
    env.service._servers.clear()
    env.service._last_seen.clear()
    env.discovery.discover.reset_mock()
    hit = await env.service.browse("srv")
    assert hit.cached and not hit.stale
    env.discovery.discover.assert_not_called()
    env.clock.now += 20
    stale = await env.service.browse("srv")
    assert stale.cached and stale.stale and stale.revalidating
    await env.drain()  # revalidation fails (unknown server), not 404 for the caller
    again = await env.service.browse("srv")
    assert again.cached and not again.revalidating
    assert env.cache.stats()["revalidations_failed"] == 1
    with pytest.raises(LookupError):
        await env.service.browse("srv", refresh=True)
    with pytest.raises(LookupError):
        await env.service.browse("srv", "unseen")


@pytest.mark.asyncio
async def test_server_returns_with_new_ip_keeps_entries_and_revalidates_there(env):
    await env.service.browse("srv")
    env.servers[:] = [_server("srv", "192.0.2.99")]
    env.service._servers.clear()
    env.clock.now += 70  # past the discovery cache so the lookup rescans
    stale = await env.service.browse("srv")
    assert stale.cached and stale.stale
    await env.drain()
    assert env.client.hosts[-1] == "http://192.0.2.99/c"
    assert not (await env.service.browse("srv")).stale


@pytest.mark.asyncio
async def test_forced_refresh_replaces_entry_and_joins_running_fetch(env):
    await env.service.browse("srv")
    env.client.content["srv"] = ["B"]
    env.client.gate = asyncio.Event()
    refreshes = [
        asyncio.create_task(env.service.browse("srv", refresh=True)) for _ in range(3)
    ]
    await _yield()
    env.client.gate.set()
    results = await asyncio.gather(*refreshes)
    assert env.client.calls == 2
    assert all(not r.cached and r.items[0].id == "B" for r in results)
    assert (await env.service.browse("srv")).items[0].id == "B"
    assert env.cache.stats()["forced_refreshes"] == 3


@pytest.mark.asyncio
async def test_forced_refresh_joins_running_revalidation(env):
    await env.service.browse("srv")
    env.clock.now += 20
    env.client.gate = asyncio.Event()
    await env.service.browse("srv")  # starts the revalidation
    await _yield()
    refresh = asyncio.create_task(env.service.browse("srv", refresh=True))
    await _yield()
    env.client.gate.set()
    await refresh
    assert env.client.calls == 2


@pytest.mark.asyncio
async def test_forced_refresh_failure_keeps_previous_entry(env):
    await env.service.browse("srv")
    env.client.error = DlnaBrowseError("down", error_code="500")
    with pytest.raises(DlnaBrowseError):
        await env.service.browse("srv", refresh=True)
    assert (await env.service.browse("srv")).cached


@pytest.mark.asyncio
async def test_second_forced_refresh_within_2s_is_answered_from_cache(env):
    await env.service.browse("srv")
    await env.service.browse("srv", refresh=True)
    calls = env.client.calls
    throttled = await env.service.browse("srv", refresh=True)
    assert throttled.cached and env.client.calls == calls
    assert env.cache.stats()["refresh_throttled"] == 1
    env.clock.now += 3
    await env.service.browse("srv", refresh=True)
    assert env.client.calls == calls + 1


@pytest.mark.asyncio
async def test_inflight_fetch_is_not_stored_after_invalidation(env):
    env.client.gate = asyncio.Event()
    task = asyncio.create_task(env.service.browse("srv"))
    await _yield()
    env.cache.clear()
    env.client.gate.set()
    page = await task
    assert page.items[0].id == "A"
    assert env.cache.stats()["entries"] == 0
    assert env.cache.stats()["generation_discards"] == 1


@pytest.mark.asyncio
async def test_aclose_cancels_and_awaits_all_tasks(env):
    env.client.gate = asyncio.Event()
    waiter = asyncio.create_task(env.service.browse("srv"))
    await _yield()
    env.service.schedule_refresh()
    await env.service.aclose()
    assert not env.service._tasks and not env.service._inflight
    assert env.service._refresh_task is None or env.service._refresh_task.done()
    with pytest.raises(asyncio.CancelledError):
        await waiter


@pytest.mark.asyncio
async def test_disabled_cache_calls_the_client_every_time():
    env = Setup(ttl=0)
    for _ in range(3):
        page = await env.service.browse("srv")
        assert (page.cached, page.cached_at, page.stale, page.revalidating) == (
            False,
            None,
            False,
            False,
        )
    assert env.client.calls == 3 and env.cache.stats()["entries"] == 0


@pytest.mark.asyncio
async def test_press_path_stays_live_and_never_touches_the_cache(env):
    await env.service.browse("srv")
    before = env.cache.stats()
    item = await env.service.get_object("srv", "x")
    assert item.title == "Live" and env.client.object_calls == 1
    assert env.cache.stats() == before


@pytest.mark.asyncio
async def test_counters_in_a_scripted_scenario(env):
    await env.service.browse("srv")  # miss
    await env.service.browse("srv")  # fresh hit
    env.clock.now += 20
    await env.service.browse("srv")  # stale hit + ok revalidation
    await env.drain()
    stats = env.cache.stats()
    assert (stats["misses"], stats["hits_fresh"], stats["hits_stale"]) == (1, 1, 1)
    assert stats["revalidations_ok"] == 1 and stats["entries"] == 1


@pytest.mark.asyncio
async def test_cached_page_is_identical_and_immutable(env):
    miss = await env.service.browse("srv")
    miss.items.clear()
    hit = await env.service.browse("srv")
    assert [i.id for i in hit.items] == ["A"]
    hit.items.clear()
    assert [i.id for i in (await env.service.browse("srv")).items] == ["A"]


@pytest.mark.asyncio
async def test_page_of_200_typical_items_stays_under_2_mb():
    env = Setup()
    titles = [f"Artist {n:03d} - Album title number {n:03d}" for n in range(200)]

    class Rich(FakeClient):
        async def browse(self, server, object_id="0", starting_index=0, count=50):
            items = [
                DlnaItem(
                    id=f"0$music$albums${n:06d}",
                    parent_id="0$music$albums",
                    title=t,
                    is_container=False,
                    resource_url=f"http://192.0.2.10:8200/MediaItems/{n}.flac",
                    media_class="object.item.audioItem.musicTrack",
                    artist=f"Artist {n:03d}",
                    album="Album title",
                    genre="Genre",
                    creator=f"Artist {n:03d}",
                    album_art_url=f"http://192.0.2.10:8200/AlbumArt/{n}.jpg",
                    duration="0:03:45.000",
                    size=30_000_000,
                    bitrate=1411,
                    sample_frequency=44100,
                    audio_channels=2,
                    protocol_info="http-get:*:audio/flac:DLNA.ORG_PN=FLAC",
                )
                for n, t in enumerate(titles)
            ]
            return BrowsePage(items, 200, 200)

    env.service.client = Rich()
    gc.collect()
    tracemalloc.start()
    try:
        before = tracemalloc.take_snapshot()
        await env.service.browse("srv", "big", 0, 200)
        gc.collect()
        after = tracemalloc.take_snapshot()
    finally:
        tracemalloc.stop()
    grown = sum(s.size_diff for s in after.compare_to(before, "filename"))
    print(f"browse cache: 200 items retain {grown} bytes ({grown // 200} per item)")
    assert grown <= 2 * 1024 * 1024


@pytest.mark.asyncio
async def test_new_service_starts_with_an_empty_cache():
    first, second = Setup(), Setup()
    await first.service.browse("srv")
    assert second.cache.stats()["entries"] == 0
    assert not (await second.service.browse("srv")).cached


@pytest.mark.asyncio
async def test_logs_contain_no_object_ids_or_titles(env, caplog):
    caplog.set_level(logging.DEBUG)
    env.client.content["srv"] = ["SecretTitle"]
    await env.service.browse("srv", "secret-object")
    await env.service.browse("srv", "secret-object")
    env.clock.now += 20
    await env.service.browse("srv", "secret-object")
    await env.drain()
    env.client.error = DlnaBrowseError("down", error_code="500")
    env.clock.now += 40
    await env.service.browse("srv", "secret-object")
    await env.drain()
    with pytest.raises(DlnaBrowseError):
        await env.service.browse("srv", "secret-object", refresh=True)
    text = caplog.text
    assert "secret-object" not in text and "SecretTitle" not in text
