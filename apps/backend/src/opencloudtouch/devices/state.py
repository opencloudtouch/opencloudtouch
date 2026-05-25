"""Centralized device state store fed by WebSocket push events.

Provides DeviceState (per-device cache) and DeviceStateManager (event bus +
state store). Routes read from the state manager before falling back to
direct HTTP queries.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo
from opencloudtouch.devices.websocket.connection import ConnectionState
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

if TYPE_CHECKING:
    from opencloudtouch.devices.websocket.icy_worker import IcyWorker

logger = logging.getLogger(__name__)


@dataclass
class DeviceState:
    """Cached state for a single device."""

    device_id: str
    now_playing: NowPlayingInfo | None = None
    volume: VolumeInfo | None = None
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    last_update: float = field(default_factory=time.time)

    def is_fresh(self, max_age: float = 10.0) -> bool:
        """Return True if state was updated within *max_age* seconds."""
        return (time.time() - self.last_update) < max_age


class DeviceStateManager:
    """In-memory state store with pub/sub event bus.

    Mirrors the ``DiscoveryEventBus`` pattern from ``devices/events.py``.
    Subscribers receive ``DeviceEvent`` objects via ``asyncio.Queue``.
    """

    MAX_SUBSCRIBERS = 20

    def __init__(self) -> None:
        self._states: dict[str, DeviceState] = {}
        self._subscribers: list[asyncio.Queue[DeviceEvent]] = []
        self._icy_worker: IcyWorker | None = None

    def set_icy_worker(self, worker: IcyWorker) -> None:
        """Attach an ICY metadata worker for radio enrichment."""
        self._icy_worker = worker

    # -- State updates -------------------------------------------------------

    def update_now_playing(self, device_id: str, info: NowPlayingInfo) -> None:
        """Update now-playing state for *device_id*."""
        state = self._ensure_state(device_id)
        state.now_playing = info
        state.last_update = time.time()

    def update_volume(self, device_id: str, info: VolumeInfo) -> None:
        """Update volume state for *device_id*."""
        state = self._ensure_state(device_id)
        state.volume = info
        state.last_update = time.time()

    def update_connection(
        self, device_id: str, connection_state: ConnectionState
    ) -> None:
        """Update connection state for *device_id*."""
        state = self._ensure_state(device_id)
        state.connection_state = connection_state
        state.last_update = time.time()

    # -- State reads ---------------------------------------------------------

    def get_state(self, device_id: str) -> DeviceState | None:
        """Return cached state for *device_id*, or ``None``."""
        return self._states.get(device_id)

    def get_all_states(self) -> dict[str, DeviceState]:
        """Return a snapshot of all device states."""
        return dict(self._states)

    # -- Pub/Sub -------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue[DeviceEvent]:
        """Subscribe to device events.

        Returns a queue that will receive ``DeviceEvent`` objects.
        Caps at ``MAX_SUBSCRIBERS``; exceeding the cap prunes all queues
        (identical behaviour to ``DiscoveryEventBus``).
        """
        if len(self._subscribers) >= self.MAX_SUBSCRIBERS:
            logger.warning(
                "Max subscribers (%d) reached — pruning all queues",
                self.MAX_SUBSCRIBERS,
            )
            self._subscribers.clear()

        queue: asyncio.Queue[DeviceEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        logger.debug(
            "Client subscribed to device events (total: %d)",
            len(self._subscribers),
        )
        return queue

    def unsubscribe(self, queue: asyncio.Queue[DeviceEvent]) -> None:
        """Remove *queue* from subscribers."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
            logger.debug("Client unsubscribed (remaining: %d)", len(self._subscribers))

    async def publish(self, event: DeviceEvent) -> None:
        """Broadcast *event* to all subscribers, pruning dead queues."""
        if not self._subscribers:
            return

        for queue in self._subscribers[:]:  # iterate over copy
            try:
                await queue.put(event)
            except Exception:
                logger.exception("Failed to publish event to subscriber")
                self._subscribers.remove(queue)

    # -- WebSocket integration -----------------------------------------------

    async def on_event(self, event: DeviceEvent) -> None:
        """Callback wired to ``WebSocketManager.event_callback``.

        Updates local state *and* publishes to subscribers.
        For ``now_playing`` radio events, fires ICY probe in background.
        """
        if event.event_type == EventType.NOW_PLAYING and event.now_playing:
            self.update_now_playing(event.device_id, event.now_playing)
        elif event.event_type == EventType.VOLUME and event.volume:
            self.update_volume(event.device_id, event.volume)
        elif event.event_type == EventType.METADATA_ENRICHED and event.now_playing:
            self.update_now_playing(event.device_id, event.now_playing)

        await self.publish(event)

        # Fire ICY probe in background for radio events
        if (
            self._icy_worker
            and event.event_type == EventType.NOW_PLAYING
            and event.now_playing
        ):
            asyncio.create_task(self._run_icy_probe(event))

    async def _run_icy_probe(self, event: DeviceEvent) -> None:
        """Run ICY probe and publish enriched event if successful."""
        assert self._icy_worker is not None
        try:
            enriched = await self._icy_worker.on_event(event)
            if enriched:
                await self.on_event(enriched)
        except Exception:
            logger.debug("ICY probe background task failed", exc_info=True)

    # -- Internals -----------------------------------------------------------

    def _ensure_state(self, device_id: str) -> DeviceState:
        """Get or create ``DeviceState`` for *device_id*."""
        if device_id not in self._states:
            self._states[device_id] = DeviceState(device_id=device_id)
        return self._states[device_id]
