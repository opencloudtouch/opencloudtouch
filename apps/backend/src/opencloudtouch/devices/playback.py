"""Shared playback helpers: state predicates, stopping playback, unreachable-retry.

Used by the sleep timer and, later, scheduled actions. All device access goes
through ``DeviceService`` with live calls (never the state cache).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.client import NowPlayingInfo

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retries apply to "device unreachable" (DeviceConnectionError) only: an invalid
# key name or a missing device must not be retried.
UNREACHABLE_RETRIES = 3
UNREACHABLE_RETRY_DELAY = 20.0
PAUSE_SETTLE_SECONDS = 2.0

_PLAYING_STATES = frozenset({"PLAY_STATE", "BUFFERING_STATE"})


def is_standby(info: NowPlayingInfo) -> bool:
    return info.source == "STANDBY"


def is_playing(info: NowPlayingInfo) -> bool:
    return info.state in _PLAYING_STATES


async def retry_unreachable(
    call: Callable[[], Awaitable[T]],
    sleep: Callable[[float], Awaitable[None]],
    retries: int = UNREACHABLE_RETRIES,
    delay: float = UNREACHABLE_RETRY_DELAY,
) -> T:
    """Run *call*; on DeviceConnectionError retry *retries* times, *delay* s apart."""
    for attempt in range(retries + 1):
        try:
            return await call()
        except DeviceConnectionError:
            if attempt == retries:
                raise
            await sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


async def stop_playback(
    device_service: Any,
    device_id: str,
    sleep: Callable[[float], Awaitable[None]],
) -> None:
    """Pause a playing device; fall back to STOP when it keeps playing.

    A device that is not playing is left alone.
    """
    if not is_playing(await device_service.get_now_playing(device_id)):
        return
    await device_service.press_key(device_id, "PAUSE", "both")
    await sleep(PAUSE_SETTLE_SECONDS)
    if (await device_service.get_now_playing(device_id)).state == "PLAY_STATE":
        await device_service.press_key(device_id, "STOP", "both")
