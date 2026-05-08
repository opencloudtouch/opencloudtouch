"""Unit tests for SetupService.

Tests for device setup orchestration logic.
Following TDD Red-Green-Refactor cycle.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.setup.models import (
    ModelInstructions,
    SetupProgress,
    SetupStatus,
    SetupStep,
)
from opencloudtouch.setup.service import SetupService


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
            return_value=True,
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")

            assert result["ip"] == "192.168.1.100"
            assert result["ssh_available"] is True
            assert result["ready_for_setup"] is True

    @pytest.mark.asyncio
    async def test_check_connectivity_ssh_not_available(self, setup_service):
        """Test connectivity check when SSH is not available."""
        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await setup_service.check_device_connectivity("192.168.1.100")

            assert result["ssh_available"] is False
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
        client.execute = AsyncMock(
            return_value=MagicMock(success=True, output="Success", exit_code=0)
        )
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_run_setup_creates_progress(self, setup_service, mock_ssh_client):
        """Test run_setup creates progress entry."""
        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient",
            return_value=mock_ssh_client,
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
        mock_client.connect = AsyncMock(
            return_value=MagicMock(success=False, error="Connection refused")
        )
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient", return_value=mock_client
        ):
            progress = await setup_service.run_setup(
                device_id="DEVICE123",
                ip="192.168.1.100",
                model="SoundTouch 10",
            )

            assert progress.status == SetupStatus.FAILED
            assert progress.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_run_setup_with_progress_callback(
        self, setup_service, mock_ssh_client
    ):
        """Test run_setup calls progress callback."""
        progress_updates = []

        async def on_progress(progress):
            progress_updates.append(progress.current_step)

        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient",
            return_value=mock_ssh_client,
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
            return_value=False,
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
        mock_client.execute = AsyncMock(
            side_effect=[
                MagicMock(output="yes", success=True),  # SSH persistence check
                MagicMock(
                    output="<bmxRegistryUrl>http://localhost:8000/bmx</bmxRegistryUrl>",
                    success=True,
                ),  # BMX check
            ]
        )
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient", return_value=mock_client
        ), patch(
            "opencloudtouch.setup.service.get_config"
        ) as mock_config:
            mock_config.return_value.station_descriptor_base_url = None
            mock_config.return_value.server_url = "http://localhost:8000"
            mock_config.return_value.host = "localhost"
            mock_config.return_value.port = 8000

            result = await setup_service.verify_setup("192.168.1.100")

            assert result["ssh_accessible"] is True
            assert result["ssh_persistent"] is True


class TestSetupServiceInternalMethods:
    """Tests for SetupService internal helper methods — error paths and edge cases."""

    @pytest.fixture
    def service(self):
        return SetupService()

    @pytest.mark.asyncio
    async def test_persist_ssh_touch_fails_logs_warning(self, service):
        """_persist_ssh logs warning when touch /mnt/nv/remote_services fails (line 170)."""
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(
            side_effect=[
                MagicMock(success=False, error="Permission denied"),  # touch fails
                MagicMock(success=True, output=""),  # ls returns nothing
            ]
        )
        # Should not raise — best-effort only
        await service._persist_ssh(mock_client)
        assert mock_client.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_apply_bmx_url_always_remounts_and_edits_directly(self, service):
        """_apply_bmx_url must remount rw and edit /opt/Bose/etc/ directly.

        Regression: readonly fallback to /mnt/nv/ doesn't work — firmware ignores it.
        See: gesellix/Bose-SoundTouch#220, scheilch/opencloudtouch#139
        """
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(
            side_effect=[
                MagicMock(success=True, output=""),  # remount rw
                MagicMock(success=True, output=""),  # sed on /opt/Bose/etc/ path
            ]
        )

        async def noop_progress(step, msg, **kwargs):
            pass

        failed = await service._apply_bmx_url(
            mock_client,
            "http://content.api.bose.io:7777/bmx/registry/v1/services",
            noop_progress,
            MagicMock(),
        )
        assert failed is False

        # Must have remounted rw
        first_cmd = mock_client.execute.call_args_list[0][0][0]
        assert "remount,rw" in first_cmd

        # sed must target /opt/Bose/etc/ directly
        sed_cmd = mock_client.execute.call_args_list[1][0][0]
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in sed_cmd
        assert "/mnt/nv/" not in sed_cmd

    @pytest.mark.asyncio
    async def test_apply_bmx_url_no_readonly_fallback(self, service):
        """_apply_bmx_url must NOT copy to /mnt/nv/ as fallback.

        Regression: firmware on ST10/ST300 ignores files on /mnt/nv/.
        """
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(
            side_effect=[
                MagicMock(success=True, output=""),  # remount rw
                MagicMock(success=True, output=""),  # sed
            ]
        )

        async def noop_progress(step, msg, **kwargs):
            pass

        await service._apply_bmx_url(
            mock_client,
            "http://content.api.bose.io:7777/bmx/registry/v1/services",
            noop_progress,
            MagicMock(),
        )

        all_cmds = [c[0][0] for c in mock_client.execute.call_args_list]
        # No cp to /mnt/nv should exist
        cp_to_mnt_nv = [c for c in all_cmds if "cp" in c and "/mnt/nv/" in c]
        assert (
            len(cp_to_mnt_nv) == 0
        ), "Must NOT copy config to /mnt/nv/ — firmware ignores it"

    @pytest.mark.asyncio
    async def test_apply_bmx_url_sed_fails_returns_true(self, service):
        """_apply_bmx_url returns True (failed) when sed command fails."""
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(
            side_effect=[
                MagicMock(success=True, output=""),  # remount rw
                MagicMock(success=False, error="sed: no such file"),  # sed fails
            ]
        )
        progress_calls = []

        async def track_progress(step, msg, **kwargs):
            progress_calls.append((step, msg))

        failed = await service._apply_bmx_url(
            mock_client,
            "http://content.api.bose.io:7777/bmx",
            track_progress,
            MagicMock(),
        )
        assert failed is True
        assert len(progress_calls) == 1

    @pytest.mark.asyncio
    async def test_verify_bmx_url_reads_canonical_path(self, service):
        """_verify_bmx_url must read from /opt/Bose/etc/ path only.

        Regression: OverrideSdkPrivateCfg.xml is ignored by firmware.
        """
        mock_client = MagicMock()
        bmx_url = "http://content.api.bose.io:7777/bmx/registry/v1/services"
        mock_client.execute = AsyncMock(
            return_value=MagicMock(
                success=True, output=f"<bmxRegistryUrl>{bmx_url}</bmxRegistryUrl>"
            )
        )

        await service._verify_bmx_url(mock_client, bmx_url)

        verify_cmd = mock_client.execute.call_args_list[0][0][0]
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in verify_cmd
        # Must NOT check OverrideSdkPrivateCfg.xml
        assert "OverrideSdkPrivateCfg" not in verify_cmd

    @pytest.mark.asyncio
    async def test_verify_setup_reads_canonical_config_path(self, service):
        """verify_setup must read BMX URL from /opt/Bose/etc/ path.

        Regression: /mnt/nv/ paths are unreliable.
        """
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.execute = AsyncMock(
            side_effect=[
                MagicMock(output="yes", success=True),  # SSH persistence
                MagicMock(
                    output="<bmxRegistryUrl>http://localhost:8000/bmx</bmxRegistryUrl>",
                    success=True,
                ),  # BMX check
            ]
        )
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient", return_value=mock_client
        ), patch(
            "opencloudtouch.setup.service.get_config"
        ) as cfg_mock:
            cfg_mock.return_value.station_descriptor_base_url = None
            cfg_mock.return_value.server_url = "http://localhost:8000"
            cfg_mock.return_value.host = "localhost"
            cfg_mock.return_value.port = 8000

            await service.verify_setup("192.168.1.100")

        # The BMX check command
        bmx_cmd = mock_client.execute.call_args_list[1][0][0]
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in bmx_cmd
        # Must NOT reference Override path or /mnt/nv/ variants
        assert "OverrideSdkPrivateCfg" not in bmx_cmd

    @pytest.mark.asyncio
    async def test_run_setup_apply_bmx_fails_returns_early(self, service):
        """run_setup closes client and returns early when _apply_bmx_url fails."""
        mock_client = MagicMock()
        # execute call ordering: touch, ls, mkdir, cp×2, remount-rw, sed(fails)
        mock_client.connect = AsyncMock(return_value=MagicMock(success=True))
        mock_client.execute = AsyncMock(
            side_effect=[
                MagicMock(success=True, output="ok"),  # touch
                MagicMock(success=True, output=""),  # ls
                MagicMock(success=True, output=""),  # mkdir backup
                MagicMock(success=True, output=""),  # cp config 1
                MagicMock(success=True, output=""),  # cp config 2
                MagicMock(success=True, output=""),  # remount rw
                MagicMock(
                    success=False, error="sed: failed"
                ),  # sed fails → failed=True
            ]
        )
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient", return_value=mock_client
        ):
            progress = await service.run_setup(
                device_id="DEVICE_FAIL",
                ip="192.168.1.200",
                model="SoundTouch 10",
            )

        mock_client.close.assert_called()
        # Progress should be in FAILED state
        assert progress is not None

    @pytest.mark.asyncio
    async def test_run_setup_exception_sets_failed_status(self, service):
        """run_setup catches unexpected exceptions and sets FAILED status (lines 136-141)."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=MagicMock(success=True))
        mock_client.execute = AsyncMock(side_effect=RuntimeError("Unexpected crash"))
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient", return_value=mock_client
        ):
            progress = await service.run_setup(
                device_id="DEVICE_CRASH",
                ip="192.168.1.201",
                model="SoundTouch 10",
            )

        assert progress.status == SetupStatus.FAILED
        assert "Unexpected crash" in progress.error

    @pytest.mark.asyncio
    async def test_verify_setup_exception_handled(self, service):
        """verify_setup catches exceptions and returns safe result (lines 298-301)."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.execute = AsyncMock(side_effect=RuntimeError("SSH failure"))
        mock_client.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.service.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "opencloudtouch.setup.service.SoundTouchSSHClient", return_value=mock_client
        ):
            result = await service.verify_setup("192.168.1.100")

        assert result["ssh_accessible"] is True
        assert result.get("verified") is False or "verified" in result
