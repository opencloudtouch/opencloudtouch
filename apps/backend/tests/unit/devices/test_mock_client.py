"""
Tests for MockDeviceClient.
"""

import pytest

from opencloudtouch.devices.client import (
    BassCapabilities,
    BassInfo,
    DeviceInfo,
    NowPlayingInfo,
    VolumeInfo,
)
from opencloudtouch.devices.mock_client import MockDeviceClient


class TestMockDeviceClient:
    """Tests for mock device client."""

    @pytest.mark.asyncio
    async def test_get_info_returns_device_info(self):
        """Test that get_info returns DeviceInfo object."""
        client = MockDeviceClient(device_id="AABBCC112233")

        info = await client.get_info()

        assert isinstance(info, DeviceInfo)
        assert info.device_id == "AABBCC112233"
        assert info.name == "Living Room"
        assert info.type == "SoundTouch 20"
        assert info.mac_address == "AABBCC112233"
        assert info.ip_address == "192.168.1.100"
        assert info.firmware_version == "28.0.12.46499"

    @pytest.mark.asyncio
    async def test_get_now_playing_returns_playback_info(self):
        """Test that get_now_playing returns NowPlayingInfo object."""
        client = MockDeviceClient(device_id="AABBCC112233")

        now_playing = await client.get_now_playing()

        assert isinstance(now_playing, NowPlayingInfo)
        assert now_playing.source == "INTERNET_RADIO"
        assert now_playing.state == "PLAY_STATE"
        assert now_playing.station_name == "Radio Paradise"

    @pytest.mark.asyncio
    async def test_different_devices_have_different_responses(self):
        """Test that different devices return different data."""
        client1 = MockDeviceClient(device_id="AABBCC112233")
        client2 = MockDeviceClient(device_id="DDEEFF445566")

        info1 = await client1.get_info()
        info2 = await client2.get_info()

        assert info1.name == "Living Room"
        assert info2.name == "Kitchen"
        assert info1.device_id != info2.device_id

    @pytest.mark.asyncio
    async def test_bluetooth_device_response(self):
        """Test device playing via Bluetooth."""
        client = MockDeviceClient(device_id="DDEEFF445566")

        now_playing = await client.get_now_playing()

        assert now_playing.source == "BLUETOOTH"
        assert now_playing.artist == "The Beatles"
        assert now_playing.track == "Here Comes The Sun"
        assert now_playing.station_name is None  # Bluetooth doesn't have station

    @pytest.mark.asyncio
    async def test_standby_device_response(self):
        """Test device in standby mode."""
        client = MockDeviceClient(device_id="112233445566")

        now_playing = await client.get_now_playing()

        assert now_playing.source == "STANDBY"
        assert now_playing.state == "STOP_STATE"
        assert now_playing.artist is None
        assert now_playing.track is None

    @pytest.mark.asyncio
    async def test_unknown_device_raises_error(self):
        """Test that unknown device ID raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mock device"):
            MockDeviceClient(device_id="UNKNOWN123")

    @pytest.mark.asyncio
    async def test_close_is_noop(self):
        """Test that close() doesn't raise errors."""
        client = MockDeviceClient(device_id="AABBCC112233")

        await client.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_all_mock_devices_have_required_fields(self):
        """Test that all mock devices have complete DeviceInfo."""
        device_ids = ["AABBCC112233", "DDEEFF445566", "112233445566"]

        for device_id in device_ids:
            client = MockDeviceClient(device_id=device_id)
            info = await client.get_info()

            assert info.device_id
            assert info.name
            assert info.type
            assert info.mac_address
            assert info.ip_address
            assert info.firmware_version

    @pytest.mark.asyncio
    async def test_all_mock_devices_have_now_playing(self):
        """Test that all mock devices have NowPlayingInfo."""
        device_ids = ["AABBCC112233", "DDEEFF445566", "112233445566"]

        for device_id in device_ids:
            client = MockDeviceClient(device_id=device_id)
            now_playing = await client.get_now_playing()

            assert now_playing.source
            assert now_playing.state


class TestMockDeviceClientVolume:
    """Tests for mock device client volume control."""

    @pytest.mark.asyncio
    async def test_get_volume_default(self):
        """Test initial volume state."""
        client = MockDeviceClient(device_id="AABBCC112233")
        vol = await client.get_volume()

        assert isinstance(vol, VolumeInfo)
        assert vol.actual == 45
        assert vol.target == 45
        assert vol.muted is False

    @pytest.mark.asyncio
    async def test_set_volume(self):
        """Test setting volume updates state."""
        client = MockDeviceClient(device_id="AABBCC112233")
        await client.set_volume(70)
        vol = await client.get_volume()

        assert vol.actual == 70
        assert vol.target == 70

    @pytest.mark.asyncio
    async def test_set_volume_clamps_high(self):
        """Test volume is clamped to max 100."""
        client = MockDeviceClient(device_id="AABBCC112233")
        await client.set_volume(150)
        vol = await client.get_volume()

        assert vol.actual == 100

    @pytest.mark.asyncio
    async def test_set_volume_clamps_low(self):
        """Test volume is clamped to min 0."""
        client = MockDeviceClient(device_id="AABBCC112233")
        await client.set_volume(-10)
        vol = await client.get_volume()

        assert vol.actual == 0

    @pytest.mark.asyncio
    async def test_set_mute_on(self):
        """Test muting the device."""
        client = MockDeviceClient(device_id="AABBCC112233")
        await client.set_mute(True)
        vol = await client.get_volume()

        assert vol.muted is True

    @pytest.mark.asyncio
    async def test_set_mute_off(self):
        """Test unmuting the device."""
        client = MockDeviceClient(device_id="AABBCC112233")
        await client.set_mute(True)
        await client.set_mute(False)
        vol = await client.get_volume()

        assert vol.muted is False


class TestMockDeviceClientBass:
    """Tests for mock device bass control."""

    @pytest.mark.asyncio
    async def test_get_bass_default(self):
        client = MockDeviceClient(device_id="AABBCC112233")
        bass = await client.get_bass()

        assert isinstance(bass, BassInfo)
        assert bass.actual == 0
        assert bass.target == 0

    @pytest.mark.asyncio
    async def test_get_bass_capabilities(self):
        client = MockDeviceClient(device_id="AABBCC112233")
        caps = await client.get_bass_capabilities()

        assert isinstance(caps, BassCapabilities)
        assert caps.available is True
        assert caps.minimum == -9
        assert caps.maximum == 0
        assert caps.default == 0

    @pytest.mark.asyncio
    async def test_set_bass(self):
        client = MockDeviceClient(device_id="AABBCC112233")
        await client.set_bass(-5)
        bass = await client.get_bass()

        assert bass.actual == -5
        assert bass.target == -5

    @pytest.mark.asyncio
    async def test_set_bass_rejects_out_of_range(self):
        client = MockDeviceClient(device_id="AABBCC112233")
        with pytest.raises(ValueError, match="between -9 and 0"):
            await client.set_bass(-10)
