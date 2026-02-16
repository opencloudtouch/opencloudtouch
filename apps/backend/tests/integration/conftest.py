"""Shared fixtures for integration tests."""

import os
import tempfile
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport, Timeout
from fastapi import FastAPI

# Set mock mode BEFORE initializing config
os.environ.setdefault("OCT_MOCK_MODE", "true")

from opencloudtouch.core.config import init_config, get_config
from opencloudtouch.db import DeviceRepository
from opencloudtouch.devices.adapter import BoseDeviceDiscoveryAdapter
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.services.sync_service import DeviceSyncService
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.service import SettingsService

# Initialize config early for integration tests
init_config()


def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app for testing (no lifespan context).

    Note: Routers already have their prefixes defined (e.g., "/api/presets"),
    so we don't add prefixes here.
    """
    from opencloudtouch.devices.api.routes import router as devices_router
    from opencloudtouch.presets.api.routes import router as presets_router
    from opencloudtouch.devices.api.preset_stream_routes import (
        router as stream_router,
        descriptor_router,
    )
    from opencloudtouch.settings.routes import router as settings_router
    from opencloudtouch.radio.api.routes import router as radio_router
    from opencloudtouch.core.exceptions import (
        DeviceNotFoundError,
        DeviceConnectionError,
        DiscoveryError,
        OpenCloudTouchError,
    )
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware

    test_app = FastAPI(title="OpenCloudTouch Test")

    # Add CORS middleware (same as main.py)
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    test_app.include_router(devices_router)  # /api/devices
    test_app.include_router(presets_router)  # /api/presets
    test_app.include_router(stream_router)  # /device/{device_id}/preset/{preset_number}
    test_app.include_router(descriptor_router)
    test_app.include_router(settings_router)  # /api/settings
    test_app.include_router(radio_router)  # /api/radio

    # Add exception handlers (same as main.py)
    @test_app.exception_handler(DeviceNotFoundError)
    async def device_not_found_handler(request: Request, exc: DeviceNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @test_app.exception_handler(DeviceConnectionError)
    async def device_connection_handler(request: Request, exc: DeviceConnectionError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @test_app.exception_handler(DiscoveryError)
    async def discovery_error_handler(request: Request, exc: DiscoveryError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @test_app.exception_handler(OpenCloudTouchError)
    async def oct_error_handler(request: Request, exc: OpenCloudTouchError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return test_app


@pytest.fixture
async def real_db():
    """Create real in-memory SQLite database."""
    # Use temporary file instead of :memory: to allow multiple connections
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    device_repo = DeviceRepository(db_path)
    settings_repo = SettingsRepository(db_path)

    await device_repo.initialize()
    await settings_repo.initialize()

    yield {
        "device_repo": device_repo,
        "settings_repo": settings_repo,
        "db_path": db_path,
    }

    await device_repo.close()
    await settings_repo.close()
    db_path.unlink(missing_ok=True)


@pytest.fixture
async def real_api_client(real_db):
    """FastAPI client with real DB and dependency in app.state.

    Uses a minimal test app WITHOUT lifespan to avoid asyncio deadlocks.
    httpx.ASGITransport does not trigger FastAPI lifespan events.

    OCT_MOCK_MODE is set globally in conftest.py to prevent real HTTP calls.
    """
    device_repo = real_db["device_repo"]
    settings_repo = real_db["settings_repo"]
    db_path = real_db["db_path"]

    # Initialize preset repository
    from opencloudtouch.presets.repository import PresetRepository
    from opencloudtouch.presets.service import PresetService

    preset_repo = PresetRepository(str(db_path))
    await preset_repo.initialize()
    preset_service = PresetService(preset_repo, device_repo)

    # Initialize services (same as main.py lifespan)
    sync_service = DeviceSyncService(
        repository=device_repo,
        discovery_timeout=10,
        manual_ips=[],
        discovery_enabled=True,
    )
    device_service = DeviceService(
        repository=device_repo,
        sync_service=sync_service,
        discovery_adapter=BoseDeviceDiscoveryAdapter(),
    )
    settings_service = SettingsService(repository=settings_repo)

    # Create test app WITHOUT lifespan (avoids asyncio deadlocks)
    test_app = create_test_app()

    # Set in app.state for dependency injection
    test_app.state.device_repo = device_repo
    test_app.state.settings_repo = settings_repo
    test_app.state.preset_repo = preset_repo
    test_app.state.device_service = device_service
    test_app.state.settings_service = settings_service
    test_app.state.preset_service = preset_service

    transport = ASGITransport(app=test_app)
    timeout = Timeout(5.0, connect=2.0)  # 5s read, 2s connect - prevent hangs

    async with AsyncClient(
        transport=transport, base_url="http://test", timeout=timeout
    ) as client:
        yield client

    await preset_repo.close()
