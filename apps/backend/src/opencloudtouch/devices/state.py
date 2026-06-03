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
from typing import TYPE_CHECKING, Awaitable, Callable, TypeAlias

from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo
from opencloudtouch.devices.websocket.connection import ConnectionState
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.devices.websocket.throttle import EventThrottle

if TYPE_CHECKING:
    from opencloudtouch.devices.websocket.icy_worker import IcyWorker

logger = logging.getLogger(__name__)

_ICY_POLL_INTERVAL = 3.0  # seconds


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

    # Callback type: (device_id, station_name) -> favicon_url | None
    get_preset_favicon_type: TypeAlias = Callable[[str, str], Awaitable[str | None]]

    def __init__(self) -> None:
        self._states: dict[str, DeviceState] = {}
        self._subscribers: list[asyncio.Queue[DeviceEvent]] = []
        self._icy_worker: IcyWorker | None = None
        self._icy_poll_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._throttle = EventThrottle(publish=self.publish)
        self._get_preset_favicon: DeviceStateManager.get_preset_favicon_type | None = (
            None
        )

    def set_icy_worker(self, worker: IcyWorker) -> None:
        """Attach an ICY metadata worker for radio enrichment."""
        self._icy_worker = worker

    def set_preset_favicon_callback(self, callback: get_preset_favicon_type) -> None:
        """Set callback for resolving preset favicon URLs."""
        self._get_preset_favicon = callback

    def start_icy_polling(self) -> None:
        """Start periodic ICY metadata polling for radio-playing devices."""
        if self._icy_poll_task is not None:
            return
        self._icy_poll_task = asyncio.create_task(self._icy_poll_loop())
        logger.info("ICY periodic polling started (%.0fs interval)", _ICY_POLL_INTERVAL)

    async def stop_icy_polling(self) -> None:
        """Stop periodic ICY metadata polling."""
        self._throttle.stop()
        if self._icy_poll_task is not None:
            self._icy_poll_task.cancel()
            await asyncio.gather(self._icy_poll_task, return_exceptions=True)
            self._icy_poll_task = None
            logger.info("ICY periodic polling stopped")

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
            logger.debug(
                "sse.dropped %s %s — no subscribers",
                event.device_id,
                event.event_type.value,
                extra={
                    "device_id": event.device_id,
                    "event_type": event.event_type.value,
                },
            )
            return

        logger.debug(
            "sse.publish %s %s to %d subscriber(s)",
            event.device_id,
            event.event_type.value,
            len(self._subscribers),
            extra={
                "device_id": event.device_id,
                "event_type": event.event_type.value,
                "subscribers": len(self._subscribers),
            },
        )
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
            logger.debug(
                "ws.now_playing %s source=%s station=%s artist=%s track=%s state=%s",
                event.device_id,
                event.now_playing.source,
                event.now_playing.station_name,
                event.now_playing.artist,
                event.now_playing.track,
                event.now_playing.state,
                extra={
                    "device_id": event.device_id,
                    "source": event.now_playing.source,
                    "station": event.now_playing.station_name,
                    "artist": event.now_playing.artist,
                    "track": event.now_playing.track,
                    "play_state": event.now_playing.state,
                },
            )
            self.update_now_playing(event.device_id, event.now_playing)
        elif event.event_type == EventType.VOLUME and event.volume:
            logger.debug(
                "ws.volume %s actual=%d target=%d muted=%s",
                event.device_id,
                event.volume.actual,
                event.volume.target,
                event.volume.muted,
                extra={
                    "device_id": event.device_id,
                    "actual": event.volume.actual,
                    "target": event.volume.target,
                    "muted": event.volume.muted,
                },
            )
            self.update_volume(event.device_id, event.volume)
        elif event.event_type == EventType.METADATA_ENRICHED and event.now_playing:
            logger.debug(
                "ws.metadata_enriched %s artist=%s track=%s art=%s",
                event.device_id,
                event.now_playing.artist,
                event.now_playing.track,
                bool(event.now_playing.artwork_url),
                extra={
                    "device_id": event.device_id,
                    "artist": event.now_playing.artist,
                    "track": event.now_playing.track,
                    "has_artwork": bool(event.now_playing.artwork_url),
                },
            )
            self.update_now_playing(event.device_id, event.now_playing)
        elif event.event_type == EventType.UNKNOWN:
            logger.debug(
                "Device %s dropping unknown event (not forwarded to SSE)",
                event.device_id,
            )
            return
        else:
            logger.debug(
                "Device %s unhandled event type: %s",
                event.device_id,
                event.event_type.value,
            )

        await self._throttle.submit(event)

        # Fire preset-favicon + ICY probe in background for radio events
        if event.event_type == EventType.NOW_PLAYING and event.now_playing:
            task = asyncio.create_task(self._run_enrichment_pipeline(event))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _run_enrichment_pipeline(self, event: DeviceEvent) -> None:
        """Run preset-favicon lookup then ICY probe for radio events."""
        assert event.now_playing is not None

        # Step 1: Preset-favicon enrichment (fast, DB lookup)
        await self._run_preset_favicon_enrichment(event)

        # Step 2: ICY metadata probe (slow, network)
        if self._icy_worker:
            await self._run_icy_probe(event)

    async def _run_preset_favicon_enrichment(self, event: DeviceEvent) -> None:
        """Look up preset favicon from DB and publish enriched event."""
        from opencloudtouch.devices.websocket.icy_worker import RADIO_SOURCES

        if self._get_preset_favicon is None:
            return

        info = event.now_playing
        if not info or info.source not in RADIO_SOURCES:
            return
        if info.artwork_url:
            return  # Already has artwork
        if not info.station_name:
            return

        try:
            favicon_url = await self._get_preset_favicon(
                event.device_id, info.station_name
            )
        except Exception:
            logger.debug(
                "Preset favicon lookup failed for %s", event.device_id, exc_info=True
            )
            return

        if not favicon_url:
            return

        logger.debug(
            "Preset favicon enrichment for %s: %s → %s",
            event.device_id,
            info.station_name,
            favicon_url,
        )

        enriched = NowPlayingInfo(
            source=info.source,
            state=info.state,
            station_name=info.station_name,
            artist=info.artist,
            track=info.track,
            album=info.album,
            artwork_url=favicon_url,
        )
        enriched_event = DeviceEvent(
            device_id=event.device_id,
            event_type=EventType.METADATA_ENRICHED,
            now_playing=enriched,
        )
        await self.on_event(enriched_event)

    async def _run_icy_probe(self, event: DeviceEvent) -> None:
        """Run ICY probe and publish enriched event if successful."""
        assert self._icy_worker is not None
        try:
            enriched = await self._icy_worker.on_event(event)
            if enriched:
                await self.on_event(enriched)
        except Exception:
            logger.debug("ICY probe background task failed", exc_info=True)

    async def _icy_poll_loop(self) -> None:
        """Periodically re-probe ICY metadata for radio-playing devices."""
        from opencloudtouch.devices.websocket.icy_worker import RADIO_SOURCES

        while True:
            await asyncio.sleep(_ICY_POLL_INTERVAL)
            if not self._icy_worker:
                continue
            for device_id, state in self._states.items():
                await self._icy_poll_device(device_id, state, RADIO_SOURCES)

    async def mark_device_offline(self, device_id: str) -> None:
        """Mark a device as offline and publish connection event via SSE."""
        self.update_connection(device_id, ConnectionState.FAILED)
        event = DeviceEvent(
            device_id=device_id,
            event_type=EventType.CONNECTION,
            connection_state=ConnectionState.FAILED,
        )
        await self.publish(event)

    async def _icy_poll_device(
        self,
        device_id: str,
        state: DeviceState,
        radio_sources: frozenset[str] | set[str],
    ) -> None:
        """Probe a single device for ICY metadata updates."""
        if not state.now_playing:
            return
        if state.now_playing.source not in radio_sources:
            return
        if state.now_playing.state != "PLAY_STATE":
            return
        if not self._icy_worker:
            return
        try:
            event = DeviceEvent(
                device_id=device_id,
                event_type=EventType.NOW_PLAYING,
                now_playing=state.now_playing,
            )
            enriched = await self._icy_worker.poll_stream(event)
            if enriched:
                await self.on_event(enriched)
        except Exception:
            logger.debug("ICY poll failed for %s", device_id, exc_info=True)

    # -- Internals -----------------------------------------------------------

    def _ensure_state(self, device_id: str) -> DeviceState:
        """Get or create ``DeviceState`` for *device_id*."""
        if device_id not in self._states:
            self._states[device_id] = DeviceState(device_id=device_id)
        return self._states[device_id]
