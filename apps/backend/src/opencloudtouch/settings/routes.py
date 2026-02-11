"""API routes for Settings management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from opencloudtouch.core.dependencies import get_settings_service
from opencloudtouch.settings.service import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SetManualIPsRequest(BaseModel):
    """Request model for setting all manual IPs at once."""

    ips: list[str] = Field(..., description="List of IP addresses to set")


class ManualIPsResponse(BaseModel):
    """Response model for manual IPs list."""

    ips: list[str] = Field(..., description="List of manual IP addresses")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    ip: str


@router.get("/manual-ips", response_model=ManualIPsResponse)
async def get_manual_ips(
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> ManualIPsResponse:
    """
    Get all manual device IP addresses.

    Returns:
        List of manually configured IP addresses
    """
    ips = await service.get_manual_ips()
    return ManualIPsResponse(ips=ips)


@router.post(
    "/manual-ips",
    response_model=ManualIPsResponse,
    status_code=status.HTTP_200_OK,
)
async def set_manual_ips(
    request: SetManualIPsRequest,
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> ManualIPsResponse:
    """
    Replace all manual device IP addresses with new list.

    Args:
        request: Request containing list of IP addresses

    Returns:
        Updated list of manual IP addresses
    """
    try:
        result_ips = await service.set_manual_ips(request.ips)
        return ManualIPsResponse(ips=result_ips)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/manual-ips/{ip}", response_model=MessageResponse)
async def delete_manual_ip(
    ip: str,
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> MessageResponse:
    """
    Remove a manual device IP address.

    Args:
        ip: IP address to remove

    Returns:
        Success message with removed IP
    """
    await service.remove_manual_ip(ip)
    return MessageResponse(message="IP removed successfully", ip=ip)
