"""Zone API routes for multi-room management."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from opencloudtouch.core.dependencies import ZoneServiceDep
from opencloudtouch.zones.models import ZoneStatus

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


@router.get(
    "",
    response_model=list[ZoneStatus],
    responses={500: {"description": "Failed to get zones"}},
)
async def get_all_zones(
    zone_service: ZoneServiceDep,
):
    """Get all active multi-room zones."""
    try:
        return await zone_service.get_all_zones()
    except Exception as e:
        logger.exception("Failed to get zones")
        raise HTTPException(status_code=500, detail="Failed to get zones") from e


@router.post("", response_model=ZoneStatus, status_code=201)
async def create_zone(
    request: CreateZoneRequest,
    zone_service: ZoneServiceDep,
):
    """Create a new multi-room zone."""
    try:
        return await zone_service.create_zone(request.master_id, request.slave_ids)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{master_id}", status_code=204)
async def dissolve_zone(
    master_id: str,
    zone_service: ZoneServiceDep,
):
    """Dissolve a multi-room zone."""
    await zone_service.dissolve_zone(master_id)


@router.post("/{master_id}/members", status_code=200)
async def add_zone_members(
    master_id: str,
    request: ModifyMembersRequest,
    zone_service: ZoneServiceDep,
):
    """Add members to an existing zone."""
    await zone_service.add_members(master_id, request.device_ids)
    return {"status": "ok"}


@router.delete("/{master_id}/members", status_code=204)
async def remove_zone_members(
    master_id: str,
    request: ModifyMembersRequest,
    zone_service: ZoneServiceDep,
):
    """Remove members from an existing zone."""
    await zone_service.remove_members(master_id, request.device_ids)


@router.put("/{master_id}/master", response_model=ZoneStatus)
async def change_master(
    master_id: str,
    request: ChangeMasterRequest,
    zone_service: ZoneServiceDep,
):
    """Change the master of a zone."""
    try:
        return await zone_service.change_master(master_id, request.new_master_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ============================================================================
# Per-device zone route
# ============================================================================


@device_zone_router.get("/{device_id}/zone", response_model=ZoneStatus | None)
async def get_device_zone(
    device_id: str,
    zone_service: ZoneServiceDep,
):
    """Get zone status for a specific device."""
    return await zone_service.get_zone_status(device_id)
