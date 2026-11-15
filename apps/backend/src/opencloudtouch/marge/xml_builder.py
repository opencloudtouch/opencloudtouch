"""XML builder functions for marge responses."""

import base64
import json
import logging
from datetime import UTC
from typing import Any
from xml.etree import ElementTree as ET

from opencloudtouch.core.config import get_config
from opencloudtouch.core.source_types import BASE_SOURCES

logger = logging.getLogger(__name__)


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
        if source not in _sources_by_name():
            # e.g. INTERNET_RADIO imported from a speaker: without a known <source>
            # the speaker drops the preset; the Orion location plays it anyway.
            source = "LOCAL_INTERNET_RADIO"
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

    for src in BASE_SOURCES:
        source_elem = ET.SubElement(sources_elem, "source")
        source_elem.set("source", src.source_type)
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


def _source_element(parent: ET.Element, src: Any) -> ET.Element:
    source = ET.SubElement(parent, "source", {"id": src.streaming_id, "type": "Audio"})
    ET.SubElement(source, "createdOn").text = src.created_on
    ET.SubElement(source, "credential", {"type": "token"})
    ET.SubElement(source, "name").text = src.source_type
    ET.SubElement(source, "sourceproviderid").text = src.streaming_id
    ET.SubElement(source, "sourcename").text = src.source_type
    ET.SubElement(source, "sourceSettings")
    ET.SubElement(source, "updatedOn").text = src.created_on
    ET.SubElement(source, "username")
    return source


_EPOCH = "2018-01-01T00:00:00.000+00:00"


def _sources_by_name() -> dict[str, Any]:
    return {src.source_type: src for src in BASE_SOURCES}


def source_name_for_id(streaming_id: str) -> str | None:
    """Source type for the Marge source id a speaker reports (e.g. "25" -> TUNEIN)."""
    for src in BASE_SOURCES:
        if src.streaming_id == streaming_id:
            return src.source_type
    return None


def _format_time(moment: Any) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


def build_recent_response_xml(recent: Any) -> ET.Element:
    """Answer of ``POST .../device/{id}/recent``: the stored recent as a flat ``<recent>``."""
    now = _format_time(recent.played_at)
    element = ET.Element("recent", {"id": str(recent.id or 0)})
    ET.SubElement(element, "contentItemType").text = "stationurl"
    ET.SubElement(element, "createdOn").text = now
    ET.SubElement(element, "lastplayedat").text = now
    ET.SubElement(element, "location").text = recent.location
    ET.SubElement(element, "name").text = recent.name
    src = _sources_by_name().get(recent.source)
    if src is not None:
        _source_element(element, src)
    ET.SubElement(element, "sourceid").text = src.streaming_id if src else ""
    ET.SubElement(element, "updatedOn").text = now
    return element


def _item_children(parent: ET.Element, item: ET.Element, now: str) -> None:
    """Fill the shared preset/recent children from a ``<ContentItem>`` element."""
    content = item.find("ContentItem")
    assert content is not None
    ET.SubElement(parent, "containerArt").text = content.findtext("containerArt") or ""
    ET.SubElement(parent, "contentItemType").text = "stationurl"
    ET.SubElement(parent, "createdOn").text = now
    ET.SubElement(parent, "location").text = content.get("location", "")
    ET.SubElement(parent, "name").text = content.findtext("itemName") or ""
    src = _sources_by_name().get(content.get("source", ""))
    if src is not None:
        _source_element(parent, src)
    ET.SubElement(parent, "updatedOn").text = now
    ET.SubElement(parent, "username")


def build_preset_response_xml(preset: Any) -> ET.Element:
    """One ``<preset buttonNumber>`` entry as the speaker's Marge calls expect it."""
    element = build_preset_xml(preset)
    entry = ET.Element("preset", {"buttonNumber": element.get("id", "")})
    _item_children(entry, element, _EPOCH)
    return entry


def build_recents_response_xml(recents: list[Any] | None) -> ET.Element:
    """``<recents>`` as listed in ``/full`` and answered to ``GET .../recents``."""
    recent_list = ET.Element("recents")
    for stored, recent in zip(recents or [], build_recents_xml(recents)):
        entry = ET.SubElement(recent_list, "recent", {"id": str(stored.id or 0)})
        _item_children(entry, recent, _EPOCH)
        ET.SubElement(entry, "lastplayedat").text = _format_time(stored.played_at)
        src = _sources_by_name().get(stored.source)
        ET.SubElement(entry, "sourceid").text = src.streaming_id if src else ""
    return recent_list


def build_streaming_account_xml(
    account_id: str,
    device_id: str | None = None,
    presets: list[Any] | None = None,
    recents: list[Any] | None = None,
) -> ET.Element:
    """Build the ``<account>`` document the speaker's own Marge sync expects.

    The speaker rejects any other root element ("account expected") and then
    fails its sync, which also breaks group creation (error 5580).
    Shape as the speaker sends and expects it.
    """
    now = _EPOCH
    account = ET.Element("account", {"id": account_id})
    ET.SubElement(account, "accountStatus").text = "OK"
    devices = ET.SubElement(account, "devices")
    if device_id:
        device = ET.SubElement(devices, "device", {"deviceid": device_id})
        ET.SubElement(device, "createdOn").text = now
        preset_list = ET.SubElement(device, "presets")
        for preset in presets or []:
            preset_list.append(build_preset_response_xml(preset))
        device.append(build_recents_response_xml(recents))
        ET.SubElement(device, "updatedOn").text = now
    ET.SubElement(account, "mode").text = "global"
    ET.SubElement(account, "preferredLanguage").text = "en"
    ET.SubElement(account, "providerSettings")
    sources = ET.SubElement(account, "sources")
    for src in BASE_SOURCES:
        _source_element(sources, src)
    return account
