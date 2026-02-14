"""
Tests for device key press functionality (Iteration 4).

Tests for simulating physical button presses on SoundTouch devices.
"""

import pytest

from opencloudtouch.devices.mock_client import MockDeviceClient


@pytest.mark.asyncio
class TestDeviceKeyPress:
    """Test key press simulation on devices."""

    async def test_press_key_preset_1(self):
        """Test pressing PRESET_1 key."""
        client = MockDeviceClient(device_id="AABBCC112233")

        # Should not raise exception
        await client.press_key("PRESET_1", "both")

    async def test_press_key_all_presets(self):
        """Test pressing all preset keys."""
        client = MockDeviceClient(device_id="AABBCC112233")

        for preset_num in range(1, 7):  # 1-6
            await client.press_key(f"PRESET_{preset_num}", "both")

    async def test_press_key_different_states(self):
        """Test different key states."""
        client = MockDeviceClient(device_id="AABBCC112233")

        # All states should work
        await client.press_key("PRESET_1", "press")
        await client.press_key("PRESET_1", "release")
        await client.press_key("PRESET_1", "both")

    async def test_press_key_invalid_key_raises(self):
        """Test that invalid key raises ValueError."""
        client = MockDeviceClient(device_id="AABBCC112233")

        with pytest.raises(ValueError, match="Invalid key"):
            await client.press_key("INVALID_KEY", "both")

    async def test_press_key_invalid_state_raises(self):
        """Test that invalid state raises ValueError."""
        client = MockDeviceClient(device_id="AABBCC112233")

        with pytest.raises(ValueError, match="Invalid state"):
            await client.press_key("PRESET_1", "invalid_state")

    async def test_press_key_play_pause_power(self):
        """Test pressing control keys."""
        client = MockDeviceClient(device_id="AABBCC112233")

        # Control keys should work
        await client.press_key("PLAY", "both")
        await client.press_key("PAUSE", "both")
        await client.press_key("POWER", "both")
