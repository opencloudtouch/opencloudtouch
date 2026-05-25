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
