"""Tests for GET /api/logs/backend endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from opencloudtouch.core.logs_routes import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestDownloadBackendLogs:
    """Tests for the /api/logs/backend download endpoint."""

    def test_returns_200_with_plain_text_content_type(self, client: TestClient):
        with patch(
            "opencloudtouch.core.logs_routes.get_log_entries",
            return_value=["2025-01-01 INFO line one", "2025-01-01 INFO line two"],
        ):
            response = client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_returns_entries_joined_by_newlines(self, client: TestClient):
        entries = ["entry A", "entry B", "entry C"]
        with patch(
            "opencloudtouch.core.logs_routes.get_log_entries",
            return_value=entries,
        ):
            response = client.get("/api/logs/backend")

        assert response.text == "entry A\nentry B\nentry C"

    def test_returns_placeholder_when_no_entries(self, client: TestClient):
        with patch(
            "opencloudtouch.core.logs_routes.get_log_entries",
            return_value=[],
        ):
            response = client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "(no log entries captured yet)" in response.text

    def test_content_disposition_is_attachment_with_log_filename(
        self, client: TestClient
    ):
        with patch(
            "opencloudtouch.core.logs_routes.get_log_entries",
            return_value=["line"],
        ):
            response = client.get("/api/logs/backend")

        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "oct-backend-" in disposition
        assert ".log" in disposition
