"""
Device API Routes
CRUD endpoints for device management. Discovery endpoints extracted to discovery_routes.py.
"""

import logging
from collections.abc import Awaitable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException

from opencloudtouch.core.config import AppConfig, get_config
from opencloudtouch.core.dependencies import (
    get_device_service,
    get_device_state_manager,
    get_preset_service,
)
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DomainValidationError,
)
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.icy_worker import RADIO_SOURCES
from opencloudtouch.presets.models import Preset
from opencloudtouch.presets.service import PresetService
from opencloudtouch.streaming.icy_metadata import IcyMetadata, probe_stream
from opencloudtouch.streaming.metadata_cache import MISSING, MetadataCache, _Missing

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Module-level singleton — no DB, no DI needed
_metadata_cache = MetadataCache(ttl=15.0)

router = APIRouter(prefix="/api/devices", tags=["Devices"])


async def _device_op(
    device_id: str,
    action: str,
    coro: Awaitable[T],
    state_manager: DeviceStateManager | None = None,
) -> T:
    """Execute a device service call with standardized error handling.

    Domain exceptions (DeviceNotFoundError, DomainValidationError,
    DeviceConnectionError) propagate to global handlers.
    Only unexpected exceptions are wrapped in 500.

    When *state_manager* is provided and a DeviceConnectionError occurs,
    the device is marked offline via SSE so all connected clients learn
    immediately.
    """
    try:
        return await coro
    except DeviceConnectionError:
        if state_manager:
            await state_manager.mark_device_offline(device_id)
        raise
    except (DeviceNotFoundError, DomainValidationError):
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


def _apply_icy_metadata(
    result: dict[str, object],
    icy: IcyMetadata,
    artist: str | None,
    track: str | None,
) -> None:
    """Apply ICY metadata fields to the result dict when missing."""
    if not artist and icy.artist:
        result["artist"] = icy.artist
    if not track and icy.track:
        result["track"] = icy.track
    if not result["artwork_url"] and icy.station_logo_url:
        result["artwork_url"] = icy.station_logo_url


async def _enrich_from_icy(
    result: dict[str, object],
    stream_url: str,
    station_name: str | None,
    artist: str | None,
    track: str | None,
) -> None:
    """Enrich result dict with ICY metadata (cached or probed)."""
    cached = _metadata_cache.get(stream_url)
    if cached is MISSING:
        try:
            icy = await probe_stream(stream_url, station_name=station_name)
            _metadata_cache.put(stream_url, icy)
            if icy:
                _apply_icy_metadata(result, icy, artist, track)
        except Exception:
            logger.debug(
                "[NowPlaying] ICY probe failed for %s", stream_url, exc_info=True
            )
    elif cached is not None and not isinstance(cached, _Missing):
        _apply_icy_metadata(result, cached, artist, track)


async def _enrich_from_presets(
    result: dict[str, object],
    info: NowPlayingInfo,
    device_id: str,
    preset_service: PresetService,
) -> Preset | None:
    """Enrich artwork from preset DB for radio sources. Returns matched preset or None."""
    if info.source not in RADIO_SOURCES:
        return None
    if not info.station_name:
        return None
    try:
        presets = await preset_service.get_all_presets(device_id)
        station_lower = info.station_name.casefold()
        best_preset = None
        for preset in presets:
            if preset.station_name and preset.station_name.casefold() == station_lower:
                if best_preset is None:
                    best_preset = preset
                if not result["artwork_url"] and preset.station_favicon:
                    result["artwork_url"] = preset.station_favicon
                    best_preset = preset
                    logger.debug(
                        "[NowPlaying] Enriched artwork from preset DB: %s",
                        preset.station_favicon,
                    )
                    break  # Found a preset with favicon — done
        return best_preset
    except Exception:
        logger.debug(
            "[NowPlaying] Preset lookup failed for %s", device_id, exc_info=True
        )
    return None


@router.get("/{device_id}/now-playing")
async def get_now_playing(
    device_id: str,
    device_service: Annotated[DeviceService, Depends(get_device_service)],
    preset_service: Annotated[PresetService, Depends(get_preset_service)],
    state_manager: Annotated[DeviceStateManager, Depends(get_device_state_manager)],
) -> dict[str, object]:
    """Get current playback status for a device."""
    cfg = get_config()
    cached = state_manager.get_state(device_id)
    if cached and cached.now_playing and cached.is_fresh(cfg.state_cache_max_age):
        info = cached.now_playing
    else:
        info = await _device_op(
            device_id,
            "get playback status",
            device_service.get_now_playing(device_id),
            state_manager=state_manager,
        )
    result: dict[str, object] = {
        "source": info.source,
        "state": info.state,
        "station_name": info.station_name,
        "artist": info.artist,
        "track": info.track,
        "album": info.album,
        "artwork_url": info.artwork_url,
    }

    # Filter out non-image artwork URLs (e.g. station homepages)
    artwork_url = result["artwork_url"]
    if isinstance(artwork_url, str) and not _is_image_url(artwork_url):
        logger.debug(
            "[NowPlaying] Filtered non-image artwork_url: %s", result["artwork_url"]
        )
        result["artwork_url"] = None

    # Enrich from preset DB and ICY metadata for radio sources
    matched_preset = await _enrich_from_presets(result, info, device_id, preset_service)
    if matched_preset and (
        not info.artist or not info.track or not result["artwork_url"]
    ):
        await _enrich_from_icy(
            result,
            matched_preset.station_url,
            info.station_name,
            info.artist,
            info.track,
        )

    # Write enriched data back to state cache so SSE snapshots include it
    enriched_info = NowPlayingInfo(
        source=info.source,
        state=info.state,
        station_name=info.station_name,
        artist=str(result["artist"]) if result.get("artist") else info.artist,
        track=str(result["track"]) if result.get("track") else info.track,
        album=info.album,
        artwork_url=(
            str(result["artwork_url"])
            if result.get("artwork_url")
            else info.artwork_url
        ),
    )
    if enriched_info.artist != info.artist or enriched_info.track != info.track:
        state_manager.update_now_playing(device_id, enriched_info)
        logger.debug(
            "[NowPlaying] Wrote enriched data back to state cache for %s",
            device_id,
        )

    logger.debug(
        "[NowPlaying] device=%s source=%s state=%s track=%r artist=%r art=%r station=%r",
        device_id,
        info.source,
        info.state,
        result.get("track", info.track),
        result.get("artist", info.artist),
        result["artwork_url"],
        info.station_name,
    )
    return result


@router.get("/{device_id}/volume")
async def get_volume(
    device_id: str,
    device_service: Annotated[DeviceService, Depends(get_device_service)],
    state_manager: Annotated[DeviceStateManager, Depends(get_device_state_manager)],
):
    """Get current volume state for a device."""
    cfg = get_config()
    cached = state_manager.get_state(device_id)
    if cached and cached.volume and cached.is_fresh(cfg.state_cache_max_age):
        vol = cached.volume
    else:
        vol = await _device_op(
            device_id,
            "get volume",
            device_service.get_volume(device_id),
            state_manager=state_manager,
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
