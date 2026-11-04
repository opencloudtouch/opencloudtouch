"""SleepTimerService behaviour on a virtual clock (acceptance criteria A.6 1-10)."""

import asyncio
import logging

import pytest

from opencloudtouch.core.exceptions import CodedApiError, DeviceNotFoundError
from opencloudtouch.sleep_timer.models import SleepTimer
from tests.unit.helpers.fake_playback import unreachable
from tests.unit.sleep_timer.conftest import DEVICE, drain, fade_values

THIRTY_MINUTES = 30 * 60


async def run_to_end(service, vtime, seconds=THIRTY_MINUTES + 5):
    await vtime.advance(seconds)
    await drain(service)


class TestFullRun:
    @pytest.mark.asyncio
    async def test_fades_pauses_and_restores_the_volume(
        self, service, vtime, devices, repository
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")

        await run_to_end(service, vtime)

        sets = devices.volumes_set()
        assert sets[:-1] == fade_values(40, 0, 30)
        assert sets[-1] == 40  # restored after the pause
        assert devices.volume == 40
        assert devices.keys() == ["PAUSE"]
        assert devices.state == "PAUSE_STATE"
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_nothing_happens_before_the_fade_starts(
        self, service, vtime, devices
    ):
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 30 - 1)
        assert devices.volumes_set() == []
        assert devices.keys() == []

    @pytest.mark.asyncio
    async def test_original_volume_is_stored_before_the_first_step(
        self, service, vtime, devices, repository
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 28)
        row = await repository.get(DEVICE)
        assert row.original_volume == 40
        assert devices.volumes_set() != []

    @pytest.mark.asyncio
    async def test_standby_end_action_order(self, service, vtime, devices):
        devices.volume = 40
        order: list[str] = []
        devices.on_call = lambda name, args: order.append(
            f"{name}:{args[0]}" if args else name
        )
        await service.start(DEVICE, 30, 30, "standby")
        await run_to_end(service, vtime)

        pause = order.index("press_key:PAUSE")
        restore = len(order) - 1 - order[::-1].index("set_volume:40")
        power = order.index("press_key:POWER")
        assert pause < restore < power
        assert devices.source == "STANDBY"

    @pytest.mark.asyncio
    async def test_standby_waits_one_second_before_power(self, service, vtime, devices):
        await service.start(DEVICE, 1, 0, "standby")
        seen: list[float] = []
        devices.on_call = lambda name, args: (
            seen.append(vtime.t) if args and args[0] == "POWER" else None
        )
        pause_time: list[float] = []
        original = devices.on_call

        def record(name, args):
            if args and args[0] == "PAUSE":
                pause_time.append(vtime.t)
            original(name, args)

        devices.on_call = record
        await run_to_end(service, vtime, 70)
        assert seen[0] - pause_time[0] >= 3  # 2 s pause settle + 1 s power delay

    @pytest.mark.asyncio
    async def test_a_device_in_standby_gets_no_power_key(self, service, vtime, devices):
        devices.source, devices.state = "STANDBY", "STOP_STATE"
        await service.start(DEVICE, 1, 0, "standby")
        await run_to_end(service, vtime, 70)
        assert devices.keys() == []

    @pytest.mark.asyncio
    async def test_no_pause_when_the_device_is_not_playing_at_the_end(
        self, service, vtime, devices
    ):
        await service.start(DEVICE, 1, 0, "stop")
        devices.state = "STOP_STATE"
        await run_to_end(service, vtime, 70)
        assert devices.keys() == []

    @pytest.mark.asyncio
    async def test_stop_is_sent_when_pause_leaves_play_state(
        self, service, vtime, devices
    ):
        devices.key_effects = {"PAUSE": "PLAY_STATE", "STOP": "STOP_STATE"}
        await service.start(DEVICE, 1, 0, "stop")
        await run_to_end(service, vtime, 70)
        assert devices.keys() == ["PAUSE", "STOP"]

    @pytest.mark.asyncio
    async def test_waits_in_chunks_of_at_most_thirty_seconds(self, service, vtime):
        waits: list[float] = []
        original = vtime.sleep

        async def spy(seconds):
            waits.append(seconds)
            await original(seconds)

        service._sleep = spy
        await service.start(DEVICE, 10, 0, "stop")
        await vtime.advance(600 + 5)
        assert waits
        assert max(waits) <= 30


class TestNoFade:
    @pytest.mark.asyncio
    async def test_zero_fade_means_no_volume_change_and_no_restore(
        self, service, vtime, devices
    ):
        await service.start(DEVICE, 1, 0, "stop")
        await run_to_end(service, vtime, 70)
        assert devices.volumes_set() == []
        assert devices.keys() == ["PAUSE"]

    @pytest.mark.asyncio
    async def test_silent_device_is_not_faded_or_restored(
        self, service, vtime, devices, repository
    ):
        devices.volume = 0
        await service.start(DEVICE, 2, 30, "stop")
        await vtime.advance(100)
        assert (await repository.get(DEVICE)).original_volume is None
        await run_to_end(service, vtime, 40)
        assert devices.volumes_set() == []

    @pytest.mark.asyncio
    async def test_muted_device_is_not_faded_or_restored(self, service, vtime, devices):
        devices.muted = True
        await service.start(DEVICE, 2, 30, "stop")
        await run_to_end(service, vtime, 130)
        assert devices.volumes_set() == []
        assert devices.keys() == ["PAUSE"]


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_mid_fade_restores_the_volume(
        self, service, vtime, devices, repository
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 15)
        assert devices.volume < 40

        await service.cancel(DEVICE)

        assert devices.volume == 40
        assert await repository.get(DEVICE) is None
        await vtime.advance(100)  # nothing fires afterwards
        assert devices.keys() == []

    @pytest.mark.asyncio
    async def test_cancel_is_idempotent(self, service, devices):
        await service.cancel(DEVICE)
        await service.start(DEVICE, 5, 0, "stop")
        await service.cancel(DEVICE)
        await service.cancel(DEVICE)

    @pytest.mark.asyncio
    async def test_cancel_without_restore_leaves_the_volume(
        self, service, vtime, devices
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 15)
        faded = devices.volume
        await service.cancel(DEVICE, restore_volume=False)
        assert devices.volume == faded

    @pytest.mark.asyncio
    async def test_cancel_does_not_touch_a_volume_the_user_changed(
        self, service, vtime, devices
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 15)
        devices.volume = 75  # the user turned it up
        await service.cancel(DEVICE)
        assert devices.volume == 75

    @pytest.mark.asyncio
    async def test_cancel_waits_for_a_running_end_sequence(
        self, service, vtime, devices, repository
    ):
        release = asyncio.Event()
        entered = asyncio.Event()
        original = devices.press_key

        async def slow_press(device_id, key, state="both"):
            entered.set()
            await release.wait()
            await original(device_id, key, state)

        devices.press_key = slow_press
        await service.start(DEVICE, 1, 0, "stop")
        await vtime.advance(61)
        await asyncio.wait_for(entered.wait(), 2)

        cancel = asyncio.create_task(service.cancel(DEVICE))
        await asyncio.sleep(0.05)
        assert not cancel.done()  # it waits, it does not interrupt

        release.set()
        await vtime.advance(3)  # the 2 s pause settle of the end sequence
        await asyncio.wait_for(cancel, 2)
        await drain(service)
        assert devices.state == "PAUSE_STATE"
        assert await repository.get(DEVICE) is None


class TestManualChangeAndReplace:
    @pytest.mark.asyncio
    async def test_manual_volume_change_ends_the_timer_without_stopping(
        self, service, vtime, devices, repository
    ):
        devices.volume = 40

        def user_turns_it_up(name, _args):
            if name == "get_volume" and len(devices.volumes_set()) == 4:
                devices.volume = 90
                devices.on_call = None

        devices.on_call = user_turns_it_up
        await service.start(DEVICE, 30, 30, "stop")
        await run_to_end(service, vtime)

        assert devices.volume == 90
        assert devices.keys() == []
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_replace_restores_first_and_new_v0_is_the_pre_fade_volume(
        self, service, vtime, devices, repository
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 15)
        assert devices.volume < 40

        await service.start(DEVICE, 10, 30, "stop")

        assert devices.volume == 40
        await vtime.advance(10 * 60 - 28)
        assert (await repository.get(DEVICE)).original_volume == 40

    @pytest.mark.asyncio
    async def test_only_one_timer_per_device(self, service, vtime, devices):
        await service.start(DEVICE, 1, 0, "stop")
        first = service._tasks[DEVICE]
        await service.start(DEVICE, 2, 0, "stop")
        await asyncio.sleep(0)
        assert first.cancelled() or first.done()
        assert len(service._tasks) == 1


class TestValidationAndErrors:
    @pytest.mark.asyncio
    async def test_fade_longer_than_the_duration_is_a_coded_error(self, service):
        with pytest.raises(CodedApiError) as caught:
            await service.start(DEVICE, 1, 61, "stop")
        assert caught.value.code == "sleep_timer_fade_too_long"
        assert caught.value.field == "fade_seconds"

    @pytest.mark.asyncio
    async def test_fade_equal_to_the_duration_is_allowed(self, service):
        timer = await service.start(DEVICE, 1, 60, "stop")
        assert timer.fade_seconds == 60

    @pytest.mark.asyncio
    async def test_unknown_device(self, service, devices):
        devices.missing = True
        with pytest.raises(DeviceNotFoundError):
            await service.start(DEVICE, 5, 0, "stop")
        with pytest.raises(DeviceNotFoundError):
            await service.get(DEVICE)

    @pytest.mark.asyncio
    async def test_unreachable_device_at_start(self, service, devices, repository):
        devices.fail("get_volume", unreachable())
        with pytest.raises(type(unreachable())):
            await service.start(DEVICE, 5, 0, "stop")
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_a_step_is_retried_and_the_timer_still_completes(
        self, service, vtime, devices
    ):
        devices.volume = 40
        sets = {"n": 0}

        def fail_seventh(name, _args):
            if name == "set_volume":
                sets["n"] += 1
                if sets["n"] == 7:
                    devices.fail("set_volume", unreachable(), unreachable())

        devices.on_call = fail_seventh
        await service.start(DEVICE, 30, 30, "stop")
        await run_to_end(service, vtime, THIRTY_MINUTES + 200)
        assert devices.keys() == ["PAUSE"]

    @pytest.mark.asyncio
    async def test_retries_exhausted_during_the_fade_gives_up(
        self, service, vtime, devices, repository, caplog
    ):
        devices.volume = 40
        sets = {"n": 0}

        def fail_from_seventh(name, _args):
            if name == "set_volume":
                sets["n"] += 1
                if sets["n"] == 7:
                    devices.fail("set_volume", *[unreachable()] * 4)

        devices.on_call = fail_from_seventh
        with caplog.at_level(logging.ERROR):
            await service.start(DEVICE, 30, 30, "stop")
            await run_to_end(service, vtime, THIRTY_MINUTES + 200)

        assert devices.keys() == []
        assert await repository.get(DEVICE) is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    @pytest.mark.asyncio
    async def test_end_sequence_failure_is_retried_then_logged(
        self, service, vtime, devices, repository, caplog
    ):
        devices.fail("press_key", *[unreachable()] * 4)
        with caplog.at_level(logging.ERROR):
            await service.start(DEVICE, 1, 0, "stop")
            await run_to_end(service, vtime, 200)
        assert await repository.get(DEVICE) is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    @pytest.mark.asyncio
    async def test_end_sequence_recovers_from_a_transient_failure(
        self, service, vtime, devices
    ):
        devices.fail("press_key", unreachable())
        await service.start(DEVICE, 1, 0, "stop")
        await run_to_end(service, vtime, 200)
        assert devices.state == "PAUSE_STATE"

    @pytest.mark.asyncio
    async def test_device_removed_before_firing_deletes_the_row(
        self, service, vtime, devices, repository
    ):
        await service.start(DEVICE, 1, 0, "stop")
        devices.missing = True
        await run_to_end(service, vtime, 70)
        assert await repository.get(DEVICE) is None


class TestRestart:
    @pytest.mark.asyncio
    async def test_a_future_timer_is_rearmed_and_fires_on_time(
        self, make_service, vtime, devices, repository
    ):
        first = make_service()
        await first.start(DEVICE, 10, 0, "stop")
        await first.shutdown()

        second = make_service()
        await second.recover()
        await vtime.advance(600 + 5)
        await drain(second)

        assert devices.state == "PAUSE_STATE"
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_a_timer_that_elapsed_five_minutes_ago_ends_now(
        self, service, vtime, devices, repository
    ):
        await repository.upsert(
            SleepTimer(DEVICE, vtime.t - 300, 30, 0, "stop", None, vtime.t - 2100)
        )
        await service.recover()
        await vtime.advance(5)
        await drain(service)
        assert devices.state == "PAUSE_STATE"
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_an_old_timer_only_restores_the_volume(
        self, service, vtime, devices, repository
    ):
        devices.volume = 0
        await repository.upsert(
            SleepTimer(DEVICE, vtime.t - 1800, 30, 30, "stop", 40, vtime.t - 3600)
        )
        await service.recover()
        await vtime.advance(5)
        await drain(service)
        assert devices.volume == 40
        assert devices.keys() == []
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_an_old_timer_keeps_its_row_until_the_restore_succeeds(
        self, service, vtime, devices, repository
    ):
        devices.volume = 0
        devices.fail("get_volume", *[unreachable()] * 4)
        await repository.upsert(
            SleepTimer(DEVICE, vtime.t - 1800, 30, 30, "stop", 40, vtime.t - 3600)
        )
        await service.recover()
        await vtime.advance(100)
        await drain(service)
        assert (await repository.get(DEVICE)).original_volume == 40

    @pytest.mark.asyncio
    async def test_a_crash_mid_fade_is_undone_after_the_restart(
        self, make_service, vtime, devices, repository
    ):
        devices.volume = 40
        first = make_service()
        await first.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 15)
        faded = devices.volume
        assert faded < 40
        first._tasks[DEVICE].cancel()  # the process dies: no shutdown, no restore
        await asyncio.sleep(0)

        second = make_service()  # a fresh process: nothing in memory
        await second.recover()
        await vtime.advance(0)
        await asyncio.sleep(0.01)

        assert 40 in devices.volumes_set()
        await vtime.advance(30)
        await drain(second)
        assert devices.keys() == ["PAUSE"]
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_a_timer_that_elapsed_long_ago_restores_the_persisted_volume(
        self, make_service, vtime, devices, repository
    ):
        devices.volume = 40
        first = make_service()
        await first.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 5)  # nearly faded out
        first._tasks[DEVICE].cancel()
        await asyncio.sleep(0)
        vtime.jump(3600)  # the speaker was offline for an hour

        second = make_service()
        await second.recover()
        await vtime.advance(5)
        await drain(second)

        assert devices.volume == 40
        assert devices.keys() == []
        assert await repository.get(DEVICE) is None

    @pytest.mark.asyncio
    async def test_the_last_value_written_is_persisted(
        self, service, vtime, devices, repository
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 15)
        row = await repository.get(DEVICE)
        assert row.last_set_volume == devices.volume

    @pytest.mark.asyncio
    async def test_a_future_timer_with_less_than_two_seconds_left_skips_the_fade(
        self, service, vtime, devices, repository
    ):
        devices.volume = 30
        await repository.upsert(
            SleepTimer(DEVICE, vtime.t + 1, 30, 30, "stop", None, vtime.t - 1799)
        )
        await service.recover()
        await vtime.advance(5)
        await drain(service)
        assert devices.volumes_set() == []
        assert devices.keys() == ["PAUSE"]


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_cancels_a_fade_and_restores_the_volume(
        self, service, vtime, devices, repository
    ):
        devices.volume = 40
        await service.start(DEVICE, 30, 30, "stop")
        await vtime.advance(THIRTY_MINUTES - 15)
        assert devices.volume < 40

        await service.shutdown()

        assert devices.volume == 40
        assert service._tasks == {}


class TestStatusAccess:
    @pytest.mark.asyncio
    async def test_get_returns_the_active_timer_without_device_calls(
        self, service, devices
    ):
        await service.start(DEVICE, 5, 0, "stop")
        calls_before = len(devices.calls)
        timer = await service.get(DEVICE)
        assert timer.duration_minutes == 5
        assert len(devices.calls) == calls_before

    @pytest.mark.asyncio
    async def test_get_without_a_timer(self, service):
        assert await service.get(DEVICE) is None


class TestShutdownRobustness:
    @pytest.mark.asyncio
    async def test_shutdown_survives_an_unreadable_store(self, service, repository):
        async def broken():
            raise RuntimeError("Database not initialized")

        repository.list_all = broken
        await service.shutdown()  # must not raise: the app is closing anyway
