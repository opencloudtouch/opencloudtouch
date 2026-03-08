"""
Tests for devices/events.py — DiscoveryEvent, DiscoveryEventBus, event_generator, factories.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from opencloudtouch.db import Device
from opencloudtouch.devices.events import (
    DiscoveryEvent,
    DiscoveryEventBus,
    DiscoveryEventType,
    device_failed_event,
    device_found_event,
    device_synced_event,
    event_generator,
    get_event_bus,
)
from opencloudtouch.discovery import DiscoveredDevice

# ── DiscoveryEvent ────────────────────────────────────────────────────────────


class TestDiscoveryEvent:
    def test_to_sse_format(self):
        """to_sse() produces correct SSE string."""
        event = DiscoveryEvent(
            type=DiscoveryEventType.STARTED,
            data={"timeout": 10},
        )
        sse = event.to_sse()
        assert sse.startswith("event: started\n")
        assert '"timeout": 10' in sse
        assert sse.endswith("\n\n")

    def test_to_sse_device_found(self):
        """to_sse() works for device_found type."""
        event = DiscoveryEvent(
            type=DiscoveryEventType.DEVICE_FOUND,
            data={"ip": "192.168.1.100", "name": "Speaker"},
        )
        sse = event.to_sse()
        assert "event: device_found" in sse
        assert "192.168.1.100" in sse

    def test_to_sse_completed(self):
        event = DiscoveryEvent(type=DiscoveryEventType.COMPLETED, data={"total": 2})
        sse = event.to_sse()
        assert "event: completed" in sse

    def test_to_sse_error(self):
        event = DiscoveryEvent(type=DiscoveryEventType.ERROR, data={"message": "fail"})
        sse = event.to_sse()
        assert "event: error" in sse
        assert "fail" in sse


# ── DiscoveryEventBus ────────────────────────────────────────────────────────


class TestDiscoveryEventBus:
    def test_subscribe_returns_queue(self):
        """subscribe() returns a new asyncio.Queue."""
        bus = DiscoveryEventBus()
        q = bus.subscribe()
        assert isinstance(q, asyncio.Queue)
        assert len(bus._subscribers) == 1

    def test_subscribe_multiple_clients(self):
        bus = DiscoveryEventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        assert q1 is not q2
        assert len(bus._subscribers) == 2

    def test_unsubscribe_removes_queue(self):
        bus = DiscoveryEventBus()
        q = bus.subscribe()
        bus.unsubscribe(q)
        assert len(bus._subscribers) == 0

    def test_unsubscribe_unknown_queue_is_noop(self):
        """Unsubscribing an unknown queue does nothing."""
        bus = DiscoveryEventBus()
        bus.subscribe()
        unknown_queue = asyncio.Queue()
        bus.unsubscribe(unknown_queue)
        assert len(bus._subscribers) == 1

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        """publish() with no subscribers does not raise."""
        bus = DiscoveryEventBus()
        event = DiscoveryEvent(type=DiscoveryEventType.STARTED, data={})
        await bus.publish(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_publish_puts_in_queue(self):
        """publish() puts the event into each subscriber queue."""
        bus = DiscoveryEventBus()
        q = bus.subscribe()

        event = DiscoveryEvent(
            type=DiscoveryEventType.DEVICE_FOUND,
            data={"ip": "192.168.1.10"},
        )
        await bus.publish(event)

        received = await asyncio.wait_for(q.get(), timeout=1.0)
        assert received is event

    @pytest.mark.asyncio
    async def test_publish_broadcasts_to_all_subscribers(self):
        """publish() sends event to every subscriber."""
        bus = DiscoveryEventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()

        event = DiscoveryEvent(type=DiscoveryEventType.COMPLETED, data={"total": 3})
        await bus.publish(event)

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r1 is event
        assert r2 is event

    @pytest.mark.asyncio
    async def test_publish_removes_dead_subscriber_on_put_error(self, monkeypatch):
        """publish() removes a subscriber whose queue.put raises."""
        bus = DiscoveryEventBus()
        bad_queue = asyncio.Queue()

        async def failing_put(item):
            raise RuntimeError("queue is full")

        monkeypatch.setattr(bad_queue, "put", failing_put)
        bus._subscribers.append(bad_queue)

        event = DiscoveryEvent(type=DiscoveryEventType.STARTED, data={})
        await bus.publish(event)
        # Dead subscriber should be removed
        assert bad_queue not in bus._subscribers


# ── get_event_bus (singleton) ─────────────────────────────────────────────────


class TestGetEventBus:
    def test_returns_event_bus_instance(self, monkeypatch):
        """get_event_bus() creates and returns a singleton."""
        import opencloudtouch.devices.events as events_module

        monkeypatch.setattr(events_module, "_event_bus", None)
        bus = get_event_bus()
        assert isinstance(bus, DiscoveryEventBus)

    def test_returns_same_instance_on_repeated_calls(self, monkeypatch):
        """get_event_bus() returns the same instance."""
        import opencloudtouch.devices.events as events_module

        monkeypatch.setattr(events_module, "_event_bus", None)
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2


# ── event_generator ───────────────────────────────────────────────────────────


class TestEventGenerator:
    @pytest.mark.asyncio
    async def test_yields_sse_from_queue(self):
        """event_generator() yields SSE-formatted strings from the queue."""
        q: asyncio.Queue = asyncio.Queue()
        event1 = DiscoveryEvent(
            type=DiscoveryEventType.DEVICE_FOUND, data={"ip": "1.2.3.4"}
        )
        event2 = DiscoveryEvent(type=DiscoveryEventType.COMPLETED, data={"total": 1})
        await q.put(event1)
        await q.put(event2)

        results = []
        async for chunk in event_generator(q):
            results.append(chunk)

        assert len(results) == 2
        assert "device_found" in results[0]
        assert "completed" in results[1]

    @pytest.mark.asyncio
    async def test_stops_after_completed_event(self):
        """event_generator() stops iteration after COMPLETED event."""
        q: asyncio.Queue = asyncio.Queue()
        await q.put(DiscoveryEvent(type=DiscoveryEventType.STARTED, data={}))
        await q.put(
            DiscoveryEvent(type=DiscoveryEventType.COMPLETED, data={"total": 0})
        )
        await q.put(
            DiscoveryEvent(type=DiscoveryEventType.DEVICE_FOUND, data={})
        )  # Should NOT be yielded

        results = []
        async for chunk in event_generator(q):
            results.append(chunk)

        assert len(results) == 2  # STARTED + COMPLETED, not the third

    @pytest.mark.asyncio
    async def test_stops_after_error_event(self):
        """event_generator() stops iteration after ERROR event."""
        q: asyncio.Queue = asyncio.Queue()
        await q.put(
            DiscoveryEvent(type=DiscoveryEventType.ERROR, data={"message": "nope"})
        )
        await q.put(DiscoveryEvent(type=DiscoveryEventType.DEVICE_FOUND, data={}))

        results = []
        async for chunk in event_generator(q):
            results.append(chunk)

        assert len(results) == 1
        assert "error" in results[0]

    @pytest.mark.asyncio
    async def test_handles_cancelled_error(self):
        """event_generator() re-raises CancelledError."""
        q: asyncio.Queue = asyncio.Queue()

        original_get = q.get

        call_count = 0

        async def get_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.CancelledError()
            return await original_get()

        q.get = get_side_effect  # type: ignore[method-assign]

        with pytest.raises(asyncio.CancelledError):
            async for _ in event_generator(q):
                pass

    @pytest.mark.asyncio
    async def test_handles_generic_exception(self):
        """event_generator() yields error event on generic exception."""
        q: asyncio.Queue = asyncio.Queue()

        original_get = q.get
        call_count = 0

        async def get_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("unexpected failure")
            return await original_get()

        q.get = get_side_effect  # type: ignore[method-assign]

        results = []
        async for chunk in event_generator(q):
            results.append(chunk)

        assert len(results) == 1
        assert "error" in results[0]
        assert "unexpected failure" in results[0]


# ── Factory functions ────────────────────────────────────────────────────────


class TestEventFactories:
    def test_device_found_event(self):
        discovered = DiscoveredDevice(
            ip="192.168.1.10", port=8090, model="SoundTouch 30"
        )
        event = device_found_event(discovered)
        assert event.type == DiscoveryEventType.DEVICE_FOUND
        assert event.data["ip"] == "192.168.1.10"
        assert event.data["port"] == 8090
        assert event.data["model"] == "SoundTouch 30"

    def test_device_synced_event(self):
        device = MagicMock(spec=Device)
        device.id = 1
        device.device_id = "AABBCCDDEEFF"
        device.ip = "192.168.1.10"
        device.name = "Living Room"
        device.model = "SoundTouch 30"

        event = device_synced_event(device)
        assert event.type == DiscoveryEventType.DEVICE_SYNCED
        assert event.data["device_id"] == "AABBCCDDEEFF"
        assert event.data["name"] == "Living Room"

    def test_device_failed_event(self):
        event = device_failed_event("192.168.1.99", "Connection refused")
        assert event.type == DiscoveryEventType.DEVICE_FAILED
        assert event.data["ip"] == "192.168.1.99"
        assert event.data["error"] == "Connection refused"


# ── REFACT-104: event_generator timeout ──────────────────────────────────────


class TestEventGeneratorTimeout:
    """Regression: event_generator must not block forever (REFACT-104)."""

    @pytest.mark.asyncio
    async def test_timeout_yields_error_event(self):
        """If no event arrives before timeout, an error SSE is emitted."""
        q: asyncio.Queue = asyncio.Queue()
        results = []
        async for chunk in event_generator(q, timeout=0.1):
            results.append(chunk)

        assert len(results) == 1
        assert "error" in results[0]
        assert "timed out" in results[0].lower()

    @pytest.mark.asyncio
    async def test_timeout_does_not_trigger_when_events_arrive(self):
        """Normal flow: events arrive in time, no timeout."""
        q: asyncio.Queue = asyncio.Queue()
        await q.put(DiscoveryEvent(type=DiscoveryEventType.STARTED, data={}))
        await q.put(DiscoveryEvent(type=DiscoveryEventType.COMPLETED, data={}))

        results = []
        async for chunk in event_generator(q, timeout=5.0):
            results.append(chunk)

        assert len(results) == 2
        assert "started" in results[0]
        assert "completed" in results[1]


# ── REFACT-106: subscriber cap ───────────────────────────────────────────────


class TestEventBusSubscriberCap:
    """Regression: dead queues must not accumulate unboundedly (REFACT-106)."""

    def test_subscriber_count_property(self):
        bus = DiscoveryEventBus()
        assert bus.subscriber_count == 0
        bus.subscribe()
        assert bus.subscriber_count == 1
        bus.subscribe()
        assert bus.subscriber_count == 2

    def test_max_subscribers_prunes_all(self):
        """Exceeding MAX_SUBSCRIBERS clears stale entries."""
        bus = DiscoveryEventBus()
        for _ in range(bus.MAX_SUBSCRIBERS):
            bus.subscribe()
        assert bus.subscriber_count == bus.MAX_SUBSCRIBERS

        # Next subscribe triggers prune + adds itself
        bus.subscribe()
        assert bus.subscriber_count == 1
