"""
OpenCloudTouch - Main FastAPI Application
Iteration 0: Basic setup with /health endpoint
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from opencloudtouch.api import devices_router
from opencloudtouch.core.config import get_config, init_config
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DiscoveryError,
    OpenCloudTouchError,
)
from opencloudtouch.core.logging import setup_logging
from opencloudtouch.db import DeviceRepository
from opencloudtouch.devices.adapter import get_discovery_adapter
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.services.sync_service import DeviceSyncService
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.presets.api.routes import router as presets_router
from opencloudtouch.presets.api.station_routes import router as stations_router
from opencloudtouch.radio.api.routes import router as radio_router
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.routes import router as settings_router
from opencloudtouch.settings.service import SettingsService

# Module-level logger
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Initialize configuration
    init_config()

    # Setup structured logging
    setup_logging()

    logger = logging.getLogger(__name__)
    cfg = get_config()
    logger.info(f"OpenCloudTouch starting on {cfg.host}:{cfg.port}")
    logger.info(f"Database: {cfg.effective_db_path}")
    logger.info(f"Discovery enabled: {cfg.discovery_enabled}")
    logger.info(f"Mock mode: {cfg.mock_mode}")

    # Initialize database
    device_repo = DeviceRepository(cfg.effective_db_path)
    await device_repo.initialize()
    app.state.device_repo = device_repo
    logger.info("Device repository initialized")

    # Initialize settings repository (convert str to Path if needed)
    from pathlib import Path

    db_path = (
        Path(cfg.effective_db_path)
        if isinstance(cfg.effective_db_path, str)
        else cfg.effective_db_path
    )
    settings_repo = SettingsRepository(db_path)
    await settings_repo.initialize()
    app.state.settings_repo = settings_repo
    logger.info("Settings repository initialized")

    # Initialize preset repository
    preset_repo = PresetRepository(cfg.effective_db_path)
    await preset_repo.initialize()
    app.state.preset_repo = preset_repo
    logger.info("Preset repository initialized")

    # Initialize preset service
    preset_service = PresetService(preset_repo)
    app.state.preset_service = preset_service
    logger.info("Preset service initialized")

    # Initialize device service
    discovery_adapter = get_discovery_adapter()
    sync_service = DeviceSyncService(
        repository=device_repo,
        discovery_timeout=cfg.discovery_timeout,
        manual_ips=cfg.manual_device_ips_list or [],
        discovery_enabled=cfg.discovery_enabled,
    )
    device_service = DeviceService(
        repository=device_repo,
        sync_service=sync_service,
        discovery_adapter=discovery_adapter,
    )
    app.state.device_service = device_service
    logger.info("Device service initialized")

    # Auto-discover devices on startup (especially mock devices)
    if cfg.mock_mode:
        logger.info("[MOCK MODE] Auto-discovering devices on startup...")
        result = await device_service.sync_devices()
        logger.info(
            f"[MOCK MODE] Device sync: {result.synced} synced, "
            f"{result.failed} failed ({result.discovered} discovered)"
        )

    # Initialize settings service
    settings_service = SettingsService(settings_repo)
    app.state.settings_service = settings_service
    logger.info("Settings service initialized")

    yield

    # Shutdown
    await device_repo.close()
    logger.info("Device repository closed")

    await settings_repo.close()
    logger.info("Settings repository closed")

    await preset_repo.close()
    logger.info("Preset repository closed")

    logger.info("OpenCloudTouch shutting down")


# Initialize config before app creation
init_config()

# FastAPI app
app = FastAPI(
    title="OpenCloudTouch",
    version="0.2.0",
    description="Open-Source replacement for discontinued streaming device cloud features",
    lifespan=lifespan,
)


# ============================================================================
# Exception Handlers - Unified Error Handling Strategy (ARCH-06)
# ============================================================================


@app.exception_handler(DeviceNotFoundError)
async def device_not_found_handler(request: Request, exc: DeviceNotFoundError):
    """Handle DeviceNotFoundError as 404 HTTP response."""
    logger = logging.getLogger(__name__)
    logger.warning(f"Device not found: {exc.device_id}")
    return JSONResponse(
        status_code=404,
        content={"error": "device_not_found", "detail": str(exc)},
    )


@app.exception_handler(DeviceConnectionError)
async def device_connection_error_handler(request: Request, exc: DeviceConnectionError):
    """Handle DeviceConnectionError as 503 Service Unavailable."""
    logger = logging.getLogger(__name__)
    logger.error(f"Device connection failed: {exc.device_ip}", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"error": "device_unavailable", "detail": str(exc)},
    )


@app.exception_handler(DiscoveryError)
async def discovery_error_handler(request: Request, exc: DiscoveryError):
    """Handle DiscoveryError as 500 Internal Server Error."""
    logger = logging.getLogger(__name__)
    logger.error(f"Discovery failed: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "discovery_failed", "detail": str(exc)},
    )


@app.exception_handler(OpenCloudTouchError)
async def oct_error_handler(request: Request, exc: OpenCloudTouchError):
    """Catch-all for other OpenCloudTouch domain exceptions."""
    logger = logging.getLogger(__name__)
    logger.error(f"OpenCloudTouch error: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc)},
    )


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
app.include_router(devices_router)
app.include_router(presets_router)
app.include_router(radio_router)
app.include_router(settings_router)
app.include_router(stations_router)  # Station descriptors for SoundTouch devices


# Health endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for Docker and monitoring."""
    cfg = get_config()
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "version": "0.2.0",
            "config": {
                "discovery_enabled": cfg.discovery_enabled,
                "db_path": cfg.db_path,
            },
        },
    )


# Static files (frontend)
# Development: ../../apps/frontend/dist (relative to src/opencloudtouch)
# Production: frontend/dist (copied during Docker build to /app/frontend/dist)
static_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
if not static_dir.exists():
    # Fallback for Docker/production deployment
    static_dir = Path(__file__).parent.parent / "frontend" / "dist"

if static_dir.exists():
    from fastapi.responses import FileResponse

    # Serve static assets (CSS, JS, images)
    app.mount(
        "/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets"
    )

    # Catch-all route for SPA (React Router) - must come AFTER API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for all non-API routes (SPA support).

        Args:
            full_path: Requested file path (e.g., "index.html", "assets/app.js")

        Returns:
            FileResponse for existing files, or index.html for SPA routes.

        Raises:
            HTTPException: 404 if path traversal attempt detected.
        """
        # SECURITY: Prevent path traversal attacks
        from urllib.parse import unquote

        # Decode URL-encoded characters (%2e = ., %2f = /)
        decoded_path = unquote(full_path)

        # Reject any path containing directory traversal patterns
        if ".." in decoded_path:
            raise HTTPException(status_code=404, detail="Not found")

        # Reject backslashes (Windows path traversal)
        if "\\" in decoded_path:
            raise HTTPException(status_code=404, detail="Not found")

        # Build safe path and verify it stays within frontend directory
        try:
            requested_path = (static_dir / decoded_path).resolve()
            frontend_root = static_dir.resolve()

            # Verify resolved path is within allowed directory
            if not str(requested_path).startswith(str(frontend_root)):
                raise HTTPException(status_code=404, detail="Not found")
        except (ValueError, OSError):
            # Handle invalid paths (e.g., illegal characters)
            raise HTTPException(status_code=404, detail="Not found")

        # If requesting a static file that exists, serve it
        if requested_path.is_file():
            return FileResponse(requested_path)

        # Otherwise serve index.html (React Router handles the rest)
        return FileResponse(static_dir / "index.html")


if __name__ == "__main__":
    import uvicorn

    cfg = get_config()
    uvicorn.run(
        "main:app",
        host=cfg.host,
        port=cfg.port,
        log_level=cfg.log_level.lower(),
        reload=True,
    )
