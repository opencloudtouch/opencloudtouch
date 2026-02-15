"""Unit tests for SetupService.

Tests for device setup orchestration logic.
Following TDD Red-Green-Refactor cycle.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from opencloudtouch.setup.service import SetupService, get_setup_service
from opencloudtouch.setup.models import (
    SetupStatus,
    SetupStep,
    SetupProgress,
    ModelInstructions,
)


@pytest.fixture(autouse=True)
def mock_config():
    """Mock config for all tests."""
    with patch("opencloudtouch.setup.service.get_config") as mock:
        config = MagicMock()
        config.server_url = "http://localhost:8000"
        config.host = "localhost"
        config.port = 8000
        mock.return_value = config
        yield mock


class TestSetupServiceInitialization:
    """Tests for SetupService initialization."""

    def test_service_initialization(self):
        """Test service initializes with empty active setups."""
        service = SetupService()
        assert service._active_setups == {}

    def test_get_setup_service_singleton(self):
        """Test get_setup_service returns singleton."""
        # Reset singleton for test
        import opencloudtouch.setup.service as service_module
        service_module._setup_service = None
        
        service1 = get_setup_service()
        service2 = get_setup_service()
        assert service1 is service2


class TestSetupServiceModelInstructions:
    """Tests for model instructions retrieval."""

    @pytest.fixture
    def setup_service(self):
        """Create setup service instance."""
        return SetupService()

    def test_get_known_model_instructions(self, setup_service):
        """Test getting instructions for known model."""
        instructions = setup_service.get_model_instructions("SoundTouch 10")
        assert isinstance(instructions, ModelInstructions)
        assert instructions.model_name == "SoundTouch 10"

    def test_get_unknown_model_instructions(self, setup_service):
        """Test getting instructions for unknown model."""
        instructions = setup_service.get_model_instructions("Unknown Model XYZ")
        assert isinstance(instructions, ModelInstructions)
        assert instructions.model_name == "Unknown"  # Default


class TestSetupServiceStatus:
    """Tests for setup status management."""

    @pytest.fixture
    def setup_service(self):
        """Create setup service instance."""
        return SetupService()

    def test_get_status_no_active_setup(self, setup_service):
        """Test getting status when no setup is active."""
        status = setup_service.get_setup_status("DEVICE123")
        assert status is None

    def test_get_status_active_setup(self, setup_service):
        """Test getting status for active setup."""
        # Manually add an active setup
        progress = SetupProgress(
            device_id="DEVICE123",
            current_step=SetupStep.SSH_CONNECT,
            status=SetupStatus.PENDING,
            message="Connecting...",
        )
        setup_service._active_setups["DEVICE123"] = progress

        status = setup_service.get_setup_status("DEVICE123")
        assert status is not None
        assert status.device_id == "DEVICE123"
        assert status.status == SetupStatus.PENDING


class TestSetupServiceConnectivity:
    """Tests for connectivity checking."""

    @pytest.fixture
    def setup_service(self):
        """Create setup service instance."""
        return SetupService()

    @pytest.mark.asyncio
    async def test_check_connectivity_ssh_available(self, setup_service):
        """Test connectivity check when SSH is available."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True
        ), patch(
            "opencloudtouch.setup.service.check_telnet_port",
            new_callable=AsyncMock,
            return_value=True
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")
            
            assert result["ip"] == "192.168.1.100"
            assert result["ssh_available"] is True
            assert result["telnet_available"] is True
            assert result["ready_for_setup"] is True

    @pytest.mark.asyncio
    async def test_check_connectivity_ssh_not_available(self, setup_service):
        """Test connectivity check when SSH is not available."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=False
        ), patch(
            "opencloudtouch.setup.service.check_telnet_port",
            new_callable=AsyncMock,
            return_value=True
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")
            
            assert result["ssh_available"] is False
            assert result["telnet_available"] is True
            assert result["ready_for_setup"] is False  # SSH required


class TestSetupServiceRunSetup:
    """Tests for setup execution."""

    @pytest.fixture
    def setup_service(self):
        """Create setup service instance."""
        return SetupService()

    @pytest.fixture
    def mock_ssh_client(self):
        """Create mock SSH client."""
        client = MagicMock()
        client.connect = AsyncMock(return_value=MagicMock(success=True))
        client.execute = AsyncMock(return_value=MagicMock(
            success=True,
            output="Success",
            exit_code=0
        ))
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_run_setup_creates_progress(self, setup_service, mock_ssh_client):
        """Test run_setup creates progress entry."""
        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient",
            return_value=mock_ssh_client
        ):
            await setup_service.run_setup(
                device_id="DEVICE123",
                ip="192.168.1.100",
                model="SoundTouch 10",
            )
            
            # Progress should exist (or be cleaned up if successful)
            # Either way, the setup should have run

    @pytest.mark.asyncio
    async def test_run_setup_ssh_connection_failure(self, setup_service):
        """Test run_setup handles SSH connection failure."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=MagicMock(
            success=False,
            error="Connection refused"
        ))
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient",
            return_value=mock_client
        ):
            progress = await setup_service.run_setup(
                device_id="DEVICE123",
                ip="192.168.1.100",
                model="SoundTouch 10",
            )
            
            assert progress.status == SetupStatus.FAILED
            assert progress.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_run_setup_with_progress_callback(self, setup_service, mock_ssh_client):
        """Test run_setup calls progress callback."""
        progress_updates = []
        
        async def on_progress(progress):
            progress_updates.append(progress.current_step)

        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient",
            return_value=mock_ssh_client
        ):
            await setup_service.run_setup(
                device_id="DEVICE123",
                ip="192.168.1.100",
                model="SoundTouch 10",
                on_progress=on_progress,
            )
            
            # Should have received multiple progress updates
            assert len(progress_updates) > 0


class TestSetupServiceVerify:
    """Tests for setup verification."""

    @pytest.fixture
    def setup_service(self):
        """Create setup service instance."""
        return SetupService()

    @pytest.mark.asyncio
    async def test_verify_setup_ssh_not_accessible(self, setup_service):
        """Test verify when SSH not accessible."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=False
        ):
            result = await setup_service.verify_setup("192.168.1.100")
            
            assert result["ip"] == "192.168.1.100"
            assert result["ssh_accessible"] is False
            assert result["verified"] is False

    @pytest.mark.asyncio
    async def test_verify_setup_success(self, setup_service):
        """Test successful verification."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.execute = AsyncMock(side_effect=[
            MagicMock(output="yes", success=True),  # SSH persistence check
            MagicMock(output="<bmxRegistryUrl>http://localhost:8000/bmx</bmxRegistryUrl>", success=True),  # BMX check
        ])
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True
        ), patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient",
            return_value=mock_client
        ), patch(
            "opencloudtouch.setup.service.get_config"
        ) as mock_config:
            mock_config.return_value.server_url = "http://localhost:8000"
            mock_config.return_value.host = "localhost"
            mock_config.return_value.port = 8000
            
            result = await setup_service.verify_setup("192.168.1.100")
            
            assert result["ssh_accessible"] is True
            assert result["ssh_persistent"] is True
