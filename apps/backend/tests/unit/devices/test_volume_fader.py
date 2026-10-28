"""VolumeFader: step formula, deadlines, manual change, retries."""

import math

import pytest

from opencloudtouch.devices.volume_fader import FadeResult, VolumeFader, step_target
from tests.unit.helpers.fake_playback import FakePlaybackDevices, unreachable
from tests.unit.helpers.virtual_time import VirtualTime

DEVICE = "AABBCC112233"


class Harness:
    """A fader whose sleep advances a virtual clock instantly."""

    def __init__(self) -> None:
        self.devices = FakePlaybackDevices()
        self.vtime = VirtualTime()
        self.sleeps: list[float] = []
        self.fader = VolumeFader(self.devices, self._sleep, self.vtime.clock)

    async def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.vtime.jump(seconds)


@pytest.fixture
def harness() -> Harness:
    return Harness()


def expected_steps(from_v: int, to_v: int, seconds: float) -> list[int]:
    steps = min(150, max(1, math.ceil(seconds / 2)))
    return [step_target(from_v, to_v, i, steps) for i in range(1, steps + 1)]


class TestStepFormula:
    def test_last_step_is_exactly_the_target(self):
        assert step_target(40, 0, 15, 15) == 0
        assert step_target(0, 100, 7, 7) == 100

    def test_rounds_half_up(self):
        assert step_target(10, 20, 1, 4) == 13  # 12.5 rounds up
        assert step_target(10, 20, 2, 4) == 15


class TestFade:
    @pytest.mark.asyncio
    async def test_fades_with_the_documented_formula(self, harness):
        harness.devices.volume = 40

        result = await harness.fader.fade(DEVICE, 40, 0, 30)

        assert result is FadeResult.COMPLETED
        wanted = [
            v
            for i, v in enumerate(expected_steps(40, 0, 30))
            if i == 0 or v != expected_steps(40, 0, 30)[i - 1]
        ]
        assert harness.devices.volumes_set() == wanted
        assert harness.devices.volume == 0

    @pytest.mark.asyncio
    async def test_steps_are_due_at_absolute_deadlines(self, harness):
        await harness.fader.fade(DEVICE, 40, 0, 30)
        # 15 steps of 2 s: the clock advanced by exactly the fade length
        assert sum(harness.sleeps) == pytest.approx(30)
        assert len(harness.sleeps) == 15

    @pytest.mark.asyncio
    async def test_a_slow_device_does_not_stretch_the_fade(self, harness):
        # every get_volume costs 1 s of virtual time
        harness.devices.on_call = lambda name, _a: (
            harness.vtime.jump(1) if name == "get_volume" else None
        )
        start = harness.vtime.t
        await harness.fader.fade(DEVICE, 40, 0, 30)
        assert harness.vtime.t - start == pytest.approx(30, abs=2.1)

    @pytest.mark.asyncio
    async def test_jumps_to_the_last_step_when_the_clock_is_past_the_end(self, harness):
        # the first call advances the clock beyond the whole fade
        harness.devices.on_call = lambda name, _a: (
            harness.vtime.jump(500)
            if name == "get_volume" and not harness.devices.volumes_set()
            else None
        )
        result = await harness.fader.fade(DEVICE, 40, 0, 30)
        assert result is FadeResult.COMPLETED
        assert harness.devices.volumes_set()[-1] == 0
        assert len(harness.devices.volumes_set()) < 5

    @pytest.mark.asyncio
    async def test_step_cap_is_150(self, harness):
        harness.devices.volume = 100
        await harness.fader.fade(DEVICE, 100, 0, 3600)
        assert len(harness.sleeps) == 150

    @pytest.mark.asyncio
    async def test_skips_duplicate_values(self, harness):
        harness.devices.volume = 5
        await harness.fader.fade(DEVICE, 5, 0, 30)  # 15 steps, only 5 distinct values
        values = harness.devices.volumes_set()
        assert len(values) == len(set(values))
        assert values[-1] == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("from_v", "to_v", "seconds"), [(40, 40, 30), (40, 0, 0)])
    async def test_nothing_to_do(self, harness, from_v, to_v, seconds):
        assert (
            await harness.fader.fade(DEVICE, from_v, to_v, seconds)
            is FadeResult.COMPLETED
        )
        assert harness.devices.calls == []

    @pytest.mark.asyncio
    async def test_muted_device_is_not_faded_by_default(self, harness):
        harness.devices.muted = True
        result = await harness.fader.fade(DEVICE, 40, 0, 30)
        assert result is FadeResult.COMPLETED
        assert harness.devices.volumes_set() == []

    @pytest.mark.asyncio
    async def test_muted_device_is_faded_with_skip_if_muted_false(self, harness):
        harness.devices.muted = True
        harness.devices.volume = 0
        await harness.fader.fade(DEVICE, 0, 30, 20, skip_if_muted=False)
        assert harness.devices.volumes_set()[-1] == 30

    @pytest.mark.asyncio
    async def test_reports_every_value_it_sets(self, harness):
        seen: list[int] = []

        async def remember(value: int) -> None:
            seen.append(value)

        await harness.fader.fade(DEVICE, 40, 0, 30, on_set=remember)
        assert seen == harness.devices.volumes_set()


class TestManualChange:
    @pytest.mark.asyncio
    async def test_aborts_when_the_user_changes_the_volume(self, harness):
        def user_turns_it_up(name, _args):
            # the knob is turned between two of our steps
            if name == "get_volume" and len(harness.devices.volumes_set()) == 4:
                harness.devices.volume = 80

        harness.devices.on_call = user_turns_it_up
        result = await harness.fader.fade(DEVICE, 40, 0, 30)

        assert result is FadeResult.MANUAL_CHANGE
        assert harness.devices.volume == 80  # left alone
        assert len(harness.devices.volumes_set()) == 4

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("nudge", "expected"),
        [
            (2, FadeResult.COMPLETED),
            (-2, FadeResult.COMPLETED),
            (3, FadeResult.MANUAL_CHANGE),
        ],
    )
    async def test_tolerance_is_two(self, harness, nudge, expected):
        def nudge_once(name, _args):
            if name == "get_volume" and len(harness.devices.volumes_set()) == 3:
                harness.devices.volume += nudge
                harness.devices.on_call = None

        harness.devices.on_call = nudge_once
        assert await harness.fader.fade(DEVICE, 40, 0, 30) is expected


class TestDeviceErrors:
    @pytest.mark.asyncio
    async def test_a_failing_step_is_retried_three_times_twenty_seconds_apart(
        self, harness
    ):
        harness.devices.fail("set_volume", unreachable(), unreachable(), unreachable())
        result = await harness.fader.fade(DEVICE, 40, 0, 30)
        assert result is FadeResult.COMPLETED
        assert harness.sleeps.count(20.0) == 3

    @pytest.mark.asyncio
    async def test_gives_up_after_the_retries(self, harness):
        harness.devices.fail("set_volume", *[unreachable()] * 4)
        result = await harness.fader.fade(DEVICE, 40, 0, 30)
        assert result is FadeResult.DEVICE_ERROR

    @pytest.mark.asyncio
    async def test_unreachable_while_checking_mute_is_a_device_error(self, harness):
        harness.devices.fail("get_volume", *[unreachable()] * 4)
        assert await harness.fader.fade(DEVICE, 40, 0, 30) is FadeResult.DEVICE_ERROR
