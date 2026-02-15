"""
Adapter for bosesoundtouchapi library
Wraps external library with our internal device client interfaces
"""

import logging
import os
from typing import List

from bosesoundtouchapi import SoundTouchClient as BoseClient
from bosesoundtouchapi import SoundTouchDevice

from opencloudtouch.core.exceptions import DeviceConnectionError, DiscoveryError
from opencloudtouch.devices.client import DeviceClient, DeviceInfo, NowPlayingInfo
from opencloudtouch.devices.discovery.ssdp import SSDPDiscovery
from opencloudtouch.discovery import DeviceDiscovery, DiscoveredDevice

logger = logging.getLogger(__name__)


class BoseDeviceDiscoveryAdapter(DeviceDiscovery):
    """Adapter using SSDP discovery for compatible devices."""

    async def discover(self, timeout: int = 10) -> List[DiscoveredDevice]:
        """
        Discover compatible devices using SSDP.

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered devices (IP + Name only, details loaded lazily)

        Raises:
            DiscoveryError: If discovery fails
        """
        logger.info(f"Starting discovery via SSDP (timeout: {timeout}s)")

        try:
            # Use SSDP discovery instead of mDNS (avoids port 5353 conflicts)
            ssdp = SSDPDiscovery(timeout=timeout)
            devices_dict = await ssdp.discover()

            logger.info(f"Discovery completed: {len(devices_dict)} device(s) found")

            discovered: List[DiscoveredDevice] = []

            for mac, device_info in devices_dict.items():
                ip = device_info.get("ip", "")
                name = device_info.get("name", "Unknown Device")
                port = 8090  # Default HTTP API port

                # Device details (model, mac, firmware) are fetched lazily in /api/devices/sync
                discovered.append(DiscoveredDevice(ip=ip, port=port, name=name))

            logger.info(
                f"Discovered {len(discovered)} device(s): {[d.name for d in discovered]}"
            )
            return discovered

        except Exception as e:
            logger.error(f"Discovery failed: {e}", exc_info=True)
            raise DiscoveryError(f"Failed to discover devices: {e}") from e


class BoseDeviceClientAdapter(DeviceClient):
    """Adapter wrapping bosesoundtouchapi library client."""

    def __init__(self, base_url: str, timeout: float = 5.0):
        """
        Initialize client adapter.

        Args:
            base_url: Base URL of device (e.g., http://192.168.1.100:8090)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Extract IP and port for BoseClient
        # BoseClient expects SoundTouchDevice object
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        self.ip = parsed.hostname or base_url.split("://")[1].split(":")[0]
        port = parsed.port or 8090

        # Create SoundTouchDevice with connectTimeout parameter
        # This initializes the device and loads info/capabilities
        device = SoundTouchDevice(host=self.ip, connectTimeout=int(timeout), port=port)

        self._client = BoseClient(device)

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
            info = self._client.GetInformation()

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
                f"Device {device_info.name} initialized",
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
            logger.error(f"Failed to get info from {self.base_url}: {e}", exc_info=True)
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
            now_playing = self._client.GetNowPlayingStatus()

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
                artwork_url=getattr(now_playing, "ArtUrl", None),
            )

        except Exception as e:
            logger.error(
                f"Failed to get now_playing from {self.base_url}: {e}", exc_info=True
            )
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
                f"Simulating key press on {self.ip}: {key} ({state})",
                extra={"device_ip": self.ip, "key": key, "state": state},
            )

            self._client.Action(key_enum, state_enum)

        except Exception as e:
            logger.error(
                f"Failed to press key {key} on {self.base_url}: {e}", exc_info=True
            )
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def store_preset(
        self,
        device_id: str,
        preset_number: int,
        station_url: str,
        station_name: str,
        oct_backend_url: str,
    ) -> None:
        """
        Store a preset on the Bose device.

        Programs the device's physical preset button to call OCT backend.
        OCT acts as HTTP proxy for HTTPS RadioBrowser streams.

        **Flow:**
        1. OCT programs Bose with: `http://{oct_ip}:7777/device/{device_id}/preset/{N}`
        2. User presses PRESET_N button on Bose device
        3. Bose requests OCT backend: `GET /device/{device_id}/preset/{N}`
        4. OCT fetches HTTPS stream from RadioBrowser
        5. OCT proxies stream as HTTP chunked transfer to Bose
        6. Bose plays HTTP stream ✅

        **Why proxy instead of direct URL?**
        - ✅ TESTED: Direct HTTPS URLs fail (LED white → orange)
        - ✅ TESTED: HTTP 302 redirect to HTTPS fails (LED white → orange)
        - ✅ SOLUTION: OCT as HTTP stream proxy (HTTPS → HTTP chunked transfer)

        Args:
            device_id: Bose device identifier (for OCT backend URL)
            preset_number: Preset slot (1-6)
            station_url: RadioBrowser stream URL (stored in DB, proxied by OCT!)
            station_name: Station display name
            oct_backend_url: OCT backend base URL (e.g., "http://192.168.178.108:7777")

        Raises:
            ConnectionError: If device is unreachable
            ValueError: If preset_number not in 1-6
        """
        if not 1 <= preset_number <= 6:
            raise ValueError(f"Preset number must be 1-6, got {preset_number}")

        try:
            from bosesoundtouchapi.models.preset import Preset

            # Build M3U playlist URL (absolute HTTP URL)
            # Hypothesis: Bose might parse playlist files better than direct stream URLs
            playlist_url = f"{oct_backend_url}/playlist/{device_id}/{preset_number}.m3u"
            
            # Also keep stream proxy URL for reference
            stream_proxy_url = f"{oct_backend_url}/device/{device_id}/preset/{preset_number}"

            logger.info(
                f"Storing preset {preset_number} on {self.ip}: {station_name}",
                extra={
                    "device_ip": self.ip,
                    "device_id": device_id,
                    "preset_number": preset_number,
                    "station_name": station_name,
                    "playlist_url": playlist_url,
                    "stream_proxy_url": stream_proxy_url,
                    "upstream_url": station_url,
                },
            )

            # Create Preset with absolute M3U playlist URL
            # Bose device will fetch the .m3u file and parse the stream URL from it
            preset = Preset(
                presetId=preset_number,
                source="INTERNET_RADIO",
                typeValue="stationurl",
                location=playlist_url,  # Absolute M3U playlist URL
                name=station_name,
                isPresetable=True,
            )

            # Call Bose API to program device
            self._client.StorePreset(preset)

            logger.info(
                f"✅ Bose device programmed with OCT BMX path: {relative_location} → {oct_stream_url}"
            )

        except Exception as e:
            logger.error(
                f"Failed to store preset {preset_number} on {self.base_url}: {e}",
                exc_info=True,
            )
            raise DeviceConnectionError(self.ip, str(e)) from e

    async def close(self) -> None:
        """Close client connections (no-op for bosesoundtouchapi)."""
        # BoseClient doesn't require explicit cleanup
        pass


# ==================== FACTORY FUNCTIONS ====================


def get_discovery_adapter(timeout: int = 10) -> DeviceDiscovery:
    """
    Factory function to get discovery adapter based on OCT_MOCK_MODE.

    Args:
        timeout: Discovery timeout in seconds

    Returns:
        DeviceDiscovery implementation (Mock or Real)
    """
    mock_mode = os.getenv("OCT_MOCK_MODE", "false").lower() == "true"

    if mock_mode:
        logger.info("[MOCK MODE] Using MockDiscoveryAdapter")
        from opencloudtouch.devices.discovery.mock import MockDiscoveryAdapter

        return MockDiscoveryAdapter(timeout=timeout)
    else:
        logger.info("[REAL MODE] Using BoseDeviceDiscoveryAdapter")
        adapter = BoseDeviceDiscoveryAdapter()
        return adapter


def get_device_client(base_url: str, timeout: float = 5.0) -> DeviceClient:
    """
    Factory function to get device client based on OCT_MOCK_MODE.

    Args:
        base_url: Base URL of device (e.g., http://192.168.1.100:8090)
        timeout: Request timeout in seconds

    Returns:
        DeviceClient implementation (Mock or Real)
    """
    mock_mode = os.getenv("OCT_MOCK_MODE", "false").lower() == "true"

    if mock_mode:
        # Extract device_id from base_url or use IP as fallback
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        ip = parsed.hostname or base_url.split("://")[1].split(":")[0]

        # For mock mode, we use MAC as device_id
        # In production, this would come from discovery
        # For testing, try to extract from known mocks
        from opencloudtouch.devices.client import DeviceInfo
        from opencloudtouch.devices.mock_client import MockDeviceClient

        # Try to find matching mock device by IP
        device_id = None
        for mac, device_data in MockDeviceClient.MOCK_DEVICES.items():
            info = device_data["info"]
            assert isinstance(info, DeviceInfo)
            if info.ip_address == ip:
                device_id = mac
                break

        if not device_id:
            # Fallback: Use first mock device
            device_id = list(MockDeviceClient.MOCK_DEVICES.keys())[0]
            logger.warning(
                f"[MOCK MODE] No mock device found for IP {ip}, using {device_id}"
            )

        logger.info(f"[MOCK MODE] Using MockDeviceClient for {device_id}")
        return MockDeviceClient(device_id=device_id, ip_address=ip)
    else:
        logger.info(f"[REAL MODE] Using BoseDeviceClientAdapter for {base_url}")
        return BoseDeviceClientAdapter(base_url=base_url, timeout=timeout)
