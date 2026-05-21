"""XML builder functions for marge responses."""

import base64
import json
import logging
from typing import Any
from xml.etree import ElementTree as ET

from opencloudtouch.core.config import get_config

logger = logging.getLogger(__name__)

# All source types known from real SoundTouch device dumps.
# Tuples: (streaming_id, name, created_on_timestamp)
# IDs: TUNEIN=25, LOCAL_INTERNET_RADIO=11 from ueberboese-api.yaml;
# remaining IDs are synthetic (no official registry exists).
_TS_2013 = "2013-01-01T00:00:00.000+00:00"
_TS_2014 = "2014-01-01T00:00:00.000+00:00"
KNOWN_SOURCE_PROVIDERS: list[tuple[str, str, str]] = [
    ("25", "TUNEIN", "2012-09-19T12:43:00.000+00:00"),
    ("11", "LOCAL_INTERNET_RADIO", _TS_2014),
    ("12", "INTERNET_RADIO", _TS_2014),
    ("30", "SPOTIFY", "2014-06-01T00:00:00.000+00:00"),
    ("31", "AMAZON", "2015-01-01T00:00:00.000+00:00"),
    ("32", "DEEZER", "2015-01-01T00:00:00.000+00:00"),
    ("40", "BLUETOOTH", _TS_2013),
    ("41", "AUX", _TS_2013),
    ("42", "AIRPLAY", "2018-01-01T00:00:00.000+00:00"),
    ("43", "ALEXA", "2017-01-01T00:00:00.000+00:00"),
    ("50", "STORED_MUSIC", _TS_2014),
    ("51", "STORED_MUSIC_MEDIA_RENDERER", _TS_2014),
    ("52", "UPNP", _TS_2014),
    ("53", "QPLAY", _TS_2014),
    ("60", "NOTIFICATION", _TS_2013),
]


def _build_orion_location(station_url: str, station_name: str, image_url: str) -> str:
    """Build Orion adapter location URL for LOCAL_INTERNET_RADIO presets.

    Encodes stream data as base64 JSON, matching the format used by
    client_adapter._build_preset_payload(). This ensures the Marge boot-sync
    response produces the same ContentItem location as /storePreset.
    """
    oct_base = get_config().station_descriptor_base_url
    stream_data = {
        "streamUrl": station_url,
        "name": station_name,
        "imageUrl": image_url,
    }
    b64 = base64.urlsafe_b64encode(json.dumps(stream_data).encode()).decode()
    return f"{oct_base}/core02/svc-bmx-adapter-orion/prod/orion/station?data={b64}"


def build_preset_xml(preset: Any) -> ET.Element:
    """Build XML element for a single preset.

    Supports two preset types:
    - SoundTouch presets (tests/mocks): slot, source, location, name, image_url
    - RadioBrowser presets (real): preset_number, station_name, station_url, station_favicon

    Args:
        preset: Preset model (either SoundTouch or RadioBrowser format)

    Returns:
        XML Element for <preset>
    """
    # Determine preset type and extract attributes
    if hasattr(preset, "slot"):
        # SoundTouch preset (mock/test format)
        preset_id = str(preset.slot)
        source = preset.source
        location = preset.location
        name = preset.name
        image_url = getattr(preset, "image_url", "")
    else:
        # RadioBrowser preset (real format)
        preset_id = str(preset.preset_number)
        source = getattr(preset, "source", None) or "LOCAL_INTERNET_RADIO"
        name = preset.station_name
        image_url = preset.station_favicon or ""
        # Build Orion adapter URL so the device resolves streams via BMX
        # instead of attempting direct playback of raw stream URLs.
        if source == "TUNEIN":
            location = getattr(preset, "station_url", "") or ""
            if location and not location.startswith("/"):
                logger.warning(
                    "TUNEIN preset %s has non-relative location: %s",
                    preset_id,
                    location[:80],
                )
        else:
            location = _build_orion_location(preset.station_url, name, image_url)

    preset_elem = ET.Element("preset")
    preset_elem.set("id", preset_id)
    preset_elem.set("createdOn", str(int(preset.created_at.timestamp())))
    preset_elem.set("updatedOn", str(int(preset.updated_at.timestamp())))

    # ContentItem child element
    content_item = ET.SubElement(preset_elem, "ContentItem")
    content_item.set("source", source)
    content_item.set("type", "stationurl")
    content_item.set("location", location)
    content_item.set("sourceAccount", "")
    content_item.set("isPresetable", "true")

    # itemName
    item_name = ET.SubElement(content_item, "itemName")
    item_name.text = name

    # containerArt (if available)
    if image_url:
        container_art = ET.SubElement(content_item, "containerArt")
        container_art.text = image_url

    return preset_elem


def build_presets_xml(presets: list[Any]) -> ET.Element:
    """Build XML element for presets list.

    Args:
        presets: List of preset models

    Returns:
        XML Element for <presets>
    """
    presets_elem = ET.Element("presets")

    for preset in presets:
        preset_xml = build_preset_xml(preset)
        presets_elem.append(preset_xml)

    return presets_elem


def build_recents_xml(recents: list[Any] | None = None) -> ET.Element:
    """Build XML element for recents list.

    Args:
        recents: List of recent items (optional)

    Returns:
        XML Element for <recents>
    """
    recents_elem = ET.Element("recents")

    if recents:
        for recent in recents:
            recent_elem = ET.SubElement(recents_elem, "recent")

            content_item = ET.SubElement(recent_elem, "ContentItem")
            content_item.set("source", recent.source)
            content_item.set("type", "stationurl")
            content_item.set("location", recent.location)

            item_name = ET.SubElement(content_item, "itemName")
            item_name.text = recent.name

    return recents_elem


def build_sources_xml() -> ET.Element:
    """Build XML element for available sources.

    Returns:
        XML Element for <sources>
    """
    sources_elem = ET.Element("sources")

    for _, source_name, _ in KNOWN_SOURCE_PROVIDERS:
        source_elem = ET.SubElement(sources_elem, "source")
        source_elem.set("source", source_name)
        source_elem.set("status", "AVAILABLE")

    return sources_elem


def build_devices_xml(devices: list[Any] | None = None) -> ET.Element:
    """Build XML element for multiroom devices list.

    Args:
        devices: List of devices (optional, for multiroom)

    Returns:
        XML Element for <devices>
    """
    devices_elem = ET.Element("devices")

    # For now, return empty list (multiroom not implemented)
    if devices:
        for device in devices:
            device_elem = ET.SubElement(devices_elem, "device")
            device_elem.set("deviceId", device.device_id)
            device_elem.set("name", device.name)

    return devices_elem


def build_full_account_xml(
    presets: list[Any], recents: list[Any] | None = None
) -> ET.Element:
    """Build XML element for full account sync.

    Args:
        presets: List of preset models
        recents: List of recent items (optional)

    Returns:
        XML Element for <boseAccount>
    """
    account_elem = ET.Element("boseAccount")
    account_elem.set("version", "1.0")

    # Add presets
    presets_xml = build_presets_xml(presets)
    account_elem.append(presets_xml)

    # Add recents
    recents_xml = build_recents_xml(recents)
    account_elem.append(recents_xml)

    # Add sources
    sources_xml = build_sources_xml()
    account_elem.append(sources_xml)

    return account_elem
