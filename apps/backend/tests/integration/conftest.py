"""Shared fixtures for integration tests."""

import tempfile
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from opencloudtouch.db import DeviceRepository
from opencloudtouch.devices.adapter import BoseDeviceDiscoveryAdapter
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.services.sync_service import DeviceSyncService
from opencloudtouch.main import app
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.service import SettingsService


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
    """FastAPI client with real DB and dependency in app.state."""
    device_repo = real_db["device_repo"]
    settings_repo = real_db["settings_repo"]
    db_path = real_db["db_path"]

    # Initialize preset repository
    from opencloudtouch.presets.repository import PresetRepository
    from opencloudtouch.presets.service import PresetService

    preset_repo = PresetRepository(str(db_path))
    await preset_repo.initialize()
    preset_service = PresetService(preset_repo)

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

    # Set in app.state for dependency injection
    app.state.device_repo = device_repo
    app.state.settings_repo = settings_repo
    app.state.preset_repo = preset_repo
    app.state.device_service = device_service
    app.state.settings_service = settings_service
    app.state.preset_service = preset_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await preset_repo.close()
