"""Unit tests for setup API routes.

Tests for device setup wizard endpoints.
Following TDD Red-Green-Refactor cycle.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from opencloudtouch.setup.routes import router
from opencloudtouch.setup.models import (
    SetupStatus,
    SetupStep,
    SetupProgress,
    ModelInstructions,
    MODEL_INSTRUCTIONS,
    get_model_instructions,
)
from opencloudtouch.setup.service import SetupService, get_setup_service


def create_mock_service():
    """Create mock setup service with common mocked methods."""
    service = MagicMock(spec=SetupService)
    service.get_model_instructions = get_model_instructions
    return service


@pytest.fixture
def mock_setup_service():
    """Create mock setup service."""
    return create_mock_service()


@pytest.fixture
def app(mock_setup_service):
    """Create test FastAPI app with setup router and mocked dependency."""
    app = FastAPI()
    app.include_router(router)
    # Override the dependency
    app.dependency_overrides[get_setup_service] = lambda: mock_setup_service
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestGetInstructions:
    """Tests for GET /api/setup/instructions/{model}."""

    def test_get_instructions_known_model(self, client):
        """Test getting instructions for known model."""
        response = client.get("/api/setup/instructions/SoundTouch%2010")
        assert response.status_code == 200
        
        data = response.json()
        assert data["model_name"] == "SoundTouch 10"
        assert data["display_name"] == "Bose SoundTouch 10"
        assert data["usb_port_type"] == "micro-usb"
        assert data["adapter_needed"] is True

    def test_get_instructions_unknown_model(self, client):
        """Test getting instructions for unknown model returns default."""
        response = client.get("/api/setup/instructions/UnknownModelXYZ")
        assert response.status_code == 200
        
        data = response.json()
        assert data["model_name"] == "Unknown"

    def test_get_instructions_url_encoded_model(self, client):
        """Test model name with spaces is handled."""
        response = client.get("/api/setup/instructions/SoundTouch%2030")
        assert response.status_code == 200
        
        data = response.json()
        assert "30" in data["model_name"]


class TestCheckConnectivity:
    """Tests for POST /api/setup/check-connectivity."""

    def test_check_connectivity_request_validation(self, client):
        """Test request validation."""
        # Missing IP
        response = client.post("/api/setup/check-connectivity", json={})
        assert response.status_code == 422

    def test_check_connectivity_with_valid_ip(self, client, mock_setup_service):
        """Test connectivity check with valid IP."""
        mock_setup_service.check_device_connectivity = AsyncMock(return_value={
            "ip": "192.168.1.100",
            "ssh_available": True,
            "telnet_available": True,
            "ready_for_setup": True,
        })

        response = client.post(
            "/api/setup/check-connectivity",
            json={"ip": "192.168.1.100"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ip"] == "192.168.1.100"
        assert data["ssh_available"] is True
        assert data["ready_for_setup"] is True


class TestStartSetup:
    """Tests for POST /api/setup/start."""

    def test_start_setup_request_validation(self, client):
        """Test request validation."""
        # Missing required fields
        response = client.post("/api/setup/start", json={})
        assert response.status_code == 422

    def test_start_setup_success(self, client, mock_setup_service):
        """Test successful setup start."""
        mock_setup_service.get_setup_status.return_value = None  # No active setup
        mock_setup_service.run_setup = AsyncMock()

        response = client.post("/api/setup/start", json={
            "device_id": "DEVICE123",
            "ip": "192.168.1.100",
            "model": "SoundTouch 10",
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["device_id"] == "DEVICE123"
        assert data["status"] == "started"

    def test_start_setup_already_in_progress(self, client, mock_setup_service):
        """Test starting setup when already in progress."""
        # Return an existing pending setup
        existing_progress = SetupProgress(
            device_id="DEVICE123",
            current_step=SetupStep.SSH_CONNECT,
            status=SetupStatus.PENDING,
        )
        mock_setup_service.get_setup_status.return_value = existing_progress

        response = client.post("/api/setup/start", json={
            "device_id": "DEVICE123",
            "ip": "192.168.1.100",
            "model": "SoundTouch 10",
        })
        assert response.status_code == 409  # Conflict


class TestGetStatus:
    """Tests for GET /api/setup/status/{device_id}."""

    def test_get_status_no_active_setup(self, client, mock_setup_service):
        """Test getting status when no setup is active."""
        mock_setup_service.get_setup_status.return_value = None

        response = client.get("/api/setup/status/DEVICE123")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "not_found"

    def test_get_status_active_setup(self, client, mock_setup_service):
        """Test getting status for active setup."""
        progress = SetupProgress(
            device_id="DEVICE123",
            current_step=SetupStep.CONFIG_MODIFY,
            status=SetupStatus.PENDING,
            message="Modifying configuration...",
        )
        mock_setup_service.get_setup_status.return_value = progress

        response = client.get("/api/setup/status/DEVICE123")
        assert response.status_code == 200
        
        data = response.json()
        assert data["device_id"] == "DEVICE123"
        assert data["current_step"] == "config_modify"
        assert data["status"] == "pending"


class TestVerifySetup:
    """Tests for POST /api/setup/verify/{device_id}."""

    def test_verify_setup_success(self, client, mock_setup_service):
        """Test successful verification."""
        mock_setup_service.verify_setup = AsyncMock(return_value={
            "ip": "192.168.1.100",
            "ssh_accessible": True,
            "ssh_persistent": True,
            "bmx_configured": True,
            "bmx_url": "<bmxRegistryUrl>http://server/bmx</bmxRegistryUrl>",
            "verified": True,
        })

        response = client.post(
            "/api/setup/verify/DEVICE123?ip=192.168.1.100"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["verified"] is True
        assert data["ssh_accessible"] is True


class TestListSupportedModels:
    """Tests for GET /api/setup/models."""

    def test_list_models(self, client):
        """Test listing all supported models."""
        response = client.get("/api/setup/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "models" in data
        assert len(data["models"]) > 0
        
        # Check structure
        model = data["models"][0]
        assert "model_name" in model
        assert "display_name" in model
        assert "usb_port_type" in model
        assert "adapter_needed" in model

    def test_list_models_contains_known_devices(self, client):
        """Test that known devices are in the list."""
        response = client.get("/api/setup/models")
        data = response.json()
        
        model_names = [m["model_name"] for m in data["models"]]
        
        # Check for known SoundTouch models
        assert "SoundTouch 10" in model_names
        assert "SoundTouch 20" in model_names
        assert "SoundTouch 30" in model_names
