"""DLNA playback and in-memory queue management."""

import asyncio
import logging
from dataclasses import dataclass

from opencloudtouch.dlna.models import DlnaItem
from opencloudtouch.dlna.renderer import DlnaRenderer


logger = logging.getLogger(__name__)


class DlnaPlaybackError(Exception):
    """Raised when a DLNA playback operation cannot be completed."""


@dataclass
class DlnaPlaybackState:
    """Current DLNA playback state for one device."""

    server_id: str
    items: list[DlnaItem]
    index: int
    device_ip: str
    playing_seen: bool = False
    is_active: bool = False
    paused_by_oct: bool = False

    @property
    def current_item(self) -> DlnaItem:
        """Return the currently selected item."""
        return self.items[self.index]


class DlnaPlaybackService:
    """Manage in-memory DLNA playback queues per SoundTouch device.

    Queue state is intentionally not persisted. OCT advances tracks itself
    because SoundTouch does not provide usable SetNextAVTransportURI support
    for this playback flow.
    """

    def __init__(self, renderer: DlnaRenderer | None = None):
        self.renderer = renderer or DlnaRenderer()
        self._states: dict[str, DlnaPlaybackState] = {}
        self._device_locks: dict[str, asyncio.Lock] = {}
        self._advance_tasks: dict[str, asyncio.Task[None]] = {}
        self._advance_inflight: set[str] = set()
        self._closed = False

    def _lock_for(self, device_id: str) -> asyncio.Lock:
        """Return the lock for a SoundTouch device."""
        return self._device_locks.setdefault(device_id, asyncio.Lock())

    async def play(
        self,
        device_id: str,
        device_ip: str,
        server_id: str,
        items: list[DlnaItem],
        object_id: str,
    ) -> DlnaItem:
        """Play an item and remember its surrounding audio queue."""

        async with self._lock_for(device_id):
            self._cancel_advance(device_id)
            playable_items = [
                item
                for item in items
                if not item.is_container
                and item.resource_url
                and (
                    item.media_class is None
                    or item.media_class.startswith("object.item.audioItem")
                )
            ]

            index = next(
                (
                    index
                    for index, item in enumerate(playable_items)
                    if item.id == object_id
                ),
                None,
            )

            if index is None:
                raise DlnaPlaybackError(f"DLNA audio item not found: {object_id}")

            state = DlnaPlaybackState(
                server_id=server_id,
                items=playable_items,
                index=index,
                device_ip=device_ip,
            )

            await self._play_item(device_ip, state.current_item)

            state.is_active = True
            self._states[device_id] = state
            return state.current_item

    async def pause(self, device_id: str, device_ip: str) -> None:
        """Pause the current item."""

        async with self._lock_for(device_id):
            self._require_state(device_id, require_active=True)
            await self.renderer.pause(device_ip)
            self._states[device_id].paused_by_oct = True

    async def resume(self, device_id: str, device_ip: str) -> None:
        """Resume the current item."""

        async with self._lock_for(device_id):
            state = self._require_state(device_id, require_active=True)
            if (
                state.paused_by_oct
                and await self.renderer.get_source(device_ip) != "UPNP"
            ):
                raise DlnaPlaybackError(
                    f"No active DLNA playback for device: {device_id}"
                )
            await self.renderer.resume(device_ip)
            state.paused_by_oct = False

    async def next(self, device_id: str, device_ip: str) -> DlnaItem:
        """Play the next item in the current queue."""
        return await self._skip(device_id, device_ip, offset=1)

    async def previous(self, device_id: str, device_ip: str) -> DlnaItem:
        """Play the previous item in the current queue."""
        return await self._skip(device_id, device_ip, offset=-1)

    async def _skip(self, device_id: str, device_ip: str, offset: int) -> DlnaItem:
        """Change track without updating queue state if playback fails."""
        async with self._lock_for(device_id):
            # A STOPPED event leaves a cancellable automatic advance pending.
            # Allow manual navigation during that handoff, but not after a
            # completed source switch or at the end of the queue.
            pending = device_id in self._advance_tasks
            state = self._require_state(device_id)
            if not state.is_active and not pending:
                raise DlnaPlaybackError(
                    f"No active DLNA playback for device: {device_id}"
                )
            # A paused session may have switched to radio without a timely
            # transport callback. Never reclaim another Bose source.
            if await self.renderer.get_source(device_ip) != "UPNP":
                state.is_active = False
                state.paused_by_oct = False
                self._cancel_advance(device_id)
                raise DlnaPlaybackError(
                    f"No active DLNA playback for device: {device_id}"
                )
            self._cancel_advance(device_id)
            target_index = state.index + offset

            if not 0 <= target_index < len(state.items):
                direction = "next" if offset > 0 else "previous"
                raise DlnaPlaybackError(f"No {direction} DLNA track")

            item = state.items[target_index]
            await self._play_item(device_ip, item)

            state.index = target_index
            state.playing_seen = False
            state.is_active = True
            state.paused_by_oct = False
            return item

    def current(self, device_id: str) -> DlnaItem | None:
        """Return the currently active DLNA item for a device."""
        state = self._states.get(device_id)
        if state is None or not state.is_active:
            return None

        return state.current_item

    async def handle_transport_state(
        self,
        device_id: str,
        transport_state: str,
    ) -> DlnaItem | None:
        """Process AVTransport events and schedule automatic advancement."""
        # Cancel outside the device lock: a pending advancement may
        # be waiting to acquire that same lock.
        if transport_state == "PAUSED_PLAYBACK":
            self._cancel_advance(device_id)

        async with self._lock_for(device_id):
            if self._closed:
                return None
            state = self._states.get(device_id)
            if state is None:
                return None

            if transport_state == "PAUSED_PLAYBACK":
                state.playing_seen = False
                state.is_active = state.paused_by_oct
                return None

            if transport_state == "PLAYING":
                # Only a pending or active DLNA session can observe PLAYING.
                # Late notifications must not revive an abandoned queue.
                if not state.is_active and device_id not in self._advance_tasks:
                    return None
                state.playing_seen = True
                state.is_active = True
                state.paused_by_oct = False
                return None

            if transport_state != "STOPPED" or not state.playing_seen:
                return None

            state.playing_seen = False
            state.is_active = False
            state.paused_by_oct = False

            if state.index >= len(state.items) - 1:
                return None

            self._cancel_advance(device_id)
            task = asyncio.create_task(
                self._advance_if_source_matches(device_id, state)
            )
            self._advance_tasks[device_id] = task
            return None

    def _cancel_advance(self, device_id: str) -> None:
        """Cancel a scheduled automatic track change."""
        task = self._advance_tasks.get(device_id)
        # Once the UPnP request has started, cancelling it can leave the
        # renderer in an unknown state. Keep tracking it for shutdown.
        if task is not None and device_id not in self._advance_inflight:
            self._advance_tasks.pop(device_id, None)
            if not task.done():
                task.cancel()

    async def _advance_if_source_matches(
        self,
        device_id: str,
        expected_state: DlnaPlaybackState,
    ) -> None:
        """Advance only if Bose still reports the UPnP playback source."""
        try:
            # Keep network checks outside the device lock so manual controls
            # and external pause events can cancel a slow source lookup.
            source = await self.renderer.get_source(expected_state.device_ip)
            if source != "UPNP":
                return

            async with self._lock_for(device_id):
                if self._closed or self._states.get(device_id) is not expected_state:
                    return

                if expected_state.index >= len(expected_state.items) - 1:
                    return

                next_item = expected_state.items[expected_state.index + 1]
                self._advance_inflight.add(device_id)
                try:
                    await self._play_item(expected_state.device_ip, next_item)
                finally:
                    self._advance_inflight.discard(device_id)

                expected_state.index += 1
                expected_state.is_active = True
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "DLNA automatic track advance failed: device=%s", device_id
            )
        finally:
            current = asyncio.current_task()
            if self._advance_tasks.get(device_id) is current:
                self._advance_tasks.pop(device_id, None)

    async def close(self) -> None:
        """Cancel and await pending automatic track changes."""
        self._closed = True
        tasks = list(self._advance_tasks.values())
        self._advance_tasks.clear()

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _play_item(self, device_ip: str, item: DlnaItem) -> None:
        """Send a playable item to the SoundTouch renderer."""
        if not item.resource_url:
            raise DlnaPlaybackError(f"DLNA item has no playable resource: {item.id}")

        await self.renderer.play_uri(device_ip, item.resource_url)

    def _require_state(
        self, device_id: str, require_active: bool = False
    ) -> DlnaPlaybackState:
        """Return playback state or raise when none exists."""
        state = self._states.get(device_id)

        if state is None or (require_active and not state.is_active):
            raise DlnaPlaybackError(f"No active DLNA playback for device: {device_id}")

        return state
