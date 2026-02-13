"""
Device API Routes
Endpoints for device discovery and management
"""

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from opencloudtouch.core.config import AppConfig, get_config
from opencloudtouch.core.dependencies import get_device_service
from opencloudtouch.core.exceptions import DeviceNotFoundError, DiscoveryError
from opencloudtouch.devices.service import DeviceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["Devices"])

# Discovery lock to prevent concurrent discovery requests
_discovery_lock = asyncio.Lock()


@router.get("/discover")
async def discover_devices(
    device_service: DeviceService = Depends(get_device_service),
) -> Dict[str, Any]:
    """
    Trigger device discovery.

    Returns:
        List of discovered devices (not yet saved to DB)
    """
    cfg = get_config()

    try:
        devices = await device_service.discover_devices(timeout=cfg.discovery_timeout)

        return {
            "count": len(devices),
            "devices": [
                {
                    "ip": d.ip,
                    "port": d.port,
                    "name": d.name,
                    "model": d.model,
                }
                for d in devices
            ],
        }
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        # Wrap generic exceptions in DiscoveryError
        raise DiscoveryError(f"Device discovery failed: {str(e)}") from e


@router.post("/sync")
async def sync_devices(
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Discover devices and sync to database.
    Queries each device for detailed info (/info endpoint).

    Returns:
        Sync summary with success/failure counts
    """
    # Prevent concurrent discovery - reject if already running
    if _discovery_lock.locked():
        logger.warning("Discovery already in progress, rejecting concurrent request")
        raise HTTPException(status_code=409, detail="Discovery already in progress")

    async with _discovery_lock:
        try:
            result = await device_service.sync_devices()
            return result.to_dict()
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            # Wrap generic exceptions in DiscoveryError
            raise DiscoveryError(f"Device sync failed: {str(e)}") from e


@router.get("")
async def get_devices(device_service: DeviceService = Depends(get_device_service)):
    """
    Get all devices from database.

    Returns:
        List of devices with details
    """
    devices = await device_service.get_all_devices()

    return {
        "count": len(devices),
        "devices": [d.to_dict() for d in devices],
    }


@router.delete("")
async def delete_all_devices(
    device_service: DeviceService = Depends(get_device_service),
    cfg: AppConfig = Depends(get_config),
):
    """
    Delete all devices from database.

    **Testing/Development endpoint only.**
    Use for cleaning database before E2E tests or manual testing.

    **Protected**: Requires OCT_ALLOW_DANGEROUS_OPERATIONS=true

    Returns:
        Confirmation message

    Raises:
        HTTPException(403): If dangerous operations are disabled in production
    """
    try:
        await device_service.delete_all_devices(
            allow_dangerous_operations=cfg.allow_dangerous_operations
        )
        return {"message": "All devices deleted"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/{device_id}")
async def get_device(
    device_id: str, device_service: DeviceService = Depends(get_device_service)
):
    """
    Get single device by device_id.

    Args:
        device_id: Device ID

    Returns:
        Device details

    Raises:
        DeviceNotFoundError: If device does not exist
    """
    device = await device_service.get_device_by_id(device_id)

    if not device:
        raise DeviceNotFoundError(device_id)

    return device.to_dict()


@router.get("/{device_id}/capabilities")
async def get_device_capabilities_endpoint(
    device_id: str, device_service: DeviceService = Depends(get_device_service)
):
    """
    Get device capabilities for UI feature detection.

    Returns which features this specific device supports:
    - HDMI control (ST300 only)
    - Bass/balance controls
    - Available input sources
    - Zone/group support
    - All supported endpoints

    Args:
        device_id: Device ID

    Returns:
        Feature flags and capabilities for UI rendering

    Example Response:
        {
            "device_id": "AABBCC112233",
            "device_type": "SoundTouch 30 Series III",
            "is_soundbar": false,
            "features": {
                "hdmi_control": false,
                "bass_control": true,
                "bluetooth": true,
                ...
            },
            "sources": ["BLUETOOTH", "AUX", "INTERNET_RADIO"],
            "advanced": {...}
        }
    """
    try:
        capabilities = await device_service.get_device_capabilities(device_id)
        return capabilities
    except ValueError as e:
        # ValueError from service means device not found
        raise DeviceNotFoundError(device_id) from e
    except Exception as e:
        logger.error(f"Failed to get capabilities for device {device_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to query device capabilities: {str(e)}"
        ) from e
