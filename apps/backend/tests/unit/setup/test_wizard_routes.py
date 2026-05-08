"""Tests for setup/wizard_routes.py — SSH-driven wizard step endpoints.

TDD RED phase: tests fail until setup/wizard_routes.py is created and
`wizard_router` is mounted in main.py.

Covers all 9 wizard endpoints:
  POST /api/setup/wizard/check-ports
  POST /api/setup/wizard/backup
  POST /api/setup/wizard/modify-config
  POST /api/setup/wizard/modify-hosts
  POST /api/setup/wizard/restore-config
  POST /api/setup/wizard/restore-hosts
  POST /api/setup/wizard/list-backups
  POST /api/setup/wizard/reboot-device
  POST /api/setup/wizard/verify-redirect
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def wizard_app():
    """Minimal FastAPI app with only wizard_router mounted."""
    from opencloudtouch.setup.wizard_routes import wizard_router

    app = FastAPI()
    app.include_router(wizard_router)
    return app


@pytest.fixture
def client(wizard_app):
    return TestClient(wizard_app, raise_server_exceptions=False)


# ── wizard/check-ports ────────────────────────────────────────────────────────


class TestWizardCheckPorts:
    """POST /api/setup/wizard/check-ports"""

    def test_ssh_accessible(self, client):
        with patch(
            "opencloudtouch.setup.wizard_routes.check_ssh_port",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.post(
                "/api/setup/wizard/check-ports",
                json={"device_ip": "192.168.1.100", "timeout": 3},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["has_ssh"] is True

    def test_ssh_not_accessible_returns_failure(self, client):
        with patch(
            "opencloudtouch.setup.wizard_routes.check_ssh_port",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = client.post(
                "/api/setup/wizard/check-ports",
                json={"device_ip": "192.168.1.100", "timeout": 3},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["has_ssh"] is False


# ── wizard/backup ─────────────────────────────────────────────────────────────


class TestWizardBackup:
    """POST /api/setup/wizard/backup"""

    def _make_backup_result(self, success, volume_value="rootfs"):
        result = MagicMock()
        result.success = success
        result.error = None if success else "SSH error"
        result.size_bytes = 1024 * 1024
        result.duration_seconds = 5.0
        result.backup_path = f"/usb/backup_{volume_value}.tar.gz"
        result.volume = MagicMock()
        result.volume.value = volume_value
        return result

    def test_successful_backup(self, client):
        mock_result = self._make_backup_result(True)
        mock_backup_service = MagicMock()
        mock_backup_service.backup_all = AsyncMock(return_value=[mock_result])

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchBackupService",
                return_value=mock_backup_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/backup",
                json={"device_ip": "192.168.1.100"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_backup_partial_failure(self, client):
        failed = self._make_backup_result(False)
        mock_backup_service = MagicMock()
        mock_backup_service.backup_all = AsyncMock(return_value=[failed])

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchBackupService",
                return_value=mock_backup_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/backup",
                json={"device_ip": "192.168.1.100"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is False


# ── wizard/modify-config ──────────────────────────────────────────────────────


class TestWizardModifyConfig:
    """POST /api/setup/wizard/modify-config"""

    def test_successful_config_modification(self, client):
        mock_result = MagicMock(
            success=True, error=None, backup_path="/usb/config.bak", diff="..."
        )
        mock_config_service = MagicMock()
        mock_config_service.modify_bmx_url = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchConfigService",
                return_value=mock_config_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-config",
                json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["old_url"] == "bmx.bose.com"
        assert body["new_url"] == "192.168.1.50"

    def test_config_modification_failure(self, client):
        mock_result = MagicMock(success=False, error="File not found")
        mock_config_service = MagicMock()
        mock_config_service.modify_bmx_url = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchConfigService",
                return_value=mock_config_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-config",
                json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_config_modification_exception_returns_503(self, client):
        """SSH connection failure returns 503, not 500."""
        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(
                side_effect=ConnectionError("SSH down")
            )
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-config",
                json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
            )
        assert response.status_code == 503
        assert "SSH" in response.json()["detail"]


# ── wizard/modify-hosts ───────────────────────────────────────────────────────


class TestWizardModifyHosts:
    """POST /api/setup/wizard/modify-hosts"""

    def test_successful_hosts_modification(self, client):
        mock_result = MagicMock(
            success=True, error=None, backup_path="/usb/hosts.bak", diff="..."
        )
        mock_hosts_service = MagicMock()
        mock_hosts_service.modify_hosts = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchHostsService",
                return_value=mock_hosts_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-hosts",
                json={
                    "device_ip": "192.168.1.100",
                    "target_addr": "192.168.1.50",
                    "include_optional": False,
                },
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_hosts_modification_failure(self, client):
        mock_result = MagicMock(success=False, error="Permission denied")
        mock_hosts_service = MagicMock()
        mock_hosts_service.modify_hosts = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchHostsService",
                return_value=mock_hosts_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-hosts",
                json={
                    "device_ip": "192.168.1.100",
                    "target_addr": "192.168.1.50",
                    "include_optional": True,
                },
            )
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_hostname_resolved_to_ip_before_hosts_modify(self, client):
        """BUG-03 Regression: hostname in target_addr must be resolved to IP."""
        mock_result = MagicMock(
            success=True, error=None, backup_path="/usb/hosts.bak", diff="..."
        )
        mock_hosts_service = MagicMock()
        mock_hosts_service.modify_hosts = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchHostsService",
                return_value=mock_hosts_service,
            ),
            patch(
                "opencloudtouch.setup.wizard_routes.socket.gethostbyname",
                return_value="192.168.178.11",
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-hosts",
                json={
                    "device_ip": "192.168.1.100",
                    "target_addr": "http://hera:7777",
                    "include_optional": False,
                },
            )
        assert response.status_code == 200
        assert response.json()["success"] is True
        # Verify that hosts_service received the resolved IP, not hostname
        mock_hosts_service.modify_hosts.assert_awaited_once()
        call_args = mock_hosts_service.modify_hosts.call_args
        assert (
            call_args[1].get("oct_ip", call_args[0][0]) == "192.168.178.11"
        ), "BUG-03: modify_hosts was called with hostname instead of resolved IP"

    def test_unresolvable_hostname_returns_400(self, client):
        """BUG-03: Unresolvable hostname in target_addr must return 400."""
        import socket as _socket

        with patch(
            "opencloudtouch.setup.wizard_routes.socket.gethostbyname",
            side_effect=_socket.gaierror("Name or service not known"),
        ):
            response = client.post(
                "/api/setup/wizard/modify-hosts",
                json={
                    "device_ip": "192.168.1.100",
                    "target_addr": "http://nonexistent.invalid:7777",
                    "include_optional": False,
                },
            )
        assert response.status_code == 400


# ── wizard/restore-config ─────────────────────────────────────────────────────


class TestWizardRestoreConfig:
    """POST /api/setup/wizard/restore-config"""

    def test_successful_restore(self, client):
        mock_result = MagicMock(success=True, error=None)
        mock_config_service = MagicMock()
        mock_config_service.restore_config = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchConfigService",
                return_value=mock_config_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/restore-config",
                json={"device_ip": "192.168.1.100", "backup_path": "/usb/config.bak"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True


# ── wizard/restore-hosts ──────────────────────────────────────────────────────


class TestWizardRestoreHosts:
    """POST /api/setup/wizard/restore-hosts"""

    def test_successful_restore(self, client):
        mock_result = MagicMock(success=True, error=None)
        mock_hosts_service = MagicMock()
        mock_hosts_service.restore_hosts = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchHostsService",
                return_value=mock_hosts_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/restore-hosts",
                json={"device_ip": "192.168.1.100", "backup_path": "/usb/hosts.bak"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True


# ── wizard/list-backups ───────────────────────────────────────────────────────


class TestWizardListBackups:
    """POST /api/setup/wizard/list-backups"""

    def test_lists_config_and_hosts_backups(self, client):
        mock_config_service = MagicMock()
        mock_config_service.list_backups = AsyncMock(return_value=["/usb/cfg1.bak"])
        mock_hosts_service = MagicMock()
        mock_hosts_service.list_backups = AsyncMock(return_value=["/usb/hosts1.bak"])

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchConfigService",
                return_value=mock_config_service,
            ),
            patch(
                "opencloudtouch.setup.wizard_routes.SoundTouchHostsService",
                return_value=mock_hosts_service,
            ),
        ):
            mock_ssh_instance = MagicMock()
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=mock_ssh_instance)
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/list-backups",
                json={"device_ip": "192.168.1.100"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["config_backups"] == ["/usb/cfg1.bak"]
        assert body["hosts_backups"] == ["/usb/hosts1.bak"]


# ── wizard/reboot-device ──────────────────────────────────────────────────────


class TestWizardRebootDevice:
    """POST /api/setup/wizard/reboot-device"""

    def test_successful_reboot(self, client):
        mock_conn = MagicMock(success=True, error=None)
        mock_exec = MagicMock(success=True, output="")
        mock_ssh = MagicMock()
        mock_ssh.connect = AsyncMock(return_value=mock_conn)
        mock_ssh.execute = AsyncMock(return_value=mock_exec)
        mock_ssh.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.wizard_routes.SoundTouchSSHClient",
            return_value=mock_ssh,
        ):
            response = client.post(
                "/api/setup/wizard/reboot-device",
                json={"ip": "192.168.1.100"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_ssh.execute.assert_called_once_with("reboot", timeout=5.0)

    def test_reboot_fails_when_ssh_unavailable(self, client):
        mock_conn = MagicMock(success=False, error="Connection refused")
        mock_ssh = MagicMock()
        mock_ssh.connect = AsyncMock(return_value=mock_conn)
        mock_ssh.close = AsyncMock()

        with patch(
            "opencloudtouch.setup.wizard_routes.SoundTouchSSHClient",
            return_value=mock_ssh,
        ):
            response = client.post(
                "/api/setup/wizard/reboot-device",
                json={"ip": "192.168.1.100"},
            )
        assert response.status_code == 503


# ── wizard/verify-redirect ────────────────────────────────────────────────────


class TestWizardVerifyRedirect:
    """POST /api/setup/wizard/verify-redirect"""

    def test_domain_correctly_redirected(self, client):
        mock_result = MagicMock(
            success=True,
            output="PING bmx.bose.com (192.168.1.50): 56 data bytes",
        )
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.execute = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.socket.gethostbyname",
                return_value="192.168.1.50",
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=mock_ssh_instance)
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/verify-redirect",
                json={
                    "device_ip": "192.168.1.100",
                    "domain": "bmx.bose.com",
                    "expected_ip": "192.168.1.50",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["resolved_ip"] == "192.168.1.50"
        assert body["matches_expected"] is True

    def test_domain_not_redirected_returns_mismatch(self, client):
        mock_result = MagicMock(
            success=True,
            output="PING bmx.bose.com (1.2.3.4): 56 data bytes",
        )
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.execute = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.socket.gethostbyname",
                return_value="192.168.1.50",
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=mock_ssh_instance)
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/verify-redirect",
                json={
                    "device_ip": "192.168.1.100",
                    "domain": "bmx.bose.com",
                    "expected_ip": "192.168.1.50",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["matches_expected"] is False

    def test_unresolvable_domain_returns_failure(self, client):
        mock_result = MagicMock(
            success=False,
            output="ping: bad address 'bmx.bose.com'",
        )
        mock_ssh_instance = MagicMock()
        mock_ssh_instance.execute = AsyncMock(return_value=mock_result)

        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.socket.gethostbyname",
                return_value="192.168.1.50",
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=mock_ssh_instance)
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/verify-redirect",
                json={
                    "device_ip": "192.168.1.100",
                    "domain": "bmx.bose.com",
                    "expected_ip": "192.168.1.50",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False


class TestVerifyRedirectInjectionProtection:
    """Regression tests for REFACT-103: Command injection via domain/expected_ip."""

    def test_domain_with_shell_metacharacters_rejected(self, client):
        """Domain containing shell metacharacters must be rejected by validation."""
        response = client.post(
            "/api/setup/wizard/verify-redirect",
            json={
                "device_ip": "192.168.1.100",
                "domain": "; rm -rf /",
                "expected_ip": "192.168.1.50",
            },
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_domain_with_backticks_rejected(self, client):
        """Domain containing backticks must be rejected."""
        response = client.post(
            "/api/setup/wizard/verify-redirect",
            json={
                "device_ip": "192.168.1.100",
                "domain": "`whoami`",
                "expected_ip": "192.168.1.50",
            },
        )
        assert response.status_code == 422

    def test_expected_ip_with_shell_injection_rejected(self, client):
        """expected_ip containing shell metacharacters must be rejected."""
        response = client.post(
            "/api/setup/wizard/verify-redirect",
            json={
                "device_ip": "192.168.1.100",
                "domain": "bmx.bose.com",
                "expected_ip": "$(cat /etc/passwd)",
            },
        )
        assert response.status_code == 422

    def test_valid_domain_accepted(self, client):
        """Valid domain names pass validation."""
        from opencloudtouch.setup.api_models import VerifyRedirectRequest

        req = VerifyRedirectRequest(
            device_ip="192.168.1.100",
            domain="bmx.bose.com",
            expected_ip="192.168.1.50",
        )
        assert req.domain == "bmx.bose.com"
        assert req.expected_ip == "192.168.1.50"


class TestWizardDetectStrategy:
    """GET /api/setup/wizard/detect-strategy"""

    def test_proxy_available_returns_hosts_only(self, client):
        with patch(
            "opencloudtouch.setup.wizard_routes._check_port_443",
            return_value=True,
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        assert response.status_code == 200
        body = response.json()
        assert body["proxy_available"] is True
        assert body["strategy"] == "hosts_only"

    def test_no_proxy_returns_bmx_and_hosts(self, client):
        with patch(
            "opencloudtouch.setup.wizard_routes._check_port_443",
            return_value=False,
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        assert response.status_code == 200
        body = response.json()
        assert body["proxy_available"] is False
        assert body["strategy"] == "bmx_and_hosts"


class TestWizardComplete:
    """POST /api/setup/wizard/complete"""

    @pytest.fixture
    def client_with_repo(self, wizard_app):
        """Client with mock device_repo on app.state."""
        mock_repo = AsyncMock()
        wizard_app.state.device_repo = mock_repo
        return TestClient(wizard_app, raise_server_exceptions=False), mock_repo

    def test_complete_sets_configured(self, client_with_repo):
        client, mock_repo = client_with_repo
        response = client.post(
            "/api/setup/wizard/complete",
            json={"device_id": "ABC123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["device_id"] == "ABC123"
        assert body["setup_status"] == "configured"

        mock_repo.update_setup_status.assert_awaited_once()
        call_kwargs = mock_repo.update_setup_status.call_args.kwargs
        assert call_kwargs["device_id"] == "ABC123"
        assert call_kwargs["setup_status"] == "configured"
        assert call_kwargs["setup_completed_at"] is not None

    def test_complete_repo_failure_returns_500(self, client_with_repo):
        client, mock_repo = client_with_repo
        mock_repo.update_setup_status.side_effect = Exception("DB write failed")
        response = client.post(
            "/api/setup/wizard/complete",
            json={"device_id": "ABC123"},
        )
        assert response.status_code == 500


# ── _check_port_443 (direct unit test) ────────────────────────────────────────


class TestCheckPort443:
    """Direct tests for _check_port_443 SSL probe function.

    The SSL context intentionally disables certificate verification because
    this function only probes whether port 443 is open, without sending
    sensitive data. These tests verify both the positive and negative paths.
    """

    def test_returns_true_when_ssl_handshake_succeeds(self):
        from opencloudtouch.setup.wizard_routes import _check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_routes.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_routes.ssl.SSLContext") as mock_ctx_cls,
        ):
            mock_sock = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_wrapped = MagicMock()
            mock_ctx.wrap_socket.return_value.__enter__ = MagicMock(
                return_value=mock_wrapped
            )
            mock_ctx.wrap_socket.return_value.__exit__ = MagicMock(return_value=False)

            result = _check_port_443("192.168.1.50")

        assert result is True
        # Verify SSL context was configured for detection-only (no verification)
        assert mock_ctx.check_hostname is False

    def test_returns_false_when_connection_refused(self):
        from opencloudtouch.setup.wizard_routes import _check_port_443

        with patch(
            "opencloudtouch.setup.wizard_routes.socket.create_connection",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            result = _check_port_443("192.168.1.50")

        assert result is False

    def test_returns_false_on_timeout(self):
        from opencloudtouch.setup.wizard_routes import _check_port_443

        with patch(
            "opencloudtouch.setup.wizard_routes.socket.create_connection",
            side_effect=TimeoutError("Connection timed out"),
        ):
            result = _check_port_443("10.0.0.1")

        assert result is False


# ── SSH 503 regression tests (bugfix-001) ──────────────────────────────────────


class TestSSHUnreachableReturns503:
    """Bugfix-001: SSH connection failures must return 503, not 500."""

    def test_backup_returns_503_when_ssh_unreachable(self, client):
        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(
                side_effect=ConnectionError(
                    "SSH connection to 192.168.1.100 failed: Connection refused"
                )
            )
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/backup",
                json={"device_ip": "192.168.1.100"},
            )
        assert response.status_code == 503
        assert "SSH" in response.json()["detail"]

    def test_modify_config_returns_503_when_ssh_unreachable(self, client):
        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(
                side_effect=ConnectionError(
                    "SSH connection to 192.168.1.100 failed: Connection refused"
                )
            )
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-config",
                json={"device_ip": "192.168.1.100", "target_addr": "192.168.1.50"},
            )
        assert response.status_code == 503
        assert "SSH" in response.json()["detail"]

    def test_modify_hosts_returns_503_when_ssh_unreachable(self, client):
        with (
            patch("opencloudtouch.setup.wizard_routes.SoundTouchSSHClient") as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_routes.socket.gethostbyname",
                return_value="192.168.1.50",
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(
                side_effect=ConnectionError(
                    "SSH connection to 192.168.1.100 failed: Connection refused"
                )
            )
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-hosts",
                json={
                    "device_ip": "192.168.1.100",
                    "target_addr": "192.168.1.50",
                    "include_optional": False,
                },
            )
        assert response.status_code == 503
        assert "SSH" in response.json()["detail"]
