"""XML builder functions for marge responses."""

import base64
import json
import logging
from datetime import UTC
from typing import Any, Sequence
from xml.etree import ElementTree as ET

from opencloudtouch.core.config import get_config
from opencloudtouch.core.dlna_reference import (
    build_orion_location,
    from_station_url,
    server_id_from_account,
)
from opencloudtouch.core.source_types import BASE_SOURCES, source_type_for_streaming_id
from opencloudtouch.marge.source_repository import MediaServerSource

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


def build_preset_xml(
    preset: Any, sources: Sequence[MediaServerSource] = ()
) -> ET.Element:
    """Build XML element for a single preset.

    Supports two preset types:
    - SoundTouch presets (tests/mocks): slot, source, location, name, image_url
    - RadioBrowser presets (real): preset_number, station_name, station_url, station_favicon

    Args:
        preset: Preset model (either SoundTouch or RadioBrowser format)

    A native DLNA preset (``native_type`` set) whose server has an active row in
    ``sources`` is written as a STORED_MUSIC item; without the row it keeps the
    v1 Orion location.

    Returns:
        XML Element for <preset>
    """
    item_type, account = "stationurl", ""
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
        dlna_ref = from_station_url(preset.station_url) if source == "DLNA" else None
        native_row = (
            next((r for r in sources if r.server_id == dlna_ref.server_id), None)
            if dlna_ref is not None and getattr(preset, "native_type", None)
            else None
        )
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
        elif dlna_ref is not None and native_row is not None:
            source, location = "STORED_MUSIC", dlna_ref.object_id
            item_type, account = preset.native_type, native_row.account
        elif dlna_ref is not None:
            # A reference, never ``streamUrl=dlna://...``: OCT resolves it on press.
            location = build_orion_location(
                get_config().station_descriptor_base_url, dlna_ref, name
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
    content_item.set("type", item_type)
    content_item.set("location", location)
    content_item.set("sourceAccount", account)
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


def _row_source_element(parent: ET.Element, row: MediaServerSource) -> None:
    """Per-server source in the shape the speaker accepted in the spike."""
    source = ET.SubElement(
        parent, "source", {"id": str(row.source_id), "type": "Audio"}
    )
    ET.SubElement(source, "credential", {"type": "token"})
    ET.SubElement(source, "name").text = row.account
    ET.SubElement(source, "sourceproviderid").text = _STORED_MUSIC_ID
    ET.SubElement(source, "sourcename").text = "Mediaserver"
    ET.SubElement(source, "sourceSettings")
    ET.SubElement(source, "username").text = row.account


_EPOCH = "2018-01-01T00:00:00.000+00:00"


_STORED_MUSIC_ID = next(
    src.streaming_id for src in BASE_SOURCES if src.source_type == "STORED_MUSIC"
)


def _sources_by_name() -> dict[str, Any]:
    return {src.source_type: src for src in BASE_SOURCES}


def source_name_for_id(streaming_id: str) -> str | None:
    """Source type for the Marge source id a speaker reports (e.g. "25" -> TUNEIN)."""
    return source_type_for_streaming_id(streaming_id)


def _format_time(moment: Any) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


def build_recent_response_xml(
    recent: Any, sources: Sequence[MediaServerSource] = ()
) -> ET.Element:
    """Answer of ``POST .../device/{id}/recent``: the stored recent as a flat ``<recent>``."""
    now = _format_time(recent.played_at)
    element = ET.Element("recent", {"id": str(recent.id or 0)})
    ET.SubElement(element, "contentItemType").text = "stationurl"
    ET.SubElement(element, "createdOn").text = now
    ET.SubElement(element, "lastplayedat").text = now
    ET.SubElement(element, "location").text = recent.location
    ET.SubElement(element, "name").text = recent.name
    sources = list(sources)
    src = _sources_by_name().get(recent.source)
    row = next((r for r in sources if str(r.source_id) == recent.source), None)
    if row is not None:
        _row_source_element(element, row)
    elif src is not None and not (src.source_type == "STORED_MUSIC" and sources):
        _source_element(element, src)
    sourceid = str(row.source_id) if row else (src.streaming_id if src else "")
    ET.SubElement(element, "sourceid").text = sourceid
    ET.SubElement(element, "updatedOn").text = now
    return element


def _item_children(
    parent: ET.Element, item: ET.Element, now: str, sources: Sequence[MediaServerSource]
) -> str | None:
    """Fill the shared preset/recent children from a ``<ContentItem>`` element.

    Returns the id of the registered media server source the item uses, if any.
    """
    content = item.find("ContentItem")
    assert content is not None
    source_name = content.get("source", "")
    server_id = (
        server_id_from_account(content.get("sourceAccount", ""))
        if source_name == "STORED_MUSIC"
        else None
    )
    row = next(
        (
            r
            for r in sources
            if (server_id is not None and r.server_id == server_id)
            or str(r.source_id) == source_name
        ),
        None,
    )
    native = row is not None and server_id is not None
    ET.SubElement(parent, "containerArt").text = content.findtext("containerArt") or ""
    ET.SubElement(parent, "contentItemType").text = (
        content.get("type", "") if native else "stationurl"
    )
    ET.SubElement(parent, "createdOn").text = now
    ET.SubElement(parent, "location").text = content.get("location", "")
    ET.SubElement(parent, "name").text = content.findtext("itemName") or ""
    src = _sources_by_name().get(source_name)
    if row is not None:
        _row_source_element(parent, row)
    elif src is not None and not (src.source_type == "STORED_MUSIC" and sources):
        _source_element(parent, src)
    ET.SubElement(parent, "updatedOn").text = now
    ET.SubElement(parent, "username")
    return str(row.source_id) if row else None


def build_preset_response_xml(
    preset: Any, sources: Sequence[MediaServerSource] = ()
) -> ET.Element:
    """One ``<preset buttonNumber>`` entry as the speaker's Marge calls expect it."""
    sources = list(sources)
    element = build_preset_xml(preset, sources)
    entry = ET.Element("preset", {"buttonNumber": element.get("id", "")})
    sourceid = _item_children(entry, element, _EPOCH, sources)
    if sourceid:
        ET.SubElement(entry, "sourceid").text = sourceid
    return entry


def build_recents_response_xml(
    recents: list[Any] | None, sources: Sequence[MediaServerSource] = ()
) -> ET.Element:
    """``<recents>`` as listed in ``/full`` and answered to ``GET .../recents``."""
    sources = list(sources)
    recent_list = ET.Element("recents")
    for stored, recent in zip(recents or [], build_recents_xml(recents)):
        entry = ET.SubElement(recent_list, "recent", {"id": str(stored.id or 0)})
        row_id = _item_children(entry, recent, _EPOCH, sources)
        ET.SubElement(entry, "lastplayedat").text = _format_time(stored.played_at)
        src = _sources_by_name().get(stored.source)
        ET.SubElement(entry, "sourceid").text = row_id or (
            src.streaming_id if src else ""
        )
    return recent_list


def build_streaming_account_xml(
    account_id: str,
    device_id: str | None = None,
    presets: list[Any] | None = None,
    recents: list[Any] | None = None,
    sources: Sequence[MediaServerSource] = (),
) -> ET.Element:
    """Build the ``<account>`` document the speaker's own Marge sync expects.

    The speaker rejects any other root element ("account expected") and then
    fails its sync, which also breaks group creation (error 5580).
    Shape as the speaker sends and expects it.
    """
    now = _EPOCH
    sources = list(sources) if device_id else []
    account = ET.Element("account", {"id": account_id})
    ET.SubElement(account, "accountStatus").text = "OK"
    devices = ET.SubElement(account, "devices")
    if device_id:
        device = ET.SubElement(devices, "device", {"deviceid": device_id})
        ET.SubElement(device, "createdOn").text = now
        preset_list = ET.SubElement(device, "presets")
        for preset in presets or []:
            preset_list.append(build_preset_response_xml(preset, sources))
        device.append(build_recents_response_xml(recents, sources))
        ET.SubElement(device, "updatedOn").text = now
    ET.SubElement(account, "mode").text = "global"
    ET.SubElement(account, "preferredLanguage").text = "en"
    ET.SubElement(account, "providerSettings")
    source_list = ET.SubElement(account, "sources")
    for src in BASE_SOURCES:
        if src.source_type == "STORED_MUSIC" and sources:
            for row in sources:  # per-server entries replace the generic one
                _row_source_element(source_list, row)
        else:
            _source_element(source_list, src)
    return account
