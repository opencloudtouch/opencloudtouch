"""Domain service for preset management.

This service encapsulates the business logic for managing preset mappings.
It separates concerns: Routes handle HTTP, Service handles business logic,
Repository handles data persistence.
"""

import logging
from typing import List, Optional

from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository

logger = logging.getLogger(__name__)


class PresetService:
    """Service for managing preset mappings.

    This service provides business logic for preset operations,
    ensuring separation between HTTP layer (routes) and data layer (repository).
    """

    def __init__(self, repository: PresetRepository):
        """Initialize the preset service.

        Args:
            repository: PresetRepository instance for data persistence
        """
        self.repository = repository

    async def set_preset(
        self,
        device_id: str,
        preset_number: int,
        station_uuid: str,
        station_name: str,
        station_url: str,
        station_homepage: Optional[str] = None,
        station_favicon: Optional[str] = None,
    ) -> Preset:
        """Set a preset for a device.

        Creates or updates a preset mapping. When the physical preset button
        is pressed on the SoundTouch device, it will load the configured station.

        Args:
            device_id: Device identifier
            preset_number: Preset number (1-6)
            station_uuid: RadioBrowser station UUID
            station_name: Station name
            station_url: Stream URL
            station_homepage: Optional station homepage URL
            station_favicon: Optional station favicon URL

        Returns:
            The saved Preset object

        Raises:
            ValueError: If preset_number is not between 1-6
        """
        preset = Preset(
            device_id=device_id,
            preset_number=preset_number,
            station_uuid=station_uuid,
            station_name=station_name,
            station_url=station_url,
            station_homepage=station_homepage,
            station_favicon=station_favicon,
        )

        saved_preset = await self.repository.set_preset(preset)

        logger.info(
            f"Set preset {preset_number} for device {device_id}: {station_name}"
        )

        return saved_preset

    async def get_preset(self, device_id: str, preset_number: int) -> Optional[Preset]:
        """Get a specific preset for a device.

        Args:
            device_id: Device identifier
            preset_number: Preset number (1-6)

        Returns:
            The Preset object if found, None otherwise
        """
        return await self.repository.get_preset(device_id, preset_number)

    async def get_all_presets(self, device_id: str) -> List[Preset]:
        """Get all presets for a device.

        Returns all configured presets (1-6) for the specified device.
        Empty slots are not included in the response.

        Args:
            device_id: Device identifier

        Returns:
            List of Preset objects
        """
        return await self.repository.get_all_presets(device_id)

    async def clear_preset(self, device_id: str, preset_number: int) -> bool:
        """Clear a specific preset for a device.

        Args:
            device_id: Device identifier
            preset_number: Preset number (1-6)

        Returns:
            True if preset was deleted, False if it didn't exist
        """
        result = await self.repository.clear_preset(device_id, preset_number)

        if result:
            logger.info(f"Cleared preset {preset_number} for device {device_id}")

        return result

    async def clear_all_presets(self, device_id: str) -> int:
        """Clear all presets for a device.

        Args:
            device_id: Device identifier

        Returns:
            Number of presets deleted
        """
        count = await self.repository.clear_all_presets(device_id)

        logger.info(f"Cleared {count} presets for device {device_id}")

        return count
