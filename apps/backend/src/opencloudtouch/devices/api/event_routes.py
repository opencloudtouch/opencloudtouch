"""SSE endpoint for real-time device events.

Clients connect to ``GET /api/events/device-stream`` and receive
``DeviceEvent`` objects as Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from opencloudtouch.core.dependencies import get_device_state_manager
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.parser import DeviceEvent

logger = logging.getLogger(__name__)

event_router = APIRouter(tags=["Events"])

_KEEPALIVE_INTERVAL = 15  # seconds


def _event_to_sse(event: DeviceEvent) -> str:
    """Format a ``DeviceEvent`` as an SSE message.

    The ``event:`` field is the event type name (e.g. ``volume``).
    The ``data:`` payload matches the existing REST API format.
    """
    data: dict = {"device_id": event.device_id}

    if event.now_playing:
        data.update(
            {
                "source": event.now_playing.source,
                "state": event.now_playing.state,
                "station_name": event.now_playing.station_name,
                "artist": event.now_playing.artist,
                "track": event.now_playing.track,
                "album": event.now_playing.album,
                "artwork_url": event.now_playing.artwork_url,
            }
        )

    if event.volume:
        data.update(
            {
                "actual": event.volume.actual,
                "target": event.volume.target,
                "muted": event.volume.muted,
            }
        )

    if event.connection_state is not None:
        data["connection_state"] = event.connection_state.value

    return f"event: {event.event_type.value}\ndata: {json.dumps(data)}\n\n"


def _snapshot_to_sse(device_id: str, state) -> str:
    """Format initial snapshot for a device as SSE messages."""
    messages = ""

    if state.now_playing:
        np = state.now_playing
        data = {
            "device_id": device_id,
            "source": np.source,
            "state": np.state,
            "station_name": np.station_name,
            "artist": np.artist,
            "track": np.track,
            "album": np.album,
            "artwork_url": np.artwork_url,
        }
        messages += f"event: now_playing\ndata: {json.dumps(data)}\n\n"

    if state.volume:
        vol = state.volume
        data = {
            "device_id": device_id,
            "actual": vol.actual,
            "target": vol.target,
            "muted": vol.muted,
        }
        messages += f"event: volume\ndata: {json.dumps(data)}\n\n"

    return messages


async def _stream_events(
    request: Request,
    state_manager: DeviceStateManager,
) -> AsyncGenerator[str, None]:
    """Generate SSE messages from the device state manager event bus."""
    queue = state_manager.subscribe()
    try:
        # 2.3.2: Initial snapshot for all known devices
        for device_id, state in state_manager.get_all_states().items():
            snapshot = _snapshot_to_sse(device_id, state)
            if snapshot:
                yield snapshot

        # Stream events with keepalive
        while True:
            if await request.is_disconnected():
                logger.debug("SSE client disconnected (request closed)")
                break
            try:
                event: DeviceEvent = await asyncio.wait_for(
                    queue.get(), timeout=_KEEPALIVE_INTERVAL
                )
                sse_msg = _event_to_sse(event)
                logger.debug(
                    "SSE → %s for device %s",
                    event.event_type.value,
                    event.device_id,
                )
                yield sse_msg
            except asyncio.TimeoutError:
                # 2.3.3: Keepalive comment
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        logger.debug("SSE client disconnected (cancelled)")
        raise
    finally:
        state_manager.unsubscribe(queue)
        logger.debug("SSE subscriber cleaned up")


@event_router.get("/api/events/device-stream")
async def device_event_stream(
    request: Request,
    state_manager: Annotated[DeviceStateManager, Depends(get_device_state_manager)],
):
    """Stream device events via Server-Sent Events.

    Pushes an initial snapshot of all known device states, then streams
    real-time updates. A keepalive comment is sent every 15 seconds.
    """
    return StreamingResponse(
        _stream_events(request, state_manager),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
