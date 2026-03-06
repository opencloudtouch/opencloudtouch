"""M3U Playlist routes for SoundTouch preset playback.

This module provides playlist file endpoints that wrap stream URLs in M3U format.
Bose SoundTouch devices might parse playlist files better than direct stream URLs.

The hypothesis is that using .m3u playlist URLs instead of direct stream URLs
could work around the Bose HTTPS/streaming limitations.

Flow:
1. OCT stores preset with: location="http://{oct_ip}:7777/playlist/{device_id}/{N}.m3u"
2. User presses PRESET_N button on Bose device
3. Bose requests: GET http://{oct_ip}:7777/playlist/{device_id}/{N}.m3u
4. OCT returns M3U with actual stream URL inside
5. Bose parses M3U and fetches the stream URL
6. If stream is HTTPS, OCT provides HTTP proxy fallback

Author: OpenCloudTouch Team
Created: 2026-02-15 (Playlist-File Hypothesis Test)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as FastAPIPath
from fastapi.responses import PlainTextResponse

from opencloudtouch.core.dependencies import get_preset_service
from opencloudtouch.presets.service import PresetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playlist", tags=["playlist"])


async def _get_preset_content(
    preset_service: PresetService,
    device_id: str,
    preset_number: int,
    format_name: str,
) -> tuple[str, str]:
    """Fetch preset and return (station_name, stream_url) or raise HTTPException.

    Args:
        preset_service: Service for looking up presets
        device_id: Bose device identifier
        preset_number: Preset number (1-6)
        format_name: Format label for log messages (e.g., "M3U", "PLS")

    Returns:
        Tuple of (station_name, stream_url)

    Raises:
        HTTPException 404: Preset not configured
        HTTPException 500: No stream URL configured
    """
    preset = await preset_service.get_preset(device_id, preset_number)

    if not preset:
        logger.warning(
            f"{format_name}: Preset not found for device {device_id}, preset {preset_number}"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Preset {preset_number} not configured for device {device_id}",
        )

    stream_url = preset.station_url
    if not stream_url:
        logger.error(
            f"{format_name}: No stream URL for device {device_id}, preset {preset_number}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"No stream URL configured for preset {preset_number}",
        )

    return preset.station_name or "Unknown Station", stream_url


@router.get(
    "/{device_id}/{preset_number}.m3u",
    response_class=PlainTextResponse,
    responses={
        200: {
            "description": "M3U playlist file",
            "content": {"audio/x-mpegurl": {}},
        },
        404: {"description": "Preset not found"},
    },
)
async def get_playlist_m3u(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_number: int = FastAPIPath(
        ..., ge=1, le=6, description="Preset number (1-6)"
    ),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Get M3U playlist file for a device preset.

    Returns an M3U playlist containing the stream URL for the specified preset.
    This format might be better parsed by Bose SoundTouch devices.

    M3U Format:
    ```
    #EXTM3U
    #EXTINF:-1,Station Name
    http://stream.url/path
    ```

    Headers:
    - Content-Type: audio/x-mpegurl

    Args:
        device_id: Bose device identifier
        preset_number: Preset number (1-6)

    Returns:
        M3U playlist content with Content-Type: audio/x-mpegurl
    """
    try:
        station_name, stream_url = await _get_preset_content(
            preset_service, device_id, preset_number, "M3U"
        )

        m3u_content = f"#EXTM3U\n#EXTINF:-1,{station_name}\n{stream_url}\n"

        logger.info(
            f"Serving M3U for {device_id} preset {preset_number}: {station_name}",
            extra={
                "device_id": device_id,
                "preset_number": preset_number,
                "station_name": station_name,
                "stream_url": stream_url,
            },
        )

        return PlainTextResponse(
            content=m3u_content,
            media_type="audio/x-mpegurl",
            headers={
                "Content-Disposition": f'inline; filename="preset{preset_number}.m3u"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error generating M3U for {device_id} preset {preset_number}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate playlist: {str(e)}",
        )


@router.get(
    "/{device_id}/{preset_number}.pls",
    response_class=PlainTextResponse,
    responses={
        200: {
            "description": "PLS playlist file",
            "content": {"audio/x-scpls": {}},
        },
        404: {"description": "Preset not found"},
    },
)
async def get_playlist_pls(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_number: int = FastAPIPath(
        ..., ge=1, le=6, description="Preset number (1-6)"
    ),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Get PLS playlist file for a device preset.

    Returns a PLS playlist containing the stream URL for the specified preset.
    Alternative format that might work better with some devices.

    PLS Format:
    ```
    [playlist]
    File1=http://stream.url/path
    Title1=Station Name
    Length1=-1
    NumberOfEntries=1
    Version=2
    ```

    Headers:
    - Content-Type: audio/x-scpls

    Args:
        device_id: Bose device identifier
        preset_number: Preset number (1-6)

    Returns:
        PLS playlist content with Content-Type: audio/x-scpls
    """
    try:
        station_name, stream_url = await _get_preset_content(
            preset_service, device_id, preset_number, "PLS"
        )

        pls_content = (
            f"[playlist]\n"
            f"File1={stream_url}\n"
            f"Title1={station_name}\n"
            f"Length1=-1\n"
            f"NumberOfEntries=1\n"
            f"Version=2\n"
        )

        logger.info(
            f"Serving PLS for {device_id} preset {preset_number}: {station_name}",
            extra={
                "device_id": device_id,
                "preset_number": preset_number,
                "station_name": station_name,
                "stream_url": stream_url,
            },
        )

        return PlainTextResponse(
            content=pls_content,
            media_type="audio/x-scpls",
            headers={
                "Content-Disposition": f'inline; filename="preset{preset_number}.pls"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error generating PLS for {device_id} preset {preset_number}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate playlist: {str(e)}",
        )
