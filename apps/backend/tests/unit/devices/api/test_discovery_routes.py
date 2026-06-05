"""Unit tests for device discovery routes (extracted from routes.py in STORY-307).

Tests discovery-specific endpoints in isolation using discovery_router.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_device_service
from opencloudtouch.devices.api.discovery_routes import (  # noqa: E402
    _discovery_lock,
    discovery_router,
)


@pytest.fixture
def mock_device_service():
    service = AsyncMock()
    return service


@pytest.fixture
def app(mock_device_service):
    application = FastAPI()
    application.include_router(discovery_router)
    application.dependency_overrides[get_device_service] = lambda: mock_device_service
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


class TestDiscoveryRouterImport:
    """Verify the discovery_router is importable and functional."""

    def test_discovery_lock_exported(self):
        """_discovery_lock is exported from discovery_routes."""
        import asyncio

        assert isinstance(_discovery_lock, asyncio.Lock)

    def test_discover_endpoint_returns_200(self, client, mock_device_service):
        """GET /api/devices/discover returns 200 with empty device list."""
        mock_device_service.discover_devices = AsyncMock(return_value=[])

        response = client.get("/api/devices/discover")

        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_sync_endpoint_returns_409_when_locked(self, client):
        """POST /api/devices/sync returns 409 when discovery lock is held."""
        from opencloudtouch.devices.api.discovery_routes import _discovery_lock

        with patch.object(_discovery_lock, "locked", return_value=True):
            response = client.post("/api/devices/sync")

        assert response.status_code == 409
