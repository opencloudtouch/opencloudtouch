"""Tests for core.static_files module — SPA static file serving.

TDD RED phase: tests fail until core/static_files.py is created.

Covers:
- _is_api_path(): pure function identifying API vs. frontend routes
- mount_static_files(): no-op when dist/ absent, mounts assets + SPA handler when present
- SPA 404 handler: JSON 404 for API routes, index.html for frontend routes,
  direct FileResponse for existing static files, path-traversal rejection.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── _is_api_path ──────────────────────────────────────────────────────────────


class TestIsApiPath:
    """_is_api_path identifies API routes that must NOT fall through to SPA."""

    def test_api_devices_is_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/api/devices") is True

    def test_api_root_is_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/api/") is True

    def test_bmx_is_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/bmx/resolve") is True

    def test_health_is_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/health") is True

    def test_openapi_is_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/openapi.json") is True

    def test_docs_is_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/docs") is True

    def test_core02_is_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/core02/svc-bmx/prod/orion") is True

    def test_root_is_not_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/") is False

    def test_frontend_devices_page_is_not_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/devices") is False

    def test_frontend_setup_page_is_not_api(self):
        from opencloudtouch.core.static_files import _is_api_path

        assert _is_api_path("/setup") is False


# ── mount_static_files ────────────────────────────────────────────────────────


class TestMountStaticFiles:
    """mount_static_files registers static file serving on the FastAPI app."""

    def test_does_nothing_when_dir_missing(self, tmp_path):
        """Non-existent dist/ is silently ignored (no error, no routes added)."""
        from opencloudtouch.core.static_files import mount_static_files

        nonexistent = tmp_path / "nonexistent"
        app = FastAPI()
        mount_static_files(app, nonexistent)  # must not raise
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/some-page")
        assert response.status_code == 404  # plain FastAPI 404, no SPA handler

    def test_returns_none(self, tmp_path):
        """mount_static_files returns None (pure side-effect function)."""
        from opencloudtouch.core.static_files import mount_static_files

        static_dir = tmp_path / "dist"
        (static_dir / "assets").mkdir(parents=True)
        (static_dir / "index.html").write_text("<html>App</html>")
        app = FastAPI()
        result = mount_static_files(app, static_dir)
        assert result is None


# ── SPA 404 handler ───────────────────────────────────────────────────────────


@pytest.fixture
def spa_app(tmp_path):
    """Minimal FastAPI app with static files mounted from a tmp dist/ dir."""
    from opencloudtouch.core.static_files import mount_static_files

    static_dir = tmp_path / "dist"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text("<html>SPA</html>")
    (static_dir / "favicon.ico").write_bytes(b"\x00\x01\x02")
    (static_dir / "supporters.csv").write_text("name,amount\nTest,10")
    app = FastAPI()
    mount_static_files(app, static_dir)
    return app


class TestSpa404Handler:
    """SPA 404 handler routes 404s to index.html or JSON depending on path."""

    def test_api_path_returns_json_404(self, spa_app):
        """API routes must get a machine-readable JSON 404 response."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/api/devices")
        assert response.status_code == 404
        body = response.json()
        assert "type" in body or "detail" in body

    def test_bmx_path_returns_json_404(self, spa_app):
        """/bmx/ routes are API, not a frontend page."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/bmx/resolve/station")
        assert response.status_code == 404
        body = response.json()
        assert "type" in body or "detail" in body

    def test_core02_path_returns_json_404(self, spa_app):
        """/core02/ routes (Bose cloud emulator) must be JSON, not SPA."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/core02/svc-bmx/prod/something")
        assert response.status_code == 404
        body = response.json()
        assert "type" in body or "detail" in body

    def test_root_serves_index_html(self, spa_app):
        """Root / serves the SPA's index.html."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/")
        assert response.status_code == 200
        assert b"SPA" in response.content

    def test_frontend_route_serves_index_html(self, spa_app):
        """Unknown paths (React Router routes) serve index.html."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/some/frontend/page")
        assert response.status_code == 200
        assert b"SPA" in response.content

    def test_existing_static_file_served_directly(self, spa_app):
        """Actual files in dist/ (e.g. favicon.ico) are served without SPA fallback."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/favicon.ico")
        assert response.status_code == 200
        assert response.content == b"\x00\x01\x02"

    def test_path_traversal_dotdot_blocked(self, spa_app):
        """Path traversal via percent-encoded '..' must be rejected.

        Raw '/../..' is normalized by httpx/browsers before reaching the handler.
        The real attack vector is percent-encoded '../' (%2e%2e%2f) that survives
        URL-parsing and is only decoded during file-path resolution.
        """
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/%2e%2e/%2e%2e/%2e%2e/etc/passwd")
        assert response.status_code == 404

    def test_path_traversal_backslash_blocked(self, spa_app):
        """Backslash in path (Windows escape) must be rejected."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/valid%5c..%5csecret")  # %5c = backslash
        assert response.status_code == 404

    def test_supporters_csv_not_cached(self, spa_app):
        """supporters.csv must have aggressive no-cache headers to prevent stale data."""
        client = TestClient(spa_app, raise_server_exceptions=False)
        response = client.get("/supporters.csv")
        assert response.status_code == 200
        # Check all cache-prevention headers (HTTP/1.1 + HTTP/1.0 + proxies)
        assert (
            response.headers["cache-control"]
            == "no-cache, no-store, must-revalidate, max-age=0"
        )
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["expires"] == "0"
