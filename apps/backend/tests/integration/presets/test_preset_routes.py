"""Integration tests for preset API endpoints."""

import tempfile
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.main import app


@pytest.fixture
async def preset_service():
    """Create and initialize a temporary preset service for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_presets.db"
        
        # Initialize device repo (needed for preset service)
        from opencloudtouch.devices.repository import DeviceRepository
        device_repo = DeviceRepository(str(db_path))
        await device_repo.initialize()
        
        # Initialize preset repo
        preset_repo = PresetRepository(str(db_path))
        await preset_repo.initialize()

        # Initialize preset service with device_repo
        service = PresetService(preset_repo, device_repo)

        # Set in app.state for dependency injection
        app.state.preset_service = service

        yield service

        await preset_repo.close()
        await device_repo.close()


@pytest.mark.asyncio
async def test_set_preset_success(preset_service):
    """Test setting a new preset via API."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/presets/set",
            json={
                "device_id": "test-device-123",
                "preset_number": 1,
                "station_uuid": "station-uuid-abc",
                "station_name": "Test Radio",
                "station_url": "http://test.radio/stream.mp3",
                "station_homepage": "https://test.radio",
                "station_favicon": "https://test.radio/favicon.ico",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["device_id"] == "test-device-123"
    assert data["preset_number"] == 1
    assert data["station_name"] == "Test Radio"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_set_preset_invalid_number(preset_service):
    """Test setting preset with invalid number."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/presets/set",
            json={
                "device_id": "test-device",
                "preset_number": 7,  # Invalid (must be 1-6)
                "station_uuid": "uuid",
                "station_name": "Station",
                "station_url": "http://example.com/stream",
            },
        )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_device_presets(preset_service):
    """Test getting all presets for a device."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Set two presets
        await client.post(
            "/api/presets/set",
            json={
                "device_id": "device-abc",
                "preset_number": 1,
                "station_uuid": "uuid1",
                "station_name": "Station 1",
                "station_url": "http://station1.com/stream",
            },
        )
        await client.post(
            "/api/presets/set",
            json={
                "device_id": "device-abc",
                "preset_number": 3,
                "station_uuid": "uuid3",
                "station_name": "Station 3",
                "station_url": "http://station3.com/stream",
            },
        )

        # Get all presets
        response = await client.get("/api/presets/device-abc")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["preset_number"] == 1
    assert data[1]["preset_number"] == 3


@pytest.mark.asyncio
async def test_get_specific_preset(preset_service):
    """Test getting a specific preset."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Set preset
        await client.post(
            "/api/presets/set",
            json={
                "device_id": "device-xyz",
                "preset_number": 2,
                "station_uuid": "uuid-jazz",
                "station_name": "Jazz FM",
                "station_url": "http://jazz.fm/stream",
            },
        )

        # Get specific preset
        response = await client.get("/api/presets/device-xyz/2")

    assert response.status_code == 200
    data = response.json()
    assert data["preset_number"] == 2
    assert data["station_name"] == "Jazz FM"


@pytest.mark.asyncio
async def test_get_nonexistent_preset(preset_service):
    """Test getting a nonexistent preset returns 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/presets/nonexistent-device/5")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_clear_preset(preset_service):
    """Test clearing a specific preset."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Set preset
        await client.post(
            "/api/presets/set",
            json={
                "device_id": "device-clear",
                "preset_number": 4,
                "station_uuid": "uuid",
                "station_name": "Station",
                "station_url": "http://station.com/stream",
            },
        )

        # Clear preset
        response = await client.delete("/api/presets/device-clear/4")

    assert response.status_code == 200
    data = response.json()
    assert "cleared" in data["message"].lower()

    # Verify preset is gone
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/presets/device-clear/4")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_station_descriptor(preset_service):
    """Test getting station descriptor."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Set preset
        await client.post(
            "/api/presets/set",
            json={
                "device_id": "soundtouch-001",
                "preset_number": 1,
                "station_uuid": "radiobrowser-uuid-123",
                "station_name": "Rock Radio",
                "station_url": "http://rock.radio/stream.aac",
                "station_homepage": "https://rock.radio",
                "station_favicon": "https://rock.radio/logo.png",
            },
        )

        # Get station descriptor (what SoundTouch device would fetch)
        response = await client.get("/stations/preset/soundtouch-001/1.json")

    assert response.status_code == 200
    data = response.json()
    assert data["stationName"] == "Rock Radio"
    assert data["streamUrl"] == "http://rock.radio/stream.aac"
    assert data["homepage"] == "https://rock.radio"
    assert data["favicon"] == "https://rock.radio/logo.png"
    assert data["uuid"] == "radiobrowser-uuid-123"


@pytest.mark.asyncio
async def test_station_descriptor_not_found(preset_service):
    """Test station descriptor for unconfigured preset returns 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/stations/preset/unconfigured-device/1.json")

    assert response.status_code == 404
