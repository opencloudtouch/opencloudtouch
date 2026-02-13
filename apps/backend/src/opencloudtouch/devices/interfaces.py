"""Protocol interfaces for device management.

Defines abstract interfaces for repository, discovery, and synchronization.
Enables dependency injection with type safety while avoiding circular dependencies.
"""

from typing import List, Optional, Protocol

from opencloudtouch.db import Device
from opencloudtouch.devices.models import SyncResult
from opencloudtouch.discovery import DiscoveredDevice


class IDeviceRepository(Protocol):
    """Protocol for device repository operations.

    Defines the interface for data persistence layer.
    Implementations must provide async database operations.
    """

    async def initialize(self) -> None:
        """Initialize repository (create schema, migrations, etc)."""
        ...

    async def close(self) -> None:
        """Close repository (cleanup connections)."""
        ...

    async def get_all(self) -> List[Device]:
        """Get all devices from database.

        Returns:
            List of all devices, empty list if none found
        """
        ...

    async def get_by_device_id(self, device_id: str) -> Optional[Device]:
        """Get device by device_id.

        Args:
            device_id: Unique device identifier

        Returns:
            Device if found, None otherwise
        """
        ...

    async def upsert(self, device: Device) -> None:
        """Insert or update device.

        Args:
            device: Device to persist

        Raises:
            RuntimeError: If repository not initialized
        """
        ...

    async def delete_all(self) -> None:
        """Delete all devices from database.

        Warning: Destructive operation, use with caution.
        """
        ...


class IDiscoveryAdapter(Protocol):
    """Protocol for device discovery operations.

    Defines the interface for discovering devices on the network.
    Implementations can use SSDP, UPnP, manual IPs, or mock data.
    """

    async def discover(self, timeout: int = 10) -> List[DiscoveredDevice]:
        """Discover devices on the network.

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered devices with basic info (IP, MAC, name)

        Raises:
            TimeoutError: If discovery times out
            Exception: If discovery fails
        """
        ...


class IDeviceSyncService(Protocol):
    """Protocol for device synchronization operations.

    Defines the interface for orchestrating device discovery and persistence.
    Implementation handles discovery → query → persist workflow.
    """

    async def sync(self) -> SyncResult:
        """Synchronize devices to database.

        Discovers devices, queries each for detailed info, persists to DB.

        Returns:
            SyncResult with statistics (discovered, synced, failed)

        Raises:
            Exception: If sync workflow fails critically
        """
        ...
