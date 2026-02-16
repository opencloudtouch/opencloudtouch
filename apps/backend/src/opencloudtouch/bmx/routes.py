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
import os
import urllib.parse
import urllib.request
from typing import Any
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bmx"])


# =============================================================================
# Pydantic Models for BMX Responses
# =============================================================================


class BmxServiceId(BaseModel):
    """Service identifier."""

    name: str
    value: int


class BmxServiceAssets(BaseModel):
    """Service branding assets."""

    name: str
    description: str = ""
    color: str = "#000000"


class BmxService(BaseModel):
    """Individual BMX service entry."""

    id: BmxServiceId
    baseUrl: str
    assets: BmxServiceAssets
    streamTypes: list[str] = ["liveRadio"]
    askAdapter: bool = False
    authenticationModel: dict[str, Any] = Field(
        default_factory=lambda: {
            "anonymousAccount": {"autoCreate": True, "enabled": True}
        }
    )


class BmxServicesResponse(BaseModel):
    """BMX registry response."""

    askAgainAfter: int = 86400000  # 24 hours in ms
    bmx_services: list[BmxService]


class BmxStream(BaseModel):
    """Audio stream info."""

    hasPlaylist: bool = True
    isRealtime: bool = True
    streamUrl: str


class BmxAudio(BaseModel):
    """Audio playback info."""

    hasPlaylist: bool = True
    isRealtime: bool = True
    streamUrl: str
    streams: list[BmxStream] = []


class BmxPlaybackResponse(BaseModel):
    """Playback response with stream URL."""

    audio: BmxAudio
    imageUrl: str = ""
    name: str
    streamType: str = "liveRadio"


# =============================================================================
# TuneIn API Integration
# =============================================================================

TUNEIN_DESCRIBE_URL = "https://opml.radiotime.com/describe.ashx?id=%s"
TUNEIN_STREAM_URL = "http://opml.radiotime.com/Tune.ashx?id=%s&formats=mp3,aac,ogg"


async def resolve_tunein_station(station_id: str) -> BmxPlaybackResponse:
    """Resolve TuneIn station ID to playable stream URL.

    Args:
        station_id: TuneIn station ID (e.g., "s158432" for Absolut Relax)

    Returns:
        BmxPlaybackResponse with stream URLs
    """
    logger.info(f"[BMX TUNEIN] Resolving station: {station_id}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get station metadata
            describe_url = TUNEIN_DESCRIBE_URL % station_id
            describe_resp = await client.get(describe_url)
            describe_xml = describe_resp.text

            # Parse station info (TuneIn API response, trusted source)
            root = ElementTree.fromstring(describe_xml)  # nosec B314
            body = root.find("body")
            outline = body.find("outline") if body is not None else None
            station_elem = outline.find("station") if outline is not None else None

            name = "Unknown Station"
            logo = ""

            if station_elem is not None:
                name_elem = station_elem.find("name")
                logo_elem = station_elem.find("logo")
                name = name_elem.text if name_elem is not None else "Unknown Station"
                logo = logo_elem.text if logo_elem is not None else ""

            # Get stream URLs
            stream_url = TUNEIN_STREAM_URL % station_id
            stream_resp = await client.get(stream_url)
            stream_urls = [
                url.strip() for url in stream_resp.text.splitlines() if url.strip()
            ]

            if not stream_urls:
                raise ValueError(f"No stream URLs found for station {station_id}")

            primary_url = stream_urls[0]

            logger.info(f"[BMX TUNEIN] Resolved {station_id} → {primary_url}")

            streams = [BmxStream(streamUrl=url) for url in stream_urls]
            audio = BmxAudio(streamUrl=primary_url, streams=streams)

            return BmxPlaybackResponse(
                audio=audio,
                imageUrl=logo,
                name=name,
            )

    except Exception as e:
        logger.error(f"[BMX TUNEIN] Error resolving {station_id}: {e}")
        raise


# =============================================================================
# BMX Registry Endpoint
# =============================================================================


def get_oct_base_url() -> str:
    """Get OCT backend URL from environment."""
    return os.getenv("OCT_BACKEND_URL", "http://192.168.178.11:7777")


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
    ]

    response = BmxServicesResponse(bmx_services=services)

    logger.info(f"[BMX REGISTRY] Returning {len(services)} services")

    return JSONResponse(
        content=response.model_dump(),
        headers={"Content-Type": "application/json"},
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
        return JSONResponse(content=response.model_dump())
    except Exception as e:
        logger.error(f"[BMX TUNEIN] Playback error: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
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
        )

    try:
        # Decode base64 data
        json_str = base64.urlsafe_b64decode(data).decode("utf-8")
        json_obj = json.loads(json_str)

        stream_url = json_obj.get("streamUrl", "")
        image_url = json_obj.get("imageUrl", "")
        name = json_obj.get("name", "Custom Station")

        logger.info(f"[BMX ORION] Custom stream: {name} → {stream_url}")

        stream = BmxStream(streamUrl=stream_url)
        audio = BmxAudio(streamUrl=stream_url, streams=[stream])

        response = BmxPlaybackResponse(
            audio=audio,
            imageUrl=image_url,
            name=name,
        )

        return JSONResponse(content=response.model_dump())

    except Exception as e:
        logger.error(f"[BMX ORION] Error: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
        )


# =============================================================================
# Legacy BMX Resolve Endpoint (for backward compatibility)
# =============================================================================


@router.post("/bmx/resolve")
async def resolve_stream(request: Request) -> Response:
    """Resolve ContentItem to playable stream URL.

    Bose devices call this endpoint with a ContentItem XML to resolve:
    - TuneIn station IDs → direct stream URLs
    - Direct stream URLs → pass through
    - OCT stream proxy URLs → pass through

    This mimics the original Bose BMX server (bmx.bose.com).
    """
    try:
        body = await request.body()
        body_str = body.decode("utf-8")

        logger.info(f"[BMX RESOLVE] Request body: {body_str}")

        # Parse XML request (from trusted SoundTouch device)
        root = ElementTree.fromstring(body_str)  # nosec B314

        # Extract attributes
        source = root.get("source", "")
        location = root.get("location", "")
        station_id = root.get("stationId", "")
        item_name = root.find("itemName")
        station_name_elem = root.find("stationName")

        item_name_text = item_name.text if item_name is not None else "Unknown"
        station_name_text = (
            station_name_elem.text if station_name_elem is not None else item_name_text
        )

        logger.info(
            f"[BMX RESOLVE] source={source}, location={location}, stationId={station_id}"
        )

        # Handle OCT relative locations (/oct/device/{id}/preset/{N})
        # Resolve to absolute OCT stream proxy URL
        if location and location.startswith("/oct/device/"):
            # Extract device_id and preset_number from path
            import re

            match = re.match(r"/oct/device/([^/]+)/preset/(\d+)", location)
            if match:
                device_id = match.group(1)
                preset_number = match.group(2)

                # Get OCT backend URL from environment
                oct_url = os.getenv("OCT_BACKEND_URL", "http://192.168.178.11:7777")
                resolved_url = f"{oct_url}/device/{device_id}/preset/{preset_number}"

                logger.info(
                    f"[BMX RESOLVE] OCT location resolved: {location} → {resolved_url}"
                )

                # Build resolved ContentItem XML
                resolved_xml = f"""<ContentItem source="INTERNET_RADIO" type="stationurl" location="{resolved_url}" isPresetable="true">
  <itemName>{item_name_text}</itemName>
  <stationName>{station_name_text}</stationName>
</ContentItem>"""

                return Response(content=resolved_xml, media_type="application/xml")

        # Handle direct stream URLs or absolute OCT stream proxy URLs
        # These are already resolved, pass through as-is
        if location and (
            location.startswith("http://") or location.startswith("https://")
        ):
            logger.info("[BMX RESOLVE] Direct URL or OCT proxy - pass through")
            return Response(content=body_str, media_type="application/xml")

        # Handle TuneIn stations (not implemented yet - would need TuneIn API)
        if source == "TUNEIN" and station_id:
            logger.warning(
                f"[BMX RESOLVE] TuneIn station {station_id} not supported yet"
            )
            # For now, pass through
            return Response(content=body_str, media_type="application/xml")

        # Handle other sources (Spotify, etc.) - pass through
        if source and source not in ["INTERNET_RADIO", "TUNEIN"]:
            logger.info(f"[BMX RESOLVE] {source} source - pass through")
            return Response(content=body_str, media_type="application/xml")

        # If we can't resolve, return error
        logger.error("[BMX RESOLVE] Unable to resolve stream")
        return Response(
            content="<error>Unable to resolve stream</error>",
            status_code=400,
            media_type="application/xml",
        )

    except Exception as e:
        logger.error(f"[BMX RESOLVE] Error: {e}", exc_info=True)
        return Response(
            content="<error>Resolution failed</error>",
            status_code=500,
            media_type="application/xml",
        )
