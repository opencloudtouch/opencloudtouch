"""Sleep timer: fade out, stop (or standby) and restore the volume after a countdown.

One timer per device. All start/replace/cancel/fire operations of a device are
serialised by a per-device lock; the countdown itself and the fade run without the
lock so that ``cancel`` can interrupt them, while the end sequence holds it so that
``cancel`` waits instead of interrupting it. The timer waits on the wall clock in
chunks of at most 30 s. The outcome is logged only.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    raise_coded,
)
from opencloudtouch.devices.playback import (
    is_standby,
    retry_unreachable,
    stop_playback,
)
from opencloudtouch.devices.volume_fader import FadeResult, VolumeFader
from opencloudtouch.sleep_timer.models import SleepTimer
from opencloudtouch.sleep_timer.repository import SleepTimerRepository

logger = logging.getLogger(__name__)

WAIT_CHUNK_SECONDS = 30.0
POWER_DELAY_SECONDS = 1.0
LATE_END_GRACE_SECONDS = 600.0  # a timer that elapsed up to 10 min ago still ends
MIN_RECOVERED_FADE_SECONDS = 2.0
SHUTDOWN_RESTORE_SECONDS = 3.0
VOLUME_TOLERANCE = 2


class SleepTimerService:
    def __init__(
        self,
        device_service: Any,
        repository: SleepTimerRepository,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._device_service = device_service
        self._repository = repository
        self._clock = clock
        self._sleep = sleep
        self._fader = VolumeFader(device_service, sleep, clock)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_set: dict[str, int] = {}

    # ------------------------------------------------------------------ public

    def now(self) -> float:
        return self._clock()

    async def get(self, device_id: str) -> SleepTimer | None:
        """The active timer (no device call); unknown devices raise DeviceNotFoundError."""
        if await self._device_service.get_device_by_id(device_id) is None:
            raise DeviceNotFoundError(device_id)
        return await self._repository.get(device_id)

    async def start(
        self,
        device_id: str,
        duration_minutes: int,
        fade_seconds: int,
        end_action: str,
    ) -> SleepTimer:
        """Start (or replace) the timer of a device."""
        if fade_seconds > duration_minutes * 60:
            raise_coded(
                422,
                error_codes.SLEEP_TIMER_FADE_TOO_LONG,
                "'fade_seconds' must not exceed the timer duration",
                field="fade_seconds",
            )
        # Live check: unknown device -> DeviceNotFoundError, unreachable -> 503
        await self._device_service.get_volume(device_id)

        async with self._lock(device_id):
            await self._cancel_locked(device_id, restore_volume=True)
            now = self._clock()
            timer = SleepTimer(
                device_id=device_id,
                ends_at=now + duration_minutes * 60,
                duration_minutes=duration_minutes,
                fade_seconds=fade_seconds,
                end_action=end_action,
                created_at=now,
            )
            await self._repository.upsert(timer)
            self._arm(timer)
            return timer

    async def cancel(self, device_id: str, *, restore_volume: bool = True) -> None:
        """Cancel the timer; waits for a running end sequence instead of interrupting it."""
        async with self._lock(device_id):
            await self._cancel_locked(device_id, restore_volume=restore_volume)

    async def recover(self) -> None:
        """Re-arm or finish the timers that were stored before a restart."""
        for timer in await self._repository.list_all():
            remaining = timer.ends_at - self._clock()
            if remaining > 0:
                self._arm(timer, recovered=True)
            elif -remaining <= LATE_END_GRACE_SECONDS:
                self._arm(timer, recovered=True, end_now=True)
            else:
                self._arm(timer, restore_only=True)

    async def shutdown(self) -> None:
        """Cancel all timers and restore faded volumes (best effort, 3 s in total)."""
        try:
            timers = await self._repository.list_all()
        except Exception:  # noqa: BLE001
            logger.warning("Sleep timers could not be read on shutdown")
            timers = []
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        restores = [self._restore_on_shutdown(t) for t in timers if t.original_volume]
        if restores:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*restores, return_exceptions=True),
                    SHUTDOWN_RESTORE_SECONDS,
                )
            except TimeoutError:
                logger.warning("Sleep timer volume restore timed out on shutdown")

    # ------------------------------------------------------------------ helpers

    def _lock(self, device_id: str) -> asyncio.Lock:
        return self._locks.setdefault(device_id, asyncio.Lock())

    def _arm(
        self,
        timer: SleepTimer,
        *,
        recovered: bool = False,
        end_now: bool = False,
        restore_only: bool = False,
    ) -> None:
        task = asyncio.create_task(
            self._guarded(timer, recovered, end_now, restore_only),
            name=f"sleep-timer-{timer.device_id}",
        )
        self._tasks[timer.device_id] = task
        task.add_done_callback(
            functools.partial(self._forget_done, timer.device_id, task)
        )

    def _forget_done(
        self, device_id: str, task: asyncio.Task[None], _done: asyncio.Task[None]
    ) -> None:
        if self._tasks.get(device_id) is task:
            del self._tasks[device_id]

    async def _cancel_locked(self, device_id: str, *, restore_volume: bool) -> None:
        task = self._tasks.pop(device_id, None)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        timer = await self._repository.get(device_id)
        if timer is None:
            return
        if restore_volume and timer.original_volume is not None:
            try:
                await self._restore_volume(timer)
            except Exception:  # noqa: BLE001
                logger.warning("Sleep timer could not restore the volume on cancel")
        await self._repository.delete(device_id)
        self._last_set.pop(device_id, None)

    async def _wait_until(self, epoch: float) -> None:
        while True:
            remaining = epoch - self._clock()
            if remaining <= 0:
                return
            await self._sleep(min(WAIT_CHUNK_SECONDS, remaining))

    async def _restore_volume(self, timer: SleepTimer) -> bool:
        """Set the stored volume again unless the user has changed it meanwhile."""
        volume = await self._device_service.get_volume(timer.device_id)
        last = self._last_set.get(timer.device_id)
        untouched = volume.target <= VOLUME_TOLERANCE or (
            last is not None and abs(volume.target - last) <= VOLUME_TOLERANCE
        )
        if not untouched or timer.original_volume is None:
            return False
        await self._device_service.set_volume(timer.device_id, timer.original_volume)
        return True

    async def _restore_on_shutdown(self, timer: SleepTimer) -> None:
        if await self._restore_volume(timer):
            await self._repository.set_original_volume(timer.device_id, None)

    # ------------------------------------------------------------------ the timer

    async def _guarded(
        self, timer: SleepTimer, recovered: bool, end_now: bool, restore_only: bool
    ) -> None:
        try:
            if restore_only:
                await self._restore_late(timer)
            else:
                await self._run(timer, recovered, end_now)
        except asyncio.CancelledError:
            raise
        except DeviceNotFoundError:
            logger.info("Sleep timer ended: device no longer exists")
            await self._finish(timer)
        except Exception:  # noqa: BLE001
            logger.exception("Sleep timer failed")
            await self._finish(timer)

    async def _finish(self, timer: SleepTimer) -> None:
        await self._repository.delete(timer.device_id)
        self._last_set.pop(timer.device_id, None)

    async def _run(self, timer: SleepTimer, recovered: bool, end_now: bool) -> None:
        if end_now:  # the user is presumably still asleep: end first, restore after
            await self._end_sequence(timer)
            return
        if recovered and timer.original_volume is not None:
            await self._undo_interrupted_fade(timer)
        await self._wait_until(timer.fade_start)
        if not await self._fade_out(timer, recovered):
            return
        await self._wait_until(timer.ends_at)
        await self._end_sequence(timer)

    async def _undo_interrupted_fade(self, timer: SleepTimer) -> None:
        """A restart interrupted the fade: give the volume back, then start over."""
        try:
            await retry_unreachable(
                functools.partial(self._restore_volume, timer), self._sleep
            )
        except Exception:  # noqa: BLE001
            logger.warning("Sleep timer could not undo the interrupted fade")
        timer.original_volume = None
        await self._repository.set_original_volume(timer.device_id, None)

    async def _fade_out(self, timer: SleepTimer, recovered: bool) -> bool:
        """Fade to 0. Returns False when the timer must not run its end sequence."""
        seconds = min(timer.fade_seconds, timer.ends_at - self._clock())
        if timer.fade_seconds <= 0 or seconds <= 0:
            return True
        if recovered and seconds < MIN_RECOVERED_FADE_SECONDS:
            return True
        try:
            volume = await retry_unreachable(
                functools.partial(self._device_service.get_volume, timer.device_id),
                self._sleep,
            )
        except DeviceConnectionError:
            logger.error("Sleep timer gave up: device unreachable before the fade")
            await self._finish(timer)
            return False
        if volume.actual <= 0 or volume.muted:
            return True

        timer.original_volume = volume.actual
        await self._repository.set_original_volume(timer.device_id, volume.actual)
        result = await self._fader.fade(
            timer.device_id,
            volume.actual,
            0,
            seconds,
            on_set=functools.partial(self._last_set.__setitem__, timer.device_id),
        )
        if result is FadeResult.MANUAL_CHANGE:
            logger.info("Sleep timer ended without stopping: manual_change")
            await self._finish(timer)
            return False
        if result is FadeResult.DEVICE_ERROR:
            logger.error("Sleep timer gave up: device unreachable during the fade")
            await self._finish(timer)
            return False
        return True

    async def _end_sequence(self, timer: SleepTimer) -> None:
        async with self._lock(timer.device_id):
            try:
                await retry_unreachable(
                    functools.partial(self._end_once, timer), self._sleep
                )
                logger.info("Sleep timer ended (%s)", timer.end_action)
            except DeviceConnectionError:
                logger.error("Sleep timer gave up: device unreachable at the end")
            finally:
                await self._finish(timer)

    async def _end_once(self, timer: SleepTimer) -> None:
        device_id = timer.device_id
        await stop_playback(self._device_service, device_id, self._sleep)
        if timer.original_volume is not None:
            try:
                await self._restore_volume(timer)
            except DeviceConnectionError:
                raise
            except Exception:  # noqa: BLE001
                logger.warning("Sleep timer could not restore the volume")
        if timer.end_action == "standby":
            info = await self._device_service.get_now_playing(device_id)
            if not is_standby(info):
                await self._sleep(POWER_DELAY_SECONDS)
                await self._device_service.press_key(device_id, "POWER", "both")

    async def _restore_late(self, timer: SleepTimer) -> None:
        """A timer that elapsed long ago: only give the volume back (retried)."""
        if timer.original_volume is not None:
            try:
                await retry_unreachable(
                    functools.partial(self._restore_volume, timer), self._sleep
                )
            except DeviceConnectionError:
                # kept: the next start retries; the user's volume is not lost
                logger.error("Sleep timer could not restore the volume (unreachable)")
                return
        await self._finish(timer)
