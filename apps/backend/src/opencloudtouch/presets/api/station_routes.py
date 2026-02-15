"""FastAPI routes for station descriptors.

These endpoints serve SoundTouch preset URLs. When a physical preset button
is pressed on a SoundTouch device, it fetches the descriptor from this endpoint
to determine which stream to play.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as FastAPIPath
from fastapi.responses import JSONResponse

from opencloudtouch.core.dependencies import get_preset_service
from opencloudtouch.presets.api.descriptor_service import StationDescriptorService
from opencloudtouch.presets.service import PresetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stations/preset", tags=["stations"])


async def get_descriptor_service(
    preset_service: PresetService = Depends(get_preset_service),
) -> StationDescriptorService:
    """Dependency: Get StationDescriptorService instance."""
    return StationDescriptorService(preset_service)


@router.get("/{device_id}/{preset_number}.json")
async def get_station_descriptor(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_number: int = FastAPIPath(
        ..., ge=1, le=6, description="Preset number (1-6)"
    ),
    descriptor_service: StationDescriptorService = Depends(get_descriptor_service),
):
    """
    Get station descriptor for a device preset.

    This endpoint is called by SoundTouch devices when a preset button is pressed.
    It returns the stream URL and metadata for playback.

    Response format:
    ```json
    {
        "stationName": "Station Name",
        "streamUrl": "http://stream.url/path",
        "homepage": "https://station.homepage",
        "favicon": "https://station.favicon/icon.png",
        "uuid": "radiobrowser-uuid"
    }
    ```
    """
    try:
        descriptor = await descriptor_service.get_descriptor(device_id, preset_number)

        if not descriptor:
            logger.warning(
                f"Station descriptor not found for device {device_id}, "
                f"preset {preset_number}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Preset {preset_number} not configured for device {device_id}",
            )

        logger.debug(
            f"Serving descriptor for {device_id} preset {preset_number}: "
            f"{descriptor['stationName']}"
        )

        return JSONResponse(content=descriptor)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting descriptor for {device_id} preset {preset_number}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to get station descriptor")
