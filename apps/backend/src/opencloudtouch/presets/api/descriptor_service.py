"""Station descriptor service for SoundTouch preset URLs.

This service generates JSON descriptors that SoundTouch devices fetch
when a preset button is pressed. The descriptor contains the stream URL
and metadata for playback.
"""

import logging
from typing import Optional

from opencloudtouch.presets.service import PresetService

logger = logging.getLogger(__name__)


class StationDescriptorService:
    """
    Service for generating station descriptors.

    Station descriptors are JSON documents that SoundTouch devices fetch
    when loading a preset. They contain the stream URL and metadata.
    """

    def __init__(self, preset_service: PresetService):
        """
        Initialize StationDescriptorService.

        Args:
            preset_service: Service for fetching preset data
        """
        self.preset_service = preset_service

    async def get_descriptor(
        self, device_id: str, preset_number: int
    ) -> Optional[dict]:
        """
        Generate station descriptor for a device preset.

        Args:
            device_id: Device identifier
            preset_number: Preset slot (1-6)

        Returns:
            Station descriptor dict if preset exists, None otherwise

        The descriptor format is optimized for SoundTouch devices:
        {
            "stationName": "Station Name",
            "streamUrl": "http://stream.url/path",
            "homepage": "https://station.homepage",
            "favicon": "https://station.favicon/icon.png",
            "uuid": "radiobrowser-uuid"
        }
        """
        preset = await self.preset_service.get_preset(device_id, preset_number)

        if not preset:
            logger.debug(
                f"No preset found for device {device_id}, preset {preset_number}"
            )
            return None

        descriptor = {
            "stationName": preset.station_name,
            "streamUrl": preset.station_url,
            "homepage": preset.station_homepage,
            "favicon": preset.station_favicon,
            "uuid": preset.station_uuid,
        }

        logger.debug(
            f"Generated descriptor for {device_id} preset {preset_number}: "
            f"{preset.station_name}"
        )

        return descriptor
