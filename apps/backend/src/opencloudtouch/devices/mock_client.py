"""
Mock device client for testing and development without real devices.

Provides deterministic responses that simulate device HTTP API.
"""

import logging
from typing import ClassVar, Optional

from opencloudtouch.devices.client import (
    BassCapabilities,
    BassInfo,
    DeviceClient,
    DeviceInfo,
    NowPlayingInfo,
    SpeakerSource,
    StoredMusicBrowse,
    StoredMusicItem,
    VolumeInfo,
)
from opencloudtouch.devices.models import SELECTABLE_SOURCES
from opencloudtouch.dlna.mock import MOCK_SERVER, mock_browse
from opencloudtouch.dlna.models import is_audio_item
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

    # device_id -> registered server ids; class-level because the app builds a client per request
    _MEDIA_SERVERS: ClassVar[dict[str, set[str]]] = {}

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
        self._bass = 0
        self._muted = False
        self._zone: ZoneStatus | None = None
        self._media_servers = self._MEDIA_SERVERS.setdefault(device_id, set())
        self.native_presets: list[tuple[int, StoredMusicItem, str]] = []

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

    async def select_source(self, source: str) -> None:
        """Mock source switch."""
        if source not in SELECTABLE_SOURCES:
            raise ValueError(f"Invalid source: {source}")
        logger.info(
            "[MOCK] select_source(%s) for device %s",
            source,
            self.device_id,
            extra={"device_id": self.device_id, "source": source},
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

    async def remove_preset(self, preset_number: int) -> None:
        """Mock remove preset (no-op for testing)."""
        logger.info(
            "[MOCK] remove_preset(%d) for device %s", preset_number, self.device_id
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

    # ---- DLNA / STORED_MUSIC Methods ----

    async def list_media_servers(self) -> list[str]:
        """Mock listMediaServers: the servers registered on this mock device."""
        return sorted(self._media_servers)

    async def get_source_list(self) -> list[SpeakerSource]:
        """Report registered servers as READY, alongside the AUX source."""
        return [SpeakerSource("AUX", "", "READY", "AUX")] + [
            SpeakerSource("STORED_MUSIC", f"{udn}/0", "READY", udn)
            for udn in sorted(self._media_servers)
        ]

    async def browse_stored_music(
        self, source_account: str, location: str | None = None
    ) -> StoredMusicBrowse:
        """Mock /navigate: speaker-style items of the mock DLNA tree."""
        account = f"{MOCK_SERVER.id}/0"
        if source_account != account:
            return StoredMusicBrowse([])
        try:
            page = mock_browse(location or "0", 0, 0)
        except KeyError:
            return StoredMusicBrowse([])
        return StoredMusicBrowse(
            [
                StoredMusicItem(
                    name=i.title,
                    is_directory=i.is_container,
                    source="STORED_MUSIC",
                    location=i.id if i.is_container else f"{i.id} TRACK",
                    source_account=account,
                    item_name=i.title,
                )
                for i in page.items
                if i.is_container or is_audio_item(i)
            ]
        )

    async def register_media_server(self, server_udn: str, name: str) -> None:
        """Mock setMusicServiceAccount: the server becomes listed and READY."""
        self._media_servers.add(server_udn)

    async def remove_media_server(self, server_udn: str) -> None:
        """Mock removeMusicServiceAccount (idempotent)."""
        self._media_servers.discard(server_udn)

    async def notify_sources_updated(self, device_id: str) -> None:
        """Mock sourcesUpdated push (no-op)."""
        logger.info("[MOCK] sourcesUpdated for device %s", device_id)

    async def store_native_preset(
        self, preset_number: int, item: StoredMusicItem, artwork_url: str = ""
    ) -> None:
        """Record the native preset write."""
        if not 1 <= preset_number <= 6:
            raise ValueError(f"Preset number must be 1-6, got {preset_number}")
        self.native_presets.append((preset_number, item, artwork_url))
