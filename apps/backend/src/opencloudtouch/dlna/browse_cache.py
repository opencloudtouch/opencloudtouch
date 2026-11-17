"""In-memory cache of filtered DLNA browse pages (stale-while-revalidate).

Pure and synchronous: it runs on the event loop only, so it needs no locks. The
service decides when to fetch or revalidate; this class owns states, the weighted
LRU bound and the per-server generation that keeps in-flight fetches from writing
back after an invalidation.
"""

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from opencloudtouch.dlna.models import BrowsePage, DlnaItem

# (server_id, object_id, starting_index, requested_count)
CacheKey = tuple[str, str, int, int]

PURGE_INTERVAL = 60.0  # seconds between lazy age purges on insert

_COUNTERS = (
    "hits_fresh",
    "hits_stale",
    "misses",
    "coalesced",
    "revalidations_ok",
    "revalidations_failed",
    "forced_refreshes",
    "refresh_throttled",
    "evictions",
    "generation_discards",
)


class _Entry:
    __slots__ = (
        "items",
        "number_returned",
        "total_matches",
        "fetched_at",
        "cached_at",
        "weight",
        "backoff_until",
        "refreshed_at",
    )

    def __init__(
        self,
        page: BrowsePage,
        fetched_at: float,
        cached_at: datetime,
    ) -> None:
        self.items: tuple[DlnaItem, ...] = tuple(page.items)
        self.number_returned = page.number_returned
        self.total_matches = page.total_matches
        self.fetched_at = fetched_at
        self.cached_at = cached_at
        self.weight = max(1, len(self.items))
        self.backoff_until = 0.0
        self.refreshed_at: float | None = None


class BrowseCache:
    """Weighted LRU cache with a fresh window and a longer stale window."""

    def __init__(
        self,
        ttl: float,
        stale_ttl: float,
        max_items: int,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.ttl = ttl
        self.stale_ttl = stale_ttl
        self.max_items = max_items
        self._clock = clock
        self._wall_clock = wall_clock
        self._entries: OrderedDict[CacheKey, _Entry] = OrderedDict()
        self._items = 0
        self._generations: dict[str, int] = {}
        self._epoch = 0
        self._last_purge = clock()
        self._counters = dict.fromkeys(_COUNTERS, 0)

    @property
    def enabled(self) -> bool:
        return self.ttl > 0

    def count(self, name: str) -> None:
        self._counters[name] += 1

    def stats(self) -> dict[str, int]:
        """Counters plus current size; no keys, ids or content."""
        return {**self._counters, "entries": len(self._entries), "items": self._items}

    def generation(self, server_id: str) -> int:
        """Token a fetch records at start; unchanged means writing back is safe."""
        return self._epoch + self._generations.get(server_id, 0)

    def get(self, key: CacheKey) -> BrowsePage | None:
        """Copy of the cached page with provenance, or ``None`` (expired entries go)."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        age = self._clock() - entry.fetched_at
        if age >= self.stale_ttl:
            self.drop(key)
            return None
        self._entries.move_to_end(key)
        return BrowsePage(
            list(entry.items),
            entry.number_returned,
            entry.total_matches,
            cached=True,
            cached_at=entry.cached_at,
            stale=age >= self.ttl,
        )

    def put(self, key: CacheKey, page: BrowsePage, generation: int) -> bool:
        """Store *page* unless the server's generation moved or it cannot fit."""
        if not self.enabled:
            return False
        if generation != self.generation(key[0]):
            self.count("generation_discards")
            return False
        entry = _Entry(
            replace(page, items=list(page.items)), self._clock(), self._wall_clock()
        )
        if entry.weight > self.max_items:
            return False
        self._purge_expired()
        self._remove(key)
        self._entries[key] = entry
        self._items += entry.weight
        while self._items > self.max_items:
            oldest = next(iter(self._entries))
            self._remove(oldest)
            self.count("evictions")
        return True

    def drop(self, key: CacheKey) -> None:
        if self._remove(key):
            self._bump(key[0])

    def drop_server(self, server_id: str) -> None:
        keys = [k for k in self._entries if k[0] == server_id]
        for key in keys:
            self._remove(key)
        if keys:
            self._bump(server_id)  # only real servers get a counter: bounded

    def clear(self) -> None:
        self._entries.clear()
        self._items = 0
        self._epoch += 1

    def in_backoff(self, key: CacheKey) -> bool:
        entry = self._entries.get(key)
        return entry is not None and self._clock() < entry.backoff_until

    def mark_failed(self, key: CacheKey, backoff: float) -> None:
        if (entry := self._entries.get(key)) is not None:
            entry.backoff_until = self._clock() + backoff

    def stamp_refresh(self, key: CacheKey) -> None:
        if (entry := self._entries.get(key)) is not None:
            entry.refreshed_at = self._clock()

    def refreshed_within(self, key: CacheKey, window: float) -> bool:
        entry = self._entries.get(key)
        return (
            entry is not None
            and entry.refreshed_at is not None
            and self._clock() - entry.refreshed_at < window
        )

    def _remove(self, key: CacheKey) -> bool:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._items -= entry.weight
        return entry is not None

    def _bump(self, server_id: str) -> None:
        self._generations[server_id] = self._generations.get(server_id, 0) + 1

    def _purge_expired(self) -> None:
        now = self._clock()
        if now - self._last_purge < PURGE_INTERVAL:
            return
        self._last_purge = now
        for key, entry in list(self._entries.items()):
            if now - entry.fetched_at >= self.stale_ttl:
                self.drop(key)
