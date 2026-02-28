"""
Device API Routes
Endpoints for device discovery and management
"""

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from opencloudtouch.core.config import AppConfig, get_config
from opencloudtouch.core.dependencies import get_device_service
from opencloudtouch.core.exceptions import DeviceNotFoundError, DiscoveryError
from opencloudtouch.devices.events import (
    DiscoveryEventType,
    event_generator,
    get_event_bus,
)
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


@router.get("/discover/stream")
async def discover_devices_stream(
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Discover devices and stream results via Server-Sent Events (SSE).

    Progressive loading:
    - Sends `device_found` events as devices are discovered via SSDP
    - Sends `device_synced` events as devices are saved to DB
    - Sends `completed` event when done

    Frontend can show devices immediately instead of waiting for full scan.

    Returns:
        StreamingResponse with SSE events

    Event Types:
        - started: Discovery started
        - device_found: Device discovered (SSDP response)
        - device_synced: Device synced to DB
        - device_failed: Device sync failed
        - completed: Discovery finished
        - error: Error occurred

    Example SSE Stream:
        event: started
        data: {"message": "Starting discovery"}

        event: device_found
        data: {"ip": "192.168.1.100", "name": "Küche", "model": "SoundTouch 10"}

        event: device_synced
        data: {"id": 1, "device_id": "ABC123", "ip": "192.168.1.100", ...}

        event: completed
        data: {"discovered": 3, "synced": 3, "failed": 0}
    """
    # Prevent concurrent discovery
    if _discovery_lock.locked():
        logger.warning("Discovery already in progress, rejecting SSE request")
        raise HTTPException(status_code=409, detail="Discovery already in progress")

    # Subscribe to events
    event_bus = get_event_bus()
    queue = event_bus.subscribe()

    async def stream_discovery():
        """Stream discovery events to client."""
        try:
            # Start discovery in background task
            async with _discovery_lock:
                # Trigger discovery with event streaming
                task = asyncio.create_task(
                    device_service.sync_devices_with_events(event_bus)
                )

                # Stream events to client
                async for sse_message in event_generator(queue):
                    yield sse_message

                # Wait for discovery to complete
                await task

        except asyncio.CancelledError:
            logger.info("Client disconnected from discovery stream")
            raise
        except Exception as e:
            logger.error(f"Discovery stream error: {e}")
            # Send error event
            from opencloudtouch.devices.events import DiscoveryEvent

            error_event = DiscoveryEvent(
                type=DiscoveryEventType.ERROR, data={"message": str(e)}
            )
            yield error_event.to_sse()
        finally:
            # Cleanup
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        stream_discovery(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


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
    except Exception as e:
        logger.error(f"Failed to press key {key} on device {device_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to press key: {str(e)}"
        ) from e
