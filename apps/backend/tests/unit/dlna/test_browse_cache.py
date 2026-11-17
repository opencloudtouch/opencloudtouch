"""Tests for the in-memory browse page cache (states, weighted LRU, generations)."""

from datetime import UTC, datetime, timedelta

from opencloudtouch.dlna.browse_cache import BrowseCache
from opencloudtouch.dlna.models import BrowsePage, DlnaItem

KEY = ("srv", "0", 0, 50)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _wall() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def _page(n: int) -> BrowsePage:
    items = [
        DlnaItem(id=f"i{k}", parent_id="0", title=f"T{k}", is_container=True)
        for k in range(n)
    ]
    return BrowsePage(items, n, n)


def _cache(clock: Clock, max_items: int = 100) -> BrowseCache:
    return BrowseCache(
        ttl=10, stale_ttl=100, max_items=max_items, clock=clock, wall_clock=_wall
    )


def _put(cache: BrowseCache, key: tuple, page: BrowsePage) -> bool:
    return cache.put(key, page, cache.generation(key[0]))


def test_miss_then_fresh_hit_carries_provenance():
    cache = _cache(Clock())
    assert cache.get(KEY) is None
    assert _put(cache, KEY, _page(3))
    hit = cache.get(KEY)
    assert hit is not None
    assert (hit.cached, hit.stale, hit.revalidating) == (True, False, False)
    assert hit.cached_at == _wall()
    assert [i.id for i in hit.items] == ["i0", "i1", "i2"]


def test_stale_then_expired_entry_is_dropped():
    clock = Clock()
    cache = _cache(clock)
    _put(cache, KEY, _page(2))
    clock.now += 10
    hit = cache.get(KEY)
    assert hit is not None and hit.stale
    clock.now += 90
    assert cache.get(KEY) is None
    assert cache.stats()["entries"] == 0


def test_reads_are_copies():
    cache = _cache(Clock())
    _put(cache, KEY, _page(2))
    first = cache.get(KEY)
    assert first is not None
    first.items.clear()
    second = cache.get(KEY)
    assert second is not None and len(second.items) == 2


def test_weighted_lru_evicts_least_recently_used():
    cache = _cache(Clock(), max_items=10)
    a, b, c = ("s", "a", 0, 50), ("s", "b", 0, 50), ("s", "c", 0, 50)
    _put(cache, a, _page(4))
    _put(cache, b, _page(4))
    assert cache.get(a) is not None  # recent hit protects a
    _put(cache, c, _page(4))
    assert cache.get(b) is None
    assert cache.get(a) is not None and cache.get(c) is not None
    stats = cache.stats()
    assert stats["items"] == 8 and stats["evictions"] == 1


def test_empty_page_weighs_one_and_oversized_page_is_not_stored():
    cache = _cache(Clock(), max_items=5)
    assert _put(cache, KEY, _page(0))
    assert cache.stats()["items"] == 1
    assert not _put(cache, ("srv", "big", 0, 50), _page(6))
    assert cache.get(("srv", "big", 0, 50)) is None


def test_servers_are_isolated():
    cache = _cache(Clock())
    _put(cache, ("one", "0", 0, 50), _page(1))
    _put(cache, ("two", "0", 0, 50), _page(2))
    one, two = cache.get(("one", "0", 0, 50)), cache.get(("two", "0", 0, 50))
    assert one is not None and two is not None
    assert (len(one.items), len(two.items)) == (1, 2)


def test_drop_bumps_generation_and_discards_stale_writes():
    cache = _cache(Clock())
    _put(cache, KEY, _page(1))
    token = cache.generation("srv")
    cache.drop(KEY)
    assert not cache.put(KEY, _page(1), token)
    assert cache.get(KEY) is None
    assert cache.stats()["generation_discards"] == 1
    assert cache.put(KEY, _page(1), cache.generation("srv"))


def test_drop_server_and_clear_bump_generations():
    cache = _cache(Clock())
    _put(cache, KEY, _page(1))
    _put(cache, ("other", "0", 0, 50), _page(1))
    token_srv, token_other = cache.generation("srv"), cache.generation("other")
    cache.drop_server("srv")
    assert cache.get(KEY) is None
    assert cache.get(("other", "0", 0, 50)) is not None
    assert cache.generation("srv") != token_srv
    assert cache.generation("other") == token_other
    cache.clear()
    assert cache.stats()["entries"] == 0
    assert cache.generation("other") != token_other


def test_insert_purges_expired_entries_of_other_keys():
    clock = Clock()
    cache = _cache(clock)
    _put(cache, ("old", "0", 0, 50), _page(1))
    clock.now += 200
    _put(cache, KEY, _page(1))
    assert cache.stats()["entries"] == 1


def test_backoff_and_refresh_stamp_live_on_the_entry():
    clock = Clock()
    cache = _cache(clock)
    assert not cache.in_backoff(KEY)
    _put(cache, KEY, _page(1))
    cache.mark_failed(KEY, 30)
    assert cache.in_backoff(KEY)
    clock.now += 31
    assert not cache.in_backoff(KEY)
    assert not cache.refreshed_within(KEY, 2)
    cache.stamp_refresh(KEY)
    assert cache.refreshed_within(KEY, 2)
    clock.now += 3
    assert not cache.refreshed_within(KEY, 2)
    _put(cache, KEY, _page(1))  # a replaced entry starts clean
    assert not cache.refreshed_within(KEY, 100)


def test_cached_at_is_wall_clock_of_fetch():
    clock = Clock()
    times = iter([_wall(), _wall() + timedelta(hours=1)])
    cache = BrowseCache(10, 100, 10, clock=clock, wall_clock=lambda: next(times))
    _put(cache, KEY, _page(1))
    hit = cache.get(KEY)
    assert hit is not None and hit.cached_at == _wall()


def test_disabled_cache_stores_nothing():
    cache = BrowseCache(0, 100, 10)
    assert not cache.enabled
    assert not _put(cache, KEY, _page(1))
    assert cache.get(KEY) is None
