"""BMX RadioBrowser playback routes.

Resolves RadioBrowser station UUIDs to stream URLs in the BMX format
expected by SoundTouch devices. This enables RadioBrowser stations
to be used as device presets.

Endpoint:
    GET /bmx/radiobrowser/v1/playback/station/{uuid}
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from opencloudtouch.bmx.models import BmxAudio, BmxPlaybackResponse, BmxStream
from opencloudtouch.bmx.stream_utils import convert_https_to_http
from opencloudtouch.bmx.tunein import get_oct_base_url
from opencloudtouch.radio.adapter import get_radio_adapter
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
)

logger = logging.getLogger(__name__)

radiobrowser_router = APIRouter(tags=["bmx"])


@radiobrowser_router.get("/bmx/radiobrowser/v1/playback/station/{uuid}")
async def bmx_radiobrowser_playback(uuid: str) -> JSONResponse:
    """Resolve RadioBrowser station UUID to stream URL.

    The device calls this with a station UUID and expects a BMX-format
    JSON response with stream URLs for playback.
    """
    logger.info(f"[BMX RADIOBROWSER] Resolving station: {uuid}")

    adapter = get_radio_adapter()

    try:
        station = await adapter.get_station_by_uuid(uuid)
    except RadioBrowserTimeoutError as e:
        logger.error(f"[BMX RADIOBROWSER] Timeout: {e}")
        return JSONResponse(
            content={"error": f"RadioBrowser timeout: {e}"},
            status_code=504,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except RadioBrowserConnectionError as e:
        logger.error(f"[BMX RADIOBROWSER] Connection error: {e}")
        return JSONResponse(
            content={"error": f"RadioBrowser unavailable: {e}"},
            status_code=503,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except RadioBrowserError as e:
        if "not found" in str(e).lower():
            return JSONResponse(
                content={"error": f"Station {uuid} not found"},
                status_code=404,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        logger.error(f"[BMX RADIOBROWSER] Error: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # Convert HTTPS to HTTP for Bose device compatibility
    stream_url = convert_https_to_http(station.url)

    base_url = get_oct_base_url()
    reporting_url = f"{base_url}/bmx/radiobrowser/v1/reporting/station/{uuid}"

    stream = BmxStream(
        streamUrl=stream_url,
        links={"bmx_reporting": {"href": reporting_url}},
    )
    audio = BmxAudio(streamUrl=stream_url, streams=[stream])

    links = {
        "bmx_nowplaying": {
            "href": f"{base_url}/bmx/radiobrowser/v1/now-playing/station/{uuid}",
            "useInternalClient": "ALWAYS",
        },
        "bmx_reporting": {"href": reporting_url},
    }

    response = BmxPlaybackResponse(
        audio=audio,
        links=links,
        imageUrl=station.favicon or "",
        name=station.name,
    )

    logger.info(f"[BMX RADIOBROWSER] Resolved {uuid} → {stream_url}")

    return JSONResponse(
        content=response.model_dump(),
        headers={"Access-Control-Allow-Origin": "*"},
    )


@radiobrowser_router.get("/bmx/radiobrowser/v1/now-playing/station/{uuid}")
async def bmx_radiobrowser_now_playing(uuid: str) -> JSONResponse:
    """Now-playing stub for RadioBrowser stations."""
    logger.info(f"[BMX RADIOBROWSER NOW-PLAYING] Station: {uuid}")
    return JSONResponse(
        content={"status": "playing", "stationId": uuid},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@radiobrowser_router.post("/bmx/radiobrowser/v1/reporting/station/{uuid}")
async def bmx_radiobrowser_reporting(uuid: str) -> JSONResponse:
    """Reporting stub for RadioBrowser stations."""
    logger.info(f"[BMX RADIOBROWSER REPORTING] Station: {uuid}")
    return JSONResponse(
        content={"status": "ok"},
        headers={"Access-Control-Allow-Origin": "*"},
    )
