"""
Mock device client for testing and development without real devices.

Provides deterministic responses that simulate device HTTP API.
"""

import copy
import logging
from dataclasses import dataclass
from typing import Optional

from opencloudtouch.devices.client import (
    BassCapabilities,
    BassInfo,
    ClockSetting,
    DeviceClient,
    DeviceInfo,
    LanguageSetting,
    NowPlayingInfo,
    PowerSavingSetting,
    VolumeInfo,
)
from opencloudtouch.devices.device_settings import LANGUAGES
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus

logger = logging.getLogger(__name__)

# Device settings (language, clock, power saving) per device id. MockDeviceClient is
# created per call, so the values live at module level; tests reset them with
# reset_mock_device_settings().
_DEFAULT_SETTINGS: dict = {
    "language": 3,
    "clock": {
        "enabled": True,
        "time_format": "24h",
        "timezone": "Europe/Berlin",
        "extra": {},
    },
    "power_saving": False,
}
_mock_settings: dict[str, dict] = {}


def reset_mock_device_settings() -> None:
    """Forget all mock device settings (test isolation)."""
    _mock_settings.clear()


@dataclass
class _MockState:
    """Volume and playback state of one mock device (shared by all clients)."""

    volume: int
    muted: bool
    source: str
    state: str
    base: NowPlayingInfo  # what the device plays when it is awake

    def snapshot(self) -> NowPlayingInfo:
        playing_content = self.source != "STANDBY"
        return NowPlayingInfo(
            source=self.source,
            state=self.state,
            station_name=self.base.station_name if playing_content else None,
            artist=self.base.artist if playing_content else None,
            track=self.base.track if playing_content else None,
            album=self.base.album if playing_content else None,
            artwork_url=self.base.artwork_url if playing_content else None,
        )


_AWAKE_SOURCE = "INTERNET_RADIO"
_PLAYING_STATES = ("PLAY_STATE", "BUFFERING_STATE")
_mock_states: dict[str, _MockState] = {}


def reset_mock_state() -> None:
    """Forget the volume and playback state of all mock devices (test isolation)."""
    _mock_states.clear()


def _settings_of(device_id: str) -> dict:
    if device_id not in _mock_settings:
        _mock_settings[device_id] = copy.deepcopy(_DEFAULT_SETTINGS)
    return _mock_settings[device_id]


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
        self._bass = 0
        self._zone: ZoneStatus | None = None

        if device_id not in self.MOCK_DEVICES:
            raise ValueError(
                f"Unknown mock device: {device_id}. "
                f"Available: {list(self.MOCK_DEVICES.keys())}"
            )

        logger.info("[MOCK] Initialized mock client for device %s", device_id)

    @property
    def _state(self) -> _MockState:
        """Lazily created from the fixture; copied, never the shared object."""
        if self.device_id not in _mock_states:
            base = self.MOCK_DEVICES[self.device_id]["now_playing"]
            assert isinstance(base, NowPlayingInfo)
            _mock_states[self.device_id] = _MockState(
                volume=45,
                muted=False,
                source=base.source,
                state=base.state,
                base=copy.copy(base),
            )
        return _mock_states[self.device_id]

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
        return self._state.snapshot()

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
            "STOP",
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
        self._apply_key(key)

    def _apply_key(self, key: str) -> None:
        """Playback state machine of the mock device."""
        mock = self._state
        if key == "PLAY":
            mock.state = "PLAY_STATE"
        elif key == "PAUSE":
            if mock.state in _PLAYING_STATES:
                mock.state = "PAUSE_STATE"
        elif key == "STOP":
            mock.state = "STOP_STATE"
        elif key == "POWER":
            if mock.source == "STANDBY":
                mock.source, mock.state = _AWAKE_SOURCE, "PLAY_STATE"
            else:
                mock.source, mock.state = "STANDBY", "STOP_STATE"
        elif key.startswith("PRESET_"):
            mock.source, mock.state = _AWAKE_SOURCE, "PLAY_STATE"

    async def get_volume(self) -> VolumeInfo:
        """Get mock volume state."""
        logger.debug("[MOCK] get_volume() for device %s", self.device_id)
        mock = self._state
        return VolumeInfo(actual=mock.volume, target=mock.volume, muted=mock.muted)

    async def set_volume(self, level: int) -> None:
        """Mock set volume."""
        logger.info("[MOCK] set_volume(%s) for device %s", level, self.device_id)
        self._state.volume = max(0, min(100, level))

    async def set_mute(self, muted: bool) -> None:
        """Mock set mute."""
        logger.info("[MOCK] set_mute(%s) for device %s", muted, self.device_id)
        self._state.muted = muted

    async def get_bass(self) -> BassInfo:
        """Get mock bass state."""
        return BassInfo(actual=self._bass, target=self._bass)

    async def get_bass_capabilities(self) -> BassCapabilities:
        """Get mock bass capabilities."""
        return BassCapabilities(
            available=True,
            minimum=-9,
            maximum=0,
            default=0,
        )

    async def set_bass(self, level: int) -> None:
        """Mock set bass."""
        capabilities = await self.get_bass_capabilities()
        if level < capabilities.minimum or level > capabilities.maximum:
            raise ValueError(
                f"Bass level must be between {capabilities.minimum} "
                f"and {capabilities.maximum}"
            )
        self._bass = level

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

    async def reboot(self) -> None:
        """Mock reboot (no-op)."""
        logger.info("[MOCK] reboot() for device %s", self.device_id)

    # --- Device settings (language, clock, power saving) -------------------

    async def get_language(self) -> LanguageSetting | None:
        """Get the mock display language."""
        language_id = _settings_of(self.device_id)["language"]
        return LanguageSetting(id=language_id, name=LANGUAGES.get(language_id))

    async def set_language(self, language_id: int) -> None:
        """Mock set display language."""
        _settings_of(self.device_id)["language"] = language_id

    async def get_clock(self) -> ClockSetting | None:
        """Get the mock standby clock."""
        clock = _settings_of(self.device_id)["clock"]
        return ClockSetting(
            enabled=clock["enabled"],
            time_format=clock["time_format"],
            timezone=clock["timezone"],
            extra=dict(clock["extra"]),
        )

    async def set_clock(
        self,
        enabled: bool,
        time_format: str | None,
        timezone: str | None,
        extra: dict[str, str],
    ) -> None:
        """Mock set standby clock."""
        _settings_of(self.device_id)["clock"] = {
            "enabled": enabled,
            "time_format": time_format,
            "timezone": timezone,
            "extra": dict(extra),
        }

    async def get_power_saving(self) -> PowerSavingSetting | None:
        """Get the mock power saving flag."""
        return PowerSavingSetting(enabled=_settings_of(self.device_id)["power_saving"])

    async def set_power_saving(self, enabled: bool) -> None:
        """Mock set power saving."""
        _settings_of(self.device_id)["power_saving"] = enabled
