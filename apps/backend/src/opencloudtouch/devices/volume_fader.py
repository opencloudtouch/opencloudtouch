"""Gradual volume change with manual-change detection.

Shared by the sleep timer (fade out) and, later, scheduled actions (fade in with
``skip_if_muted=False``). Steps are due at absolute deadlines, so a slow device
does not stretch the fade.
"""

import functools
import logging
import math
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.playback import retry_unreachable

logger = logging.getLogger(__name__)

MAX_STEPS = 150
SECONDS_PER_STEP = 2
MANUAL_CHANGE_TOLERANCE = 2


class FadeResult(StrEnum):
    COMPLETED = "completed"
    MANUAL_CHANGE = "manual_change"
    DEVICE_ERROR = "device_error"


def step_target(from_v: int, to_v: int, step: int, steps: int) -> int:
    """Volume of *step* (1..steps); the last step is exactly *to_v*."""
    return int(from_v + (to_v - from_v) * step / steps + 0.5)


class VolumeFader:
    def __init__(
        self,
        device_service: Any,
        sleep: Callable[[float], Awaitable[None]],
        clock: Callable[[], float],
    ) -> None:
        self._device_service = device_service
        self._sleep = sleep
        self._clock = clock

    async def fade(
        self,
        device_id: str,
        from_v: int,
        to_v: int,
        seconds: float,
        *,
        skip_if_muted: bool = True,
        on_set: Callable[[int], Awaitable[None]] | None = None,
    ) -> FadeResult:
        """Move the volume from *from_v* to *to_v* within *seconds*.

        *on_set* is awaited with every value this fade writes (the caller can tell
        later, even after a restart, whether a volume it finds is still its own).
        """
        if seconds <= 0 or from_v == to_v:
            return FadeResult.COMPLETED
        try:
            if skip_if_muted and await self._is_muted(device_id):
                return FadeResult.COMPLETED
            return await self._run(device_id, from_v, to_v, seconds, on_set)
        except DeviceConnectionError:
            logger.error("Volume fade stopped: device unreachable")
            return FadeResult.DEVICE_ERROR

    async def _is_muted(self, device_id: str) -> bool:
        volume = await retry_unreachable(
            functools.partial(self._device_service.get_volume, device_id), self._sleep
        )
        return bool(volume.muted)

    async def _run(
        self,
        device_id: str,
        from_v: int,
        to_v: int,
        seconds: float,
        on_set: Callable[[int], Awaitable[None]] | None,
    ) -> FadeResult:
        steps = min(MAX_STEPS, max(1, math.ceil(seconds / SECONDS_PER_STEP)))
        start = self._clock()
        last_set = from_v
        step = 1
        while step <= steps:
            if self._clock() >= start + seconds:
                step = steps  # past the end: jump to the last step
            delay = start + step * seconds / steps - self._clock()
            if delay > 0:
                await self._sleep(delay)

            current = await retry_unreachable(
                functools.partial(self._device_service.get_volume, device_id),
                self._sleep,
            )
            if abs(current.target - last_set) > MANUAL_CHANGE_TOLERANCE:
                return FadeResult.MANUAL_CHANGE

            target = step_target(from_v, to_v, step, steps)
            if target != last_set:
                await retry_unreachable(
                    functools.partial(
                        self._device_service.set_volume, device_id, target
                    ),
                    self._sleep,
                )
                last_set = target
                if on_set is not None:
                    await on_set(target)
            step += 1
        return FadeResult.COMPLETED
