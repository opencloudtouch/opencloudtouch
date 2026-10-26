"""Stream recovery watchdog.

Internet-radio stations (or servers in between) close the connection after a maximum
listener time; the speaker then reports source ``INVALID_SOURCE``. While enabled, this
service consumes the in-process device events, and when a speaker that has been playing
a preset station for a minimum time suddenly reports ``INVALID_SOURCE`` it presses the
matching preset key again, verifies that playback resumed and records the outcome.

Design notes:
- One ``asyncio.Task`` per device runs a recovery sequence, so the consumer loop is
  never blocked; only one sequence per device is active.
- Clock and sleep are injected; all timings (verification, backoff, subscription
  watchdog) use them, so tests run on virtual time.
- Limitations (documented): events coalesced by the SSE throttle (500 ms), published
  while the subscription was lost, or dropped by a full queue can hide a drop.
"""

import asyncio
import functools
import logging
import time
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    raise_coded,
)
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.streamrecovery.models import (
    OUTCOME_GAVE_UP,
    OUTCOME_RESUMED,
    OUTCOME_SKIPPED_NO_PRESET,
    OUTCOME_SKIPPED_RATE_LIMITED,
    StreamRecoveryConfig,
    StreamRecoveryEvent,
)
from opencloudtouch.streamrecovery.repository import StreamRecoveryRepository

logger = logging.getLogger(__name__)

ELIGIBLE_SOURCES = frozenset({"LOCAL_INTERNET_RADIO", "INTERNET_RADIO"})
INVALID_SOURCE = "INVALID_SOURCE"
PLAY_STATE = "PLAY_STATE"
BUFFERING_STATE = "BUFFERING_STATE"
STOPPED_STATES = frozenset({"STOP_STATE", "PAUSE_STATE"})

VERIFY_SECONDS = 45.0
BACKOFF_SECONDS = 60.0
WINDOW_SECONDS = 3600.0
SUBSCRIPTION_CHECK_SECONDS = 30.0

MIN_PLAY_RANGE = (60, 86400)
ATTEMPTS_RANGE = (1, 10)


def normalize_station(name: str | None) -> str | None:
    """NFKC-normalised, whitespace-collapsed, casefolded station name (None if empty)."""
    if not name:
        return None
    collapsed = " ".join(unicodedata.normalize("NFKC", name).split())
    return collapsed.casefold() or None


def _display_name(name: str | None) -> str | None:
    if not name:
        return None
    return " ".join(unicodedata.normalize("NFKC", name).split()) or None


def _is_int_in(value: Any, low: int, high: int) -> bool:
    return (
        isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    )


@dataclass
class _Track:
    """What the service knows about one device (updated from every NOW_PLAYING)."""

    source: str | None = None
    state: str | None = None
    station_key: str | None = None
    station_name: str | None = None
    play_started: float | None = None


@dataclass
class _Sequence:
    task: asyncio.Task | None = None
    resumed: asyncio.Event = field(default_factory=asyncio.Event)
    aborted: asyncio.Event = field(default_factory=asyncio.Event)


class StreamRecoveryService:
    """Opt-in watchdog that resumes a radio preset after an upstream drop."""

    def __init__(
        self,
        state_manager: DeviceStateManager,
        device_service: Any,
        preset_service: Any,
        repository: StreamRecoveryRepository,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_manager = state_manager
        self._device_service = device_service
        self._preset_service = preset_service
        self._repository = repository
        self._clock = clock
        self._sleep = sleep
        self._now = now or (lambda: datetime.now(UTC))

        self._config = StreamRecoveryConfig()
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[DeviceEvent] | None = None
        self._consumer: asyncio.Task | None = None
        self._watchdog: asyncio.Task | None = None
        self._tracks: dict[str, _Track] = {}
        self._sequences: dict[str, _Sequence] = {}
        self._presses: dict[str, list[float]] = {}

    # ------------------------------------------------------------------ API

    async def get_config(self) -> StreamRecoveryConfig:
        return await self._repository.get_config()

    async def list_events(self, limit: int = 20) -> list[StreamRecoveryEvent]:
        return await self._repository.list_events(limit=limit)

    async def set_config(
        self, enabled: Any, min_play_seconds: Any, max_attempts_per_hour: Any
    ) -> StreamRecoveryConfig:
        """Validate, store and apply a full configuration; the first violation wins."""
        if not _is_int_in(min_play_seconds, *MIN_PLAY_RANGE):
            raise_coded(
                422,
                error_codes.STREAM_RECOVERY_MIN_PLAY_INVALID,
                "'min_play_seconds' must be an integer from 60 to 86400",
                field="min_play_seconds",
            )
        if not _is_int_in(max_attempts_per_hour, *ATTEMPTS_RANGE):
            raise_coded(
                422,
                error_codes.STREAM_RECOVERY_ATTEMPTS_INVALID,
                "'max_attempts_per_hour' must be an integer from 1 to 10",
                field="max_attempts_per_hour",
            )
        async with self._lock:
            stored = await self._repository.set_config(
                bool(enabled), min_play_seconds, max_attempts_per_hour
            )
            self._config = stored
            await self._cancel_sequences()
            if stored.enabled and self._consumer is None:
                self._subscribe_and_run()
            elif stored.enabled:
                self._seed()
            elif self._consumer is not None:
                await self._unsubscribe_and_stop()
            return stored

    async def start(self) -> None:
        """Load the stored configuration; subscribe if the watchdog is enabled."""
        async with self._lock:
            self._config = await self._repository.get_config()
            if self._config.enabled and self._consumer is None:
                self._subscribe_and_run()

    async def stop(self) -> None:
        """Cancel the consumer, the subscription watchdog and every sequence."""
        async with self._lock:
            await self._cancel_sequences()
            await self._unsubscribe_and_stop()

    # ---------------------------------------------------------- lifecycle

    def _is_registered(self, queue: asyncio.Queue[DeviceEvent]) -> bool:
        return queue in self._state_manager._subscribers

    def _subscribe_and_run(self) -> None:
        self._queue = self._state_manager.subscribe()
        self._seed()
        self._consumer = asyncio.create_task(
            self._consume(self._queue), name="stream-recovery-consumer"
        )
        self._watchdog = asyncio.create_task(
            self._watch_subscription(), name="stream-recovery-watchdog"
        )

    async def _unsubscribe_and_stop(self) -> None:
        tasks = [t for t in (self._consumer, self._watchdog) if t is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._consumer = self._watchdog = None
        if self._queue is not None:
            self._state_manager.unsubscribe(self._queue)
            self._queue = None
        self._tracks.clear()

    async def _cancel_sequences(self) -> None:
        tasks = [s.task for s in self._sequences.values() if s.task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._sequences.clear()

    def _seed(self) -> None:
        """Arm devices that are playing a radio station now; never acts."""
        self._tracks.clear()
        for device_id, state in self._state_manager.get_all_states().items():
            info = state.now_playing
            if info is None or info.source not in ELIGIBLE_SOURCES:
                continue
            if info.state not in (PLAY_STATE, BUFFERING_STATE):
                continue
            key = normalize_station(info.station_name)
            if key is None:
                continue  # a nameless tuple arms nothing
            self._tracks[device_id] = _Track(
                source=info.source,
                state=info.state,
                station_key=key,
                station_name=_display_name(info.station_name),
                play_started=self._clock(),
            )

    async def _watch_subscription(self) -> None:
        """subscribe() clears all queues at MAX_SUBSCRIBERS: notice and subscribe again."""
        while True:
            await self._sleep(SUBSCRIPTION_CHECK_SECONDS)
            queue = self._queue
            if queue is None or self._is_registered(queue):
                continue
            async with self._lock:
                if self._queue is not queue or self._is_registered(queue):
                    continue
                logger.warning(
                    "Stream recovery lost its event subscription, subscribing again "
                    "(events in the gap are lost)"
                )
                await self._cancel_sequences()
                if self._consumer is not None:
                    self._consumer.cancel()
                    await asyncio.gather(self._consumer, return_exceptions=True)
                self._queue = self._state_manager.subscribe()
                self._seed()
                self._consumer = asyncio.create_task(
                    self._consume(self._queue), name="stream-recovery-consumer"
                )

    # ----------------------------------------------------------- consuming

    async def _consume(self, queue: asyncio.Queue[DeviceEvent]) -> None:
        while True:
            event = await queue.get()
            try:
                await self._handle(event)
            except Exception:  # noqa: BLE001 - the consumer loop must never die
                logger.exception("Stream recovery failed to process an event")

    def _update_track(self, device_id: str, info: NowPlayingInfo) -> _Track:
        """Apply *info* to the device's track and return a copy of the previous one."""
        track = self._tracks.setdefault(device_id, _Track())
        previous = _Track(**vars(track))
        key = normalize_station(info.station_name)
        now = self._clock()

        if info.source in ELIGIBLE_SOURCES and info.state == PLAY_STATE:
            self._apply_play(track, info, key, now)
        elif info.source in ELIGIBLE_SOURCES and info.state == BUFFERING_STATE:
            self._apply_buffering(track, info, key)
        else:
            track.play_started = None
            track.station_key = None
            track.station_name = None

        track.source = info.source
        track.state = info.state
        return previous

    @staticmethod
    def _apply_play(
        track: _Track, info: NowPlayingInfo, key: str | None, now: float
    ) -> None:
        changed_station = bool(key and track.station_key and key != track.station_key)
        if track.play_started is None or changed_station:
            track.play_started = now
            track.station_key = None
            track.station_name = None
        if key:
            track.station_key = key
            track.station_name = _display_name(info.station_name)

    @staticmethod
    def _apply_buffering(track: _Track, info: NowPlayingInfo, key: str | None) -> None:
        if track.play_started is None or not key:
            return
        if track.station_key and key != track.station_key:
            # another station: a new run starts at PLAY
            track.play_started = None
            track.station_key = track.station_name = None
        elif not track.station_key:
            track.station_key = key
            track.station_name = _display_name(info.station_name)

    async def _handle(self, event: DeviceEvent) -> None:
        if event.event_type != EventType.NOW_PLAYING or event.now_playing is None:
            return
        device_id = event.device_id
        info = event.now_playing
        previous = self._update_track(device_id, info)

        sequence = self._sequences.get(device_id)
        if (
            sequence is not None
            and sequence.task is not None
            and not sequence.task.done()
        ):
            self._steer_sequence(sequence, info)
            return  # further drops while a sequence runs are ignored

        if info.source != INVALID_SOURCE:
            return
        if not self._matches_trigger(previous):
            return
        play_seconds = int(self._clock() - (previous.play_started or self._clock()))
        if await self._device_service.get_device_by_id(device_id) is None:
            return

        sequence = _Sequence()
        sequence.task = asyncio.create_task(
            self._run_sequence(
                sequence,
                device_id,
                previous.station_key,
                previous.station_name,
                play_seconds,
            ),
            name=f"stream-recovery-{device_id}",
        )
        self._sequences[device_id] = sequence
        sequence.task.add_done_callback(
            functools.partial(self._forget_done, device_id, sequence)
        )

    def _forget_done(
        self, device_id: str, sequence: _Sequence, _task: asyncio.Task[None]
    ) -> None:
        if self._sequences.get(device_id) is sequence:
            del self._sequences[device_id]

    def _matches_trigger(self, previous: _Track) -> bool:
        return (
            previous.source in ELIGIBLE_SOURCES
            and previous.state in (PLAY_STATE, BUFFERING_STATE)
            and previous.play_started is not None
            and self._clock() - previous.play_started >= self._config.min_play_seconds
        )

    @staticmethod
    def _steer_sequence(sequence: _Sequence, info: NowPlayingInfo) -> None:
        """Tell a running sequence whether playback resumed or the user took over."""
        if info.source in ELIGIBLE_SOURCES and info.state == PLAY_STATE:
            sequence.resumed.set()
        elif info.source == INVALID_SOURCE:
            return  # the speaker may repeat INVALID_SOURCE
        elif info.source in ELIGIBLE_SOURCES and info.state == BUFFERING_STATE:
            return  # neither counts as resumed nor ends the sequence
        else:
            sequence.aborted.set()  # STOP/PAUSE/STANDBY or another source

    # ----------------------------------------------------------- sequence

    def _still_invalid(self, device_id: str) -> bool:
        track = self._tracks.get(device_id)
        return track is not None and track.source == INVALID_SOURCE

    def _presses_in_window(self, device_id: str) -> int:
        now = self._clock()
        recent = [
            t for t in self._presses.get(device_id, []) if now - t < WINDOW_SECONDS
        ]
        self._presses[device_id] = recent
        return len(recent)

    async def _find_preset(self, device_id: str, station_key: str | None):
        if station_key is None:
            return None
        for preset in await self._preset_service.get_all_presets(device_id):
            if normalize_station(preset.station_name) == station_key:
                return preset
        return None

    async def _press(self, device_id: str, preset_number: int) -> str | None:
        """Press PRESET_n; returns the error code of a failed press, else None."""
        try:
            await self._device_service.press_key(
                device_id, f"PRESET_{preset_number}", "both"
            )
            return None
        except DeviceNotFoundError:
            return error_codes.DEVICE_NOT_FOUND
        except (
            DeviceConnectionError,
            httpx.TransportError,
            OSError,
        ):  # incl. TimeoutError
            return error_codes.DEVICE_UNREACHABLE
        except Exception as e:  # noqa: BLE001
            # mapped to a code; the exception text is never stored
            logger.warning("Stream recovery key press failed (%s)", type(e).__name__)
            return error_codes.STREAM_RECOVERY_FAILED

    async def _wait_outcome(self, sequence: _Sequence, seconds: float) -> str:
        waiters = [
            asyncio.ensure_future(sequence.resumed.wait()),
            asyncio.ensure_future(sequence.aborted.wait()),
            asyncio.ensure_future(self._sleep(seconds)),
        ]
        try:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for waiter in waiters:
                waiter.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
        if sequence.resumed.is_set():
            return "resumed"
        if sequence.aborted.is_set():
            return "aborted"
        return "timeout"

    async def _record(
        self,
        device_id: str,
        outcome: str,
        *,
        preset_number: int | None,
        station_name: str | None,
        play_seconds: int | None,
        attempts: int = 0,
        error_code: str | None = None,
    ) -> None:
        try:
            await self._repository.add_event(
                StreamRecoveryEvent(
                    occurred_at=self._now()
                    .astimezone(UTC)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    device_id=device_id,
                    outcome=outcome,
                    preset_number=preset_number,
                    station_name=station_name,
                    play_seconds=play_seconds,
                    attempts=attempts,
                    error_code=error_code,
                )
            )
        except Exception:  # noqa: BLE001 - never lose the sequence over a log row
            logger.exception("Stream recovery could not store an event")
            return
        if outcome in (OUTCOME_RESUMED, OUTCOME_GAVE_UP):
            logger.info(
                "Stream recovery %s: device=%s preset=%s station=%s attempts=%d",
                outcome,
                device_id,
                preset_number,
                station_name,
                attempts,
            )

    async def _run_sequence(
        self,
        sequence: _Sequence,
        device_id: str,
        station_key: str | None,
        station_name: str | None,
        play_seconds: int,
    ) -> None:
        try:
            preset = await self._find_preset(device_id, station_key)
            if preset is None:
                await self._record(
                    device_id,
                    OUTCOME_SKIPPED_NO_PRESET,
                    preset_number=None,
                    station_name=station_name,
                    play_seconds=play_seconds,
                )
                return
            number = preset.preset_number
            details = {
                "preset_number": number,
                "station_name": station_name,
                "play_seconds": play_seconds,
            }
            cap = self._config.max_attempts_per_hour
            if self._presses_in_window(device_id) >= cap:
                await self._record(device_id, OUTCOME_SKIPPED_RATE_LIMITED, **details)
                return

            attempts = 0
            while True:
                if not self._still_invalid(device_id):
                    return  # the user stopped, powered off or started something else
                sequence.resumed.clear()
                sequence.aborted.clear()
                attempts += 1
                self._presses.setdefault(device_id, []).append(self._clock())
                error_code = await self._press(device_id, number)

                outcome = await self._wait_outcome(sequence, VERIFY_SECONDS)
                if outcome == "resumed":
                    await self._record(
                        device_id, OUTCOME_RESUMED, attempts=attempts, **details
                    )
                    return
                if outcome == "aborted":
                    return
                if self._presses_in_window(device_id) >= cap:
                    await self._record(
                        device_id,
                        OUTCOME_GAVE_UP,
                        attempts=attempts,
                        error_code=error_code,
                        **details,
                    )
                    return
                await self._sleep(BACKOFF_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - nothing may propagate out of the task
            logger.exception("Stream recovery sequence for %s failed", device_id)
