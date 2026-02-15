"""Domain service for preset management.

This service encapsulates the business logic for managing preset mappings.
It separates concerns: Routes handle HTTP, Service handles business logic,
Repository handles data persistence.
"""

import logging
from typing import List, Optional

from opencloudtouch.core.config import get_config
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.repository import PresetRepository

logger = logging.getLogger(__name__)


class PresetService:
    """Service for managing preset mappings.

    This service provides business logic for preset operations,
    ensuring separation between HTTP layer (routes) and data layer (repository).
    """

    def __init__(
        self, repository: PresetRepository, device_repository: DeviceRepository
    ):
        """Initialize the preset service.

        Args:
            repository: PresetRepository instance for preset data persistence
            device_repository: DeviceRepository instance for device lookups
        """
        self.repository = repository
        self.device_repository = device_repository

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

        Creates or updates a preset mapping AND programs the Bose device.
        This ensures the physical preset button will play the configured station.

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
            ValueError: If preset_number is not between 1-6 or device not found
        """
        # 1. Save to OpenCloudTouch database
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
            f"Set preset {preset_number} in database for device {device_id}: {station_name}"
        )

        # 2. Program Bose device via /storePreset API
        try:
            device = await self.device_repository.get_by_device_id(device_id)
            if not device:
                raise ValueError(f"Device {device_id} not found")

            from opencloudtouch.devices.adapter import get_device_client
            from opencloudtouch.core.config import get_config

            # Get OCT backend URL from config
            cfg = get_config()
            oct_backend_url = cfg.station_descriptor_base_url

            base_url = f"http://{device.ip}:8090"
            client = get_device_client(base_url)

            try:
                await client.store_preset(
                    device_id=device_id,
                    preset_number=preset_number,
                    station_url=station_url,  # Stored in DB, proxied by OCT!
                    station_name=station_name,
                    oct_backend_url=oct_backend_url,  # OCT HTTP stream proxy
                )
                logger.info(
                    f"✅ Bose device programmed: Preset {preset_number} = {station_name}"
                )
            finally:
                await client.close()

        except Exception as e:
            logger.error(
                f"Failed to program Bose device for preset {preset_number}: {e}",
                exc_info=True,
            )
            # Don't fail the whole operation if Bose programming fails
            # Database record is still saved, user can retry
            logger.warning(
                f"Preset {preset_number} saved to database but NOT programmed on Bose device"
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
