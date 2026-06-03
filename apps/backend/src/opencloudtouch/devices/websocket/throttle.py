"""Event throttle for SSE relay — last-event-wins strategy.

Prevents event floods to SSE subscribers during volume ramps or rapid
state transitions. State updates happen immediately (in the state manager);
only SSE *publishing* is throttled.

Cooldowns per event type:
- volume: 100ms (volume ramps generate dozens of events/second)
- now_playing: 500ms (rapid BUFFERING → PLAY flips)
- All others: no throttle (rare events like presets, zones)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

logger = logging.getLogger(__name__)

# Cooldown per event type in seconds
THROTTLE_INTERVALS: dict[EventType, float] = {
    EventType.VOLUME: 0.1,  # 100ms
    EventType.NOW_PLAYING: 0.5,  # 500ms
}


class EventThrottle:
    """Last-event-wins throttle for SSE publishing.

    For throttled event types, the latest event replaces any pending event.
    A delayed task fires after the cooldown to publish the most recent state.
    Unthrottled event types pass through immediately.
    """

    def __init__(
        self,
        publish: Callable[[DeviceEvent], Awaitable[None]],
    ) -> None:
        self._publish = publish
        # (device_id, event_type) → timestamp of last publish
        self._last_publish: dict[tuple[str, EventType], float] = {}
        # (device_id, event_type) → pending event waiting for cooldown
        self._pending: dict[tuple[str, EventType], DeviceEvent] = {}
        # (device_id, event_type) → scheduled asyncio task
        self._tasks: dict[tuple[str, EventType], asyncio.Task[None]] = {}

    async def submit(self, event: DeviceEvent) -> None:
        """Submit an event for throttled publishing."""
        interval = THROTTLE_INTERVALS.get(event.event_type)
        if interval is None:
            # No throttle — publish immediately
            await self._publish(event)
            return

        key = (event.device_id, event.event_type)
        now = time.monotonic()
        last = self._last_publish.get(key, 0.0)
        elapsed = now - last

        if elapsed >= interval:
            # Cooldown expired — publish immediately
            self._last_publish[key] = now
            await self._publish(event)
        else:
            # Within cooldown — store as pending, schedule delayed publish
            self._pending[key] = event
            if key not in self._tasks or self._tasks[key].done():
                remaining = interval - elapsed
                self._tasks[key] = asyncio.create_task(
                    self._delayed_publish(key, remaining)
                )

    async def _delayed_publish(self, key: tuple[str, EventType], delay: float) -> None:
        """Wait for cooldown, then publish the latest pending event."""
        await asyncio.sleep(delay)
        event = self._pending.pop(key, None)
        if event is not None:
            self._last_publish[key] = time.monotonic()
            await self._publish(event)

    def stop(self) -> None:
        """Cancel all pending delayed tasks."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._pending.clear()
