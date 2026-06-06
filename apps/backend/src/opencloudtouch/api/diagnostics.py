"""Diagnostics API route — server info + device status for the diagnostics page."""

import logging
import platform
import sys
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from opencloudtouch import __version__
from opencloudtouch.core.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("")
async def get_diagnostics(request: Request):
    """Collect server and device diagnostics for the diagnostics page.

    Returns server info (version, platform, config) and device status
    with health indicators.
    """
    config = get_config()

    # Server info
    server_info = {
        "version": __version__,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "discovery_enabled": config.discovery_enabled,
        "mock_mode": config.mock_mode,
        "log_level": config.log_level,
        "manual_device_ips": len(config.manual_device_ips),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Device info
    devices = []
    try:
        device_repo = request.app.state.device_repo
        all_devices = await device_repo.get_all()
        for d in all_devices:
            devices.append(
                {
                    "device_id": d.device_id,
                    "name": d.name,
                    "model": d.model,
                    "ip": d.ip,
                    "firmware_version": d.firmware_version,
                    "setup_status": d.setup_status,
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                    "setup_completed_at": (
                        d.setup_completed_at.isoformat()
                        if d.setup_completed_at
                        else None
                    ),
                    "ssh_permanent": d.ssh_permanent,
                }
            )
    except Exception:
        logger.debug("Could not collect device info for diagnostics")

    # DB stats
    db_stats = {"devices": len(devices), "presets": 0}
    try:
        preset_repo = request.app.state.preset_repo
        for d in devices:
            presets = await preset_repo.get_all_presets(d["device_id"])
            db_stats["presets"] += len(presets)
    except Exception:
        logger.debug("Could not collect preset count for diagnostics")

    return {
        "server": server_info,
        "devices": devices,
        "db_stats": db_stats,
    }
