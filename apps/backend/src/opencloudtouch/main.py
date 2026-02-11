"""
OpenCloudTouch - Main FastAPI Application
Iteration 0: Basic setup with /health endpoint
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from opencloudtouch.api import devices_router
from opencloudtouch.core.config import get_config, init_config
from opencloudtouch.core.dependencies import (
    set_device_repo,
    set_device_service,
    set_preset_repo,
    set_preset_service,
    set_settings_repo,
    set_settings_service,
)
from opencloudtouch.core.logging import setup_logging
from opencloudtouch.db import DeviceRepository
from opencloudtouch.devices.adapter import BoseDeviceDiscoveryAdapter
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
    set_device_repo(device_repo)  # Register via dependency injection
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
    set_settings_repo(settings_repo)  # Register via dependency injection
    logger.info("Settings repository initialized")

    # Initialize preset repository
    preset_repo = PresetRepository(cfg.effective_db_path)
    await preset_repo.initialize()
    set_preset_repo(preset_repo)  # Register via dependency injection
    logger.info("Preset repository initialized")

    # Initialize preset service
    preset_service = PresetService(preset_repo)
    set_preset_service(preset_service)  # Register via dependency injection
    logger.info("Preset service initialized")

    # Initialize device service
    discovery_adapter = BoseDeviceDiscoveryAdapter()
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
    set_device_service(device_service)  # Register via dependency injection
    logger.info("Device service initialized")

    # Initialize settings service
    settings_service = SettingsService(settings_repo)
    set_settings_service(settings_service)  # Register via dependency injection
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

# CORS middleware for Web UI
# CORS middleware for Web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: configure properly
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
        """Serve index.html for all non-API routes (SPA support)."""
        # If requesting a static file that exists, serve it
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)

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
