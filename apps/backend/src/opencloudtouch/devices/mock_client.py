"""
Mock device client for testing and development without real devices.

Provides deterministic responses that simulate device HTTP API.
"""

import logging
from typing import Optional

from opencloudtouch.devices.client import DeviceClient, DeviceInfo, NowPlayingInfo

logger = logging.getLogger(__name__)


class MockDeviceClient(DeviceClient):
    """
    Mock client that simulates device HTTP API responses.

    Used for:
    - CI/CD testing (no hardware needed)
    - Local development without network access
    - Deterministic test scenarios
    """

    # Predefined responses per device MAC
    MOCK_DEVICES = {
        "AABBCC112233": {
            "info": DeviceInfo(
                device_id="AABBCC112233",
                name="Living Room",
                type="SoundTouch 20",
                mac_address="AABBCC112233",
                ip_address="192.168.1.100",
                firmware_version="28.0.12.46499",
                module_type="sm2",
                variant="spotty",
                variant_mode="normal",
            ),
            "now_playing": NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="Radio Paradise",
                artist="Various Artists",
                track="Eclectic Music Stream",
                album=None,
                artwork_url="http://img.radioparadise.com/covers/l/B00008K3V0.jpg",
            ),
        },
        "DDEEFF445566": {
            "info": DeviceInfo(
                device_id="DDEEFF445566",
                name="Kitchen",
                type="SoundTouch 10",
                mac_address="DDEEFF445566",
                ip_address="192.168.1.101",
                firmware_version="28.0.12.46499",
                module_type="sm2",
                variant="spotty",
                variant_mode="normal",
            ),
            "now_playing": NowPlayingInfo(
                source="BLUETOOTH",
                state="PLAY_STATE",
                station_name=None,
                artist="The Beatles",
                track="Here Comes The Sun",
                album="Abbey Road",
                artwork_url=None,
            ),
        },
        "112233445566": {
            "info": DeviceInfo(
                device_id="112233445566",
                name="Bedroom",
                type="SoundTouch 30",
                mac_address="112233445566",
                ip_address="192.168.1.102",
                firmware_version="28.0.12.46499",
                module_type="sm2",
                variant="ginger",
                variant_mode="normal",
            ),
            "now_playing": NowPlayingInfo(
                source="STANDBY",
                state="STOP_STATE",
                station_name=None,
                artist=None,
                track=None,
                album=None,
                artwork_url=None,
            ),
        },
    }

    def __init__(self, device_id: str, ip_address: Optional[str] = None):
        """
        Initialize mock client for a specific device.

        Args:
            device_id: Device MAC address (must match MOCK_DEVICES keys)
            ip_address: Ignored (for interface compatibility)

        Raises:
            ValueError: If device_id is not in MOCK_DEVICES
        """
        self.device_id = device_id
        self.ip_address = ip_address

        if device_id not in self.MOCK_DEVICES:
            raise ValueError(
                f"Unknown mock device: {device_id}. "
                f"Available: {list(self.MOCK_DEVICES.keys())}"
            )

        logger.info(f"[MOCK] Initialized mock client for device {device_id}")

    async def get_info(self) -> DeviceInfo:
        """
        Get mock device information.

        Returns:
            DeviceInfo object with predefined device details
        """
        logger.debug(f"[MOCK] get_info() for device {self.device_id}")
        info = self.MOCK_DEVICES[self.device_id]["info"]
        assert isinstance(info, DeviceInfo)
        return info

    async def get_now_playing(self) -> NowPlayingInfo:
        """
        Get mock playback status.

        Returns:
            NowPlayingInfo object with predefined playback details
        """
        logger.debug(f"[MOCK] get_now_playing() for device {self.device_id}")
        now_playing = self.MOCK_DEVICES[self.device_id]["now_playing"]
        assert isinstance(now_playing, NowPlayingInfo)
        return now_playing

    async def press_key(self, key: str, state: str = "both") -> None:
        """
        Mock key press simulation.

        Args:
            key: Key name (e.g., "PRESET_1", "PRESET_2", ...)
            state: Key state ("press", "release", or "both")
        """
        valid_keys = [
            "PRESET_1",
            "PRESET_2",
            "PRESET_3",
            "PRESET_4",
            "PRESET_5",
            "PRESET_6",
            "PLAY",
            "PAUSE",
            "POWER",
        ]
        valid_states = ["press", "release", "both"]

        if key not in valid_keys:
            raise ValueError(f"Invalid key: {key}")

        if state not in valid_states:
            raise ValueError(
                f"Invalid state: {state}. Must be 'press', 'release', or 'both'"
            )

        logger.info(
            f"[MOCK] press_key({key}, {state}) for device {self.device_id}",
            extra={"device_id": self.device_id, "key": key, "state": state},
        )

    async def close(self) -> None:
        """Mock close (no-op)."""
        logger.debug(f"[MOCK] close() for device {self.device_id}")
        pass
