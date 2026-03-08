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

    def test_both_ports_accessible(self, client):
        with (
            patch(
                "opencloudtouch.setup.wizard_routes.check_ssh_port",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "opencloudtouch.setup.wizard_routes.check_telnet_port",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            response = client.post(
                "/api/setup/wizard/check-ports",
                json={"device_ip": "192.168.1.100", "timeout": 3},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["has_ssh"] is True
        assert body["has_telnet"] is True

    def test_only_ssh_accessible(self, client):
        with (
            patch(
                "opencloudtouch.setup.wizard_routes.check_ssh_port",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "opencloudtouch.setup.wizard_routes.check_telnet_port",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            response = client.post(
                "/api/setup/wizard/check-ports",
                json={"device_ip": "192.168.1.100", "timeout": 3},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["has_ssh"] is True
        assert body["has_telnet"] is False

    def test_no_ports_returns_failure(self, client):
        with (
            patch(
                "opencloudtouch.setup.wizard_routes.check_ssh_port",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "opencloudtouch.setup.wizard_routes.check_telnet_port",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            response = client.post(
                "/api/setup/wizard/check-ports",
                json={"device_ip": "192.168.1.100", "timeout": 3},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["has_ssh"] is False
        assert body["has_telnet"] is False


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

    def test_config_modification_exception_returns_500(self, client):
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
        assert response.status_code == 500


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
