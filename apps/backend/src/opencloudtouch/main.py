"""
OpenCloudTouch - Main FastAPI Application
Iteration 0: Basic setup with /health endpoint
"""

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from opencloudtouch import __version__, is_official_build
from opencloudtouch.api import devices_router
from opencloudtouch.api.bug_report import router as bug_report_router
from opencloudtouch.bmx.radiobrowser_routes import radiobrowser_router
from opencloudtouch.bmx.resolve_routes import resolve_router
from opencloudtouch.bmx.routes import router as bmx_router
from opencloudtouch.core.config import get_config, init_config
from opencloudtouch.core.exception_handlers import (
    register_exception_handlers,  # re-exported for backward compat
)
from opencloudtouch.core.logging import setup_logging
from opencloudtouch.core.logs_routes import router as logs_router
from opencloudtouch.api.diagnostics import router as diagnostics_router
from opencloudtouch.core.static_files import (
    find_frontend_static_dir,
    mount_static_files,
)
from opencloudtouch.db import DeviceRepository
from opencloudtouch.devices.adapter import get_discovery_adapter
from opencloudtouch.devices.api.discovery_routes import discovery_router
from opencloudtouch.devices.api.event_routes import event_router
from opencloudtouch.devices.api.preset_stream_routes import (
    descriptor_router as device_descriptor_router,
)
from opencloudtouch.devices.api.preset_stream_routes import (
    router as device_preset_stream_router,
)
from opencloudtouch.devices.health_check import DeviceHealthCheck
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.services.sync_service import DeviceSyncService
from opencloudtouch.devices.startup_check import StartupCheck
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.marge.routes import router as marge_router
from opencloudtouch.marge.service import MargeService
from opencloudtouch.presets.api.playlist_routes import router as playlist_router
from opencloudtouch.presets.api.routes import router as presets_router
from opencloudtouch.presets.api.station_routes import router as stations_router
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.radio.api.routes import router as radio_router
from opencloudtouch.recents.repository import RecentsRepository
from opencloudtouch.recents.service import RecentsService
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.routes import router as settings_router
from opencloudtouch.settings.service import SettingsService
from opencloudtouch.setup.routes import router as setup_router
from opencloudtouch.setup.service import SetupService
from opencloudtouch.setup.wizard_routes import wizard_router
from opencloudtouch.setup.wizard_service import WizardService
from opencloudtouch.swupdate.routes import router as swupdate_router
from opencloudtouch.wizard_audit.repository import WizardAuditRepository
from opencloudtouch.wizard_audit.routes import audit_router as wizard_audit_router
from opencloudtouch.zones.repository import ZoneRepository
from opencloudtouch.zones.routes import device_zone_router
from opencloudtouch.zones.routes import router as zones_router
from opencloudtouch.zones.service import ZoneService

# Module-level logger
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    init_config()
    setup_logging()

    logger = logging.getLogger(__name__)
    cfg = get_config()
    _log_startup_info(logger, cfg)

    # Performance: Increase thread pool for parallel Bose device I/O
    # Default ~5-8 workers causes serial bottleneck with >5 devices
    # 30 workers allows up to 30 parallel asyncio.to_thread() calls
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=30, thread_name_prefix="bose-io")
    loop.set_default_executor(executor)
    logger.info("Thread pool configured: 30 workers for Bose device I/O")

    # Startup: repositories → services → background tasks
    repos = await _init_repositories(app, cfg, logger)
    await _init_services(app, cfg, repos, logger)

    yield

    # Shutdown
    await _shutdown(app, repos, logger)
    executor.shutdown(wait=True)
    logger.info("Thread pool shutdown complete")


def _log_startup_info(logger: logging.Logger, cfg) -> None:
    """Log startup configuration summary."""
    logger.info("OpenCloudTouch starting on %s:%s", cfg.host, cfg.port)
    logger.info("Database: %s", cfg.effective_db_path)
    logger.info("Discovery enabled: %s", cfg.discovery_enabled)
    logger.info("Mock mode: %s", cfg.mock_mode)
    _build_tag = "official" if is_official_build() else "community"
    logger.info("Build: %s [%s]", __version__, _build_tag)


async def _init_repositories(app: FastAPI, cfg, logger: logging.Logger) -> dict:
    """Initialize all database repositories and attach to app.state.

    Returns:
        Dict mapping state attribute names to repository instances.
    """
    db_path = (
        Path(cfg.effective_db_path)
        if isinstance(cfg.effective_db_path, str)
        else cfg.effective_db_path
    )

    repo_classes = [
        ("device_repo", DeviceRepository, cfg.effective_db_path),
        ("settings_repo", SettingsRepository, db_path),
        ("preset_repo", PresetRepository, cfg.effective_db_path),
        ("recents_repo", RecentsRepository, cfg.effective_db_path),
        ("wizard_audit_repo", WizardAuditRepository, cfg.effective_db_path),
        ("zone_repo", ZoneRepository, cfg.effective_db_path),
    ]

    repos = {}
    for attr_name, repo_class, path in repo_classes:
        repo = repo_class(path)
        await repo.initialize()
        setattr(app.state, attr_name, repo)
        repos[attr_name] = repo
        logger.info("%s initialized", attr_name)

    return repos


async def _init_services(
    app: FastAPI, cfg, repos: dict, logger: logging.Logger
) -> None:
    """Initialize all services and attach to app.state."""
    device_repo = repos["device_repo"]
    settings_repo = repos["settings_repo"]
    preset_repo = repos["preset_repo"]
    recents_repo = repos["recents_repo"]

    # Recents service
    app.state.recents_service = RecentsService(recents_repo)
    logger.info("RecentsService initialized")

    # Marge service (account sync orchestration)
    app.state.marge_service = MargeService(preset_repo, recents_repo, device_repo)
    logger.info("MargeService initialized")

    # Preset service
    app.state.preset_service = PresetService(preset_repo, device_repo)
    logger.info("PresetService initialized")

    # Device service (with sync + discovery)
    sync_service = DeviceSyncService(
        repository=device_repo,
        discovery_timeout=cfg.discovery_timeout,
        manual_ips=cfg.manual_device_ips_list or [],
        discovery_enabled=cfg.discovery_enabled,
        settings_repo=settings_repo,
    )
    device_service = DeviceService(
        repository=device_repo,
        sync_service=sync_service,
        discovery_adapter=get_discovery_adapter(),
    )
    app.state.device_service = device_service
    logger.info("DeviceService initialized")

    # Zone service (with injected client factory to avoid circular deps)
    from opencloudtouch.devices.adapter import get_device_client

    zone_repo = repos["zone_repo"]
    app.state.zone_service = ZoneService(
        device_repo=device_repo,
        zone_repo=zone_repo,
        client_factory=get_device_client,
    )
    logger.info("ZoneService initialized")

    # Auto-discover in mock mode
    if cfg.mock_mode:
        logger.info("[MOCK MODE] Auto-discovering devices on startup...")
        result = await device_service.sync_devices()
        logger.info(
            "[MOCK MODE] Device sync: %d synced, %d failed (%d discovered)",
            result.synced,
            result.failed,
            result.discovered,
        )

    # Settings service
    app.state.settings_service = SettingsService(settings_repo)
    logger.info("SettingsService initialized")

    # Setup service
    app.state.setup_service = SetupService(device_repo=device_repo)
    logger.info("SetupService initialized")

    # Wizard service (orchestrates SSH wizard steps)
    app.state.wizard_service = WizardService(
        audit_repo=repos["wizard_audit_repo"],
        device_repo=device_repo,
    )
    logger.info("WizardService initialized")

    # Restore service (orchestrates restore wizard steps)
    from opencloudtouch.setup.restore_service import RestoreService

    app.state.restore_service = RestoreService(
        wizard_service=app.state.wizard_service,
        device_repo=device_repo,
    )
    logger.info("RestoreService initialized")

    # One-time startup check: verify setup_status for 'unknown' devices
    if not cfg.mock_mode:
        startup_check = StartupCheck(device_repo)
        await startup_check.run()
        logger.info("Startup device check completed")

    # Background health-check (not in mock/CI mode)
    zone_repo = repos.get("zone_repo")
    health_check = DeviceHealthCheck(device_repo, zone_repo=zone_repo)
    if not cfg.mock_mode:
        health_check.start()
        logger.info("Device health-check started")
    app.state.health_check = health_check

    await _init_websocket_pipeline(app, cfg, device_repo, logger)


def _make_preset_lookup(
    app: FastAPI, logger: logging.Logger, attr: str
) -> Callable[[str, str], Awaitable[str | None]]:
    """Create a preset attribute lookup closure (stream URL or favicon)."""

    async def _lookup(device_id: str, station_name: str) -> str | None:
        try:
            presets = await app.state.preset_service.get_all_presets(device_id)
        except Exception:
            logger.debug(
                "Preset %s lookup failed for %s", attr, device_id, exc_info=True
            )
            return None
        station_lower = station_name.casefold()
        for preset in presets:
            if preset.station_name and preset.station_name.casefold() == station_lower:
                value = getattr(preset, attr, None)
                if value:
                    return value  # type: ignore[no-any-return]
        return None

    return _lookup


async def _init_websocket_pipeline(
    app: FastAPI, cfg, device_repo, logger: logging.Logger
) -> None:
    """Initialize DeviceStateManager, ICY worker, and WebSocket manager."""
    # Device state manager (WebSocket push → state cache → SSE relay)
    app.state.device_state_manager = DeviceStateManager()

    # ICY metadata worker — enriches radio now-playing events with artwork
    from opencloudtouch.devices.websocket.icy_worker import IcyWorker

    icy_worker = IcyWorker(
        get_stream_url=_make_preset_lookup(app, logger, "station_url"),
    )
    app.state.device_state_manager.set_icy_worker(icy_worker)

    app.state.device_state_manager.set_preset_favicon_callback(
        _make_preset_lookup(app, logger, "station_favicon"),
    )
    app.state.device_state_manager.start_icy_polling()
    logger.info("DeviceStateManager initialized (with ICY worker + periodic polling)")

    # WebSocket manager — connects to SoundTouch device WS ports
    # and forwards events to DeviceStateManager
    from opencloudtouch.devices.websocket.manager import WebSocketManager

    ws_manager = WebSocketManager(
        on_event=app.state.device_state_manager.on_event,
    )
    app.state.ws_manager = ws_manager

    # Wire device sync → WS reconnect for IP changes
    app.state.device_service.set_on_device_synced(ws_manager.ensure_connection)

    # Connect to all known devices
    if cfg.mock_mode:
        logger.info("WebSocketManager: skipped (mock mode)")
        return

    devices = await device_repo.get_all()
    device_list = [{"device_id": d.device_id, "ip": d.ip} for d in devices]
    if device_list:
        await ws_manager.start(device_list)
        logger.info("WebSocketManager started for %d device(s)", len(device_list))
    else:
        logger.info("WebSocketManager: no devices to connect to")


async def _shutdown(app: FastAPI, repos: dict, logger: logging.Logger) -> None:
    """Graceful shutdown: stop background tasks, close repositories."""
    # Stop WebSocket manager first (stops pushing events)
    if hasattr(app.state, "ws_manager"):
        await app.state.ws_manager.stop()
        logger.info("WebSocketManager stopped")

    # Stop ICY polling
    if hasattr(app.state, "device_state_manager"):
        await app.state.device_state_manager.stop_icy_polling()
        logger.info("ICY polling stopped")

    await app.state.health_check.stop()
    logger.info("Device health-check stopped")

    for attr_name, repo in repos.items():
        await repo.close()
        logger.info("%s closed", type(repo).__name__)

    logger.info("OpenCloudTouch shutting down")


# Initialize config before app creation
init_config()

# FastAPI app
app = FastAPI(
    title="OpenCloudTouch",
    version=__version__,
    description="Open-Source replacement for discontinued streaming device cloud features",
    lifespan=lifespan,
)


# ============================================================================
# Exception Handlers - RFC 7807-inspired Standardized Error Responses
# ============================================================================

register_exception_handlers(app)

# ============================================================================
# CORS Middleware
# ============================================================================

# CORS middleware for Web UI
# Security: Check if wildcard is used and log warning
cfg = get_config()
if cfg.cors_origins == ["*"]:
    logger.warning(
        "CORS allows all origins - not recommended for production. "
        "Set OCT_CORS_ORIGINS to restrict access."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
# NOTE: discovery_router MUST come before devices_router so /discover path
# matches before the wildcard /{device_id} route.
app.include_router(
    discovery_router
)  # Device discovery endpoints (/discover, /sync, /stream)
app.include_router(devices_router)
app.include_router(presets_router)
app.include_router(radio_router)
app.include_router(settings_router)
app.include_router(stations_router)  # Station descriptors for SoundTouch devices
app.include_router(device_preset_stream_router)  # Stream proxy for Bose presets
app.include_router(device_descriptor_router)  # Preset descriptors (XML) for Bose
app.include_router(bmx_router)  # BMX stream resolution for Bose devices
app.include_router(radiobrowser_router)  # BMX RadioBrowser playback
app.include_router(resolve_router)  # Legacy BMX resolve endpoint
app.include_router(marge_router)  # Marge (streaming.bose.com) account sync
app.include_router(playlist_router)  # M3U/PLS playlist files for Bose presets
app.include_router(setup_router)  # Device setup wizard
app.include_router(wizard_router)  # SSH-driven wizard step endpoints
app.include_router(swupdate_router)  # SWUpdate firmware index emulation
app.include_router(zones_router)  # Multi-room zone management
app.include_router(device_zone_router)  # Per-device zone status
app.include_router(logs_router)  # Backend log download
app.include_router(bug_report_router)  # Bug report submission
app.include_router(diagnostics_router)  # Diagnostics page data
app.include_router(wizard_audit_router)  # Wizard audit trail
app.include_router(event_router)  # SSE device event stream


# Health endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for Docker and monitoring."""
    cfg = get_config()
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "opencloudtouch",
            "version": __version__,
            "build": "official" if is_official_build() else "community",
            "config": {
                "discovery_enabled": cfg.discovery_enabled,
            },
        },
    )


@app.get("/api/health/websockets", tags=["System"])
async def websocket_health(request: Request):
    """WebSocket connection health for all managed devices."""
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is None:
        return JSONResponse(
            status_code=200,
            content={"connections": {}, "total_connected": 0, "total_devices": 0},
        )
    return JSONResponse(status_code=200, content=ws_manager.get_health())


# Static files (frontend) — SPA 404 handler
mount_static_files(app, find_frontend_static_dir(Path(__file__)))


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    cfg = get_config()
    uvicorn.run(
        "main:app",
        host=cfg.host,
        port=cfg.port,
        log_level=cfg.log_level.lower(),
        reload=True,
    )
