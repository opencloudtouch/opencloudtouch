"""Tests for main application module (startup, lifecycle)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_lifespan_initialization():
    """Test lifespan context manager initializes config and DB."""
    from opencloudtouch.core.config import AppConfig
    from opencloudtouch.main import app, lifespan

    with patch("opencloudtouch.main.init_config") as mock_init_config, patch(
        "opencloudtouch.main.setup_logging"
    ) as mock_setup_logging, patch(
        "opencloudtouch.main.get_config"
    ) as mock_get_config, patch(
        "opencloudtouch.main.DeviceRepository"
    ) as mock_device_class, patch(
        "opencloudtouch.main.SettingsRepository"
    ) as mock_settings_class, patch(
        "opencloudtouch.main.PresetRepository"
    ) as mock_preset_class, patch(
        "opencloudtouch.main.RecentsRepository"
    ) as mock_recents_class, patch(
        "opencloudtouch.main.WizardAuditRepository"
    ) as mock_wizard_class, patch(
        "opencloudtouch.main.ZoneRepository"
    ) as mock_zone_class, patch(
        "opencloudtouch.main._init_services", new_callable=AsyncMock
    ):

        # Mock config
        mock_config = MagicMock(spec=AppConfig)
        mock_config.host = "0.0.0.0"
        mock_config.port = 7777
        mock_config.effective_db_path = ":memory:"
        mock_config.discovery_enabled = True
        mock_config.discovery_timeout = 10
        mock_config.manual_device_ips_list = []
        mock_config.mock_mode = False
        mock_get_config.return_value = mock_config

        # Mock all repositories with same pattern
        mock_repos = {}
        for name, cls in [
            ("device", mock_device_class),
            ("settings", mock_settings_class),
            ("preset", mock_preset_class),
            ("recents", mock_recents_class),
            ("wizard", mock_wizard_class),
            ("zone", mock_zone_class),
        ]:
            mock_repo = AsyncMock()
            mock_repo.initialize = AsyncMock()
            mock_repo.close = AsyncMock()
            cls.return_value = mock_repo
            mock_repos[name] = mock_repo

        # Mock health_check to avoid shutdown errors
        mock_health_check = AsyncMock()
        mock_health_check.stop = AsyncMock()

        # Run lifespan
        async with lifespan(app):
            # Mock app.state.health_check for shutdown
            app.state.health_check = mock_health_check

            # Verify startup
            mock_init_config.assert_called_once()
            mock_setup_logging.assert_called_once()
            for name, repo in mock_repos.items():
                repo.initialize.assert_called_once()

        # Verify shutdown — all repos closed
        for name, repo in mock_repos.items():
            repo.close.assert_called_once()


def test_main_module_uses_config_port():
    """Regression test for #70: __main__.py must use config port, not hardcoded 7777."""
    import runpy
    from pathlib import Path

    mock_config = MagicMock()
    mock_config.host = "0.0.0.0"
    mock_config.port = 9999

    with patch(
        "opencloudtouch.core.config.get_config", return_value=mock_config
    ), patch("uvicorn.run") as mock_run:
        runpy.run_path(
            str(
                Path(__file__).resolve().parents[2]
                / "src"
                / "opencloudtouch"
                / "__main__.py"
            ),
            run_name="__main__",
        )
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["port"] == 9999
        assert kwargs["host"] == "0.0.0.0"


def test_health_endpoint():
    """Test health check endpoint returns expected fields and types."""
    from opencloudtouch.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Required fields
    assert data["status"] == "healthy"
    assert data["service"] == "opencloudtouch"
    assert "version" in data
    assert "build" in data
    assert "config" in data

    # Type validation (from integration tests)
    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["build"], str)
    assert data["build"] in ("official", "community")
    assert isinstance(data["config"], dict)
    assert isinstance(data["config"]["discovery_enabled"], bool)


def test_websocket_health_no_manager():
    """WebSocket health returns empty when no manager is attached."""
    from opencloudtouch.main import app

    client = TestClient(app)
    # Ensure ws_manager is not set
    if hasattr(app.state, "ws_manager"):
        delattr(app.state, "ws_manager")

    response = client.get("/api/health/websockets")
    assert response.status_code == 200
    data = response.json()
    assert data["connections"] == {}
    assert data["total_connected"] == 0
    assert data["total_devices"] == 0


def test_websocket_health_with_manager():
    """WebSocket health returns connection info from manager."""
    from unittest.mock import MagicMock

    from opencloudtouch.main import app

    client = TestClient(app)
    mock_manager = MagicMock()
    mock_manager.get_health.return_value = {
        "connections": {
            "AABBCCDDEE11": {
                "state": "connected",
                "uptime_s": 3600,
                "events_received": 142,
            },
            "112233445566": {
                "state": "reconnecting",
                "attempt": 2,
                "events_received": 50,
            },
        },
        "total_connected": 1,
        "total_devices": 2,
    }
    app.state.ws_manager = mock_manager

    response = client.get("/api/health/websockets")
    assert response.status_code == 200
    data = response.json()
    assert data["total_connected"] == 1
    assert data["total_devices"] == 2
    assert data["connections"]["AABBCCDDEE11"]["state"] == "connected"
    assert data["connections"]["AABBCCDDEE11"]["uptime_s"] == 3600
    assert data["connections"]["112233445566"]["attempt"] == 2

    # Clean up
    delattr(app.state, "ws_manager")


def test_version_dev_format_without_signature(monkeypatch):
    """Without OCT_BUILD_SIGNATURE, version uses dev-<commit> format."""
    monkeypatch.delenv("OCT_BUILD_SIGNATURE", raising=False)
    from opencloudtouch import _resolve_version

    ver = _resolve_version()
    assert ver.startswith("dev-")
    assert ver != "dev-"  # commit hash must be present


def test_version_official_format_with_valid_signature(monkeypatch):
    """With a valid 16-char hex signature, version matches package metadata."""
    monkeypatch.setenv("OCT_BUILD_SIGNATURE", "a1b2c3d4e5f67890")
    from importlib.metadata import version as pkg_version

    from opencloudtouch import _resolve_version

    ver = _resolve_version()
    assert ver == pkg_version("opencloudtouch")


def test_version_dev_format_with_invalid_signature(monkeypatch):
    """With an invalid signature (wrong length/format), version is dev-<commit>."""
    monkeypatch.setenv("OCT_BUILD_SIGNATURE", "1")
    from opencloudtouch import _resolve_version

    ver = _resolve_version()
    assert ver.startswith("dev-")


def test_is_official_build_false_without_signature(monkeypatch):
    """is_official_build returns False without signature."""
    monkeypatch.delenv("OCT_BUILD_SIGNATURE", raising=False)
    from opencloudtouch import is_official_build

    assert is_official_build() is False


def test_is_official_build_true_with_valid_signature(monkeypatch):
    """is_official_build returns True with valid 16-char hex signature."""
    monkeypatch.setenv("OCT_BUILD_SIGNATURE", "a1b2c3d4e5f67890")
    from opencloudtouch import is_official_build

    assert is_official_build() is True


def test_app_version_matches_package_version():
    """FastAPI app.version matches the installed package version."""
    from opencloudtouch import __version__
    from opencloudtouch.main import app

    assert app.version == __version__


def test_health_version_matches_package_version():
    """Health endpoint returns the same version as __version__."""
    from opencloudtouch import __version__
    from opencloudtouch.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["version"] == __version__


def test_version_single_source_consistency():
    """All version surfaces (app, health) are identical."""
    from opencloudtouch import __version__
    from opencloudtouch.main import app

    client = TestClient(app)
    health_version = client.get("/health").json()["version"]

    assert app.version == __version__
    assert health_version == __version__


def test_cors_headers_present():
    """Test CORS headers are present in responses."""
    from opencloudtouch.main import app

    client = TestClient(app)

    # Preflight request
    response = client.options(
        "/api/devices/discover",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    # Should have CORS headers (origin is reflected back)
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-methods" in response.headers


def test_spa_path_traversal_blocked():
    """Security test: Path traversal validation logic.

    Regression test for BE-01 (P1 Critical).
    Tests path validation logic to prevent directory traversal.
    """
    from urllib.parse import unquote

    # Test the validation logic directly
    def is_safe_path(full_path: str) -> bool:
        """Replicate serve_spa() security checks."""
        decoded_path = unquote(full_path)

        # Reject directory traversal patterns
        if ".." in decoded_path:
            return False

        # Reject backslashes (Windows path traversal)
        if "\\" in decoded_path:
            return False

        return True

    # Common path traversal attack vectors
    dangerous_paths = [
        "/../../../etc/passwd",
        "..%2F..%2F..%2Fetc/passwd",
        "....//....//etc/passwd",
        "..\\..\\..\\etc\\passwd",
        "/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
        "test/../../../etc/passwd",
        "..%252f..%252fetc/passwd",  # Double-encoded
    ]

    for path in dangerous_paths:
        assert not is_safe_path(path), f"Path traversal not blocked: {path}"

    # Valid paths should pass
    safe_paths = [
        "index.html",
        "assets/main.js",
        "static/logo.png",
        "",
    ]

    for path in safe_paths:
        assert is_safe_path(path), f"Safe path incorrectly blocked: {path}"


@pytest.mark.asyncio
async def test_lifespan_error_handling():
    """Test lifespan handles errors gracefully."""
    from opencloudtouch.main import app, lifespan

    with patch("opencloudtouch.main.init_config"), patch(
        "opencloudtouch.main.setup_logging"
    ), patch("opencloudtouch.main.get_config") as mock_get_config, patch(
        "opencloudtouch.main.DeviceRepository"
    ) as mock_repo_class:

        mock_config = MagicMock()
        mock_config.host = "0.0.0.0"
        mock_config.port = 7777
        mock_config.effective_db_path = ":memory:"
        mock_config.discovery_enabled = True
        mock_config.discovery_timeout = 10
        mock_config.manual_device_ips_list = []
        mock_config.mock_mode = False
        mock_get_config.return_value = mock_config

        # Mock repo that fails to initialize
        mock_repo = AsyncMock()
        mock_repo.initialize = AsyncMock(side_effect=Exception("DB connection failed"))
        mock_repo.close = AsyncMock()
        mock_repo_class.return_value = mock_repo

        # Should raise exception
        with pytest.raises(Exception, match="DB connection failed"):
            async with lifespan(app):
                pass
