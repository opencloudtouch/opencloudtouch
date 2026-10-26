"""The mock device keeps volume, mute and playback state across client instances."""

import pytest

from opencloudtouch.devices.mock_client import MockDeviceClient, reset_mock_state

PLAYING = "AABBCC112233"  # INTERNET_RADIO / PLAY_STATE
STANDBY_DEVICE = "112233445566"


async def now(device_id=PLAYING):
    return await MockDeviceClient(device_id).get_now_playing()


class TestVolume:
    @pytest.mark.asyncio
    async def test_volume_is_shared_between_instances(self):
        await MockDeviceClient(PLAYING).set_volume(12)
        volume = await MockDeviceClient(PLAYING).get_volume()
        assert (volume.actual, volume.target) == (12, 12)

    @pytest.mark.asyncio
    async def test_default_is_45_and_clamped_to_0_100(self):
        client = MockDeviceClient(PLAYING)
        assert (await client.get_volume()).actual == 45
        await client.set_volume(250)
        assert (await client.get_volume()).actual == 100
        await client.set_volume(-5)
        assert (await client.get_volume()).actual == 0

    @pytest.mark.asyncio
    async def test_mute_is_shared_and_devices_are_independent(self):
        await MockDeviceClient(PLAYING).set_mute(True)
        assert (await MockDeviceClient(PLAYING).get_volume()).muted is True
        assert (await MockDeviceClient("DDEEFF445566").get_volume()).muted is False

    @pytest.mark.asyncio
    async def test_reset_restores_the_defaults(self):
        await MockDeviceClient(PLAYING).set_volume(3)
        reset_mock_state()
        assert (await MockDeviceClient(PLAYING).get_volume()).actual == 45


class TestKeys:
    @pytest.mark.asyncio
    async def test_starts_as_the_fixture_says(self):
        info = await now()
        assert (info.source, info.state) == ("INTERNET_RADIO", "PLAY_STATE")
        assert info.station_name == "Radio Paradise"

    @pytest.mark.asyncio
    async def test_pause_pauses_a_playing_device(self):
        await MockDeviceClient(PLAYING).press_key("PAUSE")
        assert (await now()).state == "PAUSE_STATE"

    @pytest.mark.asyncio
    async def test_pause_does_nothing_when_not_playing(self):
        client = MockDeviceClient(PLAYING)
        await client.press_key("STOP")
        await client.press_key("PAUSE")
        assert (await now()).state == "STOP_STATE"

    @pytest.mark.asyncio
    async def test_stop_and_play(self):
        client = MockDeviceClient(PLAYING)
        await client.press_key("STOP")
        assert (await now()).state == "STOP_STATE"
        await client.press_key("PLAY")
        assert (await now()).state == "PLAY_STATE"

    @pytest.mark.asyncio
    async def test_power_toggles_standby(self):
        client = MockDeviceClient(PLAYING)
        await client.press_key("POWER")
        info = await now()
        assert (info.source, info.state) == ("STANDBY", "STOP_STATE")
        assert info.station_name is None
        await client.press_key("POWER")
        info = await now()
        assert (info.source, info.state) == ("INTERNET_RADIO", "PLAY_STATE")

    @pytest.mark.asyncio
    async def test_preset_plays_and_wakes_from_standby(self):
        info = await now(STANDBY_DEVICE)
        assert info.source == "STANDBY"
        await MockDeviceClient(STANDBY_DEVICE).press_key("PRESET_3")
        info = await now(STANDBY_DEVICE)
        assert (info.source, info.state) == ("INTERNET_RADIO", "PLAY_STATE")

    @pytest.mark.asyncio
    async def test_unknown_key_is_still_rejected(self):
        with pytest.raises(ValueError, match="Invalid key"):
            await MockDeviceClient(PLAYING).press_key("EXPLODE")

    @pytest.mark.asyncio
    async def test_now_playing_is_a_copy(self):
        info = await now()
        info.state = "TAMPERED"
        assert (await now()).state == "PLAY_STATE"

    @pytest.mark.asyncio
    async def test_state_is_independent_per_device(self):
        await MockDeviceClient(PLAYING).press_key("STOP")
        assert (await now("DDEEFF445566")).state == "PLAY_STATE"
        assert (await now(PLAYING)).state == "STOP_STATE"
