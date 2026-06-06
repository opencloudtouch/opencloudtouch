"""Marge (streaming.bose.com) account sync routes."""

import logging
from typing import Annotated, Any
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from opencloudtouch.core.dependencies import get_marge_service
from opencloudtouch.core.source_types import BASE_SOURCES
from opencloudtouch.marge.service import MargeService
from opencloudtouch.marge.xml_builder import (
    build_devices_xml,
    build_full_account_xml,
    build_presets_xml,
    build_recents_xml,
    build_sources_xml,
)

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
    marge: Annotated[MargeService, Depends(get_marge_service)],
) -> Response:
    """Get full account sync for device.

    This endpoint is called by SoundTouch devices on boot to sync:
    - Presets (6 buttons)
    - Recents (recently played)
    - Sources (available sources)

    Args:
        device_id: Device MAC address (e.g., "689E194F7D2F")
        marge: Marge service dependency

    Returns:
        XML Response with <boseAccount> structure
    """
    logger.info("[MARGE] Full account sync for device %s", device_id)

    presets, recents = await marge.get_full_account(device_id)

    logger.info(
        "[MARGE] Returning %d presets, %d recents for %s",
        len(presets),
        len(recents),
        device_id,
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
    marge: Annotated[MargeService, Depends(get_marge_service)],
) -> Response:
    """Get presets for device.

    Args:
        device_id: Device MAC address
        marge: Marge service dependency

    Returns:
        XML Response with <presets> structure
    """
    logger.info("[MARGE] Get presets for device %s", device_id)

    presets = await marge.get_presets(device_id)

    return _xml_response(build_presets_xml(presets))


@router.get("/v1/systems/devices/{device_id}/recents")
async def get_recents(
    device_id: str,
    marge: Annotated[MargeService, Depends(get_marge_service)],
) -> Response:
    """Get recently played items for device.

    Args:
        device_id: Device MAC address
        marge: Marge service dependency

    Returns:
        XML Response with <recents> structure
    """
    logger.info("[MARGE] Get recents for device %s", device_id)

    recents = await marge.get_recents(device_id)

    return _xml_response(build_recents_xml(recents))


@router.get("/v1/systems/devices/{device_id}/sources")
async def get_sources(device_id: str) -> Response:
    """Get available sources for device.

    Args:
        device_id: Device MAC address

    Returns:
        XML Response with <sources> structure
    """
    logger.info("[MARGE] Get sources for device %s", device_id)

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
    logger.info("[MARGE] Get devices for device %s", device_id)

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
    logger.info("[MARGE] Device %s powered on", device_id)

    return Response(status_code=204)


@router.get("/v1/systems/devices/{device_id}/sourceproviders")
async def get_sourceproviders(device_id: str) -> Response:
    """Get available source providers for device.

    Args:
        device_id: Device MAC address

    Returns:
        XML Response with <sourceproviders> structure
    """
    logger.info("[MARGE] Get sourceproviders for device %s", device_id)

    root = ET.Element("sourceproviders")

    for src in BASE_SOURCES:
        provider_elem = ET.SubElement(root, "sourceProvider")
        provider_elem.set("source", src.source_type)
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

    root = ET.Element("sourceProviders")
    for src in BASE_SOURCES:
        elem = ET.SubElement(root, "sourceprovider")
        elem.set("id", src.streaming_id)
        ET.SubElement(elem, "createdOn").text = src.created_on
        ET.SubElement(elem, "name").text = src.source_type
        ET.SubElement(elem, "updatedOn").text = src.created_on

    return _xml_response(root, _MEDIA_STREAMING_XML)


@router.get("/streaming/account/{account_id}/full")
async def streaming_full_account(
    account_id: str,
    marge: Annotated[MargeService, Depends(get_marge_service)],
) -> Response:
    """Get full account sync via streaming endpoint.

    This is the streaming.bose.com version of the account sync endpoint.
    Resolves the device_id from the account_id (margeAccountUUID) stored
    during device discovery, then returns that device's presets.

    Args:
        account_id: Account ID (e.g., "3784726")
        marge: Marge service dependency

    Returns:
        XML Response with <account> structure
    """
    logger.info("[MARGE/STREAMING] Full account sync for account %s", account_id)

    device_id = await marge.resolve_device_id_for_account(account_id)
    if not device_id:
        logger.warning(
            "[MARGE/STREAMING] No device mapped to account %s - returning empty presets",
            account_id,
        )
        return _xml_response(build_full_account_xml([], []), _MEDIA_STREAMING_XML)

    presets, recents = await marge.get_full_account(device_id)

    logger.info(
        "[MARGE/STREAMING] Returning %d presets, %d recents for device %s (account %s)",
        len(presets),
        len(recents),
        device_id,
        account_id,
    )

    return _xml_response(build_full_account_xml(presets, recents), _MEDIA_STREAMING_XML)


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
    logger.debug("[SCMUDC] Report from device %s", device_id)

    return Response(status_code=200)


@router.post("/streaming/stats/usage")
async def streaming_stats_usage() -> Response:
    """Accept device usage statistics (stub).

    Without this endpoint, the device retries repeatedly after
    statsServerUrl is redirected to OCT.

    Returns:
        200 OK
    """
    logger.debug("[STATS] Usage stats received (stub)")

    return Response(status_code=200)


# =============================================================================
# Legacy Marge Compatibility Endpoints (firmware 27.x preset playback)
# =============================================================================
# These endpoints are called by the device during preset playback.
# Without them, the device fails with CURL ErrorCode 7 → INVALID_SOURCE.
# See: GitHub Issue #167, Zimbo88's analysis.


@router.get("/streaming/device/{device_id}/streaming_token")
async def streaming_token(device_id: str) -> Response:
    """Return a dummy streaming token for device authentication.

    SoundTouch firmware 27.x requests this token before playing a preset.
    If the request fails, the device aborts playback with INVALID_SOURCE.
    The token value is not validated — any non-empty response suffices.

    Args:
        device_id: Device MAC address

    Returns:
        JSON with a dummy access token
    """
    logger.info("[MARGE/COMPAT] Streaming token requested for device %s", device_id)

    return Response(
        content='{"access_token":"opencloudtouch","token":"opencloudtouch","expires_in":86400}',
        media_type="application/json",
    )


@router.get("/v1/blacklist/{device_id}")
@router.post("/v1/blacklist/{device_id}")
async def blacklist_check(device_id: str) -> Response:
    """Content blacklist check — always returns empty (nothing blacklisted).

    The device checks this before playing content. If the endpoint is
    unreachable, some firmware versions refuse playback.

    Args:
        device_id: Device MAC address

    Returns:
        JSON with empty blacklist
    """
    logger.debug("[MARGE/COMPAT] Blacklist check for device %s", device_id)

    return Response(
        content='{"blacklisted":false,"items":[]}',
        media_type="application/json",
    )


@router.post("/setMargeAccount")
async def set_marge_account() -> Response:
    """Pair device with a Bose Cloud account (stub).

    The SoundTouch app calls this to associate a device with an account.
    OCT doesn't use real cloud accounts, but the device expects a 200 OK.
    The actual margeAccountUUID is set via Telnet or device-side API.

    Returns:
        200 OK with status XML
    """
    logger.info("[MARGE] setMargeAccount called (stub — accepted)")

    return Response(
        content="<status>/setMargeAccount</status>",
        media_type="application/xml",
        status_code=200,
    )
