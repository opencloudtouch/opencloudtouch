"""Device Discovery API Routes.

Extracted from devices/api/routes.py (STORY-307): discovery, sync, and
SSE stream endpoints live here so routes.py stays focused on CRUD + capabilities.
"""

import asyncio
import ipaddress
import logging
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from opencloudtouch.core.config import get_config
from opencloudtouch.core.dependencies import get_device_service, get_settings_service
from opencloudtouch.core.exceptions import DiscoveryError
from opencloudtouch.devices.events import (
    DiscoveryEventType,
    event_generator,
    get_event_bus,
)
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.settings.service import SettingsService

logger = logging.getLogger(__name__)

discovery_router = APIRouter(prefix="/api/devices", tags=["Devices"])

# Discovery lock to prevent concurrent discovery requests
_discovery_lock = asyncio.Lock()


@discovery_router.get("/discover")
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
        logger.exception("Discovery failed")
        # Wrap generic exceptions in DiscoveryError
        raise DiscoveryError(f"Device discovery failed: {str(e)}") from e


@discovery_router.post("/sync")
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
            logger.exception("Sync failed")
            raise DiscoveryError(f"Device sync failed: {str(e)}") from e


@discovery_router.get("/discover/stream")
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
        task = None
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
            if task and not task.done():
                task.cancel()
            raise
        except Exception as e:
            logger.exception("Discovery stream error")
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


class ProbeRequest(BaseModel):
    """Request model for single-device probe."""

    ip: str = Field(..., description="IP address of the device to probe")


@discovery_router.post(
    "/probe",
    responses={
        422: {"description": "Invalid IP address format"},
        404: {"description": "Device not reachable at the given IP"},
    },
)
async def probe_device(
    request: ProbeRequest,
    device_service: Annotated[DeviceService, Depends(get_device_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> Dict[str, Any]:
    """
    Probe a single device by IP address.

    Contacts the device at the given IP, fetches its info, upserts it
    to the database, and adds the IP to the manual IPs list.

    Returns:
        Device data if reachable

    Raises:
        422: Invalid IP format
        404: Device not reachable at the given IP
    """
    ip = request.ip.strip()

    # Validate IP format
    try:
        ip = str(ipaddress.ip_address(ip))
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid IP address format: {ip}",
        )

    # Probe device
    try:
        device = await device_service.probe_single_device(ip)
    except Exception as e:
        logger.warning("Probe failed for %r: %s", ip, e)
        raise HTTPException(
            status_code=404,
            detail=f"Device not reachable at {ip}",
        )

    # Add to manual IPs (idempotent — skips if already present)
    try:
        current_ips = await settings_service.get_manual_ips()
        if ip not in current_ips:
            await settings_service.set_manual_ips([*current_ips, ip])
    except Exception:
        logger.warning("Failed to save manual IP %r", ip, exc_info=True)

    return {
        "device_id": device.device_id,
        "ip": device.ip,
        "name": device.name,
        "model": device.model,
    }
