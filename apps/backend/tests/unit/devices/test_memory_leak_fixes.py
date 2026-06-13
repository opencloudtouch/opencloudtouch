"""Unit tests for memory leak fixes (#366)."""

import asyncio
import time

import pytest

from opencloudtouch.devices.health_check import DeviceHealthCheck
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.icy_worker import IcyWorker
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.devices.websocket.throttle import EventThrottle
from opencloudtouch.streaming.metadata_cache import MISSING, MetadataCache
from opencloudtouch.streaming.icy_metadata import IcyMetadata


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


class TestSSEQueueBackpressure:
    """Test SSE subscriber queue backpressure (#366)."""

    def test_subscribe_creates_bounded_queue(self):
        """subscribe() should create a queue with maxsize=200."""
        manager = DeviceStateManager()
        queue = manager.subscribe()
        assert queue.maxsize == 200

    @pytest.mark.asyncio
    async def test_publish_drops_event_on_full_queue(self):
        """publish() should drop events when a subscriber queue is full."""
        manager = DeviceStateManager()
        queue = manager.subscribe()

        # Fill queue to capacity
        event = DeviceEvent(device_id="test", event_type=EventType.VOLUME)
        for _ in range(200):
            queue.put_nowait(event)

        assert queue.full()

        # Publishing should not block; event is dropped
        await manager.publish(event)

        # Queue size unchanged — event was dropped, not added
        assert queue.qsize() == 200


class TestMetadataCacheExpiredEviction:
    """Test eviction of fully expired entries in MetadataCache.get() (#366)."""

    def test_expired_entry_without_stale_data_is_deleted(self):
        """get() should delete entry expired past TTL with no stale data."""
        cache = MetadataCache(ttl=0.01, stale_ttl=0.01)
        cache.put("http://stream.example.com", None)

        # Wait for both TTL and stale_ttl to expire
        time.sleep(0.02)

        result = cache.get("http://stream.example.com")
        assert result is MISSING
        # Entry should be evicted from internal cache
        assert "http://stream.example.com" not in cache._cache

    def test_expired_entry_with_expired_stale_data_is_deleted(self):
        """get() should delete entry when both TTL and stale_ttl expired."""
        cache = MetadataCache(ttl=0.01, stale_ttl=0.02)
        metadata = IcyMetadata(artist="Artist", track="Track", raw_title="Artist - Track")
        cache.put("http://stream.example.com", metadata)

        # Wait for both TTL and stale_ttl to expire
        time.sleep(0.03)

        result = cache.get("http://stream.example.com")
        assert result is MISSING
        assert "http://stream.example.com" not in cache._cache

    def test_expired_entry_with_valid_stale_data_is_kept(self):
        """get() should keep entry when TTL expired but stale data still valid."""
        cache = MetadataCache(ttl=0.01, stale_ttl=10.0)
        metadata = IcyMetadata(artist="Artist", track="Track", raw_title="Artist - Track")
        cache.put("http://stream.example.com", metadata)

        # Wait for TTL but not stale_ttl
        time.sleep(0.02)

        result = cache.get("http://stream.example.com")
        assert result is MISSING
        # Entry should still be in cache (stale data still valid)
        assert "http://stream.example.com" in cache._cache


class TestEventThrottleTaskCleanup:
    """Test EventThrottle task cleanup after delayed publish (#366)."""

    @pytest.mark.asyncio
    async def test_tasks_dict_empty_after_delayed_publish(self):
        """_tasks should be empty after delayed publish completes."""
        published: list[DeviceEvent] = []

        async def mock_publish(event: DeviceEvent) -> None:
            published.append(event)

        throttle = EventThrottle(publish=mock_publish)

        # First publish goes through immediately (sets last_publish)
        event1 = DeviceEvent(device_id="dev1", event_type=EventType.VOLUME)
        await throttle.submit(event1)
        assert len(published) == 1

        # Second publish within cooldown triggers delayed task
        event2 = DeviceEvent(device_id="dev1", event_type=EventType.VOLUME)
        await throttle.submit(event2)

        key = ("dev1", EventType.VOLUME)
        assert key in throttle._tasks

        # Wait for delayed task to complete
        await asyncio.sleep(0.2)

        # Task reference should be cleaned up
        assert key not in throttle._tasks
        assert len(published) == 2


class TestCleanupFailCounters:
    """Test _cleanup_fail_counters() in DeviceHealthCheck (#366)."""

    def test_removes_stale_device_ids(self):
        """Devices no longer in DB should have their fail counters removed."""
        health_check = DeviceHealthCheck(device_repo=None)
        health_check._ssh_fail_count = {"A": 1, "B": 3, "C": 2}

        health_check._cleanup_fail_counters(valid_device_ids={"A", "C"})

        assert "B" not in health_check._ssh_fail_count
        assert health_check._ssh_fail_count == {"A": 1, "C": 2}

    def test_idempotent_on_empty_set(self):
        """Cleanup with empty fail counters and empty valid_ids should not error."""
        health_check = DeviceHealthCheck(device_repo=None)
        health_check._ssh_fail_count = {}

        health_check._cleanup_fail_counters(valid_device_ids=set())

        assert health_check._ssh_fail_count == {}

    def test_keeps_all_when_all_valid(self):
        """All counters should remain when all device IDs are valid."""
        health_check = DeviceHealthCheck(device_repo=None)
        health_check._ssh_fail_count = {"A": 1, "B": 2}

        health_check._cleanup_fail_counters(valid_device_ids={"A", "B"})

        assert health_check._ssh_fail_count == {"A": 1, "B": 2}

    def test_removes_all_when_no_valid_ids(self):
        """All counters should be removed when valid_ids is empty."""
        health_check = DeviceHealthCheck(device_repo=None)
        health_check._ssh_fail_count = {"A": 1, "B": 2, "C": 3}

        health_check._cleanup_fail_counters(valid_device_ids=set())

        assert health_check._ssh_fail_count == {}
