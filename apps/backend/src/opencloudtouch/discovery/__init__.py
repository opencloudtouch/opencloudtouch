"""
Device Discovery Interfaces
Abstrakte Basis für verschiedene Discovery-Mechanismen (SSDP, mDNS, Manual)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

# Default HTTP API port for Bose SoundTouch devices (/info, /volume, /now_playing, …)
SOUNDTOUCH_HTTP_PORT = 8090

# Port alias kept for backward compatibility — resolves to the same value as
# SOUNDTOUCH_HTTP_PORT.  The /info endpoint is served on port 8090 on all
# known SoundTouch devices; use OCT_DEVICE_HTTP_PORT to override at runtime.
SOUNDTOUCH_WEBSERVER_PORT = SOUNDTOUCH_HTTP_PORT


@dataclass
class DiscoveredDevice:
    """Ein durch Discovery gefundenes Gerät."""

    ip: str
    port: int = SOUNDTOUCH_HTTP_PORT
    name: Optional[str] = None
    model: Optional[str] = None
    mac_address: Optional[str] = None
    firmware_version: Optional[str] = None

    @property
    def base_url(self) -> str:
        """Base URL für HTTP API calls."""
        return (
            f"http://{self.ip}:{self.port}"  # NOSONAR — Bose devices only support HTTP
        )


class DeviceDiscovery(ABC):
    """Abstract base class for device discovery mechanisms."""

    @abstractmethod
    async def discover(self, timeout: int = 10) -> List[DiscoveredDevice]:
        """
        Discover compatible devices on the network.

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered devices

        Raises:
            DiscoveryError: If discovery fails
        """
        pass  # pragma: no cover
