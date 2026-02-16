"""FastAPI routes for Bose device preset streaming.

This module provides the stream proxy endpoint that Bose SoundTouch devices
call when playing custom presets. The device requests a stream and OCT
acts as an HTTP proxy to fetch HTTPS streams from RadioBrowser.

**Why proxy instead of redirect?**
- Bose SoundTouch devices cannot play HTTPS streams directly (certificate issues)
- HTTP 302 redirect to HTTPS URL fails with INVALID_SOURCE
- OCT proxies the stream: Fetches HTTPS → Serves as HTTP to Bose ✅
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as FastAPIPath
from fastapi.responses import Response, StreamingResponse

from opencloudtouch.core.dependencies import get_preset_service
from opencloudtouch.presets.service import PresetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device", tags=["device-presets"])
descriptor_router = APIRouter(prefix="/descriptor/device", tags=["device-descriptors"])


@router.get("/{device_id}/preset/{preset_id}")
async def stream_device_preset(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_id: int = FastAPIPath(..., ge=1, le=6, description="Preset number (1-6)"),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Stream proxy endpoint for Bose SoundTouch custom presets.

    **How it works:**
    1. User configures preset via OCT UI (e.g., "Absolut Relax" → Preset 1)
    2. OCT stores mapping in database: `device_id=689E194F7D2F, preset=1, url=https://stream.url`
    3. OCT programs Bose device with OCT backend URL:
       ```
       location="http://192.168.178.108:7777/device/689E194F7D2F/preset/1"
       ```
    4. User presses PRESET_1 button on Bose device
    5. Bose requests: `GET /device/689E194F7D2F/preset/1`
    6. OCT looks up preset in database
    7. **OCT proxies HTTPS stream as HTTP:** Fetches from RadioBrowser, streams to Bose
    8. Bose receives HTTP audio stream and plays ✅

    **Why HTTP proxy instead of direct HTTPS URL?**
    - ❌ Bose cannot play HTTPS streams directly (certificate validation fails)
    - ❌ HTTP 302 redirect to HTTPS URL → INVALID_SOURCE error
    - ✅ OCT acts as HTTP audio proxy: Fetches HTTPS → Serves as HTTP chunked transfer
    - ✅ Bose treats OCT like "TuneIn integration" (trusted HTTP source)

    **Example flow:**
    ```
    Request:  GET /device/689E194F7D2F/preset/1
    Response: HTTP 200 OK
              Content-Type: audio/mpeg
              Transfer-Encoding: chunked
              icy-name: Absolut Relax
              [Audio data stream: chunk1, chunk2, chunk3...]
    ```

    Args:
        device_id: Bose device identifier (from URL path)
        preset_id: Preset number 1-6 (from URL path)
        preset_service: Injected preset service

    Returns:
        StreamingResponse with proxied audio stream

    Raises:
        404: Preset not configured for this device
        502: RadioBrowser stream unavailable
        500: Internal server error
    """
    logger.info(
        f"[BOSE STREAM REQUEST] device={device_id}, preset={preset_id}",
        extra={"device_id": device_id, "preset_id": preset_id, "source": "bose_device"},
    )

    try:
        # Look up preset in OCT database
        preset = await preset_service.get_preset(device_id, preset_id)

        if not preset:
            logger.warning(
                f"[404] Preset {preset_id} not configured for device {device_id}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Preset {preset_id} not configured for device {device_id}",
            )

        logger.info(
            f"[HTTP PROXY] Fetching HTTPS stream from RadioBrowser: {preset.station_name}",
            extra={
                "device_id": device_id,
                "preset_id": preset_id,
                "station_name": preset.station_name,
                "upstream_url": preset.station_url,
                "protocol": "https→http_proxy",
            },
        )

        # Stream generator that manages the upstream connection
        async def stream_generator():
            """Generator that fetches and yields audio chunks from RadioBrowser."""
            try:
                async with httpx.AsyncClient(
                    timeout=30.0, follow_redirects=True
                ) as client:
                    async with client.stream(
                        "GET",
                        preset.station_url,
                        headers={
                            "User-Agent": "OpenCloudTouch/0.2.0 (Bose SoundTouch Proxy)",
                            "Icy-MetaData": "1",
                        },
                    ) as upstream_response:
                        # Check if stream is available
                        if upstream_response.status_code != 200:
                            logger.error(
                                f"[502] RadioBrowser stream unavailable: HTTP {upstream_response.status_code}",
                                extra={
                                    "device_id": device_id,
                                    "preset_id": preset_id,
                                    "upstream_status": upstream_response.status_code,
                                    "upstream_url": preset.station_url,
                                },
                            )
                            raise HTTPException(
                                status_code=502,
                                detail=f"RadioBrowser stream unavailable: HTTP {upstream_response.status_code}",
                            )

                        # Detect content type
                        content_type = upstream_response.headers.get(
                            "content-type", "audio/mpeg"
                        )

                        logger.info(
                            f"[STREAMING] {preset.station_name} → Bose device (HTTP proxy active)",
                            extra={
                                "device_id": device_id,
                                "preset_id": preset_id,
                                "content_type": content_type,
                                "upstream_headers": dict(upstream_response.headers),
                            },
                        )

                        # Stream audio chunks
                        async for chunk in upstream_response.aiter_bytes(
                            chunk_size=8192
                        ):
                            yield chunk

            except httpx.RequestError as e:
                logger.error(
                    f"[502] Failed to fetch RadioBrowser stream: {e}",
                    extra={
                        "device_id": device_id,
                        "preset_id": preset_id,
                        "upstream_url": preset.station_url,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to connect to RadioBrowser: {e}",
                )
            except Exception as e:
                logger.error(
                    f"[STREAM ERROR] Proxy interrupted: {e}",
                    extra={"device_id": device_id, "preset_id": preset_id},
                    exc_info=True,
                )
                raise

        # Return streaming response to Bose device
        return StreamingResponse(
            stream_generator(),
            media_type="audio/mpeg",  # Will be updated by generator
            headers={
                "icy-name": preset.station_name,
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Connection": "keep-alive",
                "Accept-Ranges": "none",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[STREAM ERROR] device={device_id}, preset={preset_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to serve preset stream",
        )


@descriptor_router.get("/{device_id}/preset/{preset_id}")
async def get_preset_descriptor(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_id: int = FastAPIPath(..., ge=1, le=6, description="Preset number (1-6)"),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Get preset descriptor XML for Bose SoundTouch device.

    **How it works:**
    Bose devices with `source="INTERNET_RADIO"` expect an XML descriptor endpoint
    (similar to TuneIn's `/v1/playback/station/...` endpoints).

    **Flow:**
    1. OCT programs Bose preset with descriptor URL:
       ```xml
       <ContentItem source="INTERNET_RADIO"
                    location="http://192.168.178.11:7777/descriptor/device/689E194F7D2F/preset/1">
         <itemName>Absolut relax</itemName>
       </ContentItem>
       ```
    2. User presses PRESET_1 button on Bose device
    3. Bose requests: `GET /descriptor/device/689E194F7D2F/preset/1`
    4. OCT returns XML with **direct stream URL**:
       ```xml
       <ContentItem source="INTERNET_RADIO" type="stationurl"
                    location="https://absolut-relax.live-sm.absolutradio.de/absolut-relax">
         <itemName>Absolut relax</itemName>
       </ContentItem>
       ```
    5. Bose fetches stream from direct URL and plays ✅

    Args:
        device_id: Bose device identifier
        preset_id: Preset number 1-6
        preset_service: Injected preset service

    Returns:
        XML Response with ContentItem descriptor

    Raises:
        404: Preset not configured
    """
    logger.info(
        f"[DESCRIPTOR REQUEST] device={device_id}, preset={preset_id}",
        extra={"device_id": device_id, "preset_id": preset_id, "source": "bose_device"},
    )

    preset = await preset_service.get_preset(device_id, preset_id)

    if not preset:
        logger.warning(
            f"[404] Preset {preset_id} not configured for device {device_id}"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Preset {preset_id} not configured for device {device_id}",
        )

    # Option B: HTTP 302 Redirect to stream (simpler than XML descriptor)
    logger.info(
        f"[DESCRIPTOR 302] Redirecting to {preset.station_url} for device {device_id}",
        extra={
            "device_id": device_id,
            "preset_id": preset_id,
            "station_name": preset.station_name,
            "station_url": preset.station_url,
        },
    )

    return Response(status_code=302, headers={"Location": preset.station_url})
