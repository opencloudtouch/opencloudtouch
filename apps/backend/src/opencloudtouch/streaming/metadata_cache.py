"""In-memory metadata cache for ICY stream metadata.

Caches probe results per stream URL with a configurable TTL.
Uses a stale-while-revalidate pattern: when a probe returns None but
we have previous good data, the stale data is served for up to
`stale_ttl` seconds before giving up and returning None.

LRU eviction: when cache exceeds max_size, oldest entries are removed.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass

from opencloudtouch.streaming.icy_metadata import IcyMetadata

# Default cache TTL in seconds (how often to re-probe)
DEFAULT_TTL = 15.0

# How long stale data is served when probes return None (seconds)
DEFAULT_STALE_TTL = 60.0

# Maximum cache entries (prevent unbounded growth)
DEFAULT_MAX_SIZE = 50


@dataclass(slots=True)
class _CacheEntry:
    """Internal cache entry."""

    metadata: IcyMetadata | None
    timestamp: float
    last_good_metadata: IcyMetadata | None = None
    last_good_timestamp: float = 0.0


class MetadataCache:
    """In-memory cache for ICY metadata with stale-while-revalidate.

    - Probes are triggered every `ttl` seconds (cache expiry).
    - When a probe returns data: cached normally.
    - When a probe returns None but we had data before: stale data is
      served for up to `stale_ttl` seconds, then None is returned.
    - Invalidation: call `invalidate(url)` when the stream changes.
    - LRU eviction: when cache exceeds max_size, oldest entries are removed.
    """

    def __init__(
        self,
        ttl: float = DEFAULT_TTL,
        stale_ttl: float = DEFAULT_STALE_TTL,
        max_size: int = DEFAULT_MAX_SIZE,
    ) -> None:
        self._ttl = ttl
        self._stale_ttl = stale_ttl
        self._max_size = max_size
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()

    def get(self, url: str) -> IcyMetadata | None | _Missing:
        """Look up cached metadata for a stream URL.

        Returns:
            - IcyMetadata if cached and valid (or stale but within stale_ttl)
            - None if no data and no stale fallback available
            - MISSING sentinel if not cached or expired (should probe)
        """
        entry = self._cache.get(url)
        if entry is None:
            return MISSING

        # Move to end (mark as recently used)
        self._cache.move_to_end(url)

        age = time.monotonic() - entry.timestamp

        # Cache still fresh — return whatever we have
        if age <= self._ttl:
            if entry.metadata is not None:
                return entry.metadata
            # Probe returned None but we have stale data
            if entry.last_good_metadata is not None:
                stale_age = time.monotonic() - entry.last_good_timestamp
                if stale_age <= self._stale_ttl:
                    return entry.last_good_metadata
            return None

        # Cache expired — trigger re-probe
        return MISSING

    def put(self, url: str, metadata: IcyMetadata | None) -> None:
        """Store probe result in cache.

        When metadata is None but we had good data before, the last
        good result is preserved for stale-while-revalidate.
        Evicts oldest entries if cache exceeds max_size.
        """
        now = time.monotonic()
        existing = self._cache.get(url)

        if metadata is not None:
            # Fresh data — update everything
            self._cache[url] = _CacheEntry(
                metadata=metadata,
                timestamp=now,
                last_good_metadata=metadata,
                last_good_timestamp=now,
            )
        else:
            # Probe returned None — keep last good data for stale serving
            last_good = existing.last_good_metadata if existing else None
            last_good_ts = existing.last_good_timestamp if existing else 0.0
            self._cache[url] = _CacheEntry(
                metadata=None,
                timestamp=now,
                last_good_metadata=last_good,
                last_good_timestamp=last_good_ts,
            )

        # Move to end (mark as recently used)
        self._cache.move_to_end(url)

        # Evict oldest entries if over capacity
        while len(self._cache) > self._max_size:
            oldest_url = next(iter(self._cache))
            self._cache.pop(oldest_url)

    def invalidate(self, url: str) -> None:
        """Remove a specific URL from cache (e.g., on preset change)."""
        self._cache.pop(url, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Number of entries in cache."""
        return len(self._cache)


class _Missing:
    """Sentinel type indicating a cache miss."""

    _instance: _Missing | None = None

    def __new__(cls) -> _Missing:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()
