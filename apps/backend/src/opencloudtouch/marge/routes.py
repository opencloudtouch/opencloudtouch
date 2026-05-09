"""Marge (streaming.bose.com) account sync routes."""

import logging
from typing import Any
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from opencloudtouch.core.dependencies import (
    get_preset_repository,
    get_recents_repository,
)
from opencloudtouch.marge.xml_builder import (
    build_devices_xml,
    build_full_account_xml,
    build_presets_xml,
    build_recents_xml,
    build_sources_xml,
)
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.recents.repository import RecentsRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["marge"])

_MEDIA_XML = "application/xml"
_MEDIA_STREAMING_XML = "application/vnd.bose.streaming-v1.2+xml"


def _xml_response(element: ET.Element, media_type: str = _MEDIA_XML) -> Response:
    """Serialize an ElementTree element to a FastAPI XML Response.

    Args:
        element: Root XML element to serialize
        media_type: MIME type for the response (default: application/xml)

    Returns:
        FastAPI Response with UTF-8 encoded XML content
    """
    content = ET.tostring(element, encoding="utf-8", xml_declaration=True)
    return Response(content=content, media_type=media_type)


@router.get("/v1/systems/devices/{device_id}")
async def get_full_account(
    device_id: str,
    preset_repo: PresetRepository = Depends(get_preset_repository),
    recents_repo: RecentsRepository = Depends(get_recents_repository),
) -> Response:
    """Get full account sync for device.

    This endpoint is called by SoundTouch devices on boot to sync:
    - Presets (6 buttons)
    - Recents (recently played)
    - Sources (available sources)

    Args:
        device_id: Device MAC address (e.g., "689E194F7D2F")
        preset_repo: Preset repository dependency
        recents_repo: Recents repository dependency

    Returns:
        XML Response with <boseAccount> structure
    """
    logger.info(f"[MARGE] Full account sync for device {device_id}")

    presets = await preset_repo.get_all_presets(device_id)
    recents = await recents_repo.get_recents(device_id)

    logger.info(
        f"[MARGE] Returning {len(presets)} presets, {len(recents)} recents for {device_id}"
    )
    for p in presets:
        logger.debug(
            "[MARGE] Preset %d: name=%s, source=%s, location=%.80s",
            getattr(p, "preset_id", "?"),
            getattr(p, "station_name", "?"),
            getattr(p, "source", "?"),
            getattr(p, "location", "?"),
        )

    return _xml_response(build_full_account_xml(presets, recents))


@router.get("/v1/systems/devices/{device_id}/presets")
async def get_presets(
    device_id: str,
    preset_repo: PresetRepository = Depends(get_preset_repository),
) -> Response:
    """Get presets for device.

    Args:
        device_id: Device MAC address
        preset_repo: Preset repository dependency

    Returns:
        XML Response with <presets> structure
    """
    logger.info(f"[MARGE] Get presets for device {device_id}")

    presets = await preset_repo.get_all_presets(device_id)

    return _xml_response(build_presets_xml(presets))


@router.get("/v1/systems/devices/{device_id}/recents")
async def get_recents(
    device_id: str,
    recents_repo: RecentsRepository = Depends(get_recents_repository),
) -> Response:
    """Get recently played items for device.

    Args:
        device_id: Device MAC address
        recents_repo: Recents repository dependency

    Returns:
        XML Response with <recents> structure
    """
    logger.info(f"[MARGE] Get recents for device {device_id}")

    recents = await recents_repo.get_recents(device_id)

    return _xml_response(build_recents_xml(recents))


@router.get("/v1/systems/devices/{device_id}/sources")
async def get_sources(device_id: str) -> Response:
    """Get available sources for device.

    Args:
        device_id: Device MAC address

    Returns:
        XML Response with <sources> structure
    """
    logger.info(f"[MARGE] Get sources for device {device_id}")

    sources_xml = build_sources_xml()

    return _xml_response(sources_xml)


@router.get("/v1/systems/devices/{device_id}/devices")
async def get_devices(device_id: str) -> Response:
    """Get multiroom devices for device.

    Args:
        device_id: Device MAC address

    Returns:
        XML Response with <devices> structure
    """
    logger.info(f"[MARGE] Get devices for device {device_id}")

    # TODO: Implement multiroom device discovery
    devices: list[Any] = []

    return _xml_response(build_devices_xml(devices))


@router.post("/v1/systems/devices/{device_id}/power_on")
@router.put("/v1/systems/devices/{device_id}/power_on")
async def power_on(device_id: str) -> Response:
    """Device boot notification.

    SoundTouch devices call this on power-on to notify the server.

    Args:
        device_id: Device MAC address

    Returns:
        204 No Content (acknowledgement)
    """
    logger.info(f"[MARGE] Device {device_id} powered on")

    return Response(status_code=204)


@router.get("/v1/systems/devices/{device_id}/sourceproviders")
async def get_sourceproviders(device_id: str) -> Response:
    """Get available source providers for device.

    Args:
        device_id: Device MAC address

    Returns:
        XML Response with <sourceproviders> structure
    """
    logger.info(f"[MARGE] Get sourceproviders for device {device_id}")

    # Build XML manually (simple structure)
    root = ET.Element("sourceproviders")

    providers = [
        "TUNEIN",
        "STORED_MUSIC",
        "AUX",
        "BLUETOOTH",
    ]

    for provider in providers:
        provider_elem = ET.SubElement(root, "sourceProvider")
        provider_elem.set("source", provider)
        provider_elem.set("status", "AVAILABLE")

    return _xml_response(root)


# =============================================================================
# Streaming Endpoints (streaming.bose.com compatibility)
# =============================================================================


@router.post("/streaming/support/power_on")
@router.put("/streaming/support/power_on")
async def streaming_power_on() -> Response:
    """Device boot notification via streaming endpoint.

    SoundTouch devices call this on power-on to notify the server.
    The device data is in the XML body with device ID, serial number,
    firmware version, IP address, and diagnostic data.

    Returns:
        200 OK (acknowledgement)
    """
    logger.info("[MARGE/STREAMING] Device powered on via streaming endpoint")

    return Response(
        status_code=200, media_type="application/vnd.bose.streaming-v1.2+xml"
    )


@router.get("/streaming/sourceproviders")
async def streaming_sourceproviders() -> Response:
    """Get available source providers.

    Returns list of streaming source providers like TUNEIN, SPOTIFY, etc.

    Returns:
        XML Response with <sourceProviders> structure
    """
    logger.info("[MARGE/STREAMING] Get sourceproviders")

    # Build XML per ueberboese-api.yaml spec
    root = ET.Element("sourceProviders")

    # TuneIn provider (id=25)
    tunein = ET.SubElement(root, "sourceprovider")
    tunein.set("id", "25")
    ET.SubElement(tunein, "createdOn").text = "2012-09-19T12:43:00.000+00:00"
    ET.SubElement(tunein, "name").text = "TUNEIN"
    ET.SubElement(tunein, "updatedOn").text = "2012-09-19T12:43:00.000+00:00"

    # LOCAL_INTERNET_RADIO (id=11)
    local_radio = ET.SubElement(root, "sourceprovider")
    local_radio.set("id", "11")
    ET.SubElement(local_radio, "createdOn").text = "2014-01-01T00:00:00.000+00:00"
    ET.SubElement(local_radio, "name").text = "LOCAL_INTERNET_RADIO"
    ET.SubElement(local_radio, "updatedOn").text = "2014-01-01T00:00:00.000+00:00"

    return _xml_response(root, _MEDIA_STREAMING_XML)


@router.get("/streaming/account/{account_id}/full")
async def streaming_full_account(
    account_id: str,
    preset_repo: PresetRepository = Depends(get_preset_repository),
) -> Response:
    """Get full account sync via streaming endpoint.

    This is the streaming.bose.com version of the account sync endpoint.
    Returns complete account with all devices, presets, recents, and sources.

    Args:
        account_id: Account ID (e.g., "3784726")
        preset_repo: Preset repository dependency

    Returns:
        XML Response with <account> structure
    """
    logger.info(f"[MARGE/STREAMING] Full account sync for account {account_id}")

    # For now, return a generic device_id. In future, map account_id to device.
    # The device ID is typically its MAC address.
    device_id = "689E194F7D2F"  # TODO: Get from account mapping

    # Load presets from database
    presets = await preset_repo.get_all_presets(device_id)

    logger.info(
        f"[MARGE/STREAMING] Returning {len(presets)} presets for account {account_id}"
    )

    return _xml_response(build_full_account_xml(presets, []), _MEDIA_STREAMING_XML)


@router.post("/v1/scmudc/{device_id}")
async def scmudc_reporting(device_id: str) -> Response:
    """Device reporting/telemetry endpoint.

    Devices periodically call this to report status/telemetry data.
    We acknowledge but don't process the data.

    Args:
        device_id: Device MAC address

    Returns:
        200 OK
    """
    logger.debug(f"[SCMUDC] Report from device {device_id}")

    return Response(status_code=200)
