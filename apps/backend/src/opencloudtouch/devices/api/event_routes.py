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

from opencloudtouch.core.dependencies import (
    get_device_state_manager,
    get_preset_service,
)
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.presets.service import PresetService, match_stored_music_preset

logger = logging.getLogger(__name__)

event_router = APIRouter(tags=["Events"])

_KEEPALIVE_INTERVAL = 15  # seconds


def _dlna_fields(np: NowPlayingInfo, preset_number: int | None) -> dict[str, object]:
    """DLNA fields of the REST now-playing shape."""
    return {"dlna": np.is_dlna, "preset_number": preset_number}


async def _preset_number(
    device_id: str,
    np: NowPlayingInfo | None,
    preset_service: PresetService | None,
) -> int | None:
    """Slot of the playing DLNA item, same lookup as the REST route (decision 31)."""
    if preset_service is None or np is None or np.source != "STORED_MUSIC":
        return None
    match = await match_stored_music_preset(
        {"artwork_url": np.artwork_url}, np, device_id, preset_service
    )
    return match.preset_number if match else None


def _event_to_sse(event: DeviceEvent, preset_number: int | None = None) -> str:
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
                "shuffle_setting": event.now_playing.shuffle_setting,
                "repeat_setting": event.now_playing.repeat_setting,
                **_dlna_fields(event.now_playing, preset_number),
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

    if event.event_type == EventType.SOURCE_ERROR:
        # the speaker's free text is deliberately not forwarded
        data.update(
            {
                "code": event.error_code,
                "name": event.error_name,
                "severity": event.error_severity,
            }
        )

    return f"event: {event.event_type.value}\ndata: {json.dumps(data)}\n\n"


def _snapshot_to_sse(device_id: str, state, preset_number: int | None = None) -> str:
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
            "shuffle_setting": np.shuffle_setting,
            "repeat_setting": np.repeat_setting,
            **_dlna_fields(np, preset_number),
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
    preset_service: PresetService | None = None,
) -> AsyncGenerator[str, None]:
    """Generate SSE messages from the device state manager event bus."""
    queue = state_manager.subscribe()
    try:
        # 2.3.2: Initial snapshot for all known devices
        for device_id, state in state_manager.get_all_states().items():
            slot = await _preset_number(device_id, state.now_playing, preset_service)
            snapshot = _snapshot_to_sse(device_id, state, slot)
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
                slot = await _preset_number(
                    event.device_id, event.now_playing, preset_service
                )
                sse_msg = _event_to_sse(event, slot)
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
    preset_service: Annotated[PresetService, Depends(get_preset_service)],
):
    """Stream device events via Server-Sent Events.

    Pushes an initial snapshot of all known device states, then streams
    real-time updates. A keepalive comment is sent every 15 seconds.
    """
    return StreamingResponse(
        _stream_events(request, state_manager, preset_service),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
