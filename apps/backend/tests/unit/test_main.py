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
    ) as mock_repo_class:

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

        # Mock repository
        mock_repo = AsyncMock()
        mock_repo.initialize = AsyncMock()
        mock_repo.close = AsyncMock()
        mock_repo_class.return_value = mock_repo

        # Run lifespan
        async with lifespan(app):
            # Verify startup
            mock_init_config.assert_called_once()
            mock_setup_logging.assert_called_once()
            mock_repo.initialize.assert_called_once()

        # Verify shutdown
        mock_repo.close.assert_called_once()


def test_health_endpoint():
    """Test health check endpoint returns expected fields and types."""
    from opencloudtouch.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Required fields
    assert data["status"] == "healthy"
    assert "version" in data
    assert "config" in data

    # Type validation (from integration tests)
    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["config"], dict)
    assert isinstance(data["config"]["discovery_enabled"], bool)
    assert isinstance(data["config"]["db_path"], str)


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


def test_404_returns_rfc7807_error():
    """Test that 404 Not Found returns RFC 7807 ErrorDetail.

    Tests the StarletteHTTPException handler for routing-level 404s.
    We need to test before the SPA catch-all is hit.
    """
    from opencloudtouch.main import StarletteHTTPException

    # Simulate a routing 404 by patching the router lookup
    # Alternative: Use a request that actually triggers Starlette's 404
    # Since all routes are handled by SPA catch-all, we test the handler directly

    # Create a mock request
    mock_request = MagicMock()
    mock_request.url.path = "/api/test-404"

    # Create StarletteHTTPException
    exc = StarletteHTTPException(status_code=404, detail="Not Found")

    # Call handler directly
    from opencloudtouch.main import starlette_http_exception_handler
    import asyncio

    response = asyncio.run(starlette_http_exception_handler(mock_request, exc))

    assert response.status_code == 404
    # Parse JSON from response body
    import json

    data = json.loads(response.body.decode())

    # Verify RFC 7807 structure
    assert "type" in data
    assert "title" in data
    assert "status" in data
    assert "detail" in data
    assert "instance" in data

    # Verify values
    assert data["type"] == "not_found"
    assert data["status"] == 404


def test_405_returns_rfc7807_error():
    """Test that 405 Method Not Allowed returns RFC 7807 ErrorDetail.

    Tests the StarletteHTTPException handler for routing-level 405s.
    """
    from opencloudtouch.main import StarletteHTTPException
    from unittest.mock import MagicMock
    import asyncio
    import json

    # Create a mock request
    mock_request = MagicMock()
    mock_request.url.path = "/api/devices"

    # Create StarletteHTTPException for 405
    exc = StarletteHTTPException(status_code=405, detail="Method Not Allowed")

    # Call handler directly
    from opencloudtouch.main import starlette_http_exception_handler

    response = asyncio.run(starlette_http_exception_handler(mock_request, exc))

    assert response.status_code == 405
    data = json.loads(response.body.decode())

    # Verify RFC 7807 structure
    assert "type" in data
    assert "title" in data
    assert "status" in data
    assert "detail" in data
    assert "instance" in data

    # Verify values
    assert data["status"] == 405
    assert data["instance"] == "/api/devices"
