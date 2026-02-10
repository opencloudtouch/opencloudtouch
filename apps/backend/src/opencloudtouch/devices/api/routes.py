"""
Device API Routes
Endpoints for device discovery and management
"""

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from opencloudtouch.core.config import AppConfig, get_config
from opencloudtouch.core.dependencies import get_device_repo, get_settings_repo
from opencloudtouch.devices.adapter import BoseDeviceDiscoveryAdapter
from opencloudtouch.devices.discovery.manual import ManualDiscovery
from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.devices.services import DeviceSyncService
from opencloudtouch.discovery import DiscoveredDevice
from opencloudtouch.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["Devices"])

# Discovery lock to prevent concurrent discovery requests
_discovery_lock = asyncio.Lock()


# Helper functions for discover_devices (keep functions < 20 lines)
async def _discover_via_ssdp(cfg: AppConfig) -> List[DiscoveredDevice]:
    """Discover devices via SSDP (UPnP)."""
    if not cfg.discovery_enabled:
        return []

    logger.info("Starting discovery via SSDP...")
    discovery = BoseDeviceDiscoveryAdapter()
    try:
        devices = await discovery.discover(timeout=cfg.discovery_timeout)
        logger.info(f"SSDP discovery found {len(devices)} device(s)")
        return devices
    except Exception as e:
        logger.error(f"SSDP discovery failed: {e}")
        return []


async def _discover_via_manual_ips(
    cfg: AppConfig, settings_repo: SettingsRepository
) -> List[DiscoveredDevice]:
    """
    Discover devices via manually configured IP addresses.

    Merges IPs from:
    - Database (manual_device_ips table)
    - Environment variable (CT_MANUAL_DEVICE_IPS)
    """
    # Get IPs from database
    db_ips = []
    try:
        db_ips = await settings_repo.get_manual_ips()
    except Exception as e:
        logger.error(f"Failed to get manual IPs from database: {e}")

    # Get IPs from environment variable
    env_ips = cfg.manual_device_ips_list or []

    # Merge and deduplicate
    all_ips = list(set(db_ips + env_ips))

    if not all_ips:
        return []

    logger.info(
        f"Using manual device IPs: {all_ips} (DB: {len(db_ips)}, ENV: {len(env_ips)})"
    )
    manual = ManualDiscovery(all_ips)
    try:
        devices = await manual.discover()
        logger.info(f"Manual discovery found {len(devices)} device(s)")
        return devices
    except Exception as e:
        logger.error(f"Manual discovery failed: {e}")
        return []


def _format_discovery_response(devices: List[DiscoveredDevice]) -> Dict[str, Any]:
    """Format discovery results as API response."""
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


@router.get("/discover")
async def discover_devices(
    settings_repo: SettingsRepository = Depends(get_settings_repo),
) -> Dict[str, Any]:
    """
    Trigger device discovery.

    Returns:
        List of discovered devices (not yet saved to DB)
    """
    cfg = get_config()

    # Discover via SSDP and manual IPs
    ssdp_devices = await _discover_via_ssdp(cfg)
    manual_devices = await _discover_via_manual_ips(cfg, settings_repo)

    all_devices = ssdp_devices + manual_devices
    logger.info(f"Discovery complete: {len(all_devices)} device(s) found")

    return _format_discovery_response(all_devices)


@router.post("/sync")
async def sync_devices(
    repo: DeviceRepository = Depends(get_device_repo),
    settings_repo: SettingsRepository = Depends(get_settings_repo),
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
        cfg = get_config()

        # Merge manual IPs from database and environment variable
        db_ips = []
        try:
            db_ips = await settings_repo.get_manual_ips()
        except Exception as e:
            logger.error(f"Failed to get manual IPs from database: {e}")

        env_ips = cfg.manual_device_ips_list or []
        all_manual_ips = list(set(db_ips + env_ips))

        if all_manual_ips:
            logger.info(
                f"Using manual IPs: {all_manual_ips} (DB: {len(db_ips)}, ENV: {len(env_ips)})"
            )

        # Use service layer for business logic
        service = DeviceSyncService(
            repository=repo,
            discovery_timeout=cfg.discovery_timeout,
            manual_ips=all_manual_ips,
            discovery_enabled=cfg.discovery_enabled,
        )

        result = await service.sync()
        return result.to_dict()


@router.get("")
async def get_devices(repo: DeviceRepository = Depends(get_device_repo)):
    """
    Get all devices from database.

    Returns:
        List of devices with details
    """
    devices = await repo.get_all()

    return {
        "count": len(devices),
        "devices": [d.to_dict() for d in devices],
    }


@router.delete("")
async def delete_all_devices(
    repo: DeviceRepository = Depends(get_device_repo),
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
    if not cfg.allow_dangerous_operations:
        raise HTTPException(
            status_code=403,
            detail="Dangerous operations disabled. Set OCT_ALLOW_DANGEROUS_OPERATIONS=true to enable (testing only)",
        )

    await repo.delete_all()
    logger.info("All devices deleted from database")

    return {"message": "All devices deleted"}


@router.get("/{device_id}")
async def get_device(device_id: str, repo: DeviceRepository = Depends(get_device_repo)):
    """
    Get single device by device_id.

    Args:
        device_id: Device ID

    Returns:
        Device details
    """
    device = await repo.get_by_device_id(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device.to_dict()


@router.get("/{device_id}/capabilities")
async def get_device_capabilities_endpoint(
    device_id: str, repo: DeviceRepository = Depends(get_device_repo)
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
    from bosesoundtouchapi import SoundTouchClient, SoundTouchDevice

    from opencloudtouch.devices.capabilities import (
        get_device_capabilities,
        get_feature_flags_for_ui,
    )

    # Get device from DB
    device = await repo.get_by_device_id(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        # Create device client
        st_device = SoundTouchDevice(device.ip)
        client = SoundTouchClient(st_device)

        # Get capabilities
        capabilities = await get_device_capabilities(client)

        # Convert to UI-friendly format
        feature_flags = get_feature_flags_for_ui(capabilities)

        return feature_flags

    except Exception as e:
        logger.error(f"Failed to get capabilities for device {device_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to query device capabilities: {str(e)}"
        ) from e
