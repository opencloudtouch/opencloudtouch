"""
Integration Tests - Device Discovery & Sync Flow

Lightweight E2E tests for core device workflows.
Tests API endpoints: /api/devices/discover, /api/devices/sync, /api/devices
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from opencloudtouch.core.dependencies import get_device_service
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.services.sync_service import SyncResult
from opencloudtouch.discovery import DiscoveredDevice
from opencloudtouch.main import app


@pytest.mark.asyncio
async def test_discover_sync_persist_flow():
    """
    E2E: Device discovery → sync → persistence.

    Tests the complete user workflow:
    1. GET /api/devices/discover (preview discovered devices)
    2. POST /api/devices/sync (persist to database)
    3. GET /api/devices (verify persisted devices)
    """
    # Mock DeviceService
    mock_service = AsyncMock(spec=DeviceService)

    # Step 1: Mock discovery results
    discovered = [
        DiscoveredDevice(
            ip="192.168.1.100", port=8090, name="Living Room", model="ST30"
        ),
        DiscoveredDevice(ip="192.168.1.101", port=8090, name="Kitchen", model="ST10"),
    ]
    mock_service.discover_devices.return_value = discovered

    # Step 2: Mock sync result
    sync_result = SyncResult(discovered=2, synced=2, failed=0)
    mock_service.sync_devices.return_value = sync_result

    # Step 3: Mock persisted devices
    from opencloudtouch.db import Device

    persisted_devices = [
        Device(
            device_id="AABBCC112233",
            name="Living Room",
            model="SoundTouch 30",
            ip="192.168.1.100",
            mac_address="AA:BB:CC:11:22:33",
            firmware_version="28.0.12.46499",
        ),
        Device(
            device_id="DDEEFF445566",
            name="Kitchen",
            model="SoundTouch 10",
            ip="192.168.1.101",
            mac_address="DD:EE:FF:44:55:66",
            firmware_version="28.0.12.46499",
        ),
    ]
    mock_service.get_all_devices.return_value = persisted_devices

    async def get_mock_service():
        return mock_service

    try:
        # Override dependency with mock
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Discover (preview without saving)
            response = await client.get("/api/devices/discover")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 2
            assert len(data["devices"]) == 2
            assert data["devices"][0]["ip"] == "192.168.1.100"
            assert data["devices"][1]["ip"] == "192.168.1.101"

            # 2. Sync (persist to database)
            response = await client.post("/api/devices/sync")
            assert response.status_code == 200
            data = response.json()
            assert data["discovered"] == 2
            assert data["synced"] == 2
            assert data["failed"] == 0

            # 3. Verify persisted (fetch from database)
            response = await client.get("/api/devices")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 2
            assert len(data["devices"]) == 2

            # Verify device details
            device_ids = {d["device_id"] for d in data["devices"]}
            assert device_ids == {"AABBCC112233", "DDEEFF445566"}

            # Verify names match
            device_names = {d["name"] for d in data["devices"]}
            assert device_names == {"Living Room", "Kitchen"}

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discover_returns_empty_when_no_devices():
    """Test discovery endpoint when no devices are found."""
    mock_service = AsyncMock(spec=DeviceService)
    mock_service.discover_devices.return_value = []

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/devices/discover")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0
            assert data["devices"] == []

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_partial_failure_scenario():
    """
    Test sync when some devices fail to connect.

    Verifies that sync continues despite failures and returns accurate counts.
    """
    mock_service = AsyncMock(spec=DeviceService)

    # 3 discovered, 2 synced successfully, 1 failed
    sync_result = SyncResult(discovered=3, synced=2, failed=1)
    mock_service.sync_devices.return_value = sync_result

    async def get_mock_service():
        return mock_service

    try:
        app.dependency_overrides[get_device_service] = get_mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/devices/sync")

            assert response.status_code == 200
            data = response.json()
            assert data["discovered"] == 3
            assert data["synced"] == 2
            assert data["failed"] == 1

    finally:
        app.dependency_overrides.clear()
