"""Playback helpers: state predicates, stop_playback and the unreachable retry."""

import pytest

from opencloudtouch.core.exceptions import DeviceNotFoundError
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.playback import (
    is_playing,
    is_standby,
    retry_unreachable,
    stop_playback,
)
from tests.unit.helpers.fake_playback import FakePlaybackDevices, unreachable
from tests.unit.helpers.virtual_time import VirtualTime

DEVICE = "AABBCC112233"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("PLAY_STATE", True),
        ("BUFFERING_STATE", True),
        ("PAUSE_STATE", False),
        ("STOP_STATE", False),
    ],
)
def test_is_playing(state, expected):
    assert is_playing(NowPlayingInfo(source="INTERNET_RADIO", state=state)) is expected


def test_is_standby_looks_at_the_source():
    assert is_standby(NowPlayingInfo(source="STANDBY", state="STOP_STATE")) is True
    assert is_standby(NowPlayingInfo(source="AUX", state="STOP_STATE")) is False


class TestStopPlayback:
    @pytest.mark.asyncio
    async def test_pauses_a_playing_device_and_stops_there(self):
        devices, vtime = FakePlaybackDevices(), VirtualTime()

        async def fast_sleep(seconds):
            await vtime.advance(seconds)

        await stop_playback(devices, DEVICE, fast_sleep)

        assert devices.keys() == ["PAUSE"]
        assert devices.state == "PAUSE_STATE"

    @pytest.mark.asyncio
    async def test_waits_two_seconds_between_pause_and_the_check(self):
        devices = FakePlaybackDevices()
        waited: list[float] = []

        async def sleep(seconds):
            waited.append(seconds)

        await stop_playback(devices, DEVICE, sleep)
        assert waited == [2.0]

    @pytest.mark.asyncio
    async def test_sends_stop_when_pause_did_not_leave_play_state(self):
        devices = FakePlaybackDevices()
        devices.key_effects = {"PAUSE": "PLAY_STATE", "STOP": "STOP_STATE"}

        async def sleep(_seconds):
            return None

        await stop_playback(devices, DEVICE, sleep)

        assert devices.keys() == ["PAUSE", "STOP"]
        assert devices.state == "STOP_STATE"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("state", ["PAUSE_STATE", "STOP_STATE"])
    async def test_leaves_a_device_alone_that_is_not_playing(self, state):
        devices = FakePlaybackDevices()
        devices.state = state

        async def sleep(_seconds):
            return None

        await stop_playback(devices, DEVICE, sleep)
        assert devices.keys() == []

    @pytest.mark.asyncio
    async def test_buffering_counts_as_playing(self):
        devices = FakePlaybackDevices()
        devices.state = "BUFFERING_STATE"
        devices.key_effects = {"PAUSE": "PAUSE_STATE"}

        async def sleep(_seconds):
            return None

        await stop_playback(devices, DEVICE, sleep)
        # BUFFERING is not PLAY_STATE: PAUSE was sent but STOP is not needed
        assert devices.keys() == ["PAUSE"]


class TestRetryUnreachable:
    @pytest.mark.asyncio
    async def test_returns_the_result_without_retry(self):
        waited: list[float] = []

        async def call():
            return 7

        async def sleep(seconds):
            waited.append(seconds)

        assert await retry_unreachable(call, sleep) == 7
        assert waited == []

    @pytest.mark.asyncio
    async def test_retries_three_times_twenty_seconds_apart(self):
        attempts: list[int] = []
        waited: list[float] = []

        async def call():
            attempts.append(1)
            if len(attempts) < 4:
                raise unreachable()
            return "ok"

        async def sleep(seconds):
            waited.append(seconds)

        assert await retry_unreachable(call, sleep) == "ok"
        assert len(attempts) == 4
        assert waited == [20.0, 20.0, 20.0]

    @pytest.mark.asyncio
    async def test_gives_up_after_the_fourth_attempt(self):
        attempts: list[int] = []

        async def call():
            attempts.append(1)
            raise unreachable()

        async def sleep(_seconds):
            return None

        with pytest.raises(type(unreachable())):
            await retry_unreachable(call, sleep)
        assert len(attempts) == 4

    @pytest.mark.asyncio
    async def test_other_errors_are_not_retried(self):
        attempts: list[int] = []

        async def call():
            attempts.append(1)
            raise DeviceNotFoundError(DEVICE)

        async def sleep(_seconds):
            return None

        with pytest.raises(DeviceNotFoundError):
            await retry_unreachable(call, sleep)
        assert len(attempts) == 1
