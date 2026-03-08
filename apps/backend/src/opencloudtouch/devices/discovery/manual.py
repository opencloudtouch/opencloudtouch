"""
Manual discovery fallback
Allows users to specify device IPs manually when SSDP/UPnP doesn't work
"""

import logging
from typing import List

from opencloudtouch.discovery import DeviceDiscovery, DiscoveredDevice

logger = logging.getLogger(__name__)


class ManualDiscovery(DeviceDiscovery):
    """Manual device discovery from configured IP list."""

    def __init__(self, device_ips: List[str]):
        """
        Initialize manual discovery.

        Args:
            device_ips: List of device IP addresses
        """
        self.device_ips = device_ips

    async def discover(self, timeout: int = 10) -> List[DiscoveredDevice]:
        """
        Create DiscoveredDevice entries from manual IP list.

        Args:
            timeout: Ignored for manual discovery

        Returns:
            List of devices from manual IP list
        """
        logger.info(f"Manual discovery: {len(self.device_ips)} device(s) configured")

        devices = [DiscoveredDevice(ip=ip, port=8090) for ip in self.device_ips]

        logger.info(f"Manual discovery: {len(devices)} device(s) created")
        return devices
