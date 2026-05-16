"""Preset XML parser for Bose SoundTouch devices.

Parses the /presets endpoint XML response into Preset domain objects.
This module has a single responsibility — parsing — with no I/O or DB access.

Extracted from PresetService to fulfil the Single Responsibility Principle.
"""

import base64
import json
import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

from opencloudtouch.presets.models import Preset

logger = logging.getLogger(__name__)


class DevicePresetParser:
    """Parses Bose SoundTouch /presets XML into Preset domain objects.

    Pure parsing logic — no HTTP, no database access.
    Instantiate once and reuse; the class is stateless.
    """

    def parse_presets(self, device_id: str, xml_bytes: bytes) -> list[Preset]:
        """Parse a full /presets XML document into a list of Preset objects.

        Invalid or unsupported preset elements are silently skipped.

        Args:
            device_id: The device these presets belong to.
            xml_bytes:  Raw XML bytes from the device's /presets endpoint.

        Returns:
            List of valid Preset domain objects (may be empty).
        """
        root = ET.fromstring(xml_bytes)  # nosec B314
        presets: list[Preset] = []
        for elem in root.findall("preset"):
            preset = self.parse_element(elem, device_id)
            if preset is not None:
                presets.append(preset)
        return presets

    def parse_element(
        self, preset_elem: ET.Element, device_id: str
    ) -> Optional[Preset]:
        """Parse a single <preset> XML element into a Preset domain object.

        Args:
            preset_elem: The <preset> XML element.
            device_id:   The device this preset belongs to.

        Returns:
            A Preset object, or None if the element should be skipped.
        """
        preset_id = preset_elem.get("id")
        if not preset_id:
            return None

        try:
            preset_number = int(preset_id)
        except ValueError:
            return None

        if preset_number < 1 or preset_number > 6:
            return None

        content_item = preset_elem.find("ContentItem")
        if content_item is None:
            return None

        source = content_item.get("source", "")
        location = content_item.get("location", "")
        item_name_elem = content_item.find("itemName")
        station_name = item_name_elem.text if item_name_elem is not None else "Unknown"

        resolved = self._resolve_source(
            source, location, preset_number, station_name or "Unknown"
        )
        if resolved is None:
            return None

        station_uuid, station_url, preset_source, resolved_name = resolved
        return Preset(
            device_id=device_id,
            preset_number=preset_number,
            station_uuid=station_uuid,
            station_name=resolved_name or "Unknown",
            station_url=station_url,
            station_homepage=None,
            station_favicon=None,
            source=preset_source,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_source(
        self,
        source: str,
        location: str,
        preset_number: int,
        station_name: str,
    ) -> Optional[tuple[str, str, str, str]]:
        """Resolve station identifiers from a preset's source type.

        Returns:
            Tuple of (station_uuid, station_url, preset_source, station_name),
            or None if the preset should be skipped.
        """
        if source == "LOCAL_INTERNET_RADIO":
            return self._resolve_local_internet_radio(
                location, preset_number, station_name
            )
        if source == "TUNEIN":
            logger.debug("Importing TUNEIN preset %d: %s", preset_number, station_name)
            return f"tunein_{location}", location, "TUNEIN", station_name
        if source == "INTERNET_RADIO":
            logger.debug(
                "Importing INTERNET_RADIO preset %d: %s", preset_number, station_name
            )
            return (
                f"internet_radio_{preset_number}",
                location,
                "INTERNET_RADIO",
                station_name,
            )

        logger.warning(
            "Importing preset %d with unknown source '%s'", preset_number, source
        )
        return f"{source}_{preset_number}", location, source, station_name

    def _resolve_local_internet_radio(
        self, location: str, preset_number: int, station_name: str
    ) -> Optional[tuple[str, str, str, str]]:
        """Resolve a LOCAL_INTERNET_RADIO preset URL.

        Handles two sub-types:
        - Bose BMX cloud URL (base64-encoded JSON payload)
        - OCT-managed URL (UUID embedded in path)
        """
        if "content.api.bose.io" in location or "bmx-adapter" in location:
            return self._decode_bmx_preset(location, preset_number, station_name)
        return self._decode_oct_preset(location, preset_number, station_name)

    def _decode_bmx_preset(
        self, location: str, preset_number: int, station_name: str
    ) -> Optional[tuple[str, str, str, str]]:
        """Decode a Bose BMX cloud preset URL (base64 JSON payload).

        Returns:
            Tuple of (station_uuid, station_url, preset_source, station_name),
            or None if decoding fails.
        """
        try:
            parsed_url = urlparse(location)
            query_params = parse_qs(parsed_url.query)
            data_b64 = query_params.get("data", [None])[0]

            if not data_b64:
                logger.warning(
                    "Skipping preset %d: No data parameter in BMX URL", preset_number
                )
                return None

            data = json.loads(base64.urlsafe_b64decode(data_b64).decode("utf-8"))
            stream_url = data.get("streamUrl")

            if not stream_url:
                logger.warning(
                    "Skipping preset %d: No streamUrl in BMX data", preset_number
                )
                return None

            name = data.get("name", station_name)
            station_uuid = (
                f"bmx_imported_{preset_number}_{hash(stream_url) & 0xFFFFFFFF:08x}"
            )
            logger.info(
                "Importing BMX preset %d: %s → %s...",
                preset_number,
                name,
                stream_url[:50],
            )
            return station_uuid, stream_url, "INTERNET_RADIO", name

        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.warning(
                "Skipping preset %d: Failed to decode BMX URL: %s", preset_number, e
            )
            return None

    def _decode_oct_preset(
        self, location: str, preset_number: int, station_name: str
    ) -> Optional[tuple[str, str, str, str]]:
        """Decode an OCT-managed LOCAL_INTERNET_RADIO preset URL.

        Extracts the station UUID from path format:
        ``http://host:port/stations/preset/{station_uuid}.mp3``

        Returns:
            Tuple of (station_uuid, station_url, preset_source, station_name),
            or None if the UUID cannot be extracted.
        """
        uuid_match = re.search(r"/stations/preset/([^/.]+)", location)
        if not uuid_match:
            logger.warning(
                "Skipping preset %d: Invalid LOCAL_INTERNET_RADIO location: %s",
                preset_number,
                location,
            )
            return None

        station_uuid = uuid_match.group(1)
        logger.debug(
            "Importing LOCAL_INTERNET_RADIO preset %d: %s (uuid: %s)",
            preset_number,
            station_name,
            station_uuid,
        )
        return station_uuid, location, "LOCAL_INTERNET_RADIO", station_name
