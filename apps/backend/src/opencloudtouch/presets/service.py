"""Domain service for preset management.

This service encapsulates the business logic for managing preset mappings.
It separates concerns: Routes handle HTTP, Service handles business logic,
Repository handles data persistence.
"""

import base64
import json
import logging
import re
from typing import List, Optional
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

import httpx

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
            source="LOCAL_INTERNET_RADIO",  # OCT-managed presets from RadioBrowser
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
                    station_url=station_url,
                    station_name=station_name,
                    oct_backend_url=oct_backend_url,
                    station_image_url=station_favicon or "",
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

        return bool(result)

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

    async def sync_presets_from_device(self, device_id: str) -> int:
        """Sync presets from physical device to OCT database.

        Fetches presets from device's /presets endpoint and imports them into OCT.
        This is useful when a device was configured by another OCT instance or manually.

        Args:
            device_id: Device identifier

        Returns:
            Number of presets synced

        Raises:
            ValueError: If device not found
            httpx.HTTPError: If device is unreachable
        """
        # 1. Get device IP
        device = await self.device_repository.get_by_device_id(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        # 2. Fetch presets from device
        device_url = f"http://{device.ip}:8090/presets"
        logger.info(
            f"Syncing presets from device {device_id} ({device.ip})",
            extra={"device_id": device_id, "device_ip": device.ip},
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(device_url)
            response.raise_for_status()

        # 3. Parse XML - XML from trusted local Bose device, not user input
        root = ET.fromstring(response.content)  # nosec B314
        synced_count = 0

        for preset_elem in root.findall("preset"):
            preset_id = preset_elem.get("id")
            if not preset_id:
                continue

            try:
                preset_number = int(preset_id)
                if preset_number < 1 or preset_number > 6:
                    continue
            except ValueError:
                continue

            # Parse ContentItem
            content_item = preset_elem.find("ContentItem")
            if content_item is None:
                continue

            source = content_item.get("source", "")
            location = content_item.get("location", "")
            item_name_elem = content_item.find("itemName")
            station_name = (
                item_name_elem.text if item_name_elem is not None else "Unknown"
            )

            # Parse station_uuid, station_url, and preset_source based on source type
            preset_source: Optional[str] = None

            if source == "LOCAL_INTERNET_RADIO":
                # Check if this is a Bose BMX adapter URL (cloud-dependent)
                # Format: http://content.api.bose.io:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data=BASE64
                if "content.api.bose.io" in location or "bmx-adapter" in location:
                    # This is a Bose cloud preset - decode and convert to OCT preset
                    try:
                        parsed_url = urlparse(location)
                        query_params = parse_qs(parsed_url.query)
                        data_b64 = query_params.get("data", [None])[0]

                        if not data_b64:
                            logger.warning(
                                f"Skipping preset {preset_number}: No data parameter in BMX URL"
                            )
                            continue

                        # Decode base64 and parse JSON
                        data_json = base64.b64decode(data_b64).decode("utf-8")
                        data = json.loads(data_json)

                        # Extract stream URL and metadata
                        stream_url = data.get("streamUrl")
                        bmx_station_name = data.get("name", station_name)

                        if not stream_url:
                            logger.warning(
                                f"Skipping preset {preset_number}: No streamUrl in BMX data"
                            )
                            continue

                        # Create synthetic UUID from stream URL
                        station_uuid = f"bmx_imported_{preset_number}_{hash(stream_url) & 0xFFFFFFFF:08x}"
                        station_url = stream_url
                        station_name = bmx_station_name
                        preset_source = (
                            "INTERNET_RADIO"  # Direct stream URL, cloud-independent
                        )

                        logger.info(
                            f"Importing BMX preset {preset_number}: {station_name} → {stream_url[:50]}..."
                        )

                    except (ValueError, KeyError, json.JSONDecodeError) as e:
                        logger.warning(
                            f"Skipping preset {preset_number}: Failed to decode BMX URL: {e}"
                        )
                        continue

                else:
                    # OCT-managed preset: Extract station_uuid from location URL
                    # Format: http://host:port/stations/preset/{station_uuid}.mp3
                    uuid_match = re.search(r"/stations/preset/([^/.]+)", location)
                    if not uuid_match:
                        logger.warning(
                            f"Skipping preset {preset_number}: Invalid LOCAL_INTERNET_RADIO location: {location}"
                        )
                        continue

                    station_uuid = uuid_match.group(1)
                    station_url = location  # Keep OCT descriptor URL
                    preset_source = "LOCAL_INTERNET_RADIO"

                    logger.debug(
                        f"Importing LOCAL_INTERNET_RADIO preset {preset_number}: {station_name} (uuid: {station_uuid})"
                    )

            elif source == "TUNEIN":
                # TuneIn preset: location is like "/v1/playback/station/s24854"
                station_uuid = f"tunein_{location}"
                station_url = location
                preset_source = "TUNEIN"
                logger.debug(f"Importing TUNEIN preset {preset_number}: {station_name}")

            elif source == "INTERNET_RADIO":
                # Direct URL preset: location is stream URL
                station_uuid = f"internet_radio_{preset_number}"
                station_url = location
                preset_source = "INTERNET_RADIO"
                logger.debug(
                    f"Importing INTERNET_RADIO preset {preset_number}: {station_name}"
                )

            else:
                # Unknown source type - import with synthetic UUID
                logger.warning(
                    f"Importing preset {preset_number} with unknown source '{source}'"
                )
                station_uuid = f"{source}_{preset_number}"
                station_url = location
                preset_source = source  # Keep original source

            # Create preset record
            preset = Preset(
                device_id=device_id,
                preset_number=preset_number,
                station_uuid=station_uuid,
                station_name=station_name or "Unknown",
                station_url=station_url,
                station_homepage=None,
                station_favicon=None,
                source=preset_source,
            )

            # Save to database (upsert)
            await self.repository.set_preset(preset)
            synced_count += 1

            logger.info(
                f"Synced preset {preset_number}: {station_name} (source: {source})",
                extra={
                    "device_id": device_id,
                    "preset_number": preset_number,
                    "source": source,
                },
            )

        logger.info(
            f"Synced {synced_count} presets from device {device_id}",
            extra={"device_id": device_id, "synced_count": synced_count},
        )

        return synced_count
