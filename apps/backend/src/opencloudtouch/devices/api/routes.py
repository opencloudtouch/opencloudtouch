"""
Device API Routes
CRUD endpoints for device management. Discovery endpoints extracted to discovery_routes.py.
"""

import logging
from collections.abc import Awaitable
from typing import TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException

from opencloudtouch.core.config import AppConfig, get_config
from opencloudtouch.core.dependencies import get_device_service, get_preset_service
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DomainValidationError,
)
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.presets.service import PresetService
from opencloudtouch.streaming.icy_metadata import probe_stream
from opencloudtouch.streaming.metadata_cache import MISSING, MetadataCache

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Module-level singleton — no DB, no DI needed
_metadata_cache = MetadataCache(ttl=15.0)

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


_RADIO_SOURCES = {"LOCAL_INTERNET_RADIO", "INTERNET_RADIO"}

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"}


def _is_image_url(url: str) -> bool:
    """Heuristic check whether a URL likely points to an image."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path_lower = parsed.path.lower().rstrip("/")

    # Check file extension
    for ext in _IMAGE_EXTENSIONS:
        if path_lower.endswith(ext):
            return True

    # Known image CDN patterns
    host = parsed.hostname or ""
    if any(
        pattern in host
        for pattern in ("cdn-profiles.tunein.com", "cdn-radiotime", "cloudfront.net")
    ):
        return True

    # URL path contains typical image path segments
    if any(
        seg in path_lower for seg in ("/images/", "/img/", "/logo", "/favicon", "/icon")
    ):
        return True

    return False


@router.get("/{device_id}/now-playing")
async def get_now_playing(
    device_id: str,
    device_service: DeviceService = Depends(get_device_service),
    preset_service: PresetService = Depends(get_preset_service),
):
    """Get current playback status for a device."""
    info = await _device_op(
        device_id,
        "get playback status",
        device_service.get_now_playing(device_id),
    )
    result = {
        "source": info.source,
        "state": info.state,
        "station_name": info.station_name,
        "artist": info.artist,
        "track": info.track,
        "album": info.album,
        "artwork_url": info.artwork_url,
    }

    # Filter out non-image artwork URLs (e.g. station homepages)
    if result["artwork_url"] and not _is_image_url(result["artwork_url"]):
        logger.debug(
            "[NowPlaying] Filtered non-image artwork_url: %s", result["artwork_url"]
        )
        result["artwork_url"] = None

    # Enrich from preset DB when device returns no artwork for radio sources
    matched_preset = None
    if info.source in _RADIO_SOURCES and info.station_name:
        try:
            presets = await preset_service.get_all_presets(device_id)
            for preset in presets:
                if preset.station_name == info.station_name:
                    matched_preset = preset
                    if not result["artwork_url"] and preset.station_favicon:
                        result["artwork_url"] = preset.station_favicon
                        logger.debug(
                            "[NowPlaying] Enriched artwork from preset DB: %s",
                            preset.station_favicon,
                        )
                    break
        except Exception:
            logger.debug(
                "[NowPlaying] Preset lookup failed for %s", device_id, exc_info=True
            )

    # Enrich artist/track/artwork from ICY metadata probe (cached)
    needs_icy = (
        info.source in _RADIO_SOURCES
        and matched_preset
        and (not info.artist or not info.track or not result["artwork_url"])
    )
    if needs_icy:
        stream_url = matched_preset.station_url
        cached = _metadata_cache.get(stream_url)
        if cached is MISSING:
            # Cache miss — probe inline (fast, typically <200ms)
            try:
                icy = await probe_stream(
                    stream_url, timeout=3.0, station_name=info.station_name
                )
                _metadata_cache.put(stream_url, icy)
                if icy:
                    if not info.artist and icy.artist:
                        result["artist"] = icy.artist
                    if not info.track and icy.track:
                        result["track"] = icy.track
                    if not result["artwork_url"] and icy.station_logo_url:
                        result["artwork_url"] = icy.station_logo_url
            except Exception:
                logger.debug(
                    "[NowPlaying] ICY probe failed for %s", stream_url, exc_info=True
                )
        elif cached is not None:
            # Cache hit with metadata
            if not info.artist and cached.artist:
                result["artist"] = cached.artist
            if not info.track and cached.track:
                result["track"] = cached.track
            if not result["artwork_url"] and cached.station_logo_url:
                result["artwork_url"] = cached.station_logo_url

    logger.debug(
        "[NowPlaying] device=%s source=%s state=%s track=%r artist=%r art=%r station=%r",
        device_id,
        info.source,
        info.state,
        info.track,
        info.artist,
        result["artwork_url"],
        info.station_name,
    )
    return result


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
