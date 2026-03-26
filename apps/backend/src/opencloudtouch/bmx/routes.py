"""BMX resolver routes for Bose SoundTouch devices.

This module implements the BMX (Bose Media eXchange) endpoints that the
SoundTouch device normally calls at bmx.bose.com. By redirecting the device
to OCT via USB configuration, these endpoints provide:

1. /bmx/registry/v1/services - Service registry (TuneIn, custom stations)
2. /bmx/tunein/v1/playback/station/{id} - TuneIn stream resolution
3. /core02/svc-bmx-adapter-orion/prod/orion/station - Custom stream playback
"""

import base64
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opencloudtouch.bmx.models import (
    BmxAudio,
    BmxPlaybackResponse,
    BmxService,
    BmxServiceAssets,
    BmxServiceId,
    BmxServicesResponse,
    BmxStream,
)
from opencloudtouch.bmx.stream_utils import convert_https_to_http
from opencloudtouch.bmx.tunein import get_oct_base_url, resolve_tunein_station

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bmx"])


# =============================================================================
# BMX Registry Endpoint
# =============================================================================


@router.get("/bmx/orion/now-playing/station/{station_id}")
@router.get("/bmx/orion/now-playing")
async def bmx_now_playing_stub(station_id: str | None = None) -> JSONResponse:
    """Stub endpoint for now-playing data.

    Device calls this to get currently playing track info.
    Returns minimal valid response to prevent errors.
    """
    logger.info(f"[BMX NOW-PLAYING] Station: {station_id or 'custom'}")
    return JSONResponse(
        content={
            "status": "playing",
            "stationId": station_id or "custom",
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.post("/bmx/orion/reporting/station/{station_id}")
@router.post("/bmx/orion/reporting")
async def bmx_reporting_stub(station_id: str | None = None) -> JSONResponse:
    """Stub endpoint for telemetry reporting.

    Device calls this to report playback events.
    Returns success to prevent errors.
    """
    logger.info(f"[BMX REPORTING] Station: {station_id or 'custom'}")
    return JSONResponse(
        content={"status": "ok"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/bmx/tunein/v1/now-playing/station/{station_id}")
async def bmx_tunein_now_playing(station_id: str) -> JSONResponse:
    """TuneIn now-playing stub.

    Device calls this to get currently playing track info.
    """
    logger.info(f"[BMX TUNEIN NOW-PLAYING] Station: {station_id}")
    return JSONResponse(
        content={"status": "playing", "stationId": station_id},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.post("/bmx/tunein/v1/reporting/station/{station_id}")
async def bmx_tunein_reporting(station_id: str) -> JSONResponse:
    """TuneIn reporting stub.

    Device calls this to report playback events.
    """
    logger.info(f"[BMX TUNEIN REPORTING] Station: {station_id}")
    return JSONResponse(
        content={"status": "ok"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/bmx/tunein/v1/favorite/{station_id}")
@router.post("/bmx/tunein/v1/favorite/{station_id}")
async def bmx_tunein_favorite(station_id: str) -> JSONResponse:
    """TuneIn favorite stub.

    Device calls this to mark/unmark stations as favorites.
    """
    logger.info(f"[BMX TUNEIN FAVORITE] Station: {station_id}")
    return JSONResponse(
        content={"status": "ok", "isFavorite": False},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/bmx/registry/v1/services")
async def bmx_services() -> JSONResponse:
    """Return list of available BMX services.

    This endpoint is called by the device after booting to discover
    available streaming services. We provide:
    - TUNEIN: Resolved via TuneIn API
    - LOCAL_INTERNET_RADIO: Custom stations via OCT
    """
    base_url = get_oct_base_url()

    services = [
        BmxService(
            id=BmxServiceId(name="TUNEIN", value=25),
            baseUrl=f"{base_url}/bmx/tunein",
            assets=BmxServiceAssets(
                name="TuneIn",
                description="Internet radio stations via TuneIn",
            ),
            streamTypes=["liveRadio", "onDemand"],
        ),
        BmxService(
            id=BmxServiceId(name="LOCAL_INTERNET_RADIO", value=11),
            baseUrl=f"{base_url}/core02/svc-bmx-adapter-orion/prod/orion",
            assets=BmxServiceAssets(
                name="Custom Stations",
                description="Custom radio stations via OCT",
            ),
            streamTypes=["liveRadio"],
        ),
        BmxService(
            id=BmxServiceId(name="RADIOBROWSER", value=99),
            baseUrl=f"{base_url}/bmx/radiobrowser",
            assets=BmxServiceAssets(
                name="RadioBrowser",
                description="Community radio stations via RadioBrowser.info",
            ),
            streamTypes=["liveRadio"],
        ),
    ]

    response = BmxServicesResponse(bmx_services=services)

    logger.info(f"[BMX REGISTRY] Returning {len(services)} services")

    return JSONResponse(
        content=response.model_dump(by_alias=True),
        headers={
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
    )


# =============================================================================
# TuneIn Playback Endpoint
# =============================================================================


@router.get("/bmx/tunein/v1/playback/station/{station_id}")
async def bmx_tunein_playback(station_id: str) -> JSONResponse:
    """Resolve TuneIn station to stream URL.

    The device calls this endpoint with a station ID (e.g., "s158432")
    and expects a JSON response with stream URLs.
    """
    try:
        response = await resolve_tunein_station(station_id)

        # Add CORS headers
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

        return JSONResponse(content=response.model_dump(), headers=headers)
    except Exception as e:
        logger.error(f"[BMX TUNEIN] Playback error: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )


# =============================================================================
# Custom Station Playback (Orion Adapter)
# =============================================================================


@router.get("/core02/svc-bmx-adapter-orion/prod/orion/station")
async def custom_stream_playback(request: Request) -> JSONResponse:
    """Play custom stream URL.

    This endpoint handles LOCAL_INTERNET_RADIO sources. The data parameter
    contains base64-encoded JSON with streamUrl, imageUrl, and name.
    """
    data = request.query_params.get("data", "")

    if not data:
        return JSONResponse(
            content={"error": "Missing data parameter"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    try:
        # Decode base64 data
        json_str = base64.urlsafe_b64decode(data).decode("utf-8")
        json_obj = json.loads(json_str)

        stream_url = json_obj.get("streamUrl", "")
        tunein_id = json_obj.get("tuneinId", "")
        image_url = json_obj.get("imageUrl", "")
        name = json_obj.get("name", "Custom Station")

        # TuneIn stations: resolve stream URL dynamically via TuneIn API
        if tunein_id and not stream_url:
            logger.info(f"[BMX ORION] TuneIn station detected: {tunein_id} ({name})")
            return await _resolve_tunein_for_orion(tunein_id)

        # Convert HTTPS to HTTP - Bose devices can't play HTTPS streams
        stream_url = convert_https_to_http(stream_url)

        logger.info(f"[BMX ORION] Custom stream: {name} → {stream_url}")

        stream = BmxStream(streamUrl=stream_url)
        audio = BmxAudio(streamUrl=stream_url, streams=[stream])

        # Add critical links
        base_url = get_oct_base_url()
        links = {
            "bmx_nowplaying": {
                "href": f"{base_url}/bmx/orion/now-playing",
                "useInternalClient": "ALWAYS",
            },
            "bmx_reporting": {"href": f"{base_url}/bmx/orion/reporting"},
        }

        response = BmxPlaybackResponse(
            audio=audio,
            links=links,
            imageUrl=image_url,
            name=name,
        )

        return JSONResponse(
            content=response.model_dump(),
            headers={"Access-Control-Allow-Origin": "*"},
        )

    except Exception as e:
        logger.error(f"[BMX ORION] Error: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )


async def _resolve_tunein_for_orion(tunein_id: str) -> JSONResponse:
    """Resolve TuneIn station dynamically for Orion playback.

    Called when a preset contains a tuneinId but no streamUrl.
    Fetches fresh stream URL from TuneIn API at playback time.
    """
    try:
        response = await resolve_tunein_station(tunein_id)
        return JSONResponse(
            content=response.model_dump(),
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as e:
        logger.error(f"[BMX ORION] TuneIn resolution failed for {tunein_id}: {e}")
        return JSONResponse(
            content={"error": f"TuneIn resolution failed: {e}"},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )
