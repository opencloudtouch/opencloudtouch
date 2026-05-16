"""
Device API Routes
CRUD endpoints for device management. Discovery endpoints extracted to discovery_routes.py.
"""

import logging
from collections.abc import Awaitable
from typing import TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException

from opencloudtouch.core.config import AppConfig, get_config
from opencloudtouch.core.dependencies import get_device_service
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DomainValidationError,
)
from opencloudtouch.devices.service import DeviceService

logger = logging.getLogger(__name__)

T = TypeVar("T")

router = APIRouter(prefix="/api/devices", tags=["Devices"])


async def _device_op(device_id: str, action: str, coro: Awaitable[T]) -> T:
    """Execute a device service call with standardized error handling.

    Domain exceptions (DeviceNotFoundError, DomainValidationError,
    DeviceConnectionError) propagate to global handlers.
    Only unexpected exceptions are wrapped in 500.
    """
    try:
        return await coro
    except (DeviceNotFoundError, DomainValidationError, DeviceConnectionError):
        raise
    except Exception as e:
        logger.exception("Failed to %s for device %s", action, device_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to {action}"
        ) from e  # NOSONAR


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


@router.delete("/{device_id}")
async def delete_by_device_id(
    device_id: str,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Delete device by id from database.

    Args:
        device_id: Device ID

    Returns:
        Confirmation message
    """
    await device_service.delete_by_device_id(device_id)
    return {"message": "Device successfully deleted"}


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
    return await _device_op(
        device_id,
        "query device capabilities",
        device_service.get_device_capabilities(device_id),
    )


@router.post("/{device_id}/key")
async def press_key(
    device_id: str,
    key: str,
    state: str = "both",
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Simulate a key press on a device.

    Used for E2E testing to trigger preset playback without physical button press.

    Args:
        device_id: Device ID
        key: Key name (e.g., "PRESET_1", "PRESET_2", "PRESET_3", ...)
        state: Key state ("press", "release", or "both"). Default: "both"

    Returns:
        Success message

    Raises:
        DeviceNotFoundError: If device does not exist
        HTTPException(400): If key or state is invalid
        HTTPException(500): If key press fails

    Example:
        POST /api/devices/AABBCC112233/key?key=PRESET_1&state=both
    """
    await _device_op(
        device_id,
        "press key",
        device_service.press_key(device_id, key, state),
    )
    return {"message": f"Key {key} pressed successfully", "device_id": device_id}


@router.get("/{device_id}/now-playing")
async def get_now_playing(
    device_id: str,
    device_service: DeviceService = Depends(get_device_service),
):
    """Get current playback status for a device."""
    info = await _device_op(
        device_id,
        "get playback status",
        device_service.get_now_playing(device_id),
    )
    return {
        "source": info.source,
        "state": info.state,
        "station_name": info.station_name,
        "artist": info.artist,
        "track": info.track,
        "album": info.album,
        "artwork_url": info.artwork_url,
    }


@router.get("/{device_id}/volume")
async def get_volume(
    device_id: str,
    device_service: DeviceService = Depends(get_device_service),
):
    """Get current volume state for a device."""
    vol = await _device_op(
        device_id,
        "get volume",
        device_service.get_volume(device_id),
    )
    return {"actual": vol.actual, "target": vol.target, "muted": vol.muted}


@router.put("/{device_id}/volume")
async def set_volume(
    device_id: str,
    level: int = Body(..., embed=True, ge=0, le=100),
    device_service: DeviceService = Depends(get_device_service),
):
    """Set volume level (0-100)."""
    vol = await _device_op(
        device_id,
        "set volume",
        device_service.set_volume(device_id, level),
    )
    return {"actual": vol.actual, "target": vol.target, "muted": vol.muted}


@router.put("/{device_id}/mute")
async def set_mute(
    device_id: str,
    muted: bool = Body(..., embed=True),
    device_service: DeviceService = Depends(get_device_service),
):
    """Set mute state."""
    vol = await _device_op(
        device_id,
        "set mute",
        device_service.set_mute(device_id, muted),
    )
    return {"actual": vol.actual, "target": vol.target, "muted": vol.muted}
