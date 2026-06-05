"""FastAPI routes for preset management."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as FastAPIPath
from pydantic import BaseModel, Field

from opencloudtouch.core.dependencies import get_preset_service
from opencloudtouch.core.exceptions import DeviceNotFoundError
from opencloudtouch.presets.service import PresetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/presets", tags=["presets"])


# Pydantic models for API requests/responses
class PresetSetRequest(BaseModel):
    """Request model for setting a preset."""

    device_id: str = Field(..., description="Device identifier")
    preset_number: int = Field(..., ge=1, le=6, description="Preset number (1-6)")
    station_uuid: str = Field(..., description="RadioBrowser station UUID")
    station_name: str = Field(..., description="Station name")
    station_url: str = Field(..., description="Stream URL")
    station_homepage: Optional[str] = Field(None, description="Station homepage URL")
    station_favicon: Optional[str] = Field(None, description="Station favicon URL")


class PresetResponse(BaseModel):
    """Response model for a preset."""

    id: int
    device_id: str
    preset_number: int
    station_uuid: str
    station_name: str
    station_url: str
    station_homepage: Optional[str]
    station_favicon: Optional[str]
    source: Optional[str]
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


@router.post("/set", response_model=PresetResponse, status_code=201)
async def set_preset(
    request: PresetSetRequest,
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Set a preset for a device.

    Creates or updates a preset mapping. When the physical preset button
    is pressed on the SoundTouch device, it will load the configured station.
    """
    try:
        saved_preset = await preset_service.set_preset(
            device_id=request.device_id,
            preset_number=request.preset_number,
            station_uuid=request.station_uuid,
            station_name=request.station_name,
            station_url=request.station_url,
            station_homepage=request.station_homepage,
            station_favicon=request.station_favicon,
        )

        return PresetResponse(**saved_preset.to_dict())

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))  # NOSONAR
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Error setting preset")
        raise HTTPException(status_code=500, detail="Failed to set preset")


@router.get("/{device_id}", response_model=List[PresetResponse])
async def get_device_presets(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Get all presets for a device.

    Returns all configured presets (1-6) for the specified device.
    Empty slots are not included in the response.
    """
    try:
        presets = await preset_service.get_all_presets(device_id)

        logger.debug("Retrieved %d presets for device %s", len(presets), device_id)

        return [PresetResponse(**p.to_dict()) for p in presets]

    except Exception:
        logger.exception("Error getting presets for device %s", device_id)
        raise HTTPException(status_code=500, detail="Failed to get presets")


@router.get(
    "/{device_id}/{preset_number}",
    response_model=PresetResponse,
    responses={404: {"description": "Preset not found"}},
)
async def get_preset(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_number: int = FastAPIPath(
        ..., ge=1, le=6, description="Preset number (1-6)"
    ),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Get a specific preset.

    Returns the preset configuration for the specified device and preset number.
    """
    try:
        preset = await preset_service.get_preset(device_id, preset_number)

        if not preset:
            raise HTTPException(
                status_code=404,
                detail=f"Preset {preset_number} not found for device {device_id}",
            )

        logger.debug(
            "Retrieved preset %d for device %s: %s",
            preset_number,
            device_id,
            preset.station_name,
        )

        return PresetResponse(**preset.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error getting preset %d for device %s: %s", preset_number, device_id, e
        )
        raise HTTPException(status_code=500, detail="Failed to get preset")


@router.delete("/{device_id}/{preset_number}", response_model=MessageResponse)
async def clear_preset(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_number: int = FastAPIPath(
        ..., ge=1, le=6, description="Preset number (1-6)"
    ),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Clear a specific preset.

    Removes the preset configuration. The physical preset button will no
    longer trigger playback until a new station is assigned.
    """
    try:
        deleted = await preset_service.clear_preset(device_id, preset_number)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Preset {preset_number} not found for device {device_id}",
            )

        return MessageResponse(
            message=f"Preset {preset_number} cleared for device {device_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error clearing preset %d for device %s: %s", preset_number, device_id, e
        )
        raise HTTPException(status_code=500, detail="Failed to clear preset")


@router.delete("/{device_id}", response_model=MessageResponse)
async def clear_all_presets(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Clear all presets for a device.

    Removes all preset configurations for the specified device.
    """
    try:
        count = await preset_service.clear_all_presets(device_id)

        return MessageResponse(
            message=f"Cleared {count} presets for device {device_id}"
        )

    except Exception:
        logger.exception("Error clearing all presets for device %s", device_id)
        raise HTTPException(status_code=500, detail="Failed to clear presets")


@router.post("/{device_id}/sync", response_model=MessageResponse)
async def sync_presets_from_device(
    device_id: str = FastAPIPath(..., description="Device identifier"),
    preset_service: PresetService = Depends(get_preset_service),
):
    """
    Sync presets from device to OCT database.

    Fetches presets from the physical device and imports them into OCT.
    Useful when a device was configured by another OCT instance or manually.

    Returns:
        Message with sync count

    Raises:
        404: Device not found
        502: Device unreachable
        500: Internal error
    """
    try:
        count = await preset_service.sync_presets_from_device(device_id)

        return MessageResponse(
            message=f"Synced {count} presets from device {device_id}"
        )

    except ValueError as e:
        logger.exception("Device %s not found", device_id)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Error syncing presets from device %s", device_id)
        raise HTTPException(
            status_code=502, detail="Failed to sync presets from device"
        )
