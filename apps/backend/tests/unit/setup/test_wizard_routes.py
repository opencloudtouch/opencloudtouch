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

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    """Reset config before each test to prevent cross-test pollution."""
    import os
    from opencloudtouch.core.config import clear_config

    # Save original OCT_PORT if it exists
    original_port = os.environ.get("OCT_PORT")

    # Clear config and remove OCT_PORT before test
    clear_config()
    monkeypatch.delenv("OCT_PORT", raising=False)

    yield

    # Clean up after test
    clear_config()
    # Restore original OCT_PORT if it existed
    if original_port:
        monkeypatch.setenv("OCT_PORT", original_port)
    else:
        monkeypatch.delenv("OCT_PORT", raising=False)


@pytest.fixture
def wizard_app():
    """Minimal FastAPI app with only wizard_router mounted."""
    from opencloudtouch.core.config import clear_config
    from opencloudtouch.core.dependencies import get_wizard_service
    from opencloudtouch.core.exception_handlers import register_exception_handlers
    from opencloudtouch.setup.wizard_routes import wizard_router
    from opencloudtouch.setup.wizard_service import WizardService

    # Ensure clean config state before importing router
    clear_config()

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(wizard_router)
    app.dependency_overrides[get_wizard_service] = lambda: WizardService()
    return app


@pytest.fixture
def client(wizard_app):
    return TestClient(wizard_app, raise_server_exceptions=False)


# ── wizard/server-info — port propagation ─────────────────────────────────────


class TestWizardServerInfoPort:
    """GET /api/setup/wizard/server-info must reflect configured port."""

    def test_custom_port_in_response(self, monkeypatch):
        """OCT_PORT=8080 → default_port=8080 and server_url contains :8080."""
        from opencloudtouch.core.config import clear_config
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from opencloudtouch.core.dependencies import get_wizard_service
        from opencloudtouch.core.exception_handlers import register_exception_handlers
        from opencloudtouch.setup.wizard_routes import wizard_router
        from opencloudtouch.setup.wizard_service import WizardService

        monkeypatch.setenv("OCT_PORT", "8080")
        clear_config()  # Reload config with new port

        # Create app and client AFTER setting port
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(wizard_router)
        app.dependency_overrides[get_wizard_service] = lambda: WizardService()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/setup/wizard/server-info")
        assert response.status_code == 200
        body = response.json()
        assert body["default_port"] == 8080
        assert ":8080" in body["server_url"]

    def test_default_port_in_response(self, monkeypatch):
        """Default config → default_port=7777."""
        from opencloudtouch.core.config import DEFAULT_PORT, clear_config
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from opencloudtouch.core.dependencies import get_wizard_service
        from opencloudtouch.core.exception_handlers import register_exception_handlers
        from opencloudtouch.setup.wizard_routes import wizard_router
        from opencloudtouch.setup.wizard_service import WizardService

        # Explicitly set OCT_PORT to DEFAULT_PORT to override any pollution
        monkeypatch.setenv("OCT_PORT", str(DEFAULT_PORT))
        clear_config()  # Reload config with DEFAULT_PORT

        # Create fresh app and client with clean config
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(wizard_router)
        app.dependency_overrides[get_wizard_service] = lambda: WizardService()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/setup/wizard/server-info")
        assert response.status_code == 200
        body = response.json()
        assert body["default_port"] == DEFAULT_PORT


# ── wizard/check-ports ────────────────────────────────────────────────────────


class TestWizardCheckPorts:
    """POST /api/setup/wizard/check-ports"""

    def test_ssh_accessible(self, client):
        with patch(
            "opencloudtouch.setup.wizard_service.check_ssh_port",
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
            "opencloudtouch.setup.wizard_service.check_ssh_port",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchBackupService",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchBackupService",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchConfigService",
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
        assert body["old_url"] == "https://*.bose.com (4 URLs)"
        assert body["new_url"] == "http://192.168.1.50:7777"

    def test_target_addr_with_explicit_port_propagates(self, client, monkeypatch):
        """target_addr='http://192.168.1.1:8080' → modify_bmx_url called with port=8080."""
        mock_result = MagicMock(
            success=True, error=None, backup_path="/usb/config.bak", diff="..."
        )
        mock_config_service = MagicMock()
        mock_config_service.modify_bmx_url = AsyncMock(return_value=mock_result)

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchConfigService",
                return_value=mock_config_service,
            ),
        ):
            mock_ssh.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ssh.return_value.__aexit__ = AsyncMock(return_value=False)
            response = client.post(
                "/api/setup/wizard/modify-config",
                json={
                    "device_ip": "192.168.1.100",
                    "target_addr": "http://192.168.1.1:8080",
                },
            )
        assert response.status_code == 200
        mock_config_service.modify_bmx_url.assert_called_once()
        call_args = mock_config_service.modify_bmx_url.call_args
        # port passed as keyword arg or second positional arg
        called_port = call_args.kwargs.get(
            "port", call_args.args[1] if len(call_args.args) > 1 else None
        )
        assert called_port == 8080, f"Expected port 8080, got {called_port}"

    def test_target_addr_without_port_uses_config_default(self, monkeypatch):
        """target_addr='http://192.168.1.1' (no port) → uses get_config().port via service."""
        from urllib.parse import urlparse

        from opencloudtouch.core.config import clear_config

        monkeypatch.setenv("OCT_PORT", "9090")
        clear_config()

        try:
            # Test the urlparse logic in modify_config directly
            parsed = urlparse("http://192.168.1.1")
            assert parsed.port is None, "URL without port should parse to None"
            from opencloudtouch.core.config import get_config

            fallback_port = get_config().port
            assert (
                fallback_port == 9090
            ), f"Expected config port 9090, got {fallback_port}"
        finally:
            monkeypatch.delenv("OCT_PORT", raising=False)
            clear_config()

    def test_config_modification_failure(self, client):
        mock_result = MagicMock(success=False, error="File not found")
        mock_config_service = MagicMock()
        mock_config_service.modify_bmx_url = AsyncMock(return_value=mock_result)

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchConfigService",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchHostsService",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchHostsService",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchHostsService",
                return_value=mock_hosts_service,
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.gethostbyname",
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
            "opencloudtouch.setup.wizard_helpers.socket.gethostbyname",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchConfigService",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchHostsService",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchConfigService",
                return_value=mock_config_service,
            ),
            patch(
                "opencloudtouch.setup.wizard_service.SoundTouchHostsService",
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
            "opencloudtouch.setup.wizard_service.SoundTouchSSHClient",
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
            "opencloudtouch.setup.wizard_service.SoundTouchSSHClient",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.gethostbyname",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.gethostbyname",
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.gethostbyname",
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
            "opencloudtouch.setup.wizard_routes.check_port_443",
            return_value=True,
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        assert response.status_code == 200
        body = response.json()
        assert body["proxy_available"] is True
        assert body["strategy"] == "hosts_only"

    def test_no_proxy_returns_bmx_and_hosts(self, client):
        with patch(
            "opencloudtouch.setup.wizard_routes.check_port_443",
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
        from opencloudtouch.core.dependencies import get_wizard_service
        from opencloudtouch.setup.wizard_service import WizardService

        mock_repo = AsyncMock()
        wizard_app.dependency_overrides[get_wizard_service] = lambda: WizardService(
            device_repo=mock_repo
        )
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
    """Direct tests for check_port_443 OCT reverse proxy detection.

    Two-phase detection:
    1. TLS handshake on port 443 (is anything listening?)
    2. HTTPS GET /health — does OCT respond behind the proxy?

    Only returns True when OCT is confirmed behind the proxy.
    A random service on 443 (Portainer, Traefik, etc.) returns False.
    """

    def test_returns_true_when_oct_health_responds(self):
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_helpers.ssl.SSLContext") as mock_ctx_cls,
            patch(
                "opencloudtouch.setup.wizard_helpers.urllib.request.urlopen"
            ) as mock_urlopen,
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

            # Phase 2: OCT /health returns 200 with unique fingerprint
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"status": "healthy", "service": "opencloudtouch", "version": "1.2.7"}'
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            result = check_port_443("192.168.1.50")

        assert result is True
        assert mock_ctx.check_hostname is False

    def test_returns_false_when_port_443_open_but_not_oct(self):
        """Port 443 responds (e.g. Portainer) but /health is not OCT."""
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_helpers.ssl.SSLContext") as mock_ctx_cls,
            patch(
                "opencloudtouch.setup.wizard_helpers.urllib.request.urlopen"
            ) as mock_urlopen,
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

            # Phase 2: Non-OCT service returns 404 or wrong body
            mock_resp = MagicMock()
            mock_resp.status = 404
            mock_resp.read.return_value = b"Not Found"
            # No "opencloudtouch" in body → False
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            result = check_port_443("192.168.1.50")

        assert result is False

    def test_returns_false_when_connection_refused(self):
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with patch(
            "opencloudtouch.setup.wizard_helpers.socket.create_connection",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            result = check_port_443("192.168.1.50")

        assert result is False

    def test_returns_false_on_timeout(self):
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with patch(
            "opencloudtouch.setup.wizard_helpers.socket.create_connection",
            side_effect=TimeoutError("Connection timed out"),
        ):
            result = check_port_443("10.0.0.1")

        assert result is False

    def test_returns_false_when_health_request_fails(self):
        """TLS handshake OK, but HTTP request to /health throws."""
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_helpers.ssl.SSLContext") as mock_ctx_cls,
            patch(
                "opencloudtouch.setup.wizard_helpers.urllib.request.urlopen",
                side_effect=ConnectionResetError("Connection reset"),
            ),
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

            result = check_port_443("192.168.1.50")

        assert result is False


# ── Regression: Issue #184 — False-positive proxy detection ────────────────────


class TestProxyDetectionRegression184:
    """Regression tests for GitHub Issue #184.

    Root cause: check_port_443 only did a TLS handshake. Any service on
    port 443 (Portainer, Traefik, etc.) triggered a false positive,
    causing the wizard to skip config modification. Devices kept factory
    HTTPS URLs → INVALID_SOURCE on preset playback.

    Fix: two-phase detection — TLS handshake + HTTPS GET /health.
    Only a confirmed OCT response enables hosts_only strategy.

    Scenarios:
      1. Real OCT reverse proxy, OCT responds       → hosts_only (safe)
      2. Real proxy, OCT unresponsive (502/timeout)  → bmx_and_hosts (safe fallback)
      3. Random service on 443 (Portainer)           → bmx_and_hosts (was the bug!)
      4. No service on 443 (connection refused)      → bmx_and_hosts
      5. No service on 443 (timeout)                 → bmx_and_hosts
    """

    def test_scenario1_real_oct_proxy_hosts_only(self, client):
        """S1: Real reverse proxy with OCT behind it → hosts_only."""
        with patch(
            "opencloudtouch.setup.wizard_routes.check_port_443",
            return_value=True,  # Phase 1+2 both pass
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        body = response.json()
        assert body["strategy"] == "hosts_only"
        assert body["proxy_available"] is True

    def test_scenario2_broken_proxy_requires_config(self, client):
        """S2: Proxy on 443, but OCT not responding (502/misconfigured) → bmx_and_hosts."""
        with patch(
            "opencloudtouch.setup.wizard_routes.check_port_443",
            return_value=False,  # Phase 2 fails (OCT not behind proxy)
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        body = response.json()
        assert body["strategy"] == "bmx_and_hosts"
        assert body["proxy_available"] is False

    def test_scenario3_portainer_on_443_requires_config(self, client):
        """S3: Random service (Portainer/Traefik) on 443 → bmx_and_hosts.

        THIS WAS THE BUG: old code returned True here, skipping config modification.
        """
        with patch(
            "opencloudtouch.setup.wizard_routes.check_port_443",
            return_value=False,  # Phase 2 fails (/health not OCT)
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        body = response.json()
        assert body["strategy"] == "bmx_and_hosts"
        assert body["proxy_available"] is False

    def test_scenario4_no_proxy_connection_refused_requires_config(self, client):
        """S4: Nothing on port 443 (refused) → bmx_and_hosts."""
        with patch(
            "opencloudtouch.setup.wizard_routes.check_port_443",
            return_value=False,  # Phase 1 fails (connection refused)
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        body = response.json()
        assert body["strategy"] == "bmx_and_hosts"
        assert body["proxy_available"] is False

    def test_scenario5_no_proxy_timeout_requires_config(self, client):
        """S5: Nothing on port 443 (timeout) → bmx_and_hosts."""
        with patch(
            "opencloudtouch.setup.wizard_routes.check_port_443",
            return_value=False,  # Phase 1 fails (timeout)
        ):
            response = client.get("/api/setup/wizard/detect-strategy")
        body = response.json()
        assert body["strategy"] == "bmx_and_hosts"
        assert body["proxy_available"] is False

    # ── End-to-end: verify check_port_443 itself for each scenario ──

    def test_scenario3_e2e_portainer_returns_false(self):
        """S3 E2E: Port 443 open with non-OCT service → check_port_443 returns False."""
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_helpers.ssl.SSLContext") as mock_ctx_cls,
            patch(
                "opencloudtouch.setup.wizard_helpers.urllib.request.urlopen"
            ) as mock_urlopen,
        ):
            # Phase 1: TLS handshake succeeds (Portainer answers)
            mock_sock = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.wrap_socket.return_value.__enter__ = MagicMock()
            mock_ctx.wrap_socket.return_value.__exit__ = MagicMock(return_value=False)

            # Phase 2: Portainer responds with HTML, not OCT health
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b"<html><title>Portainer</title></html>"
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            result = check_port_443("192.168.178.108")

        # Must be False — "ok" not in Portainer HTML
        assert result is False

    def test_scenario2_e2e_proxy_502_returns_false(self):
        """S2 E2E: Proxy on 443, but OCT down (502) → check_port_443 returns False."""
        from urllib.error import HTTPError

        from opencloudtouch.setup.wizard_helpers import check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_helpers.ssl.SSLContext") as mock_ctx_cls,
            patch(
                "opencloudtouch.setup.wizard_helpers.urllib.request.urlopen",
                side_effect=HTTPError(
                    "https://host/health", 502, "Bad Gateway", {}, None
                ),
            ),
        ):
            mock_sock = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.wrap_socket.return_value.__enter__ = MagicMock()
            mock_ctx.wrap_socket.return_value.__exit__ = MagicMock(return_value=False)

            result = check_port_443("192.168.178.108")

        assert result is False

    def test_scenario1_e2e_real_oct_proxy_returns_true(self):
        """S1 E2E: Real OCT proxy on 443, /health responds OK → True."""
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_helpers.ssl.SSLContext") as mock_ctx_cls,
            patch(
                "opencloudtouch.setup.wizard_helpers.urllib.request.urlopen"
            ) as mock_urlopen,
        ):
            mock_sock = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.wrap_socket.return_value.__enter__ = MagicMock()
            mock_ctx.wrap_socket.return_value.__exit__ = MagicMock(return_value=False)

            # OCT /health responds with unique fingerprint
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"status": "healthy", "service": "opencloudtouch", "version": "1.2.7"}'
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            result = check_port_443("192.168.178.108")

        assert result is True

    def test_generic_health_service_with_ok_returns_false(self):
        """Service on 443 returns {"status": "ok"} but no OCT fingerprint → False.

        Regression guard: a generic health check must NOT be mistaken
        for OCT. Only {"service": "opencloudtouch"} matches.
        """
        from opencloudtouch.setup.wizard_helpers import check_port_443

        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.create_connection"
            ) as mock_conn,
            patch("opencloudtouch.setup.wizard_helpers.ssl.SSLContext") as mock_ctx_cls,
            patch(
                "opencloudtouch.setup.wizard_helpers.urllib.request.urlopen"
            ) as mock_urlopen,
        ):
            mock_sock = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx = MagicMock()
            mock_ctx_cls.return_value = mock_ctx
            mock_ctx.wrap_socket.return_value.__enter__ = MagicMock()
            mock_ctx.wrap_socket.return_value.__exit__ = MagicMock(return_value=False)

            # Generic service: has "ok" but no "version" or "healthy"
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"status": "ok"}'
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

            result = check_port_443("192.168.178.108")

        assert result is False


# ── SSH 503 regression tests (bugfix-001) ──────────────────────────────────────


class TestSSHUnreachableReturns503:
    """Bugfix-001: SSH connection failures must return 503, not 500."""

    def test_backup_returns_503_when_ssh_unreachable(self, client):
        with (
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
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
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient"
            ) as mock_ssh,
            patch(
                "opencloudtouch.setup.wizard_helpers.socket.gethostbyname",
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


# ── _snapshot_config_files helper ─────────────────────────────────────────────


class TestSnapshotConfigFiles:
    """Unit tests for _snapshot_config_files audit helper."""

    @pytest.mark.asyncio
    async def test_snapshots_config_files(self):
        from opencloudtouch.setup.wizard_helpers import snapshot_config_files

        mock_ssh = AsyncMock()
        mock_ssh.execute = AsyncMock(
            return_value=MagicMock(success=True, output="<xml>config</xml>")
        )
        mock_repo = AsyncMock()
        mock_repo.add_config_snapshot = AsyncMock()

        await snapshot_config_files(
            ssh=mock_ssh,
            audit_repo=mock_repo,
            device_id="192.168.1.100",
            file_paths=["/opt/Bose/etc/config.xml"],
            trigger="before_modify",
        )

        mock_repo.add_config_snapshot.assert_called_once_with(
            device_id="192.168.1.100",
            file_path="/opt/Bose/etc/config.xml",
            content="<xml>config</xml>",
            trigger="before_modify",
        )

    @pytest.mark.asyncio
    async def test_skips_when_no_audit_repo(self):
        from opencloudtouch.setup.wizard_helpers import snapshot_config_files

        mock_ssh = AsyncMock()
        await snapshot_config_files(
            ssh=mock_ssh,
            audit_repo=None,
            device_id="192.168.1.100",
            file_paths=["/etc/hosts"],
            trigger="test",
        )
        mock_ssh.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_file_when_cat_fails(self):
        from opencloudtouch.setup.wizard_helpers import snapshot_config_files

        mock_ssh = AsyncMock()
        mock_ssh.execute = AsyncMock(return_value=MagicMock(success=False, output=""))
        mock_repo = AsyncMock()

        await snapshot_config_files(
            ssh=mock_ssh,
            audit_repo=mock_repo,
            device_id="DEV1",
            file_paths=["/nonexistent"],
            trigger="test",
        )
        mock_repo.add_config_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        from opencloudtouch.setup.wizard_helpers import snapshot_config_files

        mock_ssh = AsyncMock()
        mock_ssh.execute = AsyncMock(side_effect=RuntimeError("SSH error"))
        mock_repo = AsyncMock()

        await snapshot_config_files(
            ssh=mock_ssh,
            audit_repo=mock_repo,
            device_id="DEV1",
            file_paths=["/etc/hosts"],
            trigger="test",
        )

    @pytest.mark.asyncio
    async def test_multiple_files_snapshot(self):
        from opencloudtouch.setup.wizard_helpers import snapshot_config_files

        mock_ssh = AsyncMock()
        mock_ssh.execute = AsyncMock(
            return_value=MagicMock(success=True, output="content")
        )
        mock_repo = AsyncMock()
        mock_repo.add_config_snapshot = AsyncMock()

        await snapshot_config_files(
            ssh=mock_ssh,
            audit_repo=mock_repo,
            device_id="DEV1",
            file_paths=["/a.xml", "/b.xml", "/c.xml"],
            trigger="before_test",
        )
        assert mock_repo.add_config_snapshot.call_count == 3


# ── wizard/server-info ────────────────────────────────────────────────────────


class TestWizardServerInfo:
    """GET /api/setup/wizard/server-info"""

    def test_returns_server_url(self, monkeypatch):
        from opencloudtouch.core.config import DEFAULT_PORT, clear_config
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from opencloudtouch.core.dependencies import get_wizard_service
        from opencloudtouch.core.exception_handlers import register_exception_handlers
        from opencloudtouch.setup.wizard_routes import wizard_router
        from opencloudtouch.setup.wizard_service import WizardService

        # Ensure clean state with DEFAULT_PORT
        monkeypatch.setenv("OCT_PORT", str(DEFAULT_PORT))
        clear_config()

        # Create fresh app and client
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(wizard_router)
        app.dependency_overrides[get_wizard_service] = lambda: WizardService()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/setup/wizard/server-info")
        assert response.status_code == 200
        body = response.json()
        assert "server_url" in body
        assert "server_ip" in body
        assert body["default_port"] == DEFAULT_PORT

    def test_server_ip_uses_machine_hostname_not_request(self, client):
        """Bug #200: Server IP must reflect actual LAN IP, not request hostname."""
        with patch("opencloudtouch.setup.wizard_routes.socket") as mock_socket:
            mock_socket.gethostname.return_value = "myserver"
            mock_socket.gethostbyname.return_value = "192.168.1.50"
            mock_socket.gaierror = OSError

            response = client.get("/api/setup/wizard/server-info")

        assert response.status_code == 200
        body = response.json()
        assert body["server_ip"] == "192.168.1.50"
        # Port depends on current config state - check it matches the response
        assert body["server_url"] == f"http://192.168.1.50:{body['default_port']}"
        mock_socket.gethostbyname.assert_called_with("myserver")

    def test_server_ip_fallback_on_hostname_failure(self, client):
        """Bug #200: When gethostname resolution fails, fall back to request hostname."""
        with patch("opencloudtouch.setup.wizard_routes.socket") as mock_socket:
            mock_socket.gethostname.return_value = "unresolvable-host"
            mock_socket.gaierror = OSError
            mock_socket.gethostbyname.side_effect = [OSError("no host"), "10.0.0.1"]

            response = client.get("/api/setup/wizard/server-info")

        assert response.status_code == 200
        body = response.json()
        assert body["server_ip"] == "10.0.0.1"

    def test_server_ip_double_fallback_returns_raw_hostname(self, client):
        """Bug #200: When BOTH gethostbyname calls fail, raw hostname is returned."""
        with patch("opencloudtouch.setup.wizard_routes.socket") as mock_socket:
            mock_socket.gethostname.return_value = "broken-host"
            mock_socket.gaierror = OSError
            mock_socket.gethostbyname.side_effect = OSError("no resolution")
            mock_socket.AF_INET = socket.AF_INET
            mock_socket.SOCK_DGRAM = socket.SOCK_DGRAM

            response = client.get(
                "/api/setup/wizard/server-info",
                headers={"host": "my-oct-server:7777"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["server_ip"] == "my-oct-server"

    def test_server_ip_loopback_triggers_udp_fallback(self, client):
        """Bug #200: Loopback IP from Docker triggers UDP socket fallback."""
        mock_udp_socket = MagicMock()
        mock_udp_socket.getsockname.return_value = ("192.168.1.99", 0)

        with patch("opencloudtouch.setup.wizard_routes.socket") as mock_socket:
            mock_socket.gethostname.return_value = "container-abc123"
            mock_socket.gethostbyname.return_value = "127.0.0.1"
            mock_socket.gaierror = OSError
            mock_socket.AF_INET = socket.AF_INET
            mock_socket.SOCK_DGRAM = socket.SOCK_DGRAM
            mock_socket.socket.return_value = mock_udp_socket

            response = client.get("/api/setup/wizard/server-info")

        assert response.status_code == 200
        body = response.json()
        assert body["server_ip"] == "192.168.1.99"

    def test_udp_fallback_oserror_uses_request_hostname(self, client):
        """Bug #200: When UDP trick raises OSError, fall back to request hostname."""
        mock_udp_socket = MagicMock()
        mock_udp_socket.connect.side_effect = OSError("network unreachable")

        with patch("opencloudtouch.setup.wizard_routes.socket") as mock_socket:
            mock_socket.gethostname.return_value = "container-id"
            mock_socket.gethostbyname.return_value = "127.0.0.1"
            mock_socket.gaierror = OSError
            mock_socket.AF_INET = socket.AF_INET
            mock_socket.SOCK_DGRAM = socket.SOCK_DGRAM
            mock_socket.socket.return_value = mock_udp_socket

            response = client.get(
                "/api/setup/wizard/server-info",
                headers={"host": "my-server:7777"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["server_ip"] == "my-server"

    def test_udp_fallback_oserror_keeps_loopback_when_hostname_also_loopback(
        self, client
    ):
        """Bug #200: When UDP trick fails and hostname is also loopback, keep 127.x."""
        mock_udp_socket = MagicMock()
        mock_udp_socket.connect.side_effect = OSError("network unreachable")

        with patch("opencloudtouch.setup.wizard_routes.socket") as mock_socket:
            mock_socket.gethostname.return_value = "container-id"
            mock_socket.gethostbyname.return_value = "127.0.0.1"
            mock_socket.gaierror = OSError
            mock_socket.AF_INET = socket.AF_INET
            mock_socket.SOCK_DGRAM = socket.SOCK_DGRAM
            mock_socket.socket.return_value = mock_udp_socket

            response = client.get(
                "/api/setup/wizard/server-info",
                headers={"host": "127.0.0.2:7777"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["server_ip"] == "127.0.0.1"


# ── wizard/finalize ──────────────────────────────────────────────────────────


class TestWizardFinalize:
    """POST /api/setup/wizard/finalize"""

    def test_finalize_success(self, client):
        with patch.object(
            __import__(
                "opencloudtouch.setup.wizard_service", fromlist=["WizardService"]
            ).WizardService,
            "finalize_device",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "uuid": "1234567",
                "had_uuid": False,
                "uuid_was_collision": False,
                "sources_written": True,
                "sources_backup_path": "/tmp/backup",
                "system_config_written": True,
                "message": "Finalized",
            },
        ):
            response = client.post(
                "/api/setup/wizard/finalize",
                json={"device_ip": "192.168.1.100", "device_id": "AABBCCDDEEFF"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert body["uuid"] == "1234567"
            assert body["sources_written"] is True

    def test_finalize_failure(self, client):
        with patch.object(
            __import__(
                "opencloudtouch.setup.wizard_service", fromlist=["WizardService"]
            ).WizardService,
            "finalize_device",
            new_callable=AsyncMock,
            return_value={"success": False, "error": "SSH connection failed"},
        ):
            response = client.post(
                "/api/setup/wizard/finalize",
                json={"device_ip": "192.168.1.100", "device_id": "AABBCCDDEEFF"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is False
            assert "SSH" in body["error"]


# ── wizard/verify-setup ──────────────────────────────────────────────────────


class TestWizardVerifySetup:
    """POST /api/setup/wizard/verify-setup"""

    def test_verify_all_passed(self, client):
        with patch.object(
            __import__(
                "opencloudtouch.setup.wizard_service", fromlist=["WizardService"]
            ).WizardService,
            "verify_setup",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "checks": [
                    {
                        "name": "uuid_present",
                        "passed": True,
                        "message": "OK",
                        "details": {},
                    },
                ],
                "passed_count": 1,
                "failed_count": 0,
                "message": "1/1 checks passed",
            },
        ):
            response = client.post(
                "/api/setup/wizard/verify-setup",
                json={
                    "device_ip": "192.168.1.100",
                    "device_id": "AABBCCDDEEFF",
                    "expected_oct_ip": "192.168.1.50",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert body["passed_count"] == 1
            assert body["failed_count"] == 0

    def test_verify_with_failures(self, client):
        with patch.object(
            __import__(
                "opencloudtouch.setup.wizard_service", fromlist=["WizardService"]
            ).WizardService,
            "verify_setup",
            new_callable=AsyncMock,
            return_value={
                "success": False,
                "checks": [
                    {
                        "name": "uuid_present",
                        "passed": True,
                        "message": "OK",
                        "details": {},
                    },
                    {
                        "name": "hosts_oct_block",
                        "passed": False,
                        "message": "Missing",
                        "details": {},
                    },
                ],
                "passed_count": 1,
                "failed_count": 1,
                "message": "1/2 checks passed (1 failed)",
            },
        ):
            response = client.post(
                "/api/setup/wizard/verify-setup",
                json={
                    "device_ip": "192.168.1.100",
                    "device_id": "AABBCCDDEEFF",
                    "expected_oct_ip": "192.168.1.50",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is False
            assert body["failed_count"] == 1


# ── validate-hostname — DNS resolution ────────────────────────────────────────


class TestValidateHostname:
    """POST /api/setup/wizard/validate-hostname"""

    def test_resolvable_hostname_matching_ip(self, client, respx_mock):
        """Hostname resolves to expected IP → resolvable=True, matches=True."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))
            ]
            # Mock OCT health check
            respx_mock.get("http://myserver:7777/health").mock(
                return_value=httpx.Response(
                    200, json={"service": "opencloudtouch", "status": "running"}
                )
            )
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "myserver",
                    "port": 7777,
                    "expected_ip": "192.168.1.100",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is True
        assert body["resolved_ip"] == "192.168.1.100"
        assert body["matches_expected"] is True
        assert body["oct_reachable"] is True
        assert body["error"] is None
        assert body["oct_error"] is None

    def test_resolvable_hostname_mismatching_ip(self, client, respx_mock):
        """Hostname resolves to different IP → matches=False."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))
            ]
            respx_mock.get("http://myserver:7777/health").mock(
                return_value=httpx.Response(
                    200, json={"service": "opencloudtouch", "status": "running"}
                )
            )
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "myserver",
                    "port": 7777,
                    "expected_ip": "192.168.1.100",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is True
        assert body["resolved_ip"] == "10.0.0.5"
        assert body["matches_expected"] is False
        assert body["oct_reachable"] is True

    def test_resolvable_hostname_no_expected_ip(self, client, respx_mock):
        """Hostname resolves, no expected_ip → matches=null."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))
            ]
            respx_mock.get("http://myserver:7777/health").mock(
                return_value=httpx.Response(
                    200, json={"service": "opencloudtouch", "status": "running"}
                )
            )
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={"hostname": "myserver", "port": 7777, "expected_ip": None},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is True
        assert body["matches_expected"] is None
        assert body["oct_reachable"] is True

    def test_unresolvable_hostname(self, client):
        """DNS lookup fails → resolvable=False with user-friendly error."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            # errno -2 = EAI_NONAME (Name or service not known)
            mock_dns.side_effect = socket.gaierror(-2, "Name or service not known")
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "nonexistent.invalid",
                    "port": 7777,
                    "expected_ip": None,
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is False
        assert body["resolved_ip"] is None
        assert body["oct_reachable"] is False
        # User-friendly message should NOT contain technical errno
        assert "nonexistent.invalid" in body["error"]
        assert "could not be resolved" in body["error"].lower()
        assert "[Errno" not in body["error"]  # No technical error code

    def test_dns_temporary_failure(self, client):
        """DNS temporary failure → user-friendly error."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            # errno -3 = EAI_AGAIN (Temporary failure in name resolution)
            mock_dns.side_effect = socket.gaierror(-3, "Temporary failure")
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={"hostname": "example.com", "port": 7777, "expected_ip": None},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is False
        assert body["oct_reachable"] is False
        assert "temporarily unavailable" in body["error"].lower()
        assert "[Errno" not in body["error"]

    def test_dns_no_address(self, client):
        """DNS returns no address → user-friendly error."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            # errno -5 = EAI_NODATA (No address associated with hostname)
            mock_dns.side_effect = socket.gaierror(-5, "No address associated")
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={"hostname": "noaddr.test", "port": 7777, "expected_ip": None},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is False
        assert body["oct_reachable"] is False
        assert "no ip address found" in body["error"].lower()
        assert "[Errno" not in body["error"]

    def test_invalid_hostname_rejected(self, client):
        """Invalid hostname (shell metacharacters) → 422."""
        response = client.post(
            "/api/setup/wizard/validate-hostname",
            json={"hostname": "$(whoami)", "expected_ip": None},
        )
        assert response.status_code == 422

    def test_empty_dns_result(self, client):
        """DNS returns empty list → resolvable=False."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = []
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "emptyresult.local",
                    "port": 7777,
                    "expected_ip": None,
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is False
        assert body["resolved_ip"] is None
        assert body["oct_reachable"] is False
        assert "no results" in body["error"].lower()

    def test_unexpected_exception(self, client):
        """Unexpected non-socket exception → resolvable=False with user-friendly error."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.side_effect = RuntimeError("Unexpected failure")
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={"hostname": "crash.local", "port": 7777, "expected_ip": None},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is False
        assert body["resolved_ip"] is None
        assert body["oct_reachable"] is False
        # User-friendly message, no technical details leaked
        assert "could not validate" in body["error"].lower()
        assert "crash.local" in body["error"]
        assert "RuntimeError" not in body["error"]  # No exception class name
        assert "Unexpected failure" not in body["error"]  # No internal error details

    def test_oct_not_reachable_connection_refused(self, client, respx_mock):
        """DNS OK but OCT not reachable (connection refused) → oct_reachable=False."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))
            ]
            # Mock connection refused
            respx_mock.get("http://myserver:7777/health").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "myserver",
                    "port": 7777,
                    "expected_ip": "192.168.1.100",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is True
        assert body["resolved_ip"] == "192.168.1.100"
        assert body["oct_reachable"] is False
        assert "connection refused" in body["oct_error"].lower()

    def test_oct_not_reachable_timeout(self, client, respx_mock):
        """DNS OK but OCT times out → oct_reachable=False."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))
            ]
            # Mock timeout
            respx_mock.get("http://myserver:7777/health").mock(
                side_effect=httpx.TimeoutException("Connection timeout")
            )
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "myserver",
                    "port": 7777,
                    "expected_ip": "192.168.1.100",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is True
        assert body["oct_reachable"] is False
        assert "timeout" in body["oct_error"].lower()

    def test_oct_wrong_service(self, client, respx_mock):
        """DNS OK but response is not OCT → oct_reachable=False."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))
            ]
            # Mock different service
            respx_mock.get("http://myserver:7777/health").mock(
                return_value=httpx.Response(
                    200, json={"service": "nginx", "status": "running"}
                )
            )
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "myserver",
                    "port": 7777,
                    "expected_ip": "192.168.1.100",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is True
        assert body["oct_reachable"] is False
        assert "not opencloudtouch" in body["oct_error"].lower()

    def test_oct_http_error(self, client, respx_mock):
        """DNS OK but HTTP 404 → oct_reachable=False."""
        with patch("opencloudtouch.setup.wizard_routes.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))
            ]
            # Mock HTTP 404
            respx_mock.get("http://myserver:7777/health").mock(
                return_value=httpx.Response(404, text="Not Found")
            )
            response = client.post(
                "/api/setup/wizard/validate-hostname",
                json={
                    "hostname": "myserver",
                    "port": 7777,
                    "expected_ip": "192.168.1.100",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["resolvable"] is True
        assert body["oct_reachable"] is False
        assert "404" in body["oct_error"]
