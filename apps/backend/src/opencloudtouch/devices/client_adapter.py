"""
Bose SoundTouch HTTP Client Adapter.

Extracted from devices/adapter.py (STORY-305).
Wraps bosesoundtouchapi BoseClient with our internal DeviceClient interface.
"""

import asyncio
import base64
import json
import logging
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape

import httpx
from bosesoundtouchapi import SoundTouchClient as BoseClient
from bosesoundtouchapi import SoundTouchDevice

from opencloudtouch.core.exceptions import DeviceConnectionError
from opencloudtouch.devices.client import (
    DeviceClient,
    DeviceInfo,
    NowPlayingInfo,
    VolumeInfo,
)
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus

logger = logging.getLogger(__name__)


class BoseDeviceClientAdapter(DeviceClient):
    """Adapter wrapping bosesoundtouchapi library client."""

    def __init__(self, base_url: str, timeout: float = 3.0):
        """
        Initialize client adapter.

        Args:
            base_url: Base URL of device (e.g., http://192.168.1.100:8090)
            timeout: Request timeout in seconds (reduced to 3s to fail fast
                     for offline devices and avoid blocking the thread pool)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Extract IP and port for BoseClient
        # BoseClient expects SoundTouchDevice object
        parsed = urlparse(base_url)
        self.ip = parsed.hostname or base_url.split("://")[1].split(":")[0]
        port = parsed.port or 8090

        # Create SoundTouchDevice with connectTimeout parameter
        # This initializes the device and loads info/capabilities
        # NOTE: This constructor makes synchronous HTTP calls (blocking I/O).
        # Callers MUST use asyncio.to_thread() to avoid blocking the event loop.
        try:
            device = SoundTouchDevice(
                host=self.ip, connectTimeout=int(timeout), port=port
            )
            self._client = BoseClient(device)
        except Exception as e:
            logger.exception("Failed to connect to device at %s", base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    def _extract_firmware_version(self, info) -> str:
        """Extract firmware version from Components list."""
        if not hasattr(info, "Components") or not info.Components:
            return ""

        first_component = info.Components[0]
        return (
            first_component.SoftwareVersion
            if hasattr(first_component, "SoftwareVersion")
            else ""
        )

    def _extract_ip_address(self, info) -> str:
        """Extract IP address from NetworkInfo or fallback to self.ip."""
        if not info.NetworkInfo or len(info.NetworkInfo) == 0:
            return self.ip

        network_info = info.NetworkInfo[0]
        return network_info.IpAddress if hasattr(network_info, "IpAddress") else self.ip

    async def get_info(self) -> DeviceInfo:
        """
        Get device info from /info endpoint.

        Returns:
            DeviceInfo parsed from response
        """
        try:
            # BoseClient.GetInformation() returns InfoElement
            # Properties: DeviceName, DeviceId, DeviceType, ModuleType, etc.
            info = await asyncio.to_thread(self._client.GetInformation)

            firmware_version = self._extract_firmware_version(info)
            ip_address = self._extract_ip_address(info)

            device_info = DeviceInfo(
                device_id=info.DeviceId,
                name=info.DeviceName,
                type=info.DeviceType,
                mac_address=getattr(info, "MacAddress", ""),
                ip_address=ip_address,
                firmware_version=firmware_version,
                module_type=getattr(info, "ModuleType", None),
                variant=getattr(info, "Variant", None),
                variant_mode=getattr(info, "VariantMode", None),
            )

            # Structured logging with firmware details
            logger.info(
                "Device %s initialized",
                device_info.name,
                extra={
                    "device_id": device_info.device_id,
                    "device_type": device_info.type,
                    "firmware": firmware_version,
                    "module_type": device_info.module_type,
                    "variant": device_info.variant,
                },
            )

            return device_info

        except Exception as e:
            logger.exception("Failed to get info from %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def get_now_playing(self) -> NowPlayingInfo:
        """
        Get now playing info from /now_playing endpoint.

        Returns:
            NowPlayingInfo parsed from response
        """
        try:
            # BoseClient.GetNowPlayingStatus() returns NowPlayingStatus
            # Properties: Source, PlayStatus, StationName, Artist, Track, Album, ArtUrl
            now_playing = await asyncio.to_thread(self._client.GetNowPlayingStatus)

            # Map PlayStatus to our state format
            # BoseClient uses: PLAY_STATE, PAUSE_STATE, STOP_STATE, BUFFERING_STATE
            state = now_playing.PlayStatus or "STOP_STATE"
            source = now_playing.Source or "UNKNOWN"

            return NowPlayingInfo(
                source=source,
                state=state,
                station_name=getattr(now_playing, "StationName", None),
                artist=getattr(now_playing, "Artist", None),
                track=getattr(now_playing, "Track", None),
                album=getattr(now_playing, "Album", None),
                artwork_url=getattr(now_playing, "ContainerArtUrl", None),
            )

        except Exception as e:
            logger.exception("Failed to get now_playing from %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def press_key(self, key: str, state: str = "both") -> None:
        """
        Simulate a key press on the device.

        Args:
            key: Key name (e.g., "PRESET_1", "PRESET_2", ...)
            state: Key state ("press", "release", or "both")

        Raises:
            ConnectionError: If device is unreachable
            ValueError: If key or state is invalid
        """
        try:
            from bosesoundtouchapi import SoundTouchKeys
            from bosesoundtouchapi.models.keystates import KeyStates

            # Map string to enum
            try:
                key_enum = SoundTouchKeys[key]
            except KeyError:
                raise ValueError(f"Invalid key: {key}") from None

            state_map = {
                "press": KeyStates.Press,
                "release": KeyStates.Release,
                "both": KeyStates.Both,
            }

            if state not in state_map:
                raise ValueError(
                    f"Invalid state: {state}. Must be 'press', 'release', or 'both'"
                )

            state_enum = state_map[state]

            logger.info(
                "Simulating key press on %s: %s (%s)",
                self.ip,
                key,
                state,
                extra={"device_ip": self.ip, "key": key, "state": state},
            )

            await asyncio.to_thread(self._client.Action, key_enum, state_enum)

        except Exception as e:
            logger.exception("Failed to press key %s on %s", key, self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    @staticmethod
    def _build_preset_payload(
        preset_number: int,
        station_url: str,
        station_name: str,
        oct_backend_url: str,
        station_image_url: str,
        station_uuid: str,
    ) -> str:
        """Build XML payload for the /storePreset endpoint.

        Encodes stream data as base64 JSON for the Orion adapter and wraps
        it in the ContentItem XML expected by the Bose device.

        Returns:
            XML string for POST /storePreset.
        """
        stream_data = {
            "streamUrl": station_url,
            "name": station_name,
            "imageUrl": station_image_url,
        }
        if not station_url and station_uuid:
            stream_data["tuneinId"] = station_uuid

        base64_data = base64.urlsafe_b64encode(
            json.dumps(stream_data).encode()
        ).decode()

        orion_url = (
            f"{oct_backend_url}/core02/svc-bmx-adapter-orion/prod/orion/station"
            f"?data={base64_data}"
        )

        safe_name = xml_escape(station_name)
        art_xml = (
            f"<containerArt>{xml_escape(station_image_url)}</containerArt>"
            if station_image_url
            else ""
        )
        return (
            f'<preset id="{preset_number}" createdOn="0" updatedOn="0">'
            f'<ContentItem source="LOCAL_INTERNET_RADIO" type="stationurl" '
            f'location="{orion_url}" sourceAccount="" isPresetable="true">'
            f"<itemName>{safe_name}</itemName>"
            f"{art_xml}"
            f"</ContentItem></preset>"
        )

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
        """
        Store a preset on the Bose device using LOCAL_INTERNET_RADIO + Orion adapter.

        Programs the device's physical preset button to call OCT's BMX Orion adapter.
        The Orion adapter decodes the base64 payload and returns the stream URL.

        Args:
            device_id: Bose device identifier
            preset_number: Preset slot (1-6)
            station_url: RadioBrowser stream URL
            station_name: Station display name
            oct_backend_url: OCT backend base URL (e.g., "http://192.168.1.108:7777")
            station_image_url: Optional station logo URL
            station_uuid: Optional station UUID for TuneIn fallback

        Raises:
            DeviceConnectionError: If device is unreachable
            ValueError: If preset_number not in 1-6
        """
        if not 1 <= preset_number <= 6:
            raise ValueError(f"Preset number must be 1-6, got {preset_number}")

        try:
            xml_payload = self._build_preset_payload(
                preset_number,
                station_url,
                station_name,
                oct_backend_url,
                station_image_url,
                station_uuid,
            )

            logger.info(
                "Storing preset %d on %s",
                preset_number,
                self.ip,
                extra={
                    "device_ip": self.ip,
                    "device_id": device_id,
                    "preset_number": preset_number,
                },
            )

            store_url = f"{self.base_url}/storePreset"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    store_url,
                    content=xml_payload,
                    headers={"Content-Type": "application/xml"},
                )
                response.raise_for_status()

            logger.info(
                "Bose device programmed with LOCAL_INTERNET_RADIO + Orion (preset %d)",
                preset_number,
            )

        except httpx.HTTPStatusError as e:
            logger.exception(
                "HTTP error storing preset %d on %s",
                preset_number,
                self.base_url,
            )
            raise DeviceConnectionError(
                self.ip, f"HTTP {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.exception(
                "Failed to store preset %d on %s",
                preset_number,
                self.base_url,
            )
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def get_volume(self) -> VolumeInfo:
        """Get current volume state from device."""
        try:
            vol = await asyncio.to_thread(self._client.GetVolume)
            return VolumeInfo(
                actual=vol.Actual,
                target=vol.Target,
                muted=vol.IsMuted,
            )
        except Exception as e:
            logger.exception("Failed to get volume from %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def set_volume(self, level: int) -> None:
        """Set volume level (0-100)."""
        try:
            await asyncio.to_thread(self._client.SetVolumeLevel, level)
        except Exception as e:
            logger.exception("Failed to set volume on %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def set_mute(self, muted: bool) -> None:
        """Set mute state."""
        try:
            if muted:
                await asyncio.to_thread(self._client.MuteOn, refresh=False)
            else:
                await asyncio.to_thread(self._client.MuteOff, refresh=False)
        except Exception as e:
            logger.exception("Failed to set mute on %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def set_name(self, name: str) -> None:
        """
        Set device name via REST API.

        Uses POST /name endpoint with XML body:
        <?xml version="1.0"?><name>Device Name</name>

        Args:
            name: New device name (1-30 chars, will be XML-escaped)

        Raises:
            ConnectionError: If device is unreachable
            ValueError: If name is empty or too long
        """
        if not name or not name.strip():
            raise ValueError("Device name cannot be empty")
        if len(name) > 30:
            raise ValueError("Device name must be 30 characters or fewer")

        try:
            escaped_name = xml_escape(name.strip())
            xml_payload = f'<?xml version="1.0"?><name>{escaped_name}</name>'

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/name",
                    content=xml_payload,
                    headers={"Content-Type": "application/xml"},
                )
                response.raise_for_status()

            logger.info(
                "Device name updated via REST API: %s",
                name,
                extra={"device_ip": self.ip, "new_name": name},
            )

        except httpx.HTTPStatusError as e:
            logger.exception(
                "HTTP error updating device name: %s",
                e.response.status_code,
                extra={"device_ip": self.ip, "status": e.response.status_code},
            )
            raise DeviceConnectionError(
                self.ip, f"HTTP {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.exception("Failed to set name on %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def close(self) -> None:
        """Close client connections (no-op for bosesoundtouchapi)."""
        pass

    # ---- Zone Methods ----

    def _zone_to_status(self, zone) -> ZoneStatus | None:
        """Convert bosesoundtouchapi Zone to ZoneStatus."""
        if not zone or not zone.MasterDeviceId:
            return None
        members = [
            ZoneMemberInfo(
                device_id=m.DeviceId or "",
                ip_address=m.IpAddress or "",
                role="master" if m.DeviceId == zone.MasterDeviceId else "slave",
            )
            for m in (zone.Members or [])
        ]
        if not members:
            return None
        # Ensure master is always present in the members list.
        # Some SoundTouch devices omit the master from the member list
        # when queried from certain perspectives.
        if not any(m.device_id == zone.MasterDeviceId for m in members):
            members.insert(
                0,
                ZoneMemberInfo(
                    device_id=zone.MasterDeviceId,
                    ip_address=zone.MasterIpAddress or "",
                    role="master",
                ),
            )
        return ZoneStatus(
            master_id=zone.MasterDeviceId,
            master_ip=zone.MasterIpAddress or "",
            is_master=bool(zone.IsZoneMaster),
            members=members,
        )

    async def get_zone_status(self) -> ZoneStatus | None:
        """Get current zone status from device.

        Returns None on connection failure (expected scenario when
        device is offline or unreachable).
        """
        try:
            zone = await asyncio.to_thread(self._client.GetZoneStatus, refresh=True)
            return self._zone_to_status(zone)
        except Exception as e:
            logger.debug("Failed to get zone status from %s: %s", self.base_url, e)
            return None

    async def create_zone(
        self, master_ip: str, members: list[ZoneMemberInfo]
    ) -> ZoneStatus:
        """Create a new multi-room zone."""
        try:
            from bosesoundtouchapi.models import Zone, ZoneMember

            master_device_id = self._client.Device.DeviceId

            # Build Zone object: master as first member, then slaves
            # Must use AddMember() since Zone constructor mishandles ZoneMember list
            zone = Zone(
                masterDeviceId=master_device_id,
                masterIpAddress=master_ip,
                isZoneMaster=True,
            )
            # Master must be first member in zone XML
            zone._Members.append(
                ZoneMember(ipAddress=master_ip, deviceId=master_device_id)
            )
            for m in members:
                zone.AddMember(ZoneMember(ipAddress=m.ip_address, deviceId=m.device_id))

            logger.info(
                "Creating zone on %s with %d slave(s)",
                self.ip,
                len(members),
                extra={"master_ip": master_ip, "member_count": len(members)},
            )

            await asyncio.to_thread(self._client.CreateZone, zone, delay=3)

            result = await asyncio.to_thread(self._client.GetZoneStatus, refresh=True)
            return self._zone_to_status(result) or ZoneStatus(
                master_id=master_device_id,
                master_ip=master_ip,
                is_master=True,
                members=[
                    ZoneMemberInfo(
                        device_id=m.device_id, ip_address=m.ip_address, role="slave"
                    )
                    for m in members
                ],
            )
        except Exception as e:
            logger.exception("Failed to create zone on %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def add_zone_members(self, members: list[ZoneMemberInfo]) -> None:
        """Add members to existing zone."""
        try:
            from bosesoundtouchapi.models import ZoneMember

            zone_members = [
                ZoneMember(ipAddress=m.ip_address, deviceId=m.device_id)
                for m in members
            ]
            await asyncio.to_thread(self._client.AddZoneMembers, zone_members, delay=3)
        except Exception as e:
            logger.exception("Failed to add zone members on %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def remove_zone_members(self, members: list[ZoneMemberInfo]) -> None:
        """Remove members from existing zone."""
        try:
            from bosesoundtouchapi.models import ZoneMember

            zone_members = [
                ZoneMember(ipAddress=m.ip_address, deviceId=m.device_id)
                for m in members
            ]
            await asyncio.to_thread(self._client.RemoveZoneMembers, zone_members, delay=3)  # fmt: skip
        except Exception as e:
            logger.exception("Failed to remove zone members on %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def remove_zone(self) -> None:
        """Dissolve entire zone."""
        try:
            await asyncio.to_thread(self._client.RemoveZone, delay=3)
            logger.info("Zone removed on %s", self.base_url)
        except Exception as e:
            logger.exception("Failed to remove zone on %s", self.base_url)
            raise DeviceConnectionError(self.ip, str(e)) from e
