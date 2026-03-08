"""
Device Discovery Interfaces
Abstrakte Basis für verschiedene Discovery-Mechanismen (SSDP, mDNS, Manual)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DiscoveredDevice:
    """Ein durch Discovery gefundenes Gerät."""

    ip: str
    port: int = 8090  # Default HTTP API port
    name: Optional[str] = None
    model: Optional[str] = None
    mac_address: Optional[str] = None
    firmware_version: Optional[str] = None

    @property
    def base_url(self) -> str:
        """Base URL für HTTP API calls."""
        return f"http://{self.ip}:{self.port}"


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
