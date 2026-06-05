"""Tests for /api/logs/backend and /api/logs/level endpoints."""

import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.logging import CLUSTER_NAMES


def _make_clusters(**kwargs: list[str]) -> dict[str, list[str]]:
    """Build a full cluster dict with empty defaults, overriding given clusters."""
    result = {name: [] for name in CLUSTER_NAMES}
    result.update(kwargs)
    return result


@pytest.fixture
def client():
    from fastapi import FastAPI

    from opencloudtouch.core.logs_routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestDownloadBackendLogs:
    """Tests for the /api/logs/backend download endpoint."""

    def test_returns_200_with_plain_text_content_type(self, client: TestClient):
        clusters = _make_clusters(
            general=["2025-01-01 INFO line one", "2025-01-01 INFO line two"]
        )
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_returns_entries_in_cluster_section(self, client: TestClient):
        clusters = _make_clusters(marge=["entry A", "entry B", "entry C"])
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.get("/api/logs/backend")

        assert "entry A\nentry B\nentry C" in response.text
        assert "[MARGE] (3 entries" in response.text
        assert "CLUSTERED (3 entries total)" in response.text

    def test_returns_empty_marker_when_no_entries(self, client: TestClient):
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "(empty)" in response.text

    def test_content_disposition_is_attachment_with_log_filename(
        self, client: TestClient
    ):
        clusters = _make_clusters(general=["line"])
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.get("/api/logs/backend")

        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "oct-backend-" in disposition
        assert ".log" in disposition

    def test_all_cluster_sections_present(self, client: TestClient):
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.get("/api/logs/backend")

        for name in CLUSTER_NAMES:
            assert f"[{name.upper()}]" in response.text


class TestPostBackendLogs:
    """Tests for POST /api/logs/backend with frontend logs."""

    def test_post_returns_200_with_frontend_logs(self, client: TestClient):
        clusters = _make_clusters(general=["backend line"])
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.post(
                "/api/logs/backend",
                json={
                    "frontend_logs": [
                        {"timestamp": "12:00:00", "level": "ERROR", "message": "oops"},
                    ]
                },
            )

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "[12:00:00] ERROR: oops" in response.text
        assert "backend line" in response.text

    def test_post_with_empty_frontend_logs(self, client: TestClient):
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.post(
                "/api/logs/backend",
                json={"frontend_logs": []},
            )

        assert response.status_code == 200
        assert "(no frontend logs received" in response.text

    def test_post_includes_wizard_audit_section(self, client: TestClient):
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.post(
                "/api/logs/backend",
                json={"frontend_logs": []},
            )

        assert response.status_code == 200
        assert "WIZARD AUDIT TRAIL" in response.text


class TestLogLevel:
    """Tests for /api/logs/level endpoints."""

    def test_get_log_level(self, client: TestClient):
        with patch(
            "opencloudtouch.core.logs_routes.get_current_log_level",
            return_value="INFO",
        ):
            response = client.get("/api/logs/level")

        assert response.status_code == 200
        assert response.json()["level"] == "INFO"

    def test_put_valid_log_level(self, client: TestClient):
        with patch(
            "opencloudtouch.core.logs_routes.set_log_level",
        ), patch(
            "opencloudtouch.core.logs_routes.get_current_log_level",
            return_value="DEBUG",
        ):
            response = client.put(
                "/api/logs/level",
                json={"level": "DEBUG"},
            )

        assert response.status_code == 200
        assert response.json()["level"] == "DEBUG"

    def test_put_invalid_log_level_returns_400(self, client: TestClient):
        with patch(
            "opencloudtouch.core.logs_routes.set_log_level",
            side_effect=ValueError("Invalid level: TRACE"),
        ):
            response = client.put(
                "/api/logs/level",
                json={"level": "DEBUG"},
            )

        assert response.status_code == 400


class TestAuditTrailFormatters:
    """Tests for _format_audit_entries and _format_snapshots."""

    def test_format_audit_entries_empty(self):
        from opencloudtouch.core.logs_routes import _format_audit_entries

        result = _format_audit_entries([])
        assert "(no wizard audit entries recorded yet)" in result

    def test_format_audit_entries_with_data(self):
        from opencloudtouch.core.logs_routes import _format_audit_entries

        entries = [
            {
                "timestamp": "2025-01-01T12:00:00",
                "device_id": "DEV1",
                "step": 3,
                "category": "user_action",
                "event": "button_click:next",
                "detail": None,
            },
            {
                "timestamp": "2025-01-01T12:00:01",
                "device_id": "DEV1",
                "step": 4,
                "category": "config_change",
                "event": "bmx_url_modified",
                "detail": "old=bmx.bose.com",
            },
        ]
        result = _format_audit_entries(entries)
        assert "Audit Log (2 entries)" in result
        assert "button_click:next" in result
        assert "old=bmx.bose.com" in result

    def test_format_snapshots_empty(self):
        from opencloudtouch.core.logs_routes import _format_snapshots

        result = _format_snapshots([])
        assert "(no config snapshots recorded yet)" in result

    def test_format_snapshots_with_data(self):
        from opencloudtouch.core.logs_routes import _format_snapshots

        snapshots = [
            {
                "timestamp": "2025-01-01T12:00:00",
                "device_id": "DEV1",
                "trigger": "before_modify",
                "file_path": "/etc/hosts",
                "content": "127.0.0.1 localhost",
            },
        ]
        result = _format_snapshots(snapshots)
        assert "Config Snapshots (1 entries)" in result
        assert "/etc/hosts" in result
        assert "127.0.0.1 localhost" in result


class TestZipDownload:
    """Tests for ZIP log download when persistent log_dir is configured."""

    @pytest.fixture
    def log_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "logs"
        d.mkdir()
        (d / "marge.log").write_text("marge warning line\n", encoding="utf-8")
        (d / "general.log").write_text("general info line\n", encoding="utf-8")
        (d / "database.log.1").write_text("old db backup\n", encoding="utf-8")
        return d

    @pytest.fixture
    def client_with_log_dir(self, log_dir: Path):
        from fastapi import FastAPI

        from opencloudtouch.core.logs_routes import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app), log_dir

    def test_zip_response_when_log_dir_exists(self, client_with_log_dir):
        client, log_dir = client_with_log_dir
        clusters = _make_clusters(general=["ram entry"])
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=log_dir,
            ),
        ):
            response = client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "application/zip" in response.headers["content-type"]
        assert "oct-logs-" in response.headers["content-disposition"]
        assert ".zip" in response.headers["content-disposition"]

    def test_zip_contains_persistent_log_files(self, client_with_log_dir):
        client, log_dir = client_with_log_dir
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=log_dir,
            ),
        ):
            response = client.get("/api/logs/backend")

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        names = zf.namelist()
        assert "logs/marge.log" in names
        assert "logs/general.log" in names
        assert "logs/database.log.1" in names

    def test_zip_contains_ram_buffer(self, client_with_log_dir):
        client, log_dir = client_with_log_dir
        clusters = _make_clusters(marge=["ram marge warning"])
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=log_dir,
            ),
        ):
            response = client.get("/api/logs/backend")

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        ram_content = zf.read("ram-buffer.log").decode("utf-8")
        assert "ram marge warning" in ram_content

    def test_zip_contains_frontend_logs_when_posted(self, client_with_log_dir):
        client, log_dir = client_with_log_dir
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=log_dir,
            ),
        ):
            response = client.post(
                "/api/logs/backend",
                json={
                    "frontend_logs": [
                        {
                            "timestamp": "14:30:00",
                            "level": "WARN",
                            "message": "react err",
                        },
                    ]
                },
            )

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        assert "frontend-console.log" in zf.namelist()
        fe_content = zf.read("frontend-console.log").decode("utf-8")
        assert "react err" in fe_content

    def test_zip_contains_audit_trail(self, client_with_log_dir):
        client, log_dir = client_with_log_dir
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=log_dir,
            ),
        ):
            response = client.get("/api/logs/backend")

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        assert "wizard-audit.log" in zf.namelist()

    def test_plaintext_fallback_when_no_log_dir(self, client: TestClient):
        clusters = _make_clusters(general=["fallback entry"])
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "fallback entry" in response.text


class TestBuildRamBufferText:
    """Tests for _build_ram_buffer_text helper."""

    def test_empty_clusters(self):
        from opencloudtouch.core.logs_routes import _build_ram_buffer_text

        clusters = _make_clusters()
        with patch(
            "opencloudtouch.core.logs_routes.get_clustered_log_entries",
            return_value=clusters,
        ):
            result = _build_ram_buffer_text()

        assert "BACKEND LOG BUFFER" in result
        assert "0 entries total" in result
        for name in CLUSTER_NAMES:
            assert f"[{name.upper()}]" in result

    def test_with_entries(self):
        from opencloudtouch.core.logs_routes import _build_ram_buffer_text

        clusters = _make_clusters(general=["line1", "line2"], marge=["marge1"])
        with patch(
            "opencloudtouch.core.logs_routes.get_clustered_log_entries",
            return_value=clusters,
        ):
            result = _build_ram_buffer_text()

        assert "3 entries total" in result
        assert "line1\nline2" in result
        assert "marge1" in result


class TestBuildFrontendSection:
    """Tests for _build_frontend_section helper."""

    def test_empty_frontend_logs(self):
        from opencloudtouch.core.logs_routes import _build_frontend_section

        result = _build_frontend_section(frontend_logs=[], frontend_log_buffers=None)
        assert "FRONTEND CONSOLE LOGS (0 entries" in result
        assert "(no frontend logs received" in result

    def test_with_frontend_logs(self):
        from opencloudtouch.core.logs_routes import (
            FrontendLogEntry,
            _build_frontend_section,
        )

        logs = [
            FrontendLogEntry(timestamp="12:00", level="ERROR", message="err1"),
            FrontendLogEntry(timestamp="12:01", level="WARN", message="warn1"),
        ]
        result = _build_frontend_section(frontend_logs=logs, frontend_log_buffers=None)
        assert "2 entries" in result
        assert "[12:00] ERROR: err1" in result
        assert "[12:01] WARN: warn1" in result

    def test_with_structured_buffers(self):
        from opencloudtouch.core.logs_routes import (
            FrontendLogEntry,
            _build_frontend_section,
        )

        buffers = {
            "websocket": [
                FrontendLogEntry(
                    timestamp="12:00", level="INFO", message="ws connected"
                ),
            ],
            "api": [],
        }
        result = _build_frontend_section(frontend_logs=[], frontend_log_buffers=buffers)
        assert "FRONTEND [WEBSOCKET]" in result
        assert "ws connected" in result
        assert "FRONTEND [API]" in result
        assert "(empty)" in result

    def test_structured_buffers_take_precedence(self):
        from opencloudtouch.core.logs_routes import (
            FrontendLogEntry,
            _build_frontend_section,
        )

        buffers = {
            "main": [
                FrontendLogEntry(timestamp="12:00", level="INFO", message="buf msg"),
            ],
        }
        flat_logs = [
            FrontendLogEntry(timestamp="11:00", level="ERROR", message="flat msg"),
        ]
        result = _build_frontend_section(
            frontend_logs=flat_logs, frontend_log_buffers=buffers
        )
        assert "buf msg" in result
        assert "flat msg" not in result


class TestPostWithStructuredBuffers:
    """Tests for POST /api/logs/backend with frontend_log_buffers."""

    def test_post_with_frontend_log_buffers_plaintext(self, client: TestClient):
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.post(
                "/api/logs/backend",
                json={
                    "frontend_logs": [],
                    "frontend_log_buffers": {
                        "websocket": [
                            {"timestamp": "14:00", "level": "INFO", "message": "ws ok"},
                        ],
                        "api": [],
                    },
                },
            )

        assert response.status_code == 200
        assert "FRONTEND [WEBSOCKET]" in response.text
        assert "ws ok" in response.text

    def test_post_with_frontend_log_buffers_zip(
        self, client: TestClient, tmp_path: Path
    ):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "general.log").write_text("line\n", encoding="utf-8")

        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=log_dir,
            ),
        ):
            response = client.post(
                "/api/logs/backend",
                json={
                    "frontend_logs": [],
                    "frontend_log_buffers": {
                        "ws": [
                            {"timestamp": "14:00", "level": "INFO", "message": "ok"},
                        ],
                    },
                },
            )

        assert response.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        assert "frontend-ws.log" in zf.namelist()
        content = zf.read("frontend-ws.log").decode("utf-8")
        assert "ok" in content


class TestAuditTrailSection:
    """Tests for _build_audit_trail_section error paths."""

    def test_audit_repo_not_initialized(self, client: TestClient):
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = client.get("/api/logs/backend")

        assert "wizard audit repository not initialized" in response.text

    def test_audit_repo_exception(self, client: TestClient):
        from fastapi import FastAPI

        from opencloudtouch.core.logs_routes import router

        app = FastAPI()
        app.include_router(router)

        audit_repo = AsyncMock()
        audit_repo.get_entries = AsyncMock(side_effect=RuntimeError("db broken"))
        app.state.wizard_audit_repo = audit_repo

        error_client = TestClient(app)
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = error_client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "error reading audit trail" in response.text

    def test_audit_repo_success(self, client: TestClient):
        from fastapi import FastAPI

        from opencloudtouch.core.logs_routes import router

        app = FastAPI()
        app.include_router(router)

        audit_repo = AsyncMock()
        audit_repo.get_entries = AsyncMock(
            return_value=[
                {
                    "timestamp": "2025-01-01T12:00:00",
                    "device_id": "DEV1",
                    "step": 1,
                    "category": "setup",
                    "event": "started",
                    "detail": None,
                }
            ]
        )
        audit_repo.get_config_snapshots = AsyncMock(return_value=[])
        app.state.wizard_audit_repo = audit_repo

        audit_client = TestClient(app)
        clusters = _make_clusters()
        with (
            patch(
                "opencloudtouch.core.logs_routes.get_clustered_log_entries",
                return_value=clusters,
            ),
            patch(
                "opencloudtouch.core.logs_routes.get_persistent_log_dir",
                return_value=None,
            ),
        ):
            response = audit_client.get("/api/logs/backend")

        assert response.status_code == 200
        assert "Audit Log (1 entries)" in response.text
        assert "started" in response.text


class TestLogLevelValidation:
    """Tests for log level request validation."""

    def test_put_with_invalid_body(self, client: TestClient):
        response = client.put("/api/logs/level", json={"level": "INVALID"})
        assert response.status_code == 422
