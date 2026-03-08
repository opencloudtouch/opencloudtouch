"""
Adapter for bosesoundtouchapi library
Wraps external library with our internal device client interfaces
"""

import logging
import os
from typing import List

from opencloudtouch.core.exceptions import DiscoveryError
from opencloudtouch.devices.client import DeviceClient
from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter  # re-export
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


# NOTE: BoseDeviceClientAdapter was extracted to devices/client_adapter.py (STORY-305).
# The import above keeps it available from this module for backward compatibility.


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
