"""Tests for EventThrottle — last-event-wins SSE throttling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.devices.websocket.throttle import (
    THROTTLE_INTERVALS,
    EventThrottle,
)


def _make_event(
    device_id: str = "AABBCCDDEE11",
    event_type: EventType = EventType.VOLUME,
) -> DeviceEvent:
    return DeviceEvent(device_id=device_id, event_type=event_type)


@pytest.fixture
def publish_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def throttle(publish_mock: AsyncMock) -> EventThrottle:
    return EventThrottle(publish=publish_mock)


class TestEventThrottle:
    """EventThrottle unit tests."""

    async def test_unthrottled_events_pass_through(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """Events without throttle config are published immediately."""
        event = _make_event(event_type=EventType.PRESETS)
        await throttle.submit(event)
        publish_mock.assert_awaited_once_with(event)

    async def test_first_throttled_event_passes_through(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """First event of a throttled type passes immediately."""
        event = _make_event(event_type=EventType.VOLUME)
        await throttle.submit(event)
        publish_mock.assert_awaited_once_with(event)

    async def test_rapid_events_throttled(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """Rapid successive events are throttled — only first and last arrive."""
        events = [_make_event(event_type=EventType.VOLUME) for _ in range(5)]

        # Submit all rapidly (no await between)
        for e in events:
            await throttle.submit(e)

        # Only the first event published immediately
        assert publish_mock.await_count == 1
        publish_mock.assert_awaited_with(events[0])

        # Wait for delayed publish to fire
        await asyncio.sleep(THROTTLE_INTERVALS[EventType.VOLUME] + 0.05)

        # Now the last event should also be published
        assert publish_mock.await_count == 2
        publish_mock.assert_awaited_with(events[-1])

    async def test_last_event_wins(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """Within cooldown, only the latest event is published."""
        e1 = _make_event(event_type=EventType.VOLUME)
        e2 = _make_event(event_type=EventType.VOLUME)
        e3 = _make_event(event_type=EventType.VOLUME)

        await throttle.submit(e1)  # passes through
        await throttle.submit(e2)  # pending
        await throttle.submit(e3)  # replaces e2

        await asyncio.sleep(THROTTLE_INTERVALS[EventType.VOLUME] + 0.05)

        assert publish_mock.await_count == 2
        # Second call should be e3, not e2
        publish_mock.assert_awaited_with(e3)

    async def test_different_devices_independent(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """Throttle tracks devices independently."""
        e_dev1 = _make_event(device_id="DEVICE_A", event_type=EventType.VOLUME)
        e_dev2 = _make_event(device_id="DEVICE_B", event_type=EventType.VOLUME)

        await throttle.submit(e_dev1)
        await throttle.submit(e_dev2)

        # Both should pass through immediately (first for each device)
        assert publish_mock.await_count == 2

    async def test_different_event_types_independent(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """Throttle tracks event types independently."""
        e_vol = _make_event(event_type=EventType.VOLUME)
        e_np = _make_event(event_type=EventType.NOW_PLAYING)

        await throttle.submit(e_vol)
        await throttle.submit(e_np)

        assert publish_mock.await_count == 2

    async def test_after_cooldown_passes_through(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """After cooldown expires, next event passes through immediately."""
        e1 = _make_event(event_type=EventType.VOLUME)
        e2 = _make_event(event_type=EventType.VOLUME)

        await throttle.submit(e1)
        await asyncio.sleep(THROTTLE_INTERVALS[EventType.VOLUME] + 0.05)

        await throttle.submit(e2)
        assert publish_mock.await_count == 2
        publish_mock.assert_awaited_with(e2)

    async def test_now_playing_throttle_interval(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """NowPlaying events use 500ms throttle."""
        e1 = _make_event(event_type=EventType.NOW_PLAYING)
        e2 = _make_event(event_type=EventType.NOW_PLAYING)

        await throttle.submit(e1)
        await throttle.submit(e2)

        # Only first published
        assert publish_mock.await_count == 1

        # Wait 500ms
        await asyncio.sleep(THROTTLE_INTERVALS[EventType.NOW_PLAYING] + 0.05)
        assert publish_mock.await_count == 2

    async def test_stop_cancels_pending(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """stop() cancels pending delayed tasks."""
        e1 = _make_event(event_type=EventType.VOLUME)
        e2 = _make_event(event_type=EventType.VOLUME)

        await throttle.submit(e1)
        await throttle.submit(e2)  # pending

        throttle.stop()
        await asyncio.sleep(THROTTLE_INTERVALS[EventType.VOLUME] + 0.05)

        # Only the first event should have been published
        assert publish_mock.await_count == 1

    async def test_zone_events_not_throttled(
        self, throttle: EventThrottle, publish_mock: AsyncMock
    ) -> None:
        """Zone events pass through without throttling."""
        events = [_make_event(event_type=EventType.ZONE) for _ in range(3)]
        for e in events:
            await throttle.submit(e)
        assert publish_mock.await_count == 3
