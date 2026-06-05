"""Unit tests for setup API routes.

Tests for device setup wizard endpoints.
Following TDD Red-Green-Refactor cycle.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_setup_service, get_wizard_service
from opencloudtouch.setup import wizard_helpers
from opencloudtouch.setup.models import (
    SetupProgress,
    SetupStatus,
    SetupStep,
    get_model_instructions,
)
from opencloudtouch.setup.routes import router
from opencloudtouch.setup.service import SetupService
from opencloudtouch.setup.wizard_routes import wizard_router
from opencloudtouch.setup.wizard_service import WizardService


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
    from opencloudtouch.core.exception_handlers import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.include_router(wizard_router)
    # Override the dependency
    app.dependency_overrides[get_setup_service] = lambda: mock_setup_service
    app.dependency_overrides[get_wizard_service] = lambda: WizardService()
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
        mock_setup_service.check_device_connectivity = AsyncMock(
            return_value={
                "ip": "192.168.1.100",
                "ssh_available": True,
                "telnet_available": True,
                "ready_for_setup": True,
            }
        )

        response = client.post(
            "/api/setup/check-connectivity", json={"ip": "192.168.1.100"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["ip"] == "192.168.1.100"
        assert data["ssh_available"] is True
        assert data["ready_for_setup"] is True


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
        mock_setup_service.verify_setup = AsyncMock(
            return_value={
                "ip": "192.168.1.100",
                "ssh_accessible": True,
                "ssh_persistent": True,
                "bmx_configured": True,
                "bmx_url": "<bmxRegistryUrl>http://server/bmx</bmxRegistryUrl>",
                "verified": True,
            }
        )

        response = client.post("/api/setup/verify/DEVICE123?ip=192.168.1.100")
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


class TestEnablePermanentSSH:
    """Tests for POST /api/setup/ssh/enable-permanent."""

    @pytest.mark.asyncio
    async def test_enable_permanent_ssh_success(self, client, monkeypatch):
        """Test enabling permanent SSH successfully."""
        # Mock SSH client
        mock_connection = AsyncMock()
        mock_connection.run = AsyncMock(
            return_value=MagicMock(stdout="", stderr="", exit_status=0)
        )

        mock_ssh_client = AsyncMock()
        mock_ssh_client.connect = AsyncMock(
            return_value=MagicMock(success=True, output="Connected")
        )
        mock_ssh_client.execute = AsyncMock(
            return_value=MagicMock(success=True, output="", exit_code=0, error=None)
        )
        mock_ssh_client.close = AsyncMock()
        mock_ssh_client._connection = mock_connection

        # Patch SoundTouchSSHClient
        from opencloudtouch.setup import routes

        monkeypatch.setattr(
            routes, "SoundTouchSSHClient", lambda host, port: mock_ssh_client
        )

        # Make request
        response = client.post(
            "/api/setup/ssh/enable-permanent",
            json={
                "device_id": "DEVICE123",
                "ip": "192.168.1.100",
                "make_permanent": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["permanent_enabled"] is True
        assert "permanently enabled" in data["message"]

        # Verify SSH client was called correctly
        mock_ssh_client.connect.assert_awaited_once()
        mock_ssh_client.execute.assert_awaited_once()
        mock_ssh_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enable_permanent_ssh_not_requested(self, client, monkeypatch):
        """Test when permanent SSH is not requested."""
        response = client.post(
            "/api/setup/ssh/enable-permanent",
            json={
                "device_id": "DEVICE123",
                "ip": "192.168.1.100",
                "make_permanent": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["permanent_enabled"] is False
        assert "temporary" in data["message"]

    @pytest.mark.asyncio
    async def test_enable_permanent_ssh_connection_failed(self, client, monkeypatch):
        """Test when SSH connection fails."""
        mock_ssh_client = AsyncMock()
        mock_ssh_client.connect = AsyncMock(
            return_value=MagicMock(success=False, error="Connection refused")
        )
        mock_ssh_client.close = AsyncMock()

        from opencloudtouch.setup import routes

        monkeypatch.setattr(
            routes, "SoundTouchSSHClient", lambda host, port: mock_ssh_client
        )

        response = client.post(
            "/api/setup/ssh/enable-permanent",
            json={
                "device_id": "DEVICE123",
                "ip": "192.168.1.100",
                "make_permanent": True,
            },
        )

        assert response.status_code == 503
        assert "Connection refused" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_enable_permanent_ssh_command_failed(self, client, monkeypatch):
        """Test when SSH command execution fails."""
        mock_ssh_client = AsyncMock()
        mock_ssh_client.connect = AsyncMock(
            return_value=MagicMock(success=True, output="Connected")
        )
        mock_ssh_client.execute = AsyncMock(
            return_value=MagicMock(
                success=False, output="Permission denied", exit_code=1, error="Failed"
            )
        )
        mock_ssh_client.close = AsyncMock()

        from opencloudtouch.setup import routes

        monkeypatch.setattr(
            routes, "SoundTouchSSHClient", lambda host, port: mock_ssh_client
        )

        response = client.post(
            "/api/setup/ssh/enable-permanent",
            json={
                "device_id": "DEVICE123",
                "ip": "192.168.1.100",
                "make_permanent": True,
            },
        )

        assert response.status_code == 500
        assert "Command failed" in response.json()["detail"]

    def test_enable_permanent_ssh_missing_fields(self, client):
        """Test request validation with missing fields."""
        # Missing ip
        response = client.post(
            "/api/setup/ssh/enable-permanent",
            json={"device_id": "DEVICE123", "make_permanent": True},
        )
        assert response.status_code == 422

        # Missing device_id
        response = client.post(
            "/api/setup/ssh/enable-permanent",
            json={"ip": "192.168.1.100", "make_permanent": True},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /wizard/verify-redirect
# ---------------------------------------------------------------------------


def _make_ssh_ctx(execute_result):
    """Return a mock async context manager whose ssh.execute returns execute_result."""
    from unittest.mock import AsyncMock, MagicMock

    mock_ssh = AsyncMock()
    mock_ssh.execute = AsyncMock(return_value=execute_result)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ssh)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx


class TestWizardVerifyRedirect:
    """Tests for POST /api/setup/wizard/verify-redirect."""

    ENDPOINT = "/api/setup/wizard/verify-redirect"
    PAYLOAD = {
        "device_ip": "192.168.1.100",
        "domain": "bose.vtuner.com",
        "expected_ip": "192.168.1.50",
    }

    def _ping_output(self, domain, resolved_ip):
        return f"PING {domain} ({resolved_ip}): 56 data bytes\n64 bytes from {resolved_ip}: seq=0"

    @pytest.mark.asyncio
    async def test_successful_match(self, client, monkeypatch):
        """Resolved IP matches expected → success=True, matches_expected=True."""
        import socket

        monkeypatch.setattr(socket, "gethostbyname", lambda h: "192.168.1.50")

        from opencloudtouch.setup.ssh_client import CommandResult

        result = CommandResult(
            success=True,
            output=self._ping_output("bose.vtuner.com", "192.168.1.50"),
            exit_code=0,
        )
        monkeypatch.setattr(
            wizard_helpers, "SoundTouchSSHClient", lambda ip: _make_ssh_ctx(result)
        )

        response = client.post(self.ENDPOINT, json=self.PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["matches_expected"] is True
        assert data["resolved_ip"] == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_mismatch_returns_success_false(self, client, monkeypatch):
        """Resolved IP doesn't match expected → success=False, matches_expected=False."""
        import socket

        monkeypatch.setattr(socket, "gethostbyname", lambda h: "192.168.1.50")

        from opencloudtouch.setup.ssh_client import CommandResult

        result = CommandResult(
            success=True,
            output=self._ping_output("bose.vtuner.com", "1.2.3.4"),
            exit_code=0,
        )
        monkeypatch.setattr(
            wizard_helpers, "SoundTouchSSHClient", lambda ip: _make_ssh_ctx(result)
        )

        response = client.post(self.ENDPOINT, json=self.PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["matches_expected"] is False
        assert data["resolved_ip"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_hostname_expected_ip_is_resolved(self, client, monkeypatch):
        """expected_ip as hostname ('myserver') is resolved server-side before comparison."""
        import socket

        monkeypatch.setattr(socket, "gethostbyname", lambda h: "10.0.0.99")

        from opencloudtouch.setup.ssh_client import CommandResult

        result = CommandResult(
            success=True,
            output=self._ping_output("bose.vtuner.com", "10.0.0.99"),
            exit_code=0,
        )
        monkeypatch.setattr(
            wizard_helpers, "SoundTouchSSHClient", lambda ip: _make_ssh_ctx(result)
        )

        response = client.post(
            self.ENDPOINT,
            json={**self.PAYLOAD, "expected_ip": "myserver"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_unresolvable_domain_on_device(self, client, monkeypatch):
        """If ping produces no match (domain unresolvable), success=False."""
        import socket

        monkeypatch.setattr(socket, "gethostbyname", lambda h: "192.168.1.50")

        from opencloudtouch.setup.ssh_client import CommandResult

        result = CommandResult(
            success=False,
            output="ping: bad address 'bose.vtuner.com'",
            exit_code=1,
        )
        monkeypatch.setattr(
            wizard_helpers, "SoundTouchSSHClient", lambda ip: _make_ssh_ctx(result)
        )

        response = client.post(self.ENDPOINT, json=self.PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["resolved_ip"] == ""

    def test_missing_device_ip_returns_422(self, client):
        """Validation: device_ip is required."""
        response = client.post(
            self.ENDPOINT,
            json={"domain": "bose.vtuner.com", "expected_ip": "192.168.1.50"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_command_result_uses_output_field(self, client, monkeypatch):
        """
        BUG-06 Regression: routes.py used result.stdout instead of result.output.
        CommandResult has .output not .stdout → AttributeError → 500.
        """
        import socket

        from opencloudtouch.setup.ssh_client import CommandResult

        monkeypatch.setattr(socket, "gethostbyname", lambda h: "192.168.1.50")

        # Build a CommandResult with .output (correct field name)
        result = CommandResult(
            success=True,
            output=self._ping_output("bose.vtuner.com", "192.168.1.50"),
            exit_code=0,
        )
        # Verify the model has 'output' but NOT 'stdout'
        assert hasattr(
            result, "output"
        ), "BUG-06: CommandResult must have .output field"
        assert not hasattr(
            result, "stdout"
        ), "BUG-06: CommandResult must NOT have .stdout - routes.py must use .output"

        monkeypatch.setattr(
            wizard_helpers, "SoundTouchSSHClient", lambda ip: _make_ssh_ctx(result)
        )

        response = client.post(self.ENDPOINT, json=self.PAYLOAD)
        # Must not return 500 (AttributeError: has no attribute 'stdout')
        assert response.status_code != 500, (
            "BUG-06: verify-redirect returned 500 – routes.py likely uses result.stdout "
            "instead of result.output"
        )
        assert (
            response.status_code == 200
        ), f"BUG-06: Expected 200, got {response.status_code}: {response.text}"


# ---------------------------------------------------------------------------
# /wizard/reboot-device
# ---------------------------------------------------------------------------


class TestWizardRebootDevice:
    """Tests for POST /api/setup/wizard/reboot-device.

    Regression: endpoint was missing entirely. Step 6 told the user to reboot
    in the next step, but Step 7 had no reboot button/API.
    """

    ENDPOINT = "/api/setup/wizard/reboot-device"

    @pytest.mark.asyncio
    async def test_reboot_success(self, client, monkeypatch):
        """Test successful reboot command delivery.

        The SSH connection drops immediately on reboot (expected).
        A successful or error result from execute() both indicate
        the command was accepted — we return success=True regardless.
        """
        mock_ssh_client = AsyncMock()
        mock_ssh_client.connect = AsyncMock(
            return_value=MagicMock(success=True, output="Connected")
        )
        # execute may raise or return error — both OK for reboot
        mock_ssh_client.execute = AsyncMock(
            return_value=MagicMock(success=True, output="", exit_code=0, error=None)
        )
        mock_ssh_client.close = AsyncMock()

        from opencloudtouch.setup import wizard_service as routes

        monkeypatch.setattr(
            routes, "SoundTouchSSHClient", lambda host, port: mock_ssh_client
        )

        response = client.post(self.ENDPOINT, json={"ip": "192.168.1.79"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Neustart" in data["message"]
        mock_ssh_client.execute.assert_awaited_once_with("reboot", timeout=5.0)
        mock_ssh_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reboot_connection_failure_returns_503(self, client, monkeypatch):
        """Test that SSH connection failure returns 503."""
        mock_ssh_client = AsyncMock()
        mock_ssh_client.connect = AsyncMock(
            return_value=MagicMock(success=False, error="Connection refused")
        )
        mock_ssh_client.close = AsyncMock()

        from opencloudtouch.setup import wizard_service as routes

        monkeypatch.setattr(
            routes, "SoundTouchSSHClient", lambda host, port: mock_ssh_client
        )

        response = client.post(self.ENDPOINT, json={"ip": "192.168.1.99"})

        assert response.status_code == 503
        assert "Connection refused" in response.json()["detail"]

    def test_missing_ip_returns_422(self, client):
        """Validation: ip field is required."""
        response = client.post(self.ENDPOINT, json={})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# BUG-04: enable-permanent uses port 22 (was 17317 which is Bose Telnet)
# ---------------------------------------------------------------------------


class TestEnablePermanentSSHPort:
    """
    BUG-04 Regression: enable-permanent-ssh passed port=17317 to SSHClient.
    Port 17317 is the Bose Telnet service. SSH runs on port 22.
    Result: /mnt/nv/remote_services was never created → no persistence.
    """

    @pytest.mark.asyncio
    async def test_uses_port_22(self, client, monkeypatch):
        """enable-permanent must connect via SSH port 22, not Telnet port 17317."""
        from opencloudtouch.setup import routes

        captured_port = []

        def capture_ssh_client(host, port):
            captured_port.append(port)
            mock_ssh = AsyncMock()
            mock_ssh.connect = AsyncMock(return_value=MagicMock(success=True))
            mock_ssh.execute = AsyncMock(
                return_value=MagicMock(success=True, output="", exit_code=0, error=None)
            )
            mock_ssh.close = AsyncMock()
            return mock_ssh

        monkeypatch.setattr(routes, "SoundTouchSSHClient", capture_ssh_client)

        client.post(
            "/api/setup/ssh/enable-permanent",
            json={"device_id": "X", "ip": "192.168.1.100", "make_permanent": True},
        )

        assert len(captured_port) >= 1, "SoundTouchSSHClient was never called"
        assert captured_port[0] == 22, (
            f"BUG-04: enable-permanent-ssh must use port 22 (SSH), "
            f"got port={captured_port[0]}. Port 17317 = Bose Telnet!"
        )


# ---------------------------------------------------------------------------
# BUG-19: /wizard/check-ports request uses device_ip, response has has_ssh
# ---------------------------------------------------------------------------


class TestCheckPorts:
    """
    BUG-19 Regression: Frontend sent {device_id} but backend expects {device_ip}.
    Response field name was also wrong: frontend read .ssh_available, backend
    returned .has_ssh.
    """

    ENDPOINT = "/api/setup/wizard/check-ports"

    def test_request_uses_device_ip(self, client, monkeypatch):
        """Endpoint must accept device_ip field (not device_id)."""
        import opencloudtouch.setup.wizard_service as routes

        monkeypatch.setattr(routes, "check_ssh_port", AsyncMock(return_value=True))

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 200, (
            f"BUG-19: /wizard/check-ports with device_ip field failed: "
            f"{response.status_code} {response.json()}"
        )

    def test_request_with_device_id_is_rejected(self, client):
        """device_id field must NOT be accepted (wrong field name)."""
        response = client.post(self.ENDPOINT, json={"device_id": "DEVICE123"})
        assert response.status_code == 422, (
            f"BUG-19: device_id should be rejected (field is device_ip). "
            f"Got {response.status_code}"
        )

    def test_response_has_has_ssh_field(self, client, monkeypatch):
        """Response must use has_ssh field (not ssh_available)."""
        import opencloudtouch.setup.wizard_service as routes

        monkeypatch.setattr(routes, "check_ssh_port", AsyncMock(return_value=True))

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 200
        data = response.json()

        assert (
            "has_ssh" in data
        ), f"BUG-19: Response must contain 'has_ssh' field. Got: {list(data.keys())}"
        assert (
            "ssh_available" not in data
        ), "BUG-19: 'ssh_available' should not exist (frontend was reading wrong field)"

    def test_ssh_available_returns_true_in_has_ssh(self, client, monkeypatch):
        """When SSH is open, has_ssh=True should be returned."""
        import opencloudtouch.setup.wizard_service as routes

        monkeypatch.setattr(routes, "check_ssh_port", AsyncMock(return_value=True))

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 200
        data = response.json()
        assert data["has_ssh"] is True
        assert data["success"] is True

    def test_no_ssh_returns_success_false(self, client, monkeypatch):
        """When SSH is not open, success=False."""
        import opencloudtouch.setup.wizard_service as routes

        monkeypatch.setattr(routes, "check_ssh_port", AsyncMock(return_value=False))

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# ---------------------------------------------------------------------------
# BUG-07: /wizard/modify-config response missing old_url/new_url fields
# ---------------------------------------------------------------------------


class TestModifyConfig:
    """
    BUG-07 Regression: ConfigModifyResponse was missing old_url/new_url fields.
    Step 5 UI showed 'Alte URL: N/A' and 'Neue URL: N/A'.
    """

    ENDPOINT = "/api/setup/wizard/modify-config"

    def test_response_schema_has_old_url_field(self, client, monkeypatch):
        """Response must contain old_url field."""
        from opencloudtouch.setup.api_models import ConfigModifyResponse

        fields = ConfigModifyResponse.model_fields
        assert "old_url" in fields, (
            "BUG-07: ConfigModifyResponse must have 'old_url' field. "
            "Step 5 UI shows 'Alte URL: N/A' without it."
        )

    def test_response_schema_has_new_url_field(self, client, monkeypatch):
        """Response must contain new_url field."""
        from opencloudtouch.setup.api_models import ConfigModifyResponse

        fields = ConfigModifyResponse.model_fields
        assert "new_url" in fields, (
            "BUG-07: ConfigModifyResponse must have 'new_url' field. "
            "Step 5 UI shows 'Neue URL: N/A' without it."
        )

    def test_response_old_url_not_required_has_default(self, client):
        """old_url and new_url should have defaults (not break old integrations)."""
        from opencloudtouch.setup.api_models import ConfigModifyResponse

        # Test that model can be created with just required fields
        response = ConfigModifyResponse(success=True, message="OK")
        assert response.old_url == ""
        assert response.new_url == ""


# ---------------------------------------------------------------------------
# BUG-25: /wizard/backup requires device_ip not device_id
# ---------------------------------------------------------------------------


class TestBackup:
    """
    BUG-25 Regression: Steps 4-7 sent {device_id} but backend expects {device_ip}.
    Result: 422 Validation Error for all wizard operations.
    """

    ENDPOINT = "/api/setup/wizard/backup"

    def test_requires_device_ip_not_device_id(self, client):
        """Endpoint must require device_ip field, not device_id."""
        # Sending device_id should fail with 422
        response = client.post(self.ENDPOINT, json={"device_id": "DEVICE123"})
        assert response.status_code == 422, (
            f"BUG-25: device_id should be rejected (endpoint expects device_ip). "
            f"Got {response.status_code}"
        )

    def test_accepts_device_ip_field(self, client, monkeypatch):
        """Endpoint must accept device_ip field."""
        from opencloudtouch.setup.api_models import BackupRequest

        # Verify model has device_ip field
        fields = BackupRequest.model_fields
        assert "device_ip" in fields, (
            f"BUG-25: BackupRequest must have 'device_ip' field. "
            f"Got fields: {list(fields.keys())}"
        )

    def test_backup_response_has_volumes_list(self, client):
        """Response uses volumes[]: list, not backups.rootfs object."""
        from opencloudtouch.setup.api_models import BackupResponse

        # Response must have 'volumes' as a list (not backups.rootfs)
        fields = BackupResponse.model_fields
        assert "volumes" in fields, (
            "BUG-23+BUG-25: BackupResponse must have 'volumes' list field. "
            "Frontend was reading backups.rootfs → TypeError."
        )
        assert (
            "total_size_mb" in fields
        ), "BackupResponse must have 'total_size_mb' field."


# ===========================================================================
# Wizard SSH Endpoint Integration Tests
# Tests that exercise the actual route handler with mocked SSH/services
# ===========================================================================


def _make_ssh_context(mock_ssh):
    """Create an async context manager returning mock_ssh."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_ssh)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestWizardBackupRoute:
    """Tests calling POST /api/setup/wizard/backup with real route handler."""

    ENDPOINT = "/api/setup/wizard/backup"

    def test_backup_success(self, client, monkeypatch):
        """Successful backup returns 200 with volumes list."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.backup_service import BackupResult, VolumeType

        mock_ssh = AsyncMock()
        mock_results = [
            BackupResult(
                volume=VolumeType.ROOTFS,
                success=True,
                backup_path="/usb/backups/rootfs.tgz",
                size_bytes=1024 * 1024,
                duration_seconds=2.5,
            )
        ]

        mock_backup_svc = AsyncMock()
        mock_backup_svc.backup_all = AsyncMock(return_value=mock_results)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchBackupService", lambda ssh: mock_backup_svc
        )

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["volumes"]) == 1
        assert data["total_size_mb"] > 0

    def test_backup_partial_failure_returns_success_false(self, client, monkeypatch):
        """Backup with failed volumes returns success=False."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.backup_service import BackupResult, VolumeType

        mock_ssh = AsyncMock()
        mock_results = [
            BackupResult(
                volume=VolumeType.ROOTFS,
                success=False,
                error="tar: write error",
            )
        ]

        mock_backup_svc = AsyncMock()
        mock_backup_svc.backup_all = AsyncMock(return_value=mock_results)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchBackupService", lambda ssh: mock_backup_svc
        )

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "tar: write error" in data["message"]

    def test_backup_ssh_exception_returns_503(self, client, monkeypatch):
        """SSH connection failure returns 503 (Service Unavailable)."""

        def raise_on_enter(ip):
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("SSH failed"))
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        monkeypatch.setattr(wizard_helpers, "SoundTouchSSHClient", raise_on_enter)

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 503
        assert "SSH" in response.json()["detail"]


class TestWizardModifyConfigRoute:
    """Tests calling POST /api/setup/wizard/modify-config with real route handler."""

    ENDPOINT = "/api/setup/wizard/modify-config"

    def test_modify_config_success(self, client, monkeypatch):
        """Successful config modification returns 200."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.config_service import ModifyResult

        mock_ssh = AsyncMock()
        mock_result = ModifyResult(
            success=True,
            backup_path="/usb/backups/config_backup.xml",
            diff="- bmx.bose.com\n+ 192.168.1.50",
        )

        mock_config_svc = AsyncMock()
        mock_config_svc.modify_bmx_url = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchConfigService", lambda ssh: mock_config_svc
        )

        response = client.post(
            self.ENDPOINT,
            json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["old_url"] == "bmx.bose.com"
        assert data["new_url"] == "192.168.1.50"

    def test_modify_config_failure_returns_200_with_success_false(
        self, client, monkeypatch
    ):
        """Failed modification returns 200 with success=False."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.config_service import ModifyResult

        mock_ssh = AsyncMock()
        mock_result = ModifyResult(success=False, error="File not found")

        mock_config_svc = AsyncMock()
        mock_config_svc.modify_bmx_url = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchConfigService", lambda ssh: mock_config_svc
        )

        response = client.post(
            self.ENDPOINT,
            json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_modify_config_ssh_exception_returns_503(self, client, monkeypatch):
        """SSH exception during config modification returns 503."""

        def fail_ctx(ip):
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(side_effect=OSError("SSH timeout"))
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        monkeypatch.setattr(wizard_helpers, "SoundTouchSSHClient", fail_ctx)

        response = client.post(
            self.ENDPOINT,
            json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
        )
        assert response.status_code == 503


class TestWizardModifyHostsRoute:
    """Tests calling POST /api/setup/wizard/modify-hosts."""

    ENDPOINT = "/api/setup/wizard/modify-hosts"

    def test_modify_hosts_success(self, client, monkeypatch):
        """Successful hosts modification returns 200."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.hosts_service import ModifyResult

        mock_ssh = AsyncMock()
        mock_result = ModifyResult(
            success=True,
            backup_path="/usb/backups/hosts.bak",
            diff="+ 192.168.1.50 bmx.bose.com",
        )

        mock_hosts_svc = AsyncMock()
        mock_hosts_svc.modify_hosts = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchHostsService", lambda ssh: mock_hosts_svc
        )

        response = client.post(
            self.ENDPOINT,
            json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_modify_hosts_failure(self, client, monkeypatch):
        """Failed hosts modification returns 200 with success=False."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.hosts_service import ModifyResult

        mock_ssh = AsyncMock()
        mock_result = ModifyResult(success=False, error="Write failed")

        mock_hosts_svc = AsyncMock()
        mock_hosts_svc.modify_hosts = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchHostsService", lambda ssh: mock_hosts_svc
        )

        response = client.post(
            self.ENDPOINT,
            json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_modify_hosts_ssh_exception_returns_503(self, client, monkeypatch):
        """SSH exception returns 503."""

        def fail_ctx(ip):
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(side_effect=OSError("Network error"))
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        monkeypatch.setattr(wizard_helpers, "SoundTouchSSHClient", fail_ctx)

        response = client.post(
            self.ENDPOINT,
            json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
        )
        assert response.status_code == 503


class TestWizardRestoreRoutes:
    """Tests for restore-config and restore-hosts endpoints."""

    def test_restore_config_success(self, client, monkeypatch):
        """POST /wizard/restore-config success returns 200."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.config_service import RestoreResult

        mock_ssh = AsyncMock()
        mock_result = RestoreResult(success=True)

        mock_config_svc = AsyncMock()
        mock_config_svc.restore_config = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchConfigService", lambda ssh: mock_config_svc
        )

        response = client.post(
            "/api/setup/wizard/restore-config",
            json={
                "device_ip": "192.168.1.100",
                "backup_path": "/usb/backups/config_backup.xml",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_restore_config_failure(self, client, monkeypatch):
        """POST /wizard/restore-config failure returns 200 with success=False."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.config_service import RestoreResult

        mock_ssh = AsyncMock()
        mock_result = RestoreResult(success=False, error="File missing")

        mock_config_svc = AsyncMock()
        mock_config_svc.restore_config = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchConfigService", lambda ssh: mock_config_svc
        )

        response = client.post(
            "/api/setup/wizard/restore-config",
            json={
                "device_ip": "192.168.1.100",
                "backup_path": "/usb/backups/config_backup.xml",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_restore_hosts_success(self, client, monkeypatch):
        """POST /wizard/restore-hosts success returns 200."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.hosts_service import RestoreResult

        mock_ssh = AsyncMock()
        mock_result = RestoreResult(success=True)

        mock_hosts_svc = AsyncMock()
        mock_hosts_svc.restore_hosts = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchHostsService", lambda ssh: mock_hosts_svc
        )

        response = client.post(
            "/api/setup/wizard/restore-hosts",
            json={
                "device_ip": "192.168.1.100",
                "backup_path": "/usb/backups/hosts.bak",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_restore_hosts_failure(self, client, monkeypatch):
        """POST /wizard/restore-hosts failure returns 200 with success=False."""
        from opencloudtouch.setup import wizard_service as routes
        from opencloudtouch.setup.hosts_service import RestoreResult

        mock_ssh = AsyncMock()
        mock_result = RestoreResult(success=False, error="Permission denied")

        mock_hosts_svc = AsyncMock()
        mock_hosts_svc.restore_hosts = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchHostsService", lambda ssh: mock_hosts_svc
        )

        response = client.post(
            "/api/setup/wizard/restore-hosts",
            json={
                "device_ip": "192.168.1.100",
                "backup_path": "/usb/backups/hosts.bak",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is False


class TestWizardListBackupsRoute:
    """Tests for POST /api/setup/wizard/list-backups."""

    ENDPOINT = "/api/setup/wizard/list-backups"

    def test_list_backups_success(self, client, monkeypatch):
        """Successful list-backups returns 200 with backup lists."""
        from opencloudtouch.setup import wizard_service as routes

        mock_ssh = AsyncMock()
        mock_config_svc = AsyncMock()
        mock_config_svc.list_backups = AsyncMock(
            return_value=["/usb/backups/config_backup.xml"]
        )
        mock_hosts_svc = AsyncMock()
        mock_hosts_svc.list_backups = AsyncMock(return_value=["/usb/backups/hosts.bak"])

        monkeypatch.setattr(
            wizard_helpers,
            "SoundTouchSSHClient",
            lambda ip: _make_ssh_context(mock_ssh),
        )
        monkeypatch.setattr(
            routes, "SoundTouchConfigService", lambda ssh: mock_config_svc
        )
        monkeypatch.setattr(
            routes, "SoundTouchHostsService", lambda ssh: mock_hosts_svc
        )

        response = client.post(self.ENDPOINT, json={"device_ip": "192.168.1.100"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["config_backups"]) == 1
        assert len(data["hosts_backups"]) == 1


class TestEnablePermanentSSHException:
    """Test exception path in enable_permanent_ssh (lines 197-199)."""

    def test_unexpected_exception_returns_500(self, client, monkeypatch):
        """Unexpected exception (not HTTPException) returns 500."""
        from opencloudtouch.setup import routes

        mock_ssh = AsyncMock()
        mock_ssh.connect = AsyncMock(return_value=MagicMock(success=True))
        mock_ssh.execute = AsyncMock(side_effect=RuntimeError("Unexpected DB error"))
        mock_ssh.close = AsyncMock()

        monkeypatch.setattr(routes, "SoundTouchSSHClient", lambda host, port: mock_ssh)

        response = client.post(
            "/api/setup/ssh/enable-permanent",
            json={
                "device_id": "DEVICE1",
                "ip": "192.168.1.100",
                "make_permanent": True,
            },
        )
        assert response.status_code == 500
        assert (
            response.json()["detail"]
            == "An unexpected error occurred while enabling permanent SSH"
        )


class TestWizardRestoreExceptionPaths:
    """Tests for exception paths in restore-config, restore-hosts, list-backups."""

    def test_restore_config_ssh_exception_returns_503(self, client, monkeypatch):
        """SSH exception in restore-config returns 503."""

        def fail_ctx(ip):
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(side_effect=OSError("SSH error"))
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        monkeypatch.setattr(wizard_helpers, "SoundTouchSSHClient", fail_ctx)

        response = client.post(
            "/api/setup/wizard/restore-config",
            json={
                "device_ip": "192.168.1.100",
                "backup_path": "/usb/backups/config.xml",
            },
        )
        assert response.status_code == 503

    def test_restore_hosts_ssh_exception_returns_503(self, client, monkeypatch):
        """SSH exception in restore-hosts returns 503."""

        def fail_ctx(ip):
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(side_effect=OSError("SSH error"))
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        monkeypatch.setattr(wizard_helpers, "SoundTouchSSHClient", fail_ctx)

        response = client.post(
            "/api/setup/wizard/restore-hosts",
            json={
                "device_ip": "192.168.1.100",
                "backup_path": "/usb/backups/hosts.bak",
            },
        )
        assert response.status_code == 503

    def test_list_backups_ssh_exception_returns_503(self, client, monkeypatch):
        """SSH exception in list-backups returns 503."""

        def fail_ctx(ip):
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(side_effect=OSError("SSH error"))
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        monkeypatch.setattr(wizard_helpers, "SoundTouchSSHClient", fail_ctx)

        response = client.post(
            "/api/setup/wizard/list-backups",
            json={"device_ip": "192.168.1.100"},
        )
        assert response.status_code == 503


class TestWizardRebootExceptionPath:
    """Test exception path in wizard_reboot_device (lines 481-483)."""

    def test_unexpected_exception_returns_500(self, client, monkeypatch):
        """Unexpected exception during reboot returns 500."""
        from opencloudtouch.setup import wizard_service as routes

        mock_ssh = AsyncMock()
        mock_ssh.connect = AsyncMock(return_value=MagicMock(success=True))
        mock_ssh.execute = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_ssh.close = AsyncMock()

        monkeypatch.setattr(routes, "SoundTouchSSHClient", lambda host, port: mock_ssh)

        response = client.post(
            "/api/setup/wizard/reboot-device",
            json={"ip": "192.168.1.100"},
        )
        assert response.status_code == 500
        assert "Unexpected error" in response.json()["detail"]


class TestWizardVerifyRedirectExceptionPaths:
    """Test exception paths in wizard_verify_redirect (lines 506-507, 543-545)."""

    def test_socket_gaierror_uses_raw_ip(self, client, monkeypatch):
        """socket.gaierror during hostname resolution uses raw expected_ip."""
        import socket

        from opencloudtouch.setup.ssh_client import CommandResult

        def raise_gaierror(h):
            raise socket.gaierror("Name resolution failed")

        monkeypatch.setattr(socket, "gethostbyname", raise_gaierror)

        result = CommandResult(
            success=True,
            output="PING bmx.bose.com (192.168.1.50): 56 data bytes",
            exit_code=0,
        )
        monkeypatch.setattr(
            wizard_helpers, "SoundTouchSSHClient", lambda ip: _make_ssh_ctx(result)
        )

        response = client.post(
            "/api/setup/wizard/verify-redirect",
            json={
                "device_ip": "192.168.1.100",
                "domain": "bmx.bose.com",
                "expected_ip": "192.168.1.50",
            },
        )
        # Should still work using the raw IP
        assert response.status_code == 200
        data = response.json()
        assert data["resolved_ip"] == "192.168.1.50"

    def test_ssh_exception_returns_503(self, client, monkeypatch):
        """SSH connection failure in verify_redirect returns 503."""
        import socket

        monkeypatch.setattr(socket, "gethostbyname", lambda h: "192.168.1.50")

        def fail_ctx(ip):
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("SSH failed"))
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        monkeypatch.setattr(wizard_helpers, "SoundTouchSSHClient", fail_ctx)

        response = client.post(
            "/api/setup/wizard/verify-redirect",
            json={
                "device_ip": "192.168.1.100",
                "domain": "bmx.bose.com",
                "expected_ip": "192.168.1.50",
            },
        )
        assert response.status_code == 503
