"""Zone API routes for multi-room management."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from opencloudtouch.core.dependencies import get_zone_service
from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.zones.models import ZoneStatus
from opencloudtouch.zones.service import ZoneService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zones", tags=["Zones"])
device_zone_router = APIRouter(prefix="/api/devices", tags=["Zones"])


# ============================================================================
# Request models
# ============================================================================


class CreateZoneRequest(BaseModel):
    """Request to create a new zone."""

    master_id: str
    slave_ids: list[str]


class ModifyMembersRequest(BaseModel):
    """Request to add or remove zone members."""

    device_ids: list[str]


class ChangeMasterRequest(BaseModel):
    """Request to change zone master."""

    new_master_id: str


# ============================================================================
# Zone routes
# ============================================================================


@router.get("", response_model=list[ZoneStatus])
async def get_all_zones(
    zone_service: ZoneService = Depends(get_zone_service),
):
    """Get all active multi-room zones."""
    try:
        return await zone_service.get_all_zones()
    except Exception as e:
        logger.error("Failed to get zones: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ZoneStatus, status_code=201)
async def create_zone(
    request: CreateZoneRequest,
    zone_service: ZoneService = Depends(get_zone_service),
):
    """Create a new multi-room zone."""
    try:
        return await zone_service.create_zone(request.master_id, request.slave_ids)
    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DeviceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Failed to create zone: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{master_id}", status_code=204)
async def dissolve_zone(
    master_id: str,
    zone_service: ZoneService = Depends(get_zone_service),
):
    """Dissolve a multi-room zone."""
    try:
        await zone_service.dissolve_zone(master_id)
    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DeviceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Failed to dissolve zone: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{master_id}/members", status_code=200)
async def add_zone_members(
    master_id: str,
    request: ModifyMembersRequest,
    zone_service: ZoneService = Depends(get_zone_service),
):
    """Add members to an existing zone."""
    try:
        await zone_service.add_members(master_id, request.device_ids)
        return {"status": "ok"}
    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DeviceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Failed to add zone members: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{master_id}/members", status_code=204)
async def remove_zone_members(
    master_id: str,
    request: ModifyMembersRequest,
    zone_service: ZoneService = Depends(get_zone_service),
):
    """Remove members from an existing zone."""
    try:
        await zone_service.remove_members(master_id, request.device_ids)
    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DeviceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Failed to remove zone members: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{master_id}/master", response_model=ZoneStatus)
async def change_master(
    master_id: str,
    request: ChangeMasterRequest,
    zone_service: ZoneService = Depends(get_zone_service),
):
    """Change the master of a zone."""
    try:
        return await zone_service.change_master(master_id, request.new_master_id)
    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DeviceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Failed to change master: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Per-device zone route
# ============================================================================


@device_zone_router.get("/{device_id}/zone", response_model=ZoneStatus | None)
async def get_device_zone(
    device_id: str,
    zone_service: ZoneService = Depends(get_zone_service),
):
    """Get zone status for a specific device."""
    try:
        return await zone_service.get_zone_status(device_id)
    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DeviceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Failed to get device zone: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
