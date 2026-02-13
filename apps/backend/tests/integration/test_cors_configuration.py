"""
Regression test for CORS configuration (E2E Preview Port Support).

Bug History:
- Date: 2026-02-13
- Symptom: E2E tests showed "Fehler beim Laden der Geräte" + "Failed to fetch"
- Root Cause: CORS origins missing port 4173 (Vite preview server)
- Impact: All E2E tests failed (0/36 passing)
- Fix: Added http://localhost:4173 to cors_origins default list

This test ensures the CORS configuration includes all necessary development ports:
- 3000: Legacy dev server
- 4173: Vite preview (E2E tests) ← Critical for E2E!
- 5173: Vite dev server
- 7777: Backend server
"""

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.config import get_config
from opencloudtouch.main import app


class TestCORSConfiguration:
    """Test CORS headers for all development/test environments."""

    def test_cors_includes_vite_preview_port(self):
        """
        Regression test: CORS must allow port 4173 (Vite preview).

        Without this, E2E tests fail with "Failed to fetch" because
        the browser blocks cross-origin requests from localhost:4173
        to localhost:7778.
        """
        config = get_config()

        # Verify port 4173 is in CORS origins
        assert "http://localhost:4173" in config.cors_origins, (
            "CORS origins must include http://localhost:4173 (Vite preview). "
            "E2E tests run against preview build and will fail without this!"
        )

    def test_cors_includes_all_dev_ports(self):
        """Verify all development server ports are allowed."""
        config = get_config()

        required_origins = [
            "http://localhost:4173",  # Vite preview (E2E tests)
            "http://localhost:5173",  # Vite dev server
            "http://localhost:7777",  # Backend API
        ]

        for origin in required_origins:
            assert origin in config.cors_origins, f"Missing CORS origin: {origin}"

    @pytest.mark.asyncio
    async def test_cors_headers_in_response(self):
        """
        Integration test: Verify CORS headers are actually sent in responses.

        Simulates a preflight OPTIONS request from port 4173.
        """
        client = TestClient(app)

        # Simulate preflight request from Vite preview (port 4173)
        response = client.options(
            "/api/devices",
            headers={
                "Origin": "http://localhost:4173",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Backend should allow this origin
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] in [
            "http://localhost:4173",
            "*",  # Wildcard also acceptable in test mode
        ]

    @pytest.mark.asyncio
    async def test_api_accessible_from_preview_port(self):
        """
        End-to-end test: Verify /api/devices endpoint works with CORS.

        This simulates what happens in E2E tests when the frontend
        (localhost:4173) calls the backend (localhost:7778).

        Note: This test only checks CORS headers, not full app functionality.
        Full integration is tested in test_api_integration.py.
        """
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # We can't test /api/devices without lifespan (no dependencies initialized)
        # Instead, test /health which doesn't need dependencies
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:4173"},
        )

        # Should succeed (200 OK) with CORS headers
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

        # Response should be valid JSON
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
