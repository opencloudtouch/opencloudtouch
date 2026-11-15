"""Security validation tests for Issues #1-#6.

Covers:
- Private-IP whitelist for device_ip (WizardDeviceRequest)
- Private-IP whitelist for oct_host (TelnetConfigureRequest)
- Localhost/loopback block for device_ip (SSRF prevention)
- Sanitized error messages (no raw exception text in HTTP responses)
- Device lock (concurrent requests → 409 Conflict)
- Specific HTTP status codes (503/504 for connection/timeout errors)
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from opencloudtouch.setup.api_models import (
    PortCheckRequest,
    TelnetConfigureRequest,
    TelnetVerifyRequest,
    WizardDeviceRequest,
)


# ============================================================================
# #1 — oct_host Whitelist (Private IPs only)
# ============================================================================


class TestOctHostWhitelist:
    """TelnetConfigureRequest.oct_host must be private IP, localhost, or .local."""

    @pytest.mark.parametrize(
        "host",
        [
            "192.168.1.50",
            "10.0.0.1",
            "172.16.0.1",
            "172.31.255.255",
            "fd00::1",
            "localhost",
            "127.0.0.1",
            "::1",
            "myserver.local",
            "oct.local",
        ],
    )
    def test_private_ip_and_local_hostnames_accepted(self, host):
        req = TelnetConfigureRequest(
            device_ip="192.168.1.100", oct_host=host, port=7777
        )
        assert req.oct_host == host

    @pytest.mark.parametrize(
        "host",
        [
            "8.8.8.8",
            "1.1.1.1",
            "142.250.80.46",
            "evil.com",
            "attacker.io",
            "bose.com",
            "myserver.example.com",
        ],
    )
    def test_public_ip_and_external_hostname_rejected(self, host):
        with pytest.raises(ValidationError) as exc_info:
            TelnetConfigureRequest(
                device_ip="192.168.1.100", oct_host=host, port=7777
            )
        error_text = str(exc_info.value)
        assert "private" in error_text.lower() or "local" in error_text.lower()

    def test_empty_oct_host_rejected(self):
        with pytest.raises(ValidationError):
            TelnetConfigureRequest(
                device_ip="192.168.1.100", oct_host="", port=7777
            )

    def test_shell_injection_rejected(self):
        with pytest.raises(ValidationError):
            TelnetConfigureRequest(
                device_ip="192.168.1.100", oct_host="; rm -rf /", port=7777
            )


# ============================================================================
# #2 — device_ip Whitelist (Private IPs only + Block localhost)
# ============================================================================


class TestDeviceIpWhitelist:
    """WizardDeviceRequest.device_ip must be private, non-loopback."""

    @pytest.mark.parametrize(
        "ip",
        [
            "192.168.1.100",
            "192.168.0.1",
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "fd00::1",
        ],
    )
    def test_private_ip_accepted(self, ip):
        req = PortCheckRequest(device_ip=ip)
        assert req.device_ip == ip or req.device_ip == str(
            __import__("ipaddress").ip_address(ip)
        )

    @pytest.mark.parametrize(
        "ip,reason",
        [
            ("127.0.0.1", "loopback IPv4"),
            ("::1", "loopback IPv6"),
            ("0.0.0.0", "unspecified"),
        ],
    )
    def test_loopback_blocked(self, ip, reason):
        with pytest.raises(ValidationError) as exc_info:
            PortCheckRequest(device_ip=ip)
        assert "loopback" in str(exc_info.value).lower() or "not allowed" in str(
            exc_info.value
        ).lower()

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",
            "1.1.1.1",
            "142.250.80.46",
            "169.254.169.254",
            "172.32.0.1",
        ],
    )
    def test_public_ip_rejected(self, ip):
        with pytest.raises(ValidationError) as exc_info:
            PortCheckRequest(device_ip=ip)
        assert "private" in str(exc_info.value).lower()

    def test_hostname_rejected(self):
        with pytest.raises(ValidationError):
            PortCheckRequest(device_ip="evil.com")


# ============================================================================
# #3 — Sanitized Error Messages
# ============================================================================


@pytest.fixture
def wizard_app():
    """Minimal FastAPI app with wizard_router and mocked WizardService."""
    from opencloudtouch.core.config import clear_config
    from opencloudtouch.core.dependencies import get_wizard_service
    from opencloudtouch.core.exception_handlers import register_exception_handlers
    from opencloudtouch.setup.wizard_routes import wizard_router
    from opencloudtouch.setup.wizard_service import WizardService

    clear_config()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(wizard_router)
    app.dependency_overrides[get_wizard_service] = lambda: WizardService()
    return app


@pytest.fixture
def client(wizard_app):
    return TestClient(wizard_app, raise_server_exceptions=False)


class TestSanitizedErrorMessages:
    """Error responses must NOT leak raw exception text."""

    def test_telnet_configure_generic_error_sanitized(self, client):
        """Generic Exception must not leak internal details."""
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.configure_telnet_urls",
            new_callable=AsyncMock,
            side_effect=Exception("INTERNAL: /opt/secret/path at line 42"),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-configure",
                json={
                    "device_ip": "192.168.1.100",
                    "oct_host": "192.168.1.50",
                    "port": 7777,
                },
            )
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "/opt/secret/path" not in detail
        assert "line 42" not in detail
        assert "Check server logs" in detail

    def test_telnet_verify_generic_error_sanitized(self, client):
        """Generic Exception must not leak internal details."""
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.verify_telnet_config",
            new_callable=AsyncMock,
            side_effect=Exception("INTERNAL: password=hunter2"),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-verify",
                json={"device_ip": "192.168.1.100"},
            )
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "hunter2" not in detail
        assert "Check server logs" in detail


# ============================================================================
# #5 — Concurrent Device Lock (409 Conflict)
# ============================================================================


class TestDeviceLock:
    """Concurrent Telnet operations on same device must return 409."""

    def test_concurrent_configure_returns_409(self, client):
        """Second request for same device_ip gets 409 Conflict."""
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.configure_telnet_urls",
            new_callable=AsyncMock,
            side_effect=RuntimeError(
                "Another Telnet operation is already in progress for 192.168.1.100"
            ),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-configure",
                json={
                    "device_ip": "192.168.1.100",
                    "oct_host": "192.168.1.50",
                    "port": 7777,
                },
            )
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]

    def test_concurrent_verify_returns_409(self, client):
        """Second request for same device_ip gets 409 Conflict."""
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.verify_telnet_config",
            new_callable=AsyncMock,
            side_effect=RuntimeError(
                "Another Telnet operation is already in progress for 192.168.1.100"
            ),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-verify",
                json={"device_ip": "192.168.1.100"},
            )
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]


# ============================================================================
# #6 — Specific HTTP Status Codes (503 / 504)
# ============================================================================


class TestSpecificHttpStatusCodes:
    """ConnectionRefusedError → 503, TimeoutError → 504."""

    def test_connection_refused_returns_503(self, client):
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.configure_telnet_urls",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-configure",
                json={
                    "device_ip": "192.168.1.100",
                    "oct_host": "192.168.1.50",
                    "port": 7777,
                },
            )
        assert resp.status_code == 503
        assert "not reachable" in resp.json()["detail"]

    def test_timeout_returns_504(self, client):
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.configure_telnet_urls",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-configure",
                json={
                    "device_ip": "192.168.1.100",
                    "oct_host": "192.168.1.50",
                    "port": 7777,
                },
            )
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"]

    def test_verify_connection_refused_returns_503(self, client):
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.verify_telnet_config",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError(),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-verify",
                json={"device_ip": "192.168.1.100"},
            )
        assert resp.status_code == 503

    def test_verify_timeout_returns_504(self, client):
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.verify_telnet_config",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-verify",
                json={"device_ip": "192.168.1.100"},
            )
        assert resp.status_code == 504

    def test_value_error_returns_400(self, client):
        with patch(
            "opencloudtouch.setup.wizard_service.WizardService.configure_telnet_urls",
            new_callable=AsyncMock,
            side_effect=ValueError("bad param"),
        ):
            resp = client.post(
                "/api/setup/wizard/telnet-configure",
                json={
                    "device_ip": "192.168.1.100",
                    "oct_host": "192.168.1.50",
                    "port": 7777,
                },
            )
        assert resp.status_code == 400
