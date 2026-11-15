"""Marge (streaming.bose.com) account sync routes."""

import logging
from datetime import datetime
from typing import Annotated, Any
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import fromstring as parse_xml_string
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from opencloudtouch.core.dependencies import (
    get_marge_service,
    get_stereo_pair_service,
)
from opencloudtouch.core.logging import clip_for_log
from opencloudtouch.core.source_types import BASE_SOURCES
from opencloudtouch.marge.service import MargeService
from opencloudtouch.recents.models import RecentPlay
from opencloudtouch.stereo_pairs.repository import DeviceAlreadyPairedError
from opencloudtouch.stereo_pairs.service import StereoPairService, UnknownDeviceError
from opencloudtouch.stereo_pairs.xml import (
    EMPTY_GROUP_XML,
    GROUP_DELETED_XML,
    GROUP_TEARDOWN_XML,
    MARGE_ERROR_DEVICE_IN_GROUP,
    MARGE_ERROR_INVALID_REQUEST,
    MARGE_ERROR_UNKNOWN_DEVICE,
    InvalidGroupError,
    build_error_xml,
    build_group_xml,
    parse_group_request,
)
from opencloudtouch.marge.xml_builder import (
    build_devices_xml,
    build_full_account_xml,
    build_streaming_account_xml,
    build_presets_xml,
    build_preset_response_xml,
    build_recent_response_xml,
    build_recents_response_xml,
    build_recents_xml,
    build_sources_xml,
    source_name_for_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["marge"])

_MEDIA_XML = "application/xml"
_MEDIA_STREAMING_XML = "application/vnd.bose.streaming-v1.2+xml"


def _xml_response(
    element: ET.Element, media_type: str = _MEDIA_XML, status_code: int = 200
) -> Response:
    """Serialize an ElementTree element to a FastAPI XML Response.

    Args:
        element: Root XML element to serialize
        media_type: MIME type for the response (default: application/xml)

    Returns:
        FastAPI Response with UTF-8 encoded XML content
    """
    content = ET.tostring(element, encoding="utf-8", xml_declaration=True)
    return Response(content=content, media_type=media_type, status_code=status_code)


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
    """Account sync of the speaker (every 60 s), answered in the ``<account>`` shape.

    The device is resolved from the account id (margeAccountUUID stored during
    discovery); an unknown account gets an account without devices.
    """
    logger.info("[MARGE/STREAMING] Full account sync for account %s", account_id)

    device_id = await marge.resolve_device_id_for_account(account_id)
    if not device_id:
        logger.warning(
            "[MARGE/STREAMING] No device mapped to account %s - returning empty presets",
            account_id,
        )
        return _xml_response(
            build_streaming_account_xml(account_id), _MEDIA_STREAMING_XML
        )

    presets, recents = await marge.get_full_account(device_id)
    logger.info(
        "[MARGE/STREAMING] Returning %d presets, %d recents for device %s (account %s)",
        len(presets),
        len(recents),
        device_id,
        account_id,
    )
    return _xml_response(
        build_streaming_account_xml(account_id, device_id, presets, recents),
        _MEDIA_STREAMING_XML,
    )


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


# ---------------------------------------------------------------------------
# Stereo pair groups (speaker -> OCT). The shapes were checked against captures
# of real speakers.
# ---------------------------------------------------------------------------

StereoPairServiceDep = Annotated[StereoPairService, Depends(get_stereo_pair_service)]


def _log_group_call(request: Request, status_code: int, body: bytes = b"") -> None:
    logger.info(
        "[MARGE/GROUP] %s %s -> %d request=%s",
        request.method,
        request.url.path,
        status_code,
        clip_for_log(body.decode("utf-8", errors="replace")),
    )


def _group_response(body: bytes, status_code: int = 200) -> Response:
    return Response(
        content=body, media_type=_MEDIA_STREAMING_XML, status_code=status_code
    )


def _group_error(code: str, message: str) -> Response:
    return _group_response(build_error_xml(code, message), 400)


MargeServiceDep = Annotated[MargeService, Depends(get_marge_service)]


@router.put(
    "/streaming/account/{account_id}/device/{device_id}", include_in_schema=False
)
async def rename_device(
    account_id: str, device_id: str, request: Request, marge: MargeServiceDep
) -> Response:
    """Speaker rename: the speaker only applies a new name after this answers 2xx."""
    body = await request.body()
    logger.info(
        "[MARGE/DEVICE] PUT %s request=%s",
        request.url.path,
        clip_for_log(body.decode("utf-8", errors="replace")),
    )
    try:
        root = parse_xml_string(body)
    except (ParseError, ValueError):
        return Response(status_code=400)
    name = (root.findtext("name") or "").strip()
    if root.tag != "device" or not name or root.get("deviceid", device_id) != device_id:
        return Response(status_code=400)
    if not await marge.rename_device(device_id, name):
        return Response(status_code=404)
    device = ET.Element("device", {"deviceid": device_id})
    ET.SubElement(device, "name").text = name
    ET.SubElement(device, "macaddress").text = device_id
    return _xml_response(device, _MEDIA_STREAMING_XML)


@router.put(
    "/streaming/account/{account_id}/device/{device_id}/preset/{slot}",
    include_in_schema=False,
)
async def put_device_preset(
    account_id: str, device_id: str, slot: int, request: Request, marge: MargeServiceDep
) -> Response:
    """Speaker stored a preset on its own: take it over and echo the stored entry."""
    body = await request.body()
    logger.info(
        "[MARGE/PRESET] PUT %s request=%s",
        request.url.path,
        clip_for_log(body.decode("utf-8", errors="replace")),
    )
    try:
        root = parse_xml_string(body)
    except (ParseError, ValueError):
        return Response(status_code=400)
    location = (root.findtext("location") or "").strip()
    name = (root.findtext("name") or root.findtext("username") or "").strip()
    if root.tag != "preset" or not location or not 1 <= slot <= 6:
        return Response(status_code=400)
    stored = await marge.store_preset(
        device_id, slot, (root.findtext("sourceid") or "").strip(), name, location
    )
    return _xml_response(build_preset_response_xml(stored), _MEDIA_STREAMING_XML)


@router.delete(
    "/streaming/account/{account_id}/device/{device_id}/preset/{slot}",
    include_in_schema=False,
)
async def delete_device_preset(
    account_id: str, device_id: str, slot: int, marge: MargeServiceDep
) -> Response:
    """Speaker removed a preset (also sent before it overwrites a duplicate)."""
    logger.info(
        "[MARGE/PRESET] DELETE device %s slot %d", clip_for_log(device_id, 64), slot
    )
    if not 1 <= slot <= 6:
        return Response(status_code=400)
    await marge.delete_preset(device_id, slot)
    return Response(status_code=200)


@router.get(
    "/streaming/account/{account_id}/device/{device_id}/recents",
    include_in_schema=False,
)
async def get_device_recents(
    account_id: str, device_id: str, marge: MargeServiceDep
) -> Response:
    """The speaker reads its recents back after reporting one."""
    recents = await marge.get_recents(device_id)
    return _xml_response(build_recents_response_xml(recents), _MEDIA_STREAMING_XML)


@router.post(
    "/streaming/account/{account_id}/device/{device_id}/recent", include_in_schema=False
)
async def add_device_recent(
    account_id: str,
    device_id: str,
    request: Request,
    marge: Annotated[MargeService, Depends(get_marge_service)],
) -> Response:
    """Store what the speaker just played; answers 201 with the stored recent."""
    body = await request.body()
    logger.info(
        "[MARGE/RECENT] POST %s request=%s",
        request.url.path,
        clip_for_log(body.decode("utf-8", errors="replace")),
    )
    try:
        root = parse_xml_string(body)
    except (ParseError, ValueError):
        return Response(status_code=400)
    if root.tag != "recent" or not (root.findtext("location") or "").strip():
        return Response(status_code=400)
    source_id = (root.findtext("sourceid") or "").strip()
    played_at = None
    raw_time = (root.findtext("lastplayedat") or "").strip()
    if raw_time:
        try:
            played_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        except ValueError:
            played_at = None  # shortcut: unparsable time falls back to "now"
    stored = await marge.add_recent(
        RecentPlay(
            device_id=device_id,
            source=source_name_for_id(source_id) or source_id,
            location=(root.findtext("location") or "").strip(),
            name=(root.findtext("name") or "").strip(),
            played_at=played_at,
        )
    )
    return _xml_response(
        build_recent_response_xml(stored), _MEDIA_STREAMING_XML, status_code=201
    )


@router.post("/streaming/account/{account_id}/group/")
@router.post("/streaming/account/{account_id}/group", include_in_schema=False)
async def create_device_group(
    account_id: str, request: Request, stereo: StereoPairServiceDep
) -> Response:
    """Create a speaker group (stereo pair); idempotent for the same composition."""
    body = await request.body()
    try:
        pair = await stereo.marge_create(parse_group_request(body))
    except DeviceAlreadyPairedError as exc:
        logger.warning("[MARGE/GROUP] Cannot create group: %s", clip_for_log(str(exc)))
        _log_group_call(request, 400, body)
        return _group_error(MARGE_ERROR_DEVICE_IN_GROUP, str(exc))
    except InvalidGroupError as exc:
        logger.warning(
            "[MARGE/GROUP] Invalid group request: %s", clip_for_log(str(exc))
        )
        _log_group_call(request, 400, body)
        return _group_error(MARGE_ERROR_INVALID_REQUEST, str(exc))
    _log_group_call(request, 201, body)
    response = _group_response(build_group_xml(pair), 201)
    # same form as the reference Marge server (it omits the /streaming prefix)
    response.headers["Location"] = (
        f"{str(request.base_url).rstrip('/')}/account/{account_id}/group/{pair.id}"
    )
    return response


@router.get("/streaming/account/{account_id}/device/{device_id}/group/")
@router.get(
    "/streaming/account/{account_id}/device/{device_id}/group", include_in_schema=False
)
async def get_device_group(
    account_id: str, device_id: str, request: Request, stereo: StereoPairServiceDep
) -> Response:
    """Return the group of a device, or an empty <group/> if it is not in one."""
    try:
        pair = await stereo.get_for_device(device_id)
    except UnknownDeviceError:
        _log_group_call(request, 400)
        return _group_error(MARGE_ERROR_UNKNOWN_DEVICE, "Device does not exist")
    _log_group_call(request, 200)
    if pair is None:
        return _group_response(EMPTY_GROUP_XML)
    return _group_response(build_group_xml(pair))


@router.put("/streaming/account/{account_id}/group/{group_id}")
@router.post(
    "/streaming/account/{account_id}/group/{group_id}", include_in_schema=False
)
async def update_device_group(
    account_id: str, group_id: int, request: Request, stereo: StereoPairServiceDep
) -> Response:
    """Rename a group (the only field a speaker updates)."""
    body = await request.body()
    try:
        pair = await stereo.marge_rename(group_id, parse_group_request(body).name)
    except InvalidGroupError as exc:
        _log_group_call(request, 400, body)
        return _group_error(MARGE_ERROR_INVALID_REQUEST, str(exc))
    if pair is None:
        _log_group_call(request, 400, body)
        return _group_error(MARGE_ERROR_UNKNOWN_DEVICE, "Group does not exist")
    _log_group_call(request, 200, body)
    return _group_response(build_group_xml(pair))


@router.delete("/streaming/account/{account_id}/group/{group_id}")
async def delete_device_group(
    account_id: str, group_id: int, request: Request, stereo: StereoPairServiceDep
) -> Response:
    """Dissolve a group. Idempotent: an unknown id is also a success."""
    await stereo.marge_dissolve(group_id)
    _log_group_call(request, 200)
    return _group_response(GROUP_DELETED_XML)


@router.delete("/streaming/account/{account_id}/group/", include_in_schema=False)
@router.delete("/streaming/account/{account_id}/group", include_in_schema=False)
async def teardown_account_groups(account_id: str, request: Request) -> Response:
    """Acknowledge a speaker's own group teardown (no group id in the path).

    OCT dissolves groups through its own API and keeps the state itself, so the
    speaker's report only needs a success answer.
    """
    _log_group_call(request, 200)
    return _group_response(GROUP_TEARDOWN_XML)


@router.get(
    "/streaming/account/{account_id}/provider_settings", include_in_schema=False
)
async def get_provider_settings(account_id: str) -> Response:
    """Static provider settings, same document as the reference Marge servers."""
    root = ET.Element("providerSettings")
    for key, value, provider in (
        ("ELIGIBLE_FOR_TRIAL", "false", "14"),
        ("STREAMING_QUALITY", "2", "15"),
    ):
        setting = ET.SubElement(root, "providerSetting")
        ET.SubElement(setting, "boseId").text = account_id
        ET.SubElement(setting, "keyName").text = key
        ET.SubElement(setting, "value").text = value
        ET.SubElement(setting, "providerId").text = provider
    return _xml_response(root, _MEDIA_STREAMING_XML)
