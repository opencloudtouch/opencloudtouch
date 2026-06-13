"""Unit tests for memory leak fixes (#366)."""

import time

import pytest

from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.icy_worker import IcyWorker
from opencloudtouch.streaming.metadata_cache import MISSING, MetadataCache


class TestMetadataCacheLRUEviction:
    """Test LRU eviction in MetadataCache."""

    def test_cache_evicts_oldest_when_full(self):
        """Cache should evict oldest entries when max_size is exceeded."""
        cache = MetadataCache(max_size=3)

        # Fill cache
        for i in range(3):
            cache.put(f"url_{i}", None)

        assert cache.size == 3

        # Add one more — should evict url_0 (oldest)
        cache.put("url_3", None)
        assert cache.size == 3
        assert cache.get("url_0") is MISSING  # Evicted
        assert cache.get("url_1") is not MISSING  # Still there

    def test_cache_get_moves_to_end(self):
        """Cache.get() should mark entry as recently used (LRU)."""
        cache = MetadataCache(max_size=3)

        cache.put("url_0", None)
        cache.put("url_1", None)
        cache.put("url_2", None)

        # Access url_0 to mark it as recently used
        cache.get("url_0")

        # Add url_3 — should evict url_1 (oldest), not url_0
        cache.put("url_3", None)

        assert cache.get("url_0") is not MISSING  # Still there (LRU)
        assert cache.get("url_1") is MISSING  # Evicted


class TestIcyWorkerLRUEviction:
    """Test LRU eviction in IcyWorker probe history."""

    @pytest.mark.asyncio
    async def test_last_probe_evicts_when_full(self):
        """_last_probe should evict oldest entry when max size exceeded."""

        async def mock_get_stream_url(device_id: str, station: str) -> str | None:
            return None

        worker = IcyWorker(mock_get_stream_url)

        # Manually fill _last_probe beyond limit
        from opencloudtouch.devices.websocket.icy_worker import _MAX_PROBE_HISTORY

        for i in range(_MAX_PROBE_HISTORY + 1):
            worker._last_probe[f"station_{i}"] = time.monotonic()
            worker._last_probe.move_to_end(f"station_{i}")
            worker._evict_if_needed(worker._last_probe)

        # Should be capped at max size
        assert len(worker._last_probe) == _MAX_PROBE_HISTORY
        # Oldest entry should be evicted
        assert "station_0" not in worker._last_probe

    @pytest.mark.asyncio
    async def test_last_metadata_evicts_when_full(self):
        """_last_metadata should evict oldest entry when max size exceeded."""

        async def mock_get_stream_url(device_id: str, station: str) -> str | None:
            return None

        worker = IcyWorker(mock_get_stream_url)

        # Manually fill _last_metadata beyond limit
        from opencloudtouch.devices.websocket.icy_worker import _MAX_PROBE_HISTORY

        for i in range(_MAX_PROBE_HISTORY + 1):
            device_id = f"device_{i}"
            worker._last_metadata[device_id] = ("Artist", "Track")
            worker._last_metadata.move_to_end(device_id)
            worker._evict_if_needed(worker._last_metadata)

        # Should be capped at max size
        assert len(worker._last_metadata) == _MAX_PROBE_HISTORY
        # Oldest entry should be evicted
        assert "device_0" not in worker._last_metadata


class TestDeviceStateManagerCleanup:
    """Test stale state cleanup in DeviceStateManager."""

    def test_cleanup_removes_stale_states(self):
        """cleanup_stale_states should remove old entries."""
        manager = DeviceStateManager()

        # Add some states
        manager.update_now_playing("device_1", None)
        manager.update_now_playing("device_2", None)

        # Make device_1 look old
        state1 = manager.get_state("device_1")
        state1.last_update = time.time() - 90000  # 25 hours ago

        # Run cleanup (24h threshold)
        removed = manager.cleanup_stale_states(max_age_seconds=86400.0)

        assert removed == 1
        assert manager.get_state("device_1") is None  # Removed
        assert manager.get_state("device_2") is not None  # Still there

    def test_cleanup_does_nothing_if_all_fresh(self):
        """cleanup_stale_states should not remove fresh states."""
        manager = DeviceStateManager()

        manager.update_now_playing("device_1", None)
        manager.update_now_playing("device_2", None)

        removed = manager.cleanup_stale_states(max_age_seconds=86400.0)

        assert removed == 0
        assert manager.get_state("device_1") is not None
        assert manager.get_state("device_2") is not None
