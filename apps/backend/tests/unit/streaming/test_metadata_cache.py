"""Tests for MetadataCache."""

from __future__ import annotations

from unittest.mock import patch

from opencloudtouch.streaming.icy_metadata import IcyMetadata
from opencloudtouch.streaming.metadata_cache import MISSING, MetadataCache


def _meta(artist: str = "Artist", track: str = "Track") -> IcyMetadata:
    return IcyMetadata(artist=artist, track=track, raw_title=f"{artist} - {track}")


class TestCacheBasics:
    """Basic get/put operations."""

    def test_miss_on_empty_cache(self):
        cache = MetadataCache()
        assert cache.get("http://stream.test") is MISSING

    def test_hit_after_put(self):
        cache = MetadataCache()
        meta = _meta()
        cache.put("http://stream.test", meta)
        assert cache.get("http://stream.test") is meta

    def test_different_urls_independent(self):
        cache = MetadataCache()
        meta1 = _meta("A1", "T1")
        meta2 = _meta("A2", "T2")
        cache.put("http://a.test", meta1)
        cache.put("http://b.test", meta2)
        assert cache.get("http://a.test") is meta1
        assert cache.get("http://b.test") is meta2

    def test_size(self):
        cache = MetadataCache()
        assert cache.size == 0
        cache.put("http://a.test", _meta())
        assert cache.size == 1
        cache.put("http://b.test", None)
        assert cache.size == 2


class TestNoMetadataHandling:
    """Streams where probe returns None."""

    def test_none_cached_within_ttl(self):
        """None result is cached within TTL (no re-probe)."""
        cache = MetadataCache(ttl=15.0)
        cache.put("http://no-icy.test", None)
        assert cache.get("http://no-icy.test") is None

    def test_none_expires_after_ttl(self):
        """None result expires after TTL — triggers re-probe."""
        cache = MetadataCache(ttl=15.0)
        cache.put("http://no-icy.test", None)

        with patch("opencloudtouch.streaming.metadata_cache.time") as mock_time:
            mock_time.monotonic.return_value = (
                cache._cache["http://no-icy.test"].timestamp + 16.0
            )
            assert cache.get("http://no-icy.test") is MISSING

    def test_none_stays_until_invalidated(self):
        cache = MetadataCache()
        cache.put("http://no-icy.test", None)
        assert cache.get("http://no-icy.test") is None
        cache.invalidate("http://no-icy.test")
        assert cache.get("http://no-icy.test") is MISSING


class TestStaleWhileRevalidate:
    """Stale data served when probe returns None after having data."""

    def test_stale_data_served_after_none_probe(self):
        """When probe returns None but we had data, stale data is served."""
        cache = MetadataCache(ttl=15.0, stale_ttl=60.0)
        good = _meta("Kygo", "Firestone")
        cache.put("http://stream.test", good)
        # Probe returns None (song transition)
        cache.put("http://stream.test", None)
        # Should return stale data, not None
        result = cache.get("http://stream.test")
        assert result is good

    def test_stale_data_expires_after_stale_ttl(self):
        """Stale data expires after stale_ttl — None returned."""
        cache = MetadataCache(ttl=15.0, stale_ttl=60.0)
        good = _meta("Kygo", "Firestone")

        # Simulate: good data put at t=0, None put at t=50, check at t=62
        with patch("opencloudtouch.streaming.metadata_cache.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0  # t=0
            cache.put("http://stream.test", good)

            mock_time.monotonic.return_value = 1050.0  # t=50: None probe
            cache.put("http://stream.test", None)

            mock_time.monotonic.return_value = (
                1062.0  # t=62: TTL fresh (12s), stale expired (62s)
            )
            assert cache.get("http://stream.test") is None

    def test_stale_data_still_valid_within_stale_ttl(self):
        """Stale data served when within stale_ttl window."""
        cache = MetadataCache(ttl=15.0, stale_ttl=60.0)
        good = _meta("Kygo", "Firestone")

        with patch("opencloudtouch.streaming.metadata_cache.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0
            cache.put("http://stream.test", good)

            mock_time.monotonic.return_value = 1010.0  # None probe 10s later
            cache.put("http://stream.test", None)

            mock_time.monotonic.return_value = (
                1020.0  # 10s after None (TTL ok), 20s stale (ok)
            )
            result = cache.get("http://stream.test")
            assert result is good

    def test_fresh_data_replaces_stale(self):
        """When new data arrives after stale period, it replaces stale."""
        cache = MetadataCache(ttl=15.0, stale_ttl=60.0)
        old = _meta("Kygo", "Firestone")
        cache.put("http://stream.test", old)
        cache.put("http://stream.test", None)  # song transition
        new = _meta("Nickelback", "Photograph")
        cache.put("http://stream.test", new)
        assert cache.get("http://stream.test") is new

    def test_no_stale_data_for_first_none(self):
        """First probe returning None has no stale data to fall back on."""
        cache = MetadataCache(ttl=15.0, stale_ttl=60.0)
        cache.put("http://stream.test", None)
        assert cache.get("http://stream.test") is None

    def test_none_expired_triggers_reprobe(self):
        """After None TTL expires, MISSING is returned to trigger re-probe."""
        cache = MetadataCache(ttl=15.0, stale_ttl=60.0)
        good = _meta("Kygo", "Firestone")

        with patch("opencloudtouch.streaming.metadata_cache.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0
            cache.put("http://stream.test", good)

            mock_time.monotonic.return_value = 1010.0
            cache.put("http://stream.test", None)

            # TTL expired (16s after None put) → should re-probe
            mock_time.monotonic.return_value = 1026.0
            assert cache.get("http://stream.test") is MISSING


class TestTTL:
    """TTL expiry for streams with metadata."""

    def test_entry_expires_after_ttl(self):
        cache = MetadataCache(ttl=15.0)
        cache.put("http://stream.test", _meta())

        # Simulate time passing beyond TTL
        with patch("opencloudtouch.streaming.metadata_cache.time") as mock_time:
            # First call is in put() — already happened
            # get() calls time.monotonic() to check expiry
            mock_time.monotonic.return_value = (
                cache._cache["http://stream.test"].timestamp + 16.0
            )
            assert cache.get("http://stream.test") is MISSING

    def test_entry_valid_within_ttl(self):
        cache = MetadataCache(ttl=15.0)
        meta = _meta()
        cache.put("http://stream.test", meta)

        with patch("opencloudtouch.streaming.metadata_cache.time") as mock_time:
            mock_time.monotonic.return_value = (
                cache._cache["http://stream.test"].timestamp + 10.0
            )
            assert cache.get("http://stream.test") is meta


class TestInvalidation:
    """Cache invalidation on preset change."""

    def test_invalidate_specific_url(self):
        cache = MetadataCache()
        cache.put("http://a.test", _meta())
        cache.put("http://b.test", _meta())
        cache.invalidate("http://a.test")
        assert cache.get("http://a.test") is MISSING
        assert cache.get("http://b.test") is not MISSING

    def test_invalidate_nonexistent_is_noop(self):
        cache = MetadataCache()
        cache.invalidate("http://doesnt-exist.test")  # no error

    def test_invalidate_all(self):
        cache = MetadataCache()
        cache.put("http://a.test", _meta())
        cache.put("http://b.test", None)
        cache.invalidate_all()
        assert cache.size == 0
        assert cache.get("http://a.test") is MISSING
        assert cache.get("http://b.test") is MISSING

    def test_invalidate_allows_reprobe_of_no_metadata_stream(self):
        """After invalidation, a no-metadata stream can be re-probed."""
        cache = MetadataCache()
        cache.put("http://stream.test", None)
        assert cache.get("http://stream.test") is None  # marked as no-metadata
        cache.invalidate("http://stream.test")
        assert cache.get("http://stream.test") is MISSING  # can probe again


class TestMissingSentinel:
    """MISSING sentinel behavior."""

    def test_is_falsy(self):
        assert not MISSING

    def test_is_singleton(self):
        from opencloudtouch.streaming.metadata_cache import _Missing

        assert _Missing() is MISSING

    def test_repr(self):
        assert repr(MISSING) == "MISSING"

    def test_none_is_not_missing(self):
        """None and MISSING are distinct — None means 'no metadata', MISSING means 'not cached'."""
        assert None is not MISSING
