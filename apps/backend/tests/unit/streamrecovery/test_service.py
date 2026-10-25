"""StreamRecoveryService: trigger signature, sequences, limits and lifecycle."""

import asyncio
import logging

import httpx
import pytest

from opencloudtouch.core.exceptions import (
    CodedApiError,
    DeviceConnectionError,
    DeviceNotFoundError,
)
from opencloudtouch.devices.websocket.parser import EventType
from tests.unit.streamrecovery.conftest import (
    DEVICE,
    events_of,
    finish,
    make_preset,
    now_playing_event,
    settle,
)

RADIO = "LOCAL_INTERNET_RADIO"
STATION = "Radio X"
SIX_HOURS = 21600


async def play(feed, vtime, seconds=SIX_HOURS, *, source=RADIO, station=STATION):
    """The device starts playing *station* and keeps playing for *seconds*."""
    await feed(now_playing_event(source, "PLAY_STATE", station))
    vtime.jump(seconds)


async def drop(feed, *, buffering_first=True):
    """The station closes the connection: BUFFERING (optional), then INVALID_SOURCE."""
    if buffering_first:
        await feed(now_playing_event(RADIO, "BUFFERING_STATE"))
    await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))


def keys(devices):
    return [press[1] for press in devices.presses]


class TestConfig:
    @pytest.mark.asyncio
    async def test_defaults_and_persistence(self, service):
        config = await service.get_config()
        assert (
            config.enabled,
            config.min_play_seconds,
            config.max_attempts_per_hour,
        ) == (
            False,
            600,
            3,
        )
        assert config.updated_at is None

        stored = await service.set_config(True, 300, 2)
        assert stored.updated_at is not None
        assert await service.get_config() == stored

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad",
        [59, 86401, "x", None, 600.5, True, -1],
    )
    async def test_invalid_min_play_seconds(self, service, bad):
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_config(True, bad, 3)
        assert excinfo.value.status_code == 422
        assert excinfo.value.code == "stream_recovery_min_play_invalid"
        assert excinfo.value.field == "min_play_seconds"
        assert (await service.get_config()).updated_at is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [0, 11, "3", None, 2.5, False])
    async def test_invalid_max_attempts(self, service, bad):
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_config(True, 600, bad)
        assert excinfo.value.code == "stream_recovery_attempts_invalid"
        assert excinfo.value.field == "max_attempts_per_hour"

    @pytest.mark.asyncio
    async def test_first_violation_wins(self, service):
        with pytest.raises(CodedApiError) as excinfo:
            await service.set_config(True, 1, 99)
        assert excinfo.value.code == "stream_recovery_min_play_invalid"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [60, 86400])
    async def test_range_limits_are_inclusive(self, service, value):
        assert (await service.set_config(False, value, 1)).min_play_seconds == value
        assert (await service.set_config(False, 600, 10)).max_attempts_per_hour == 10


class TestTriggerAndResume:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("source", ["LOCAL_INTERNET_RADIO", "INTERNET_RADIO"])
    async def test_drop_presses_the_matching_preset_and_records_resumed(
        self, service, enabled, feed, vtime, devices, repository, source
    ):
        await enabled()
        await feed(now_playing_event(source, "PLAY_STATE", STATION))
        vtime.jump(SIX_HOURS)
        await feed(now_playing_event(source, "BUFFERING_STATE"))

        await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))  # no station name

        assert [(p[0], p[1], p[2]) for p in devices.presses] == [
            (DEVICE, "PRESET_2", "both")
        ]
        await feed(now_playing_event(source, "PLAY_STATE", STATION))
        (event,) = await events_of(repository)
        assert event.outcome == "resumed"
        assert event.attempts == 1
        assert event.play_seconds == SIX_HOURS
        assert event.preset_number == 2
        assert event.station_name == STATION
        assert event.device_id == DEVICE
        assert event.error_code is None
        assert event.occurred_at == "2026-10-26T05:52:08Z"

    @pytest.mark.asyncio
    async def test_resumed_is_logged_at_info_without_urls_or_ips(
        self, service, enabled, feed, vtime, repository, caplog
    ):
        await enabled()
        await play(feed, vtime)
        with caplog.at_level(
            logging.INFO, logger="opencloudtouch.streamrecovery.service"
        ):
            await drop(feed)
            await feed(now_playing_event(RADIO, "PLAY_STATE", STATION))
            await finish(service)
        text = caplog.text
        assert DEVICE in text and "2" in text and STATION in text
        assert "http" not in text

    @pytest.mark.asyncio
    async def test_buffering_does_not_count_as_resumed(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled(max_attempts=1)
        await play(feed, vtime)
        await drop(feed)

        await feed(now_playing_event(RADIO, "BUFFERING_STATE", STATION))
        await vtime.advance(45)

        (event,) = await events_of(repository)
        assert event.outcome == "gave_up"

    @pytest.mark.asyncio
    async def test_a_play_state_that_arrived_before_the_press_does_not_count(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled(max_attempts=1)
        await play(feed, vtime)
        await feed(now_playing_event(RADIO, "BUFFERING_STATE"))
        await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        # the press already happened; nothing new arrives within the window
        await vtime.advance(45)

        (event,) = await events_of(repository)
        assert event.outcome == "gave_up"

    @pytest.mark.asyncio
    async def test_station_key_is_the_last_name_of_the_play_run(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled()
        await feed(now_playing_event(RADIO, "PLAY_STATE", STATION))
        await feed(now_playing_event(RADIO, "PLAY_STATE", None))  # nameless update
        await feed(
            now_playing_event(
                RADIO,
                "METADATA_ENRICHED",
                "Other FM",
                event_type=EventType.METADATA_ENRICHED,
            )
        )
        vtime.jump(SIX_HOURS)
        await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))

        assert keys(devices) == ["PRESET_2"]

    @pytest.mark.asyncio
    async def test_matching_ignores_case_and_whitespace(
        self, service, enabled, feed, vtime, devices, presets
    ):
        presets.presets[DEVICE] = [make_preset(4, "  RADIO   x ")]
        await enabled()
        await play(feed, vtime, station="radio x")
        await drop(feed)
        assert keys(devices) == ["PRESET_4"]

    @pytest.mark.asyncio
    async def test_switching_station_inside_a_run_restarts_the_play_timer(
        self, service, enabled, feed, vtime, devices
    ):
        await enabled()
        await play(feed, vtime, seconds=SIX_HOURS, station="Other FM")
        await feed(now_playing_event(RADIO, "PLAY_STATE", STATION))  # user switched
        vtime.jump(60)
        await drop(feed)
        assert devices.presses == []  # only 60 s on the new station


class TestSequenceAndLimits:
    @pytest.mark.asyncio
    async def test_worked_timeline_with_two_attempts(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled(max_attempts=2)
        await play(feed, vtime)
        start = vtime.t
        await drop(feed)  # t=0: press 1
        await vtime.advance(45)  # no resume
        await vtime.advance(60)  # backoff -> press 2 at t=105
        await vtime.advance(45)  # no resume by t=150 -> gave_up
        await finish(service)

        assert [round(p[3] - start) for p in devices.presses] == [0, 105]
        (event,) = await events_of(repository)
        assert (event.outcome, event.attempts, event.error_code) == ("gave_up", 2, None)

        # a new drop at t=1000 finds the cap exhausted
        await feed(now_playing_event(RADIO, "STOP_STATE"))
        vtime.jump(150)  # t=300
        await feed(now_playing_event(RADIO, "PLAY_STATE", STATION))
        vtime.jump(700)  # t=1000 (700 s played)
        assert round(vtime.t - start) == 1000
        await drop(feed)
        await finish(service)
        assert len(devices.presses) == 2
        newest = (await events_of(repository))[0]
        assert newest.outcome == "skipped_rate_limited"
        assert newest.attempts == 0

    @pytest.mark.asyncio
    async def test_repeated_invalid_source_events_start_no_second_sequence(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled(max_attempts=3)
        await play(feed, vtime)
        await drop(feed)
        for _ in range(3):
            await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        assert len(devices.presses) == 1
        assert await events_of(repository) == []
        sequences = [
            t
            for t in asyncio.all_tasks()
            if t.get_name() == f"stream-recovery-{DEVICE}"
        ]
        assert len(sequences) == 1

    @pytest.mark.asyncio
    async def test_cap_is_counted_per_hour_in_a_sliding_window(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled(max_attempts=1)
        await play(feed, vtime)
        await drop(feed)
        await vtime.advance(45)  # gave up after press 1
        await finish(service)
        assert len(devices.presses) == 1

        vtime.jump(3601)  # an hour later the press no longer counts
        await feed(now_playing_event(RADIO, "STOP_STATE"))
        await play(feed, vtime)
        await drop(feed)
        assert len(devices.presses) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "interruption",
        [
            ("LOCAL_INTERNET_RADIO", "STOP_STATE"),
            ("STANDBY", "STANDBY"),
            ("BLUETOOTH", "PLAY_STATE"),
            ("TUNEIN", "PLAY_STATE"),
            ("SPOTIFY", "PLAY_STATE"),
        ],
    )
    @pytest.mark.parametrize("when", ["verification", "backoff"])
    async def test_user_action_ends_the_sequence_silently(
        self, service, enabled, feed, vtime, devices, repository, interruption, when
    ):
        await enabled(max_attempts=3)
        await play(feed, vtime)
        await drop(feed)
        if when == "backoff":
            await vtime.advance(45)  # verification failed -> backoff running
        source, state = interruption

        await feed(now_playing_event(source, state))
        await vtime.advance(120)

        assert len(devices.presses) == 1  # no further press
        assert await events_of(repository) == []  # and no event, not even resumed

    @pytest.mark.asyncio
    async def test_resumption_must_come_after_the_press(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled()
        await play(feed, vtime)
        await drop(feed)
        await feed(now_playing_event(RADIO, "PLAY_STATE", STATION))
        (event,) = await events_of(repository)
        assert event.outcome == "resumed"


class TestNoTrigger:
    @pytest.mark.asyncio
    async def test_short_play_does_not_match(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled(min_play_seconds=600)
        await play(feed, vtime, seconds=599)
        await drop(feed)
        assert devices.presses == [] and await events_of(repository) == []

    @pytest.mark.asyncio
    async def test_exactly_min_play_seconds_matches(
        self, service, enabled, feed, vtime, devices
    ):
        await enabled(min_play_seconds=600)
        await play(feed, vtime, seconds=600)
        await drop(feed)
        assert keys(devices) == ["PRESET_2"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("state", ["STOP_STATE", "PAUSE_STATE", "STANDBY"])
    async def test_previous_state_not_playing(
        self, service, enabled, feed, vtime, devices, repository, state
    ):
        await enabled()
        await play(feed, vtime)
        await feed(now_playing_event(RADIO, state, STATION))
        await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        assert devices.presses == [] and await events_of(repository) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("source", ["TUNEIN", "BLUETOOTH", "AUX", "SPOTIFY"])
    async def test_other_sources_are_not_handled(
        self, service, enabled, feed, vtime, devices, repository, source
    ):
        await enabled()
        await play(feed, vtime, source=source)
        await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        assert devices.presses == [] and await events_of(repository) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("new_source", ["UNKNOWN", "TUNEIN", "STANDBY"])
    async def test_a_new_source_other_than_invalid_source(
        self, service, enabled, feed, vtime, devices, repository, new_source
    ):
        await enabled()
        await play(feed, vtime)
        await feed(now_playing_event(new_source, "PLAY_STATE"))
        assert devices.presses == [] and await events_of(repository) == []

    @pytest.mark.asyncio
    async def test_disabled_service_never_presses(self, service, feed, vtime, devices):
        await play(feed, vtime)
        await drop(feed)
        assert devices.presses == []

    @pytest.mark.asyncio
    async def test_other_event_types_are_ignored(
        self, service, enabled, feed, vtime, devices
    ):
        await enabled()
        await play(feed, vtime)
        await feed(
            now_playing_event(
                "INVALID_SOURCE", "PLAY_STATE", event_type=EventType.VOLUME
            )
        )
        assert devices.presses == []

    @pytest.mark.asyncio
    async def test_unknown_device_gives_no_action_and_no_event(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled()
        await play(feed, vtime)
        devices.missing_devices.add(DEVICE)
        await drop(feed)
        assert devices.presses == [] and await events_of(repository) == []

    @pytest.mark.asyncio
    async def test_throttle_coalescing_hides_the_drop_but_spaced_events_show_it(
        self, service, enabled, state_manager, vtime, devices
    ):
        await enabled()
        await state_manager.on_event(now_playing_event(RADIO, "PLAY_STATE", STATION))
        vtime.jump(SIX_HOURS)

        # INVALID_SOURCE is replaced by PLAY inside the 500 ms window: last event wins
        await state_manager.on_event(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        await state_manager.on_event(now_playing_event(RADIO, "PLAY_STATE", STATION))
        await asyncio.sleep(0.7)  # real time: the delayed publish carries only PLAY
        await settle()
        assert devices.presses == []

        vtime.jump(SIX_HOURS)  # the delayed PLAY restarted the play timer
        await asyncio.sleep(0.55)  # cooldown over: the next event goes out at once
        await state_manager.on_event(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        await settle()
        assert keys(devices) == ["PRESET_2"]


class TestSkippedNoPreset:
    @pytest.mark.asyncio
    async def test_no_matching_preset(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled()
        await play(feed, vtime, station="Unknown Station")
        await drop(feed)
        (event,) = await events_of(repository)
        assert (event.outcome, event.station_name, event.preset_number) == (
            "skipped_no_preset",
            "Unknown Station",
            None,
        )
        assert devices.presses == []

    @pytest.mark.asyncio
    async def test_no_station_name_ever_seen(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled()
        await feed(now_playing_event(RADIO, "PLAY_STATE", None))
        vtime.jump(SIX_HOURS)
        await drop(feed)
        (event,) = await events_of(repository)
        assert event.outcome == "skipped_no_preset"
        assert event.station_name is None
        assert devices.presses == []


class TestPressErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (DeviceNotFoundError(DEVICE), "device_not_found"),
            (DeviceConnectionError("1.2.3.4", "x"), "device_unreachable"),
            (TimeoutError(), "device_unreachable"),
            (httpx.ConnectError("boom"), "device_unreachable"),
            (OSError("boom"), "device_unreachable"),
            (RuntimeError("boom"), "stream_recovery_failed"),
        ],
    )
    async def test_gave_up_carries_the_code_of_the_last_press(
        self, service, enabled, feed, vtime, devices, repository, error, code
    ):
        await enabled(max_attempts=1)
        devices.press_errors = [error]
        await play(feed, vtime)
        await drop(feed)
        await vtime.advance(45)

        (event,) = await events_of(repository)
        assert (event.outcome, event.error_code, event.attempts) == ("gave_up", code, 1)
        assert "boom" not in repr(event) and "1.2.3.4" not in repr(event)

    @pytest.mark.asyncio
    async def test_the_last_press_decides_and_the_consumer_survives(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled(max_attempts=2)
        devices.press_errors = [RuntimeError("first"), None]  # second press succeeds
        await play(feed, vtime)
        await drop(feed)
        await vtime.advance(45)
        await vtime.advance(60)
        await vtime.advance(45)

        await finish(service)
        (event,) = await events_of(repository)
        assert (event.outcome, event.error_code) == ("gave_up", None)

        # the consumer loop is still alive afterwards (and the cap of 2 is used up)
        await feed(now_playing_event(RADIO, "STOP_STATE"))
        await play(feed, vtime, seconds=700)
        await drop(feed)
        await finish(service)
        assert (await events_of(repository))[0].outcome == "skipped_rate_limited"


class TestSeedingAndLifecycle:
    @pytest.mark.asyncio
    async def test_enabling_while_playing_seeds_play_started_without_pressing(
        self, service, feed, vtime, devices, state_manager
    ):
        state_manager.update_now_playing(
            DEVICE, now_playing_event(RADIO, "PLAY_STATE", STATION).now_playing
        )
        await service.set_config(True, 600, 3)

        await drop(feed)  # seeded 'now': far less than 600 s played
        assert devices.presses == []

        state_manager.update_now_playing(
            DEVICE, now_playing_event(RADIO, "PLAY_STATE", STATION).now_playing
        )
        await service.set_config(True, 600, 3)  # reconfigure re-seeds
        await feed(now_playing_event(RADIO, "PLAY_STATE", STATION))
        vtime.jump(601)
        await drop(feed)
        assert keys(devices) == ["PRESET_2"]

    @pytest.mark.asyncio
    async def test_seed_with_invalid_source_or_nameless_tuple_arms_nothing(
        self, service, feed, vtime, devices, repository, state_manager
    ):
        state_manager.update_now_playing(
            DEVICE, now_playing_event("INVALID_SOURCE", "PLAY_STATE").now_playing
        )
        state_manager.update_now_playing(
            "OTHER",
            now_playing_event(RADIO, "PLAY_STATE", None, device_id="OTHER").now_playing,
        )
        await service.set_config(True, 600, 3)
        vtime.jump(SIX_HOURS)

        await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        await feed(now_playing_event("INVALID_SOURCE", "PLAY_STATE", device_id="OTHER"))
        assert devices.presses == [] and await events_of(repository) == []

    @pytest.mark.asyncio
    async def test_reconfigure_cancels_pending_sequences_without_events(
        self, service, enabled, feed, vtime, devices, repository
    ):
        await enabled()
        await play(feed, vtime)
        await drop(feed)
        assert len(devices.presses) == 1

        await service.set_config(True, 900, 3)
        await vtime.advance(200)

        assert len(devices.presses) == 1
        assert await events_of(repository) == []
        assert not [
            t
            for t in asyncio.all_tasks()
            if t.get_name() == f"stream-recovery-{DEVICE}"
        ]

    @pytest.mark.asyncio
    async def test_disabling_unsubscribes_and_later_events_do_nothing(
        self, service, enabled, feed, vtime, devices, state_manager
    ):
        await enabled()
        assert len(state_manager._subscribers) == 1
        await play(feed, vtime)

        await service.set_config(False, 600, 3)

        assert state_manager._subscribers == []
        await drop(feed)
        assert devices.presses == []

    @pytest.mark.asyncio
    async def test_resubscribes_after_the_manager_cleared_all_queues(
        self, service, enabled, feed, vtime, devices, state_manager, caplog
    ):
        await enabled()
        await play(feed, vtime)
        for _ in range(20):  # the 21st subscribe clears every queue, including ours
            state_manager.subscribe()
        assert not service._is_registered(service._queue)

        with caplog.at_level(logging.WARNING):
            await drop(feed)  # published during the gap
            assert devices.presses == []
            await vtime.advance(31)

        assert service._is_registered(service._queue)
        assert "subscribe" in caplog.text.lower()
        # re-seeded without acting: no press for the gap event
        assert devices.presses == []

    @pytest.mark.asyncio
    async def test_stop_finishes_all_tasks(
        self, state_manager, devices, presets, repository, vtime
    ):
        from opencloudtouch.streamrecovery.service import StreamRecoveryService

        svc = StreamRecoveryService(
            state_manager,
            devices,
            presets,
            repository,
            clock=vtime.clock,
            sleep=vtime.sleep,
        )
        await svc.start()
        await svc.set_config(True, 600, 3)
        await play(lambda e: state_manager.publish(e), vtime)
        await state_manager.publish(now_playing_event("INVALID_SOURCE", "PLAY_STATE"))
        await settle()

        await svc.stop()

        names = [t.get_name() for t in asyncio.all_tasks() if not t.done()]
        assert not [n for n in names if n.startswith("stream-recovery")]
        assert state_manager._subscribers == []

    @pytest.mark.asyncio
    async def test_start_with_stored_enabled_config_subscribes(
        self, state_manager, devices, presets, repository, vtime
    ):
        from opencloudtouch.streamrecovery.service import StreamRecoveryService

        await repository.set_config(True, 600, 3)
        svc = StreamRecoveryService(
            state_manager,
            devices,
            presets,
            repository,
            clock=vtime.clock,
            sleep=vtime.sleep,
        )
        await svc.start()
        try:
            assert len(state_manager._subscribers) == 1
        finally:
            await svc.stop()
