"""
Device API Routes
CRUD endpoints for device management. Discovery endpoints extracted to discovery_routes.py.
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException

from opencloudtouch.core.config import AppConfig, get_config
from opencloudtouch.core.dependencies import get_device_service
from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.devices.service import DeviceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["Devices"])


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
    except DeviceConnectionError:
        raise
    except Exception as e:
        logger.error("Failed to get capabilities for device %s: %s", device_id, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to query device capabilities: {str(e)}"
        ) from e


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
    try:
        await device_service.press_key(device_id, key, state)
        return {"message": f"Key {key} pressed successfully", "device_id": device_id}
    except ValueError as e:
        # Device not found
        if "not found" in str(e).lower():
            raise DeviceNotFoundError(device_id) from e
        # Invalid key or state
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DeviceConnectionError:
        raise
    except Exception as e:
        logger.error("Failed to press key %s on device %s: %s", key, device_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to press key on device"
        ) from e


@router.get("/{device_id}/now-playing")
async def get_now_playing(
    device_id: str,
    device_service: DeviceService = Depends(get_device_service),
):
    """Get current playback status for a device."""
    try:
        info = await device_service.get_now_playing(device_id)
        return {
            "source": info.source,
            "state": info.state,
            "station_name": info.station_name,
            "artist": info.artist,
            "track": info.track,
            "album": info.album,
            "artwork_url": info.artwork_url,
        }
    except ValueError as e:
        if "not found" in str(e).lower():
            raise DeviceNotFoundError(device_id) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DeviceConnectionError:
        raise
    except Exception as e:
        logger.error("Failed to get now playing for device %s: %s", device_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to get playback status"
        ) from e


@router.get("/{device_id}/volume")
async def get_volume(
    device_id: str,
    device_service: DeviceService = Depends(get_device_service),
):
    """Get current volume state for a device."""
    try:
        vol = await device_service.get_volume(device_id)
        return {"actual": vol.actual, "target": vol.target, "muted": vol.muted}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise DeviceNotFoundError(device_id) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DeviceConnectionError:
        raise
    except Exception as e:
        logger.error("Failed to get volume for device %s: %s", device_id, e)
        raise HTTPException(status_code=500, detail="Failed to get volume") from e


@router.put("/{device_id}/volume")
async def set_volume(
    device_id: str,
    level: int = Body(..., embed=True, ge=0, le=100),
    device_service: DeviceService = Depends(get_device_service),
):
    """Set volume level (0-100)."""
    try:
        vol = await device_service.set_volume(device_id, level)
        return {"actual": vol.actual, "target": vol.target, "muted": vol.muted}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise DeviceNotFoundError(device_id) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DeviceConnectionError:
        raise
    except Exception as e:
        logger.error("Failed to set volume for device %s: %s", device_id, e)
        raise HTTPException(status_code=500, detail="Failed to set volume") from e


@router.put("/{device_id}/mute")
async def set_mute(
    device_id: str,
    muted: bool = Body(..., embed=True),
    device_service: DeviceService = Depends(get_device_service),
):
    """Set mute state."""
    try:
        vol = await device_service.set_mute(device_id, muted)
        return {"actual": vol.actual, "target": vol.target, "muted": vol.muted}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise DeviceNotFoundError(device_id) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DeviceConnectionError:
        raise
    except Exception as e:
        logger.error("Failed to set mute for device %s: %s", device_id, e)
        raise HTTPException(status_code=500, detail="Failed to set mute") from e
