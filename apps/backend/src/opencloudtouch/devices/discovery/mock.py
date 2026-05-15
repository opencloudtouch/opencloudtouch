"""
Mock discovery adapter for testing and development without real devices.

Provides predefined devices that simulate Bose® hardware.
"""

import logging
from typing import List

from opencloudtouch.discovery import (
    SOUNDTOUCH_HTTP_PORT,
    DeviceDiscovery,
    DiscoveredDevice,
)

logger = logging.getLogger(__name__)


class MockDiscoveryAdapter(DeviceDiscovery):
    """
    Mock discovery that returns predefined Bose® devices.

    Used for:
    - CI/CD testing (no hardware needed)
    - Local development without network access
    - Deterministic test scenarios
    """

    # Predefined mock devices (matches real device schema)
    MOCK_DEVICES = {
        "AABBCC112233": {
            "ip": "192.168.1.100",
            "mac": "AABBCC112233",
            "name": "Living Room",
            "model": "SoundTouch 20",
            "firmware_version": "28.0.12.46499",
        },
        "DDEEFF445566": {
            "ip": "192.168.1.101",
            "mac": "DDEEFF445566",
            "name": "Kitchen",
            "model": "SoundTouch 10",
            "firmware_version": "28.0.12.46499",
        },
        "112233445566": {
            "ip": "192.168.1.102",
            "mac": "112233445566",
            "name": "Bedroom",
            "model": "SoundTouch 30",
            "firmware_version": "28.0.12.46499",
        },
    }

    def __init__(self, timeout: int = 10):
        """
        Initialize mock discovery.

        Args:
            timeout: Ignored (for interface compatibility)
        """
        self.timeout = timeout

    async def discover(self, timeout: int = 10) -> List[DiscoveredDevice]:
        """
        Return predefined mock devices.

        Args:
            timeout: Ignored (for interface compatibility)

        Returns:
            List of DiscoveredDevice objects
        """
        logger.info("[MOCK] Returning %d predefined devices", len(self.MOCK_DEVICES))

        devices = []
        for mac, device_data in self.MOCK_DEVICES.items():
            devices.append(
                DiscoveredDevice(
                    ip=device_data["ip"],
                    port=SOUNDTOUCH_HTTP_PORT,
                    name=device_data["name"],
                    model=device_data["model"],
                    mac_address=mac,
                    firmware_version=device_data["firmware_version"],
                )
            )

        return devices
