"""
Device Discovery Events

Event system for streaming device discovery progress to frontend via SSE.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Dict

from opencloudtouch.db import Device
from opencloudtouch.discovery import DiscoveredDevice

logger = logging.getLogger(__name__)


class DiscoveryEventType(str, Enum):
    """Discovery event types for SSE streaming."""

    STARTED = "started"
    DEVICE_FOUND = "device_found"
    DEVICE_SYNCED = "device_synced"
    DEVICE_FAILED = "device_failed"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class DiscoveryEvent:
    """Discovery event for SSE streaming."""

    type: DiscoveryEventType
    data: Dict[str, Any]

    def to_sse(self) -> str:
        """
        Format as Server-Sent Events message.

        Returns:
            SSE formatted string
        """
        return f"event: {self.type.value}\ndata: {json.dumps(self.data)}\n\n"


class DiscoveryEventBus:
    """
    Event bus for discovery events.

    Broadcasts events to all subscribed clients via asyncio.Queue.
    Dead queues are pruned during publish (REFACT-106).
    """

    MAX_SUBSCRIBERS = 20  # Safety cap to prevent unbounded growth

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    @property
    def subscriber_count(self) -> int:
        """Return current number of subscribers."""
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue:
        """
        Subscribe to discovery events.

        Returns:
            Queue that will receive DiscoveryEvent objects
        """
        if len(self._subscribers) >= self.MAX_SUBSCRIBERS:
            logger.warning(
                "Max subscribers (%d) reached — pruning all queues",
                self.MAX_SUBSCRIBERS,
            )
            self._subscribers.clear()

        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        logger.debug(
            "Client subscribed to discovery events (total: %d)",
            len(self._subscribers),
        )
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """
        Unsubscribe from discovery events.

        Args:
            queue: Queue to remove from subscribers
        """
        if queue in self._subscribers:
            self._subscribers.remove(queue)
            logger.debug("Client unsubscribed (remaining: %d)", len(self._subscribers))

    async def publish(self, event: DiscoveryEvent):
        """
        Publish event to all subscribers.

        Args:
            event: Event to broadcast
        """
        if not self._subscribers:
            logger.debug("No subscribers for event: %s", event.type)
            return

        logger.debug(
            "Broadcasting event %s to %d subscriber(s)",
            event.type,
            len(self._subscribers),
        )

        # Broadcast to all subscribers
        for queue in self._subscribers[
            :
        ]:  # Copy list to avoid modification during iteration
            try:
                await queue.put(event)
            except Exception:
                logger.exception("Failed to publish event to subscriber")
                # Remove dead subscriber
                self._subscribers.remove(queue)


# Global event bus instance
_event_bus: DiscoveryEventBus | None = None


def get_event_bus() -> DiscoveryEventBus:
    """
    Get global event bus instance.

    Returns:
        Global DiscoveryEventBus singleton
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = DiscoveryEventBus()
    return _event_bus


async def event_generator(
    queue: asyncio.Queue, timeout: float = 30.0
) -> AsyncGenerator[str, None]:
    """
    Generate SSE messages from event queue.

    Applies a per-event timeout to prevent indefinite blocking when no
    COMPLETED/ERROR event is published (REFACT-104: lock starvation fix).

    Args:
        queue: Queue receiving DiscoveryEvent objects
        timeout: Max seconds to wait for each event (default 30s)

    Yields:
        SSE formatted strings
    """
    try:
        while True:
            try:
                event: DiscoveryEvent = await asyncio.wait_for(
                    queue.get(), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Event generator timed out waiting for event after %.0fs",
                    timeout,
                )
                timeout_event = DiscoveryEvent(
                    type=DiscoveryEventType.ERROR,
                    data={"message": "Discovery timed out"},
                )
                yield timeout_event.to_sse()
                break
            yield event.to_sse()

            # Stop streaming after completed/error events
            if event.type in (DiscoveryEventType.COMPLETED, DiscoveryEventType.ERROR):
                break
    except asyncio.CancelledError:
        logger.debug("Event generator cancelled")
        raise
    except Exception as e:
        logger.exception("Event generator error: %s", e)
        # Send error event to client
        error_event = DiscoveryEvent(
            type=DiscoveryEventType.ERROR,
            data={"message": f"Stream error: {str(e)}"},
        )
        yield error_event.to_sse()


def device_found_event(device: DiscoveredDevice) -> DiscoveryEvent:
    """Create device_found event from discovered device."""
    return DiscoveryEvent(
        type=DiscoveryEventType.DEVICE_FOUND,
        data={
            "ip": device.ip,
            "port": device.port,
            "name": device.name,
            "model": device.model,
        },
    )


def device_synced_event(device: Device) -> DiscoveryEvent:
    """Create device_synced event from synced device."""
    return DiscoveryEvent(
        type=DiscoveryEventType.DEVICE_SYNCED,
        data={
            "id": device.id,
            "device_id": device.device_id,
            "ip": device.ip,
            "name": device.name,
            "model": device.model,
        },
    )


def device_failed_event(ip: str, error: str) -> DiscoveryEvent:
    """Create device_failed event."""
    return DiscoveryEvent(
        type=DiscoveryEventType.DEVICE_FAILED,
        data={"ip": ip, "error": error},
    )
