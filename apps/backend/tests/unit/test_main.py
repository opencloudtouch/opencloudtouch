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


@pytest.fixture
def mock_init_services_deps():
    """Patch every class/function _init_services constructs or calls.

    Lets tests call _init_services() directly (instead of mocking it away
    like test_lifespan_initialization does) to exercise its internal
    branching logic, without any of it touching real repos/services.
    """
    patches = {
        "recents": patch("opencloudtouch.main.RecentsService"),
        "marge": patch("opencloudtouch.main.MargeService"),
        "preset": patch("opencloudtouch.main.PresetService"),
        "sync": patch("opencloudtouch.main.DeviceSyncService"),
        "device": patch("opencloudtouch.main.DeviceService"),
        "discovery_adapter": patch("opencloudtouch.main.get_discovery_adapter"),
        "zone": patch("opencloudtouch.main.ZoneService"),
        "settings": patch("opencloudtouch.main.SettingsService"),
        "setup": patch("opencloudtouch.main.SetupService"),
        "wizard": patch("opencloudtouch.main.WizardService"),
        "restore": patch("opencloudtouch.setup.restore_service.RestoreService"),
        "health_check": patch("opencloudtouch.main.DeviceHealthCheck"),
        "ws_pipeline": patch(
            "opencloudtouch.main._init_websocket_pipeline", new_callable=AsyncMock
        ),
        "startup_check": patch("opencloudtouch.main.StartupCheck"),
        "radio_adapter": patch("opencloudtouch.radio.adapter.get_radio_adapter"),
    }
    mocks = {name: p.start() for name, p in patches.items()}
    mocks["device"].return_value.sync_devices = AsyncMock(
        return_value=MagicMock(synced=0, failed=0, discovered=0)
    )
    mocks["startup_check"].return_value.run = AsyncMock()
    yield mocks
    for p in patches.values():
        p.stop()


def _build_init_services_repos():
    """Minimal repos dict covering every key _init_services reads."""
    return {
        key: AsyncMock()
        for key in (
            "device_repo",
            "settings_repo",
            "preset_repo",
            "recents_repo",
            "wizard_audit_repo",
            "zone_repo",
        )
    }


@pytest.mark.asyncio
async def test_init_services_skips_health_check_when_device_polling_disabled(
    mock_init_services_deps,
):
    """OCT_DEVICE_POLLING_ENABLED=false must prevent DeviceHealthCheck.start()."""
    from fastapi import FastAPI

    from opencloudtouch.main import _init_services

    app = FastAPI()
    cfg = MagicMock()
    cfg.mock_mode = True  # skip StartupCheck/radio adapters, keep the test focused
    cfg.device_polling_enabled = False
    cfg.discovery_timeout = 3
    cfg.manual_device_ips_list = []
    cfg.discovery_enabled = True

    await _init_services(app, cfg, _build_init_services_repos(), MagicMock())

    health_check_instance = mock_init_services_deps["health_check"].return_value
    health_check_instance.start.assert_not_called()
    assert app.state.health_check is health_check_instance


@pytest.mark.asyncio
async def test_init_services_starts_health_check_when_device_polling_enabled(
    mock_init_services_deps,
):
    """Default (device_polling_enabled=true, not mock_mode) still starts polling."""
    from fastapi import FastAPI

    from opencloudtouch.main import _init_services

    app = FastAPI()
    cfg = MagicMock()
    cfg.mock_mode = False
    cfg.device_polling_enabled = True
    cfg.discovery_timeout = 3
    cfg.manual_device_ips_list = []
    cfg.discovery_enabled = True

    await _init_services(app, cfg, _build_init_services_repos(), MagicMock())

    health_check_instance = mock_init_services_deps["health_check"].return_value
    health_check_instance.start.assert_called_once()


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


def test_version_matches_package_metadata_without_signature(monkeypatch):
    """Without OCT_BUILD_SIGNATURE, version still resolves from package metadata.

    Self-built images have no CI signature, but the pyproject.toml version
    is baked into the wheel by the same `pip install .` step regardless —
    so unsigned builds report the real version, not a placeholder.
    """
    monkeypatch.delenv("OCT_BUILD_SIGNATURE", raising=False)
    monkeypatch.delenv("OCT_VERSION", raising=False)
    from importlib.metadata import version as pkg_version

    from opencloudtouch import _resolve_version

    assert _resolve_version() == pkg_version("opencloudtouch")


def test_version_matches_package_metadata_with_valid_signature(monkeypatch):
    """With a valid 16-char hex signature, version matches package metadata."""
    monkeypatch.setenv("OCT_BUILD_SIGNATURE", "a1b2c3d4e5f67890")
    monkeypatch.delenv("OCT_VERSION", raising=False)
    from importlib.metadata import version as pkg_version

    from opencloudtouch import _resolve_version

    assert _resolve_version() == pkg_version("opencloudtouch")


def test_version_identical_regardless_of_signature_validity(monkeypatch):
    """The version string must not depend on signature validity.

    Whether a build is trustworthy is a separate question — see
    is_official_build() / the /health "build" field. A version string
    that changed shape based on the signature was the root cause of the
    frontend always claiming an update was available for self-built images.
    """
    monkeypatch.delenv("OCT_VERSION", raising=False)
    from opencloudtouch import _resolve_version

    monkeypatch.delenv("OCT_BUILD_SIGNATURE", raising=False)
    no_sig = _resolve_version()

    monkeypatch.setenv("OCT_BUILD_SIGNATURE", "1")  # invalid: wrong length
    invalid_sig = _resolve_version()

    monkeypatch.setenv("OCT_BUILD_SIGNATURE", "a1b2c3d4e5f67890")  # valid
    valid_sig = _resolve_version()

    assert no_sig == invalid_sig == valid_sig


def test_version_uses_oct_version_override_when_set(monkeypatch):
    """OCT_VERSION overrides the package-metadata version when set (fork use case)."""
    monkeypatch.setenv("OCT_VERSION", "my-fork-1.0.0")
    from opencloudtouch import _resolve_version

    assert _resolve_version() == "my-fork-1.0.0"


def test_version_falls_back_when_package_metadata_missing(monkeypatch):
    """If the package isn't installed at all, resolve to a safe fallback string.

    Normally unreachable in Docker/`pip install -e` setups (the package is
    always installed), but _resolve_version() must not crash if it somehow
    is - PackageNotFoundError is the documented failure mode.
    """
    monkeypatch.delenv("OCT_VERSION", raising=False)
    import opencloudtouch
    from opencloudtouch import PackageNotFoundError, _resolve_version

    with patch.object(opencloudtouch, "version", side_effect=PackageNotFoundError):
        assert _resolve_version() == "0.0.0-unknown"


def test_version_ignores_blank_oct_version_override(monkeypatch):
    """A blank/whitespace-only OCT_VERSION is ignored, not used as the version."""
    monkeypatch.setenv("OCT_VERSION", "   ")
    from importlib.metadata import version as pkg_version

    from opencloudtouch import _resolve_version

    assert _resolve_version() == pkg_version("opencloudtouch")


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
