"""
Mock device client for testing and development without real devices.

Provides deterministic responses that simulate device HTTP API.
"""

import logging
from typing import Optional

from opencloudtouch.devices.client import (
    DeviceClient,
    DeviceInfo,
    NowPlayingInfo,
    VolumeInfo,
)
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus

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
        self._volume = 45
        self._muted = False
        self._zone: ZoneStatus | None = None

        if device_id not in self.MOCK_DEVICES:
            raise ValueError(
                f"Unknown mock device: {device_id}. "
                f"Available: {list(self.MOCK_DEVICES.keys())}"
            )

        logger.info("[MOCK] Initialized mock client for device %s", device_id)

    async def get_info(self) -> DeviceInfo:
        """
        Get mock device information.

        Returns:
            DeviceInfo object with predefined device details
        """
        logger.debug("[MOCK] get_info() for device %s", self.device_id)
        info = self.MOCK_DEVICES[self.device_id]["info"]
        assert isinstance(info, DeviceInfo)
        return info

    async def get_now_playing(self) -> NowPlayingInfo:
        """
        Get mock playback status.

        Returns:
            NowPlayingInfo object with predefined playback details
        """
        logger.debug("[MOCK] get_now_playing() for device %s", self.device_id)
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
            "[MOCK] press_key(%s, %s) for device %s",
            key,
            state,
            self.device_id,
            extra={"device_id": self.device_id, "key": key, "state": state},
        )

    async def get_volume(self) -> VolumeInfo:
        """Get mock volume state."""
        logger.debug("[MOCK] get_volume() for device %s", self.device_id)
        return VolumeInfo(actual=self._volume, target=self._volume, muted=self._muted)

    async def set_volume(self, level: int) -> None:
        """Mock set volume."""
        logger.info("[MOCK] set_volume(%s) for device %s", level, self.device_id)
        self._volume = max(0, min(100, level))

    async def set_mute(self, muted: bool) -> None:
        """Mock set mute."""
        logger.info("[MOCK] set_mute(%s) for device %s", muted, self.device_id)
        self._muted = muted

    async def set_name(self, name: str) -> None:
        """Mock set name."""
        logger.info("[MOCK] set_name(%s) for device %s", name, self.device_id)
        data = self.MOCK_DEVICES.get(self.device_id)
        if data:
            info = data["info"]
            if isinstance(info, DeviceInfo):
                info.name = name

    async def close(self) -> None:
        """Mock close (no-op)."""
        logger.debug("[MOCK] close() for device %s", self.device_id)
        pass

    async def store_preset(
        self,
        device_id: str,
        preset_number: int,
        station_url: str,
        station_name: str,
        oct_backend_url: str,
        station_image_url: str = "",
        station_uuid: str = "",
    ) -> None:
        """Mock store preset (no-op for testing)."""
        logger.info(  # NOSONAR — internal IDs for debug
            "[MOCK] store_preset(%d, %s) for device %s",
            preset_number,
            station_name,
            device_id,
        )

    # ---- Zone Methods ----

    async def get_zone_status(self) -> ZoneStatus | None:
        """Mock get zone status."""
        logger.debug("[MOCK] get_zone_status() for device %s", self.device_id)
        return self._zone

    async def create_zone(
        self, master_ip: str, members: list[ZoneMemberInfo]
    ) -> ZoneStatus:
        """Mock create zone."""
        logger.info("[MOCK] create_zone() for device %s", self.device_id)
        all_members = [
            ZoneMemberInfo(
                device_id=self.device_id, ip_address=master_ip, role="master"
            )
        ] + [
            ZoneMemberInfo(device_id=m.device_id, ip_address=m.ip_address, role="slave")
            for m in members
        ]
        self._zone = ZoneStatus(
            master_id=self.device_id,
            master_ip=master_ip,
            is_master=True,
            members=all_members,
        )
        return self._zone

    async def add_zone_members(self, members: list[ZoneMemberInfo]) -> None:
        """Mock add zone members."""
        logger.info("[MOCK] add_zone_members() for device %s", self.device_id)
        if self._zone:
            existing_ids = {m.device_id for m in self._zone.members}
            for m in members:
                if m.device_id not in existing_ids:
                    self._zone.members.append(
                        ZoneMemberInfo(
                            device_id=m.device_id, ip_address=m.ip_address, role="slave"
                        )
                    )

    async def remove_zone_members(self, members: list[ZoneMemberInfo]) -> None:
        """Mock remove zone members."""
        logger.info("[MOCK] remove_zone_members() for device %s", self.device_id)
        if self._zone:
            remove_ids = {m.device_id for m in members}
            self._zone.members = [
                m for m in self._zone.members if m.device_id not in remove_ids
            ]

    async def remove_zone(self) -> None:
        """Mock remove zone."""
        logger.info("[MOCK] remove_zone() for device %s", self.device_id)
        self._zone = None
