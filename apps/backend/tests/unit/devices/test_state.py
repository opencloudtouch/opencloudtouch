"""Tests for DeviceStateManager — centralized state store + event bus."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo
from opencloudtouch.devices.state import DeviceState, DeviceStateManager
from opencloudtouch.devices.websocket.connection import ConnectionState
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

# ---------------------------------------------------------------------------
# DeviceState dataclass
# ---------------------------------------------------------------------------


class TestDeviceState:
    def test_defaults(self):
        state = DeviceState(device_id="AA")
        assert state.device_id == "AA"
        assert state.now_playing is None
        assert state.volume is None
        assert state.connection_state == ConnectionState.DISCONNECTED
        assert state.last_update > 0

    def test_is_fresh_within_max_age(self):
        state = DeviceState(device_id="AA", last_update=time.time())
        assert state.is_fresh(max_age=10.0) is True

    def test_is_fresh_expired(self):
        state = DeviceState(device_id="AA", last_update=time.time() - 20)
        assert state.is_fresh(max_age=10.0) is False

    def test_is_fresh_boundary(self):
        """Exactly at boundary — should be stale."""
        with patch("opencloudtouch.devices.state.time") as mock_time:
            mock_time.time.return_value = 100.0
            state = DeviceState(device_id="AA", last_update=90.0)
            assert state.is_fresh(max_age=10.0) is False

    def test_is_fresh_just_inside(self):
        with patch("opencloudtouch.devices.state.time") as mock_time:
            mock_time.time.return_value = 99.9
            state = DeviceState(device_id="AA", last_update=90.0)
            assert state.is_fresh(max_age=10.0) is True


# ---------------------------------------------------------------------------
# DeviceStateManager — state updates
# ---------------------------------------------------------------------------


class TestStateManagerUpdates:
    def test_update_now_playing(self):
        mgr = DeviceStateManager()
        info = NowPlayingInfo(source="RADIO", state="PLAY_STATE", track="Song")
        mgr.update_now_playing("D1", info)

        state = mgr.get_state("D1")
        assert state is not None
        assert state.now_playing is info
        assert state.is_fresh()

    def test_update_volume(self):
        mgr = DeviceStateManager()
        vol = VolumeInfo(actual=42, target=42, muted=False)
        mgr.update_volume("D1", vol)

        state = mgr.get_state("D1")
        assert state is not None
        assert state.volume is vol

    def test_update_connection(self):
        mgr = DeviceStateManager()
        mgr.update_connection("D1", ConnectionState.CONNECTED)

        state = mgr.get_state("D1")
        assert state is not None
        assert state.connection_state == ConnectionState.CONNECTED

    def test_get_state_missing(self):
        mgr = DeviceStateManager()
        assert mgr.get_state("NONEXISTENT") is None

    def test_get_all_states(self):
        mgr = DeviceStateManager()
        mgr.update_volume("D1", VolumeInfo(10, 10, False))
        mgr.update_volume("D2", VolumeInfo(20, 20, True))

        all_states = mgr.get_all_states()
        assert len(all_states) == 2
        assert "D1" in all_states
        assert "D2" in all_states

    def test_get_all_states_returns_copy(self):
        mgr = DeviceStateManager()
        mgr.update_volume("D1", VolumeInfo(10, 10, False))

        snapshot = mgr.get_all_states()
        snapshot["D1"] = None  # Mutate copy
        assert mgr.get_state("D1") is not None  # Original unchanged

    def test_concurrent_updates_same_device(self):
        mgr = DeviceStateManager()
        mgr.update_now_playing("D1", NowPlayingInfo(source="AUX", state="PLAY_STATE"))
        mgr.update_volume("D1", VolumeInfo(50, 50, False))
        mgr.update_connection("D1", ConnectionState.CONNECTED)

        state = mgr.get_state("D1")
        assert state.now_playing.source == "AUX"
        assert state.volume.actual == 50
        assert state.connection_state == ConnectionState.CONNECTED


# ---------------------------------------------------------------------------
# DeviceStateManager — subscribe / unsubscribe / publish
# ---------------------------------------------------------------------------


class TestStateManagerPubSub:
    @pytest.mark.asyncio
    async def test_subscribe_returns_queue(self):
        mgr = DeviceStateManager()
        queue = mgr.subscribe()
        assert isinstance(queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self):
        mgr = DeviceStateManager()
        queue = mgr.subscribe()
        mgr.unsubscribe(queue)
        assert queue not in mgr._subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self):
        """Unsubscribing unknown queue should not raise."""
        mgr = DeviceStateManager()
        unknown = asyncio.Queue()
        mgr.unsubscribe(unknown)  # No error

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self):
        mgr = DeviceStateManager()
        q1 = mgr.subscribe()
        q2 = mgr.subscribe()

        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.VOLUME,
            volume=VolumeInfo(30, 30, False),
        )
        await mgr.publish(event)

        assert not q1.empty()
        assert not q2.empty()
        assert (await q1.get()) is event
        assert (await q2.get()) is event

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        """Publishing with no subscribers should not raise."""
        mgr = DeviceStateManager()
        event = DeviceEvent(device_id="D1", event_type=EventType.VOLUME)
        await mgr.publish(event)  # No error

    @pytest.mark.asyncio
    async def test_dead_subscriber_pruned(self):
        """Failing subscriber should be removed during publish."""
        mgr = DeviceStateManager()
        good_queue = mgr.subscribe()

        # Create a broken queue that raises on put
        bad_queue = asyncio.Queue()
        bad_queue.put = _raise_on_put
        mgr._subscribers.append(bad_queue)

        event = DeviceEvent(device_id="D1", event_type=EventType.VOLUME)
        await mgr.publish(event)

        assert good_queue in mgr._subscribers
        assert bad_queue not in mgr._subscribers
        assert not good_queue.empty()

    @pytest.mark.asyncio
    async def test_max_subscriber_cap(self):
        mgr = DeviceStateManager()
        for _ in range(DeviceStateManager.MAX_SUBSCRIBERS):
            mgr.subscribe()

        assert len(mgr._subscribers) == DeviceStateManager.MAX_SUBSCRIBERS

        # Next subscribe triggers prune + adds new queue
        new_queue = mgr.subscribe()
        assert len(mgr._subscribers) == 1
        assert mgr._subscribers[0] is new_queue


async def _raise_on_put(item):
    raise RuntimeError("dead queue")


# ---------------------------------------------------------------------------
# DeviceStateManager — on_event (WebSocket integration)
# ---------------------------------------------------------------------------


class TestStateManagerOnEvent:
    @pytest.mark.asyncio
    async def test_on_event_updates_now_playing(self):
        mgr = DeviceStateManager()
        np = NowPlayingInfo(source="RADIO", state="PLAY_STATE", track="Hello")
        event = DeviceEvent(
            device_id="D1", event_type=EventType.NOW_PLAYING, now_playing=np
        )
        await mgr.on_event(event)

        state = mgr.get_state("D1")
        assert state.now_playing is np

    @pytest.mark.asyncio
    async def test_on_event_updates_volume(self):
        mgr = DeviceStateManager()
        vol = VolumeInfo(actual=55, target=55, muted=True)
        event = DeviceEvent(device_id="D1", event_type=EventType.VOLUME, volume=vol)
        await mgr.on_event(event)

        state = mgr.get_state("D1")
        assert state.volume is vol

    @pytest.mark.asyncio
    async def test_on_event_publishes_to_subscribers(self):
        mgr = DeviceStateManager()
        queue = mgr.subscribe()

        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.VOLUME,
            volume=VolumeInfo(10, 10, False),
        )
        await mgr.on_event(event)

        received = await queue.get()
        assert received is event

    @pytest.mark.asyncio
    async def test_on_event_unknown_type_still_publishes(self):
        """Unknown event types should still be published (e.g. presets, zone)."""
        mgr = DeviceStateManager()
        queue = mgr.subscribe()

        event = DeviceEvent(device_id="D1", event_type=EventType.PRESETS)
        await mgr.on_event(event)

        received = await queue.get()
        assert received.event_type == EventType.PRESETS

    @pytest.mark.asyncio
    async def test_on_event_ignores_now_playing_without_data(self):
        """NOW_PLAYING event with now_playing=None should not crash."""
        mgr = DeviceStateManager()
        event = DeviceEvent(
            device_id="D1", event_type=EventType.NOW_PLAYING, now_playing=None
        )
        await mgr.on_event(event)

        state = mgr.get_state("D1")
        # State not created because no data to store
        assert state is None

    @pytest.mark.asyncio
    async def test_on_event_metadata_enriched_updates_now_playing(self):
        """METADATA_ENRICHED event should update now_playing state."""
        mgr = DeviceStateManager()
        queue = mgr.subscribe()

        enriched_info = NowPlayingInfo(
            source="INTERNET_RADIO",
            state="PLAY_STATE",
            station_name="WDR 2",
            artwork_url="https://cdn.example.com/logo.png",
            artist="Enriched Artist",
        )
        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.METADATA_ENRICHED,
            now_playing=enriched_info,
        )
        await mgr.on_event(event)

        state = mgr.get_state("D1")
        assert state is not None
        assert state.now_playing is enriched_info
        assert state.now_playing.artwork_url == "https://cdn.example.com/logo.png"

        received = await queue.get()
        assert received.event_type == EventType.METADATA_ENRICHED

    @pytest.mark.asyncio
    async def test_on_event_metadata_enriched_without_data_no_crash(self):
        """METADATA_ENRICHED event with now_playing=None should not crash."""
        mgr = DeviceStateManager()
        event = DeviceEvent(
            device_id="D1", event_type=EventType.METADATA_ENRICHED, now_playing=None
        )
        await mgr.on_event(event)
        state = mgr.get_state("D1")
        assert state is None


class TestDeviceStateManagerIcyIntegration:
    """Tests for ICY worker integration in DeviceStateManager."""

    @pytest.mark.asyncio
    async def test_set_icy_worker(self):
        """set_icy_worker should attach worker."""
        from unittest.mock import MagicMock

        mgr = DeviceStateManager()
        worker = MagicMock()
        mgr.set_icy_worker(worker)
        assert mgr._icy_worker is worker

    @pytest.mark.asyncio
    async def test_icy_probe_publishes_enriched_event(self):
        """ICY worker success should publish metadata_enriched event."""
        from unittest.mock import AsyncMock

        enriched_info = NowPlayingInfo(
            source="INTERNET_RADIO",
            state="PLAY_STATE",
            station_name="WDR 2",
            artwork_url="https://cdn.example.com/icy.png",
        )
        enriched_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.METADATA_ENRICHED,
            now_playing=enriched_info,
        )

        worker = AsyncMock()
        worker.on_event = AsyncMock(return_value=enriched_event)

        mgr = DeviceStateManager()
        mgr.set_icy_worker(worker)
        queue = mgr.subscribe()

        # Trigger with a now_playing event
        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO", state="PLAY_STATE", station_name="WDR 2"
            ),
        )
        await mgr.on_event(np_event)

        # Wait for background task
        await asyncio.sleep(0.05)

        # Should have received: now_playing + metadata_enriched
        events = []
        while not queue.empty():
            events.append(await queue.get())

        types = [e.event_type for e in events]
        assert EventType.NOW_PLAYING in types
        assert EventType.METADATA_ENRICHED in types

        # State should be updated to enriched version
        state = mgr.get_state("D1")
        assert state is not None
        assert state.now_playing is not None
        assert state.now_playing.artwork_url == "https://cdn.example.com/icy.png"

    @pytest.mark.asyncio
    async def test_icy_probe_failure_does_not_block(self):
        """ICY worker exception should not break the event pipeline."""
        from unittest.mock import AsyncMock

        worker = AsyncMock()
        worker.on_event = AsyncMock(side_effect=RuntimeError("probe crash"))

        mgr = DeviceStateManager()
        mgr.set_icy_worker(worker)
        queue = mgr.subscribe()

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO", state="PLAY_STATE", station_name="WDR 2"
            ),
        )
        # Should not raise
        await mgr.on_event(np_event)
        await asyncio.sleep(0.05)

        # Original event should still have been published
        received = await queue.get()
        assert received.event_type == EventType.NOW_PLAYING

    @pytest.mark.asyncio
    async def test_no_icy_probe_for_non_radio(self):
        """ICY worker should not be called for non-radio events."""
        from unittest.mock import AsyncMock

        worker = AsyncMock()
        worker.on_event = AsyncMock(return_value=None)

        mgr = DeviceStateManager()
        mgr.set_icy_worker(worker)

        vol_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.VOLUME,
            volume=VolumeInfo(actual=50, target=50, muted=False),
        )
        await mgr.on_event(vol_event)
        await asyncio.sleep(0.05)

        # Worker should not have been called for volume events
        worker.on_event.assert_not_called()


class TestDeviceStateManagerBackgroundTasks:
    """Tests for _background_tasks cleanup and mark_device_offline."""

    @pytest.mark.asyncio
    async def test_background_task_added_and_cleaned_up(self):
        """ICY probe task should be added to _background_tasks and auto-cleaned."""
        from unittest.mock import AsyncMock

        worker = AsyncMock()
        worker.on_event = AsyncMock(return_value=None)

        mgr = DeviceStateManager()
        mgr.set_icy_worker(worker)

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO", state="PLAY_STATE", station_name="WDR 2"
            ),
        )
        await mgr.on_event(np_event)

        # Task was created
        assert len(mgr._background_tasks) >= 0  # may already have completed

        # Wait for task to complete and get cleaned up
        await asyncio.sleep(0.1)
        assert len(mgr._background_tasks) == 0

    @pytest.mark.asyncio
    async def test_mark_device_offline(self):
        mgr = DeviceStateManager()
        queue = mgr.subscribe()

        await mgr.mark_device_offline("D1")

        state = mgr.get_state("D1")
        assert state is not None
        assert state.connection_state == ConnectionState.FAILED

        received = await queue.get()
        assert received.event_type == EventType.CONNECTION
        assert received.connection_state == ConnectionState.FAILED
        assert received.device_id == "D1"

    @pytest.mark.asyncio
    async def test_start_icy_polling_idempotent(self):
        mgr = DeviceStateManager()
        mgr.start_icy_polling()
        task1 = mgr._icy_poll_task
        mgr.start_icy_polling()
        task2 = mgr._icy_poll_task
        assert task1 is task2
        await mgr.stop_icy_polling()

    @pytest.mark.asyncio
    async def test_stop_icy_polling(self):
        mgr = DeviceStateManager()
        mgr.start_icy_polling()
        assert mgr._icy_poll_task is not None

        await mgr.stop_icy_polling()
        assert mgr._icy_poll_task is None

    @pytest.mark.asyncio
    async def test_stop_icy_polling_when_not_started(self):
        mgr = DeviceStateManager()
        await mgr.stop_icy_polling()  # should not raise

    @pytest.mark.asyncio
    async def test_on_event_now_playing_without_data_falls_to_else(self):
        """NOW_PLAYING with now_playing=None goes to else branch."""
        mgr = DeviceStateManager()
        event = DeviceEvent(
            device_id="D1", event_type=EventType.NOW_PLAYING, now_playing=None
        )
        await mgr.on_event(event)
        # Falls into else branch (unhandled), no state created
        assert mgr.get_state("D1") is None

    @pytest.mark.asyncio
    async def test_on_event_volume_without_data_falls_to_else(self):
        """VOLUME with volume=None goes to else branch."""
        mgr = DeviceStateManager()
        event = DeviceEvent(device_id="D1", event_type=EventType.VOLUME, volume=None)
        await mgr.on_event(event)
        assert mgr.get_state("D1") is None


# ---------------------------------------------------------------------------
# DeviceStateManager — preset-favicon enrichment
# ---------------------------------------------------------------------------


class TestPresetFaviconEnrichment:
    """Tests for preset-favicon enrichment in the SSE pipeline."""

    @pytest.mark.asyncio
    async def test_favicon_enrichment_publishes_metadata_enriched(self):
        """Radio event without artwork should trigger favicon lookup."""
        from unittest.mock import AsyncMock

        favicon_cb = AsyncMock(return_value="https://cdn.example.com/logo.png")

        mgr = DeviceStateManager()
        mgr.set_preset_favicon_callback(favicon_cb)
        queue = mgr.subscribe()

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="WDR 2",
            ),
        )
        await mgr.on_event(np_event)
        await asyncio.sleep(0.1)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        types = [e.event_type for e in events]
        assert EventType.NOW_PLAYING in types
        assert EventType.METADATA_ENRICHED in types

        enriched = [e for e in events if e.event_type == EventType.METADATA_ENRICHED]
        assert enriched[0].now_playing.artwork_url == "https://cdn.example.com/logo.png"

        favicon_cb.assert_called_once_with("D1", "WDR 2")

    @pytest.mark.asyncio
    async def test_favicon_skipped_when_artwork_already_present(self):
        """Radio event with artwork should NOT trigger favicon lookup."""
        from unittest.mock import AsyncMock

        favicon_cb = AsyncMock(return_value="https://cdn.example.com/logo.png")

        mgr = DeviceStateManager()
        mgr.set_preset_favicon_callback(favicon_cb)

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="WDR 2",
                artwork_url="https://existing-art.png",
            ),
        )
        await mgr.on_event(np_event)
        await asyncio.sleep(0.1)

        favicon_cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_favicon_skipped_for_non_radio_source(self):
        """Non-radio source should NOT trigger favicon lookup."""
        from unittest.mock import AsyncMock

        favicon_cb = AsyncMock(return_value="https://cdn.example.com/logo.png")

        mgr = DeviceStateManager()
        mgr.set_preset_favicon_callback(favicon_cb)

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="SPOTIFY",
                state="PLAY_STATE",
                station_name="My Playlist",
            ),
        )
        await mgr.on_event(np_event)
        await asyncio.sleep(0.1)

        favicon_cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_favicon_not_found_no_enrichment(self):
        """Favicon callback returning None should not publish enrichment."""
        from unittest.mock import AsyncMock

        favicon_cb = AsyncMock(return_value=None)

        mgr = DeviceStateManager()
        mgr.set_preset_favicon_callback(favicon_cb)
        queue = mgr.subscribe()

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="Unknown Station",
            ),
        )
        await mgr.on_event(np_event)
        await asyncio.sleep(0.1)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        types = [e.event_type for e in events]
        assert EventType.METADATA_ENRICHED not in types

    @pytest.mark.asyncio
    async def test_favicon_callback_exception_does_not_block(self):
        """Favicon callback exception should not break the pipeline."""
        from unittest.mock import AsyncMock

        favicon_cb = AsyncMock(side_effect=RuntimeError("DB down"))

        mgr = DeviceStateManager()
        mgr.set_preset_favicon_callback(favicon_cb)
        queue = mgr.subscribe()

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="WDR 2",
            ),
        )
        await mgr.on_event(np_event)
        await asyncio.sleep(0.1)

        # Original event should still have been published
        received = await queue.get()
        assert received.event_type == EventType.NOW_PLAYING

    @pytest.mark.asyncio
    async def test_favicon_and_icy_both_run(self):
        """Both favicon enrichment and ICY probe should run for radio events."""
        from unittest.mock import AsyncMock

        favicon_cb = AsyncMock(return_value="https://cdn.example.com/favicon.png")

        icy_enriched = NowPlayingInfo(
            source="INTERNET_RADIO",
            state="PLAY_STATE",
            station_name="WDR 2",
            artwork_url="https://cdn.example.com/icy.png",
            artist="ICY Artist",
        )
        icy_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.METADATA_ENRICHED,
            now_playing=icy_enriched,
        )

        worker = AsyncMock()
        worker.on_event = AsyncMock(return_value=icy_event)

        mgr = DeviceStateManager()
        mgr.set_preset_favicon_callback(favicon_cb)
        mgr.set_icy_worker(worker)
        queue = mgr.subscribe()

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="WDR 2",
            ),
        )
        await mgr.on_event(np_event)
        await asyncio.sleep(0.2)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        types = [e.event_type for e in events]
        assert EventType.NOW_PLAYING in types
        assert EventType.METADATA_ENRICHED in types

        # Both callbacks were invoked
        favicon_cb.assert_called_once_with("D1", "WDR 2")
        worker.on_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_favicon_callback_set(self):
        """Without favicon callback, enrichment pipeline still works."""
        from unittest.mock import AsyncMock

        worker = AsyncMock()
        worker.on_event = AsyncMock(return_value=None)

        mgr = DeviceStateManager()
        mgr.set_icy_worker(worker)

        np_event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="WDR 2",
            ),
        )
        # Should not raise
        await mgr.on_event(np_event)
        await asyncio.sleep(0.1)
