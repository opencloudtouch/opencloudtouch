"""Unit tests for the bug report API route."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.api.bug_report import (
    BugReportRequest,
    _anonymize_ip,
    _build_issue_body,
    _build_log_text,
    _collect_diagnostics,
    _create_github_issue,
    _update_issue_body,
    _upload_screenshot,
)

# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestBugReportRequest:
    def test_valid_request(self):
        req = BugReportRequest(
            description="App crashes when clicking presets",
            steps_to_reproduce="1. Open preset page\n2. Click any preset",
            expected_behavior="Preset should play",
            installation_type="docker",
            hardware="raspberry-pi-4",
        )
        assert req.description == "App crashes when clicking presets"
        assert req.soundtouch_devices == []
        assert req.other_installation == ""

    def test_description_too_short(self):
        with pytest.raises(Exception):
            BugReportRequest(
                description="short",
                steps_to_reproduce="1. Open preset page\n2. Click any preset",
                expected_behavior="Works",
                installation_type="docker",
                hardware="raspberry-pi-4",
            )

    def test_optional_other_fields(self):
        req = BugReportRequest(
            description="App crashes consistently on my system",
            steps_to_reproduce="1. Start app\n2. Open browser",
            expected_behavior="No crash",
            installation_type="other",
            hardware="other",
            other_installation="Synology DSM",
            other_hardware="Synology DS920+",
        )
        assert req.other_installation == "Synology DSM"
        assert req.other_hardware == "Synology DS920+"


# ---------------------------------------------------------------------------
# Markdown builder
# ---------------------------------------------------------------------------


class TestBuildIssueBody:
    def test_basic_sections(self):
        req = BugReportRequest(
            description="Audio drops out randomly",
            steps_to_reproduce="1. Play any radio station\n2. Wait 10 minutes",
            expected_behavior="Continuous playback without drops",
            installation_type="docker",
            hardware="raspberry-pi-4",
            soundtouch_devices=["SoundTouch 30", "SoundTouch 10"],
            network_config="wifi",
        )
        diag = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {
                "discovery_enabled": True,
                "mock_mode": False,
                "log_level": "INFO",
                "manual_device_ips": "",
            },
            "devices": [],
            "db_stats": {"presets": 12, "recents": 5, "devices": 2},
            "timestamp": "2025-01-01T00:00:00+00:00",
        }

        body = _build_issue_body(req, diag)

        assert "## Bug Description" in body
        assert "Audio drops out randomly" in body
        assert "## Steps to Reproduce" in body
        assert "## Expected Behavior" in body
        assert "## Environment" in body
        assert "docker" in body
        assert "raspberry-pi-4" in body
        assert "SoundTouch 30, SoundTouch 10" in body
        assert "Wi-Fi" in body
        assert "## DB Statistics" in body

    def test_other_fields_appended(self):
        req = BugReportRequest(
            description="Cannot access the web interface at all",
            steps_to_reproduce="1. Open browser\n2. Navigate to URL",
            expected_behavior="Web UI loads",
            installation_type="other",
            hardware="other",
            other_installation="Synology DSM",
            other_hardware="Synology DS920+",
        )
        diag = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }

        body = _build_issue_body(req, diag)

        assert "other (Synology DSM)" in body
        assert "other (Synology DS920+)" in body

    def test_frontend_logs_included(self):
        req = BugReportRequest(
            description="Error boundary triggered unexpectedly",
            steps_to_reproduce="1. Navigate between pages quickly",
            expected_behavior="Smooth navigation",
            installation_type="docker",
            hardware="raspberry-pi-4",
            frontend_logs=[
                {
                    "timestamp": "12:00:00",
                    "level": "ERROR",
                    "message": "Component unmount race",
                },
            ],
        )
        diag = {
            "backend_version": "0.2.0",
            "backend_logs": [
                {"timestamp": "12:00:01", "level": "WARNING", "message": "Slow query"},
            ],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }

        body = _build_issue_body(req, diag)

        # Logs are uploaded as gzipped file, not embedded in body
        assert "## Frontend Logs" not in body
        assert "## Backend Logs" not in body

    def test_screenshot_not_in_body(self):
        """Screenshot is uploaded separately, not embedded in issue body."""
        req = BugReportRequest(
            description="Visual glitch in preset grid layout",
            steps_to_reproduce="1. Open preset page\n2. Resize window",
            expected_behavior="Grid adjusts properly",
            installation_type="docker",
            hardware="raspberry-pi-4",
            screenshot_data_url="data:image/jpeg;base64,/9j/4AAQ...",
        )
        diag = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }

        body = _build_issue_body(req, diag)
        assert "## Screenshot" not in body

    def test_screenshot_placeholder_comment_in_body(self):
        """Body should not contain data URL (uploaded separately)."""
        req = BugReportRequest(
            description="Visual glitch in preset grid layout",
            steps_to_reproduce="1. Open preset page\n2. Resize window",
            expected_behavior="Grid adjusts properly",
            installation_type="docker",
            hardware="raspberry-pi-4",
            screenshot_data_url="data:image/jpeg;base64," + "A" * 50000,
        )
        diag = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }

        body = _build_issue_body(req, diag)
        assert "data:image" not in body

    def test_device_status_with_devices(self):
        req = BugReportRequest(
            description="Cannot control specific device properly",
            steps_to_reproduce="1. Select device\n2. Try to change volume",
            expected_behavior="Volume changes",
            installation_type="docker",
            hardware="raspberry-pi-4",
        )
        diag = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [
                {"name": "Living Room", "uuid": 1, "ip": "192.x.x.50"},
            ],
            "db_stats": {},
            "timestamp": "",
        }

        body = _build_issue_body(req, diag)
        assert "## Device Status" in body
        assert "Living Room" in body
        assert "ID 1" in body

    def test_additional_info_included(self):
        req = BugReportRequest(
            description="Intermittent connectivity loss to devices",
            steps_to_reproduce="1. Wait for some time\n2. Check device status",
            expected_behavior="Devices stay connected",
            installation_type="docker",
            hardware="raspberry-pi-4",
            additional_info="This only happens after midnight",
        )
        diag = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }

        body = _build_issue_body(req, diag)
        assert "## Additional Info" in body
        assert "This only happens after midnight" in body


# ---------------------------------------------------------------------------
# Diagnostics collection
# ---------------------------------------------------------------------------


class TestCollectDiagnostics:
    @pytest.mark.asyncio
    async def test_collect_with_mocked_repos(self):
        mock_request = MagicMock()

        mock_device = MagicMock()
        mock_device.name = "Kitchen"
        mock_device.device_id = "dev001"
        mock_device.ip_address = "10.0.0.1"

        mock_device_repo = AsyncMock()
        mock_device_repo.get_all.return_value = [mock_device]

        mock_preset_repo = AsyncMock()
        mock_preset_repo.get_all_presets.return_value = [MagicMock(), MagicMock()]

        mock_recents_repo = AsyncMock()
        mock_recents_repo.get_recents.return_value = [MagicMock()]

        mock_request.app.state.device_repo = mock_device_repo
        mock_request.app.state.preset_repo = mock_preset_repo
        mock_request.app.state.recents_repo = mock_recents_repo

        diag = await _collect_diagnostics(mock_request)

        assert diag["backend_version"] is not None
        assert isinstance(diag["backend_version"], str)
        assert diag["devices"][0]["name"] == "Kitchen"
        assert diag["db_stats"]["devices"] == 1
        assert diag["db_stats"]["presets"] == 2
        assert diag["db_stats"]["recents"] == 1
        assert "timestamp" in diag
        assert "config" in diag

    @pytest.mark.asyncio
    async def test_collect_handles_repo_errors(self):
        mock_request = MagicMock()
        mock_request.app.state.device_repo = AsyncMock(
            get_all=AsyncMock(side_effect=RuntimeError("DB down"))
        )

        diag = await _collect_diagnostics(mock_request)

        assert diag["backend_version"] is not None
        assert isinstance(diag["backend_version"], str)
        assert diag["devices"] == []
        assert diag["db_stats"]["devices"] == "?"


# ---------------------------------------------------------------------------
# Route integration
# ---------------------------------------------------------------------------


class TestBugReportRoute:
    def _make_payload(self, **overrides):
        defaults = {
            "description": "Something is broken in the application",
            "steps_to_reproduce": "1. Open the app\n2. Click on presets",
            "expected_behavior": "Presets should load correctly",
            "installation_type": "docker",
            "hardware": "raspberry-pi-4",
        }
        defaults.update(overrides)
        return defaults

    def test_returns_503_without_token(self):
        from opencloudtouch.main import app

        with patch("opencloudtouch.api.bug_report.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.github_token = ""
            mock_cfg.return_value = cfg

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/api/bug-report", json=self._make_payload())
            assert response.status_code == 503

    @patch("opencloudtouch.api.github_client.create_github_issue")
    @patch("opencloudtouch.api.bug_report._collect_diagnostics")
    @patch("opencloudtouch.api.bug_report.get_config")
    def test_success_returns_issue_url(self, mock_cfg, mock_diag, mock_create):
        from opencloudtouch.main import app

        cfg = MagicMock()
        cfg.github_token = "ghp_test123"
        cfg.github_repo = "test/repo"
        mock_cfg.return_value = cfg

        mock_diag.return_value = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }
        mock_create.return_value = ("https://github.com/test/repo/issues/42", 42)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/bug-report", json=self._make_payload())

        assert response.status_code == 200
        assert response.json()["issue_url"] == "https://github.com/test/repo/issues/42"
        mock_create.assert_called_once()

    def test_validation_rejects_short_description(self):
        from opencloudtouch.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/bug-report",
            json=self._make_payload(description="short"),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# _anonymize_ip helper
# ---------------------------------------------------------------------------


class TestAnonymizeIp:
    def test_ipv4_masks_middle_octets(self):
        assert _anonymize_ip("192.168.178.88") == "192.x.x.88"

    def test_non_ipv4_returns_as_is(self):
        assert _anonymize_ip("localhost") == "localhost"
        assert _anonymize_ip("::1") == "::1"
        assert _anonymize_ip("not.an.ip") == "not.an.ip"


# ---------------------------------------------------------------------------
# _create_github_issue error path
# ---------------------------------------------------------------------------


class TestCreateGithubIssue:
    @pytest.mark.asyncio
    async def test_raises_http_502_on_github_error(self):
        from fastapi import HTTPException

        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Unprocessable Entity"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await _create_github_issue(
                    token="ghp_test",
                    repo="test/repo",
                    title="Bug title",
                    body="Bug body",
                    labels=["bug"],
                )
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_returns_url_and_number_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/test/repo/issues/7",
            "number": 7,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            url, number = await _create_github_issue(
                token="ghp_test",
                repo="test/repo",
                title="Bug title",
                body="Bug body",
                labels=["bug"],
            )
        assert url == "https://github.com/test/repo/issues/7"
        assert number == 7


# ---------------------------------------------------------------------------
# _upload_screenshot paths
# ---------------------------------------------------------------------------


class TestUploadScreenshot:
    @pytest.mark.asyncio
    async def test_returns_none_for_non_base64_url(self):
        result = await _upload_screenshot(
            token="ghp_test",
            repo="test/repo",
            issue_number=1,
            data_url="data:image/jpeg,raw-data-no-base64",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_upload_failure(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _upload_screenshot(
                token="ghp_test",
                repo="test/repo",
                issue_number=1,
                data_url="data:image/jpeg;base64,/9j/AAAA",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_download_url_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "content": {
                "download_url": "https://raw.githubusercontent.com/test/repo/main/.github/bug-screenshots/issue-1.jpg"
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _upload_screenshot(
                token="ghp_test",
                repo="test/repo",
                issue_number=1,
                data_url="data:image/jpeg;base64,/9j/AAAA",
            )
        assert result is not None
        assert "raw.githubusercontent.com" in result


# ---------------------------------------------------------------------------
# _update_issue_body
# ---------------------------------------------------------------------------


class TestUpdateIssueBody:
    @pytest.mark.asyncio
    async def test_sends_patch_request(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await _update_issue_body(
                token="ghp_test",
                repo="test/repo",
                issue_number=42,
                body="Updated issue body",
            )

        mock_client.patch.assert_called_once()
        call_kwargs = mock_client.patch.call_args
        assert "issues/42" in call_kwargs[0][0]
        assert call_kwargs[1]["json"]["body"] == "Updated issue body"


# ---------------------------------------------------------------------------
# Route — screenshot upload branch
# ---------------------------------------------------------------------------


class TestBugReportRouteScreenshot:
    def _make_payload(self, **overrides):
        defaults = {
            "description": "Something is broken in the application",
            "steps_to_reproduce": "1. Open the app\n2. Click on presets",
            "expected_behavior": "Presets should load correctly",
            "installation_type": "docker",
            "hardware": "raspberry-pi-4",
        }
        defaults.update(overrides)
        return defaults

    @patch("opencloudtouch.api.github_client.update_issue_body")
    @patch("opencloudtouch.api.github_client.upload_screenshot")
    @patch("opencloudtouch.api.github_client.create_github_issue")
    @patch("opencloudtouch.api.bug_report._collect_diagnostics")
    @patch("opencloudtouch.api.bug_report.get_config")
    def test_screenshot_uploaded_and_issue_updated(
        self, mock_cfg, mock_diag, mock_create, mock_upload, mock_update
    ):
        from opencloudtouch.main import app

        cfg = MagicMock()
        cfg.github_token = "ghp_test123"
        cfg.github_repo = "test/repo"
        mock_cfg.return_value = cfg

        mock_diag.return_value = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }
        mock_create.return_value = ("https://github.com/test/repo/issues/42", 42)
        mock_upload.return_value = "https://raw.githubusercontent.com/test/repo/main/.github/bug-screenshots/issue-42.jpg"
        mock_update.return_value = None

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/bug-report",
            json=self._make_payload(
                screenshot_data_url="data:image/jpeg;base64,/9j/AAAA"
            ),
        )

        assert response.status_code == 200
        mock_upload.assert_called_once()
        mock_update.assert_called_once()

    @patch("opencloudtouch.api.github_client.upload_screenshot")
    @patch("opencloudtouch.api.github_client.create_github_issue")
    @patch("opencloudtouch.api.bug_report._collect_diagnostics")
    @patch("opencloudtouch.api.bug_report.get_config")
    def test_screenshot_upload_failure_does_not_break_route(
        self, mock_cfg, mock_diag, mock_create, mock_upload
    ):
        from opencloudtouch.main import app

        cfg = MagicMock()
        cfg.github_token = "ghp_test123"
        cfg.github_repo = "test/repo"
        mock_cfg.return_value = cfg

        mock_diag.return_value = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }
        mock_create.return_value = ("https://github.com/test/repo/issues/99", 99)
        mock_upload.return_value = None  # upload returned None → skip update

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/bug-report",
            json=self._make_payload(
                screenshot_data_url="data:image/jpeg;base64,/9j/AAAA"
            ),
        )

        assert response.status_code == 200
        assert response.json()["issue_url"] == "https://github.com/test/repo/issues/99"

    @patch("opencloudtouch.api.github_client.upload_screenshot")
    @patch("opencloudtouch.api.github_client.create_github_issue")
    @patch("opencloudtouch.api.bug_report._collect_diagnostics")
    @patch("opencloudtouch.api.bug_report.get_config")
    def test_screenshot_exception_is_caught(
        self, mock_cfg, mock_diag, mock_create, mock_upload
    ):
        from opencloudtouch.main import app

        cfg = MagicMock()
        cfg.github_token = "ghp_test123"
        cfg.github_repo = "test/repo"
        mock_cfg.return_value = cfg

        mock_diag.return_value = {
            "backend_version": "0.2.0",
            "backend_logs": [],
            "config": {},
            "devices": [],
            "db_stats": {},
            "timestamp": "",
        }
        mock_create.return_value = ("https://github.com/test/repo/issues/77", 77)
        mock_upload.side_effect = RuntimeError("Network error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/bug-report",
            json=self._make_payload(
                screenshot_data_url="data:image/jpeg;base64,/9j/AAAA"
            ),
        )

        # Should still return 200 — exception is caught inside the route
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# _build_log_text
# ---------------------------------------------------------------------------


class TestBuildLogText:
    def test_basic_diagnostics(self):
        result = _build_log_text(
            diagnostics={
                "backend_version": "1.0.0",
                "timestamp": "2025-01-01T00:00:00",
                "devices": [],
                "db_stats": {},
                "config": {},
                "backend_logs": [],
            },
            frontend_logs=[],
        )
        assert "=== OCT Diagnostic Bundle ===" in result
        assert "Version: 1.0.0" in result
        assert "Timestamp: 2025-01-01T00:00:00" in result

    def test_with_devices(self):
        result = _build_log_text(
            diagnostics={
                "backend_version": "1.0.0",
                "timestamp": "2025-01-01",
                "devices": [
                    {"name": "Living Room", "uuid": "ABC", "ip": "192.x.x.10"},
                ],
                "db_stats": {},
                "config": {},
                "backend_logs": [],
            },
            frontend_logs=[],
        )
        assert "Devices" in result
        assert "Living Room" in result
        assert "ABC" in result

    def test_with_db_stats_and_config(self):
        result = _build_log_text(
            diagnostics={
                "backend_version": "1.0.0",
                "timestamp": "2025-01-01",
                "devices": [],
                "db_stats": {"presets": 12, "devices": 2},
                "config": {"mock_mode": True, "log_level": "DEBUG"},
                "backend_logs": [],
            },
            frontend_logs=[],
        )
        assert "DB Stats" in result
        assert "presets: 12" in result
        assert "Config" in result
        assert "mock_mode: True" in result

    def test_with_backend_logs(self):
        result = _build_log_text(
            diagnostics={
                "backend_version": "1.0.0",
                "timestamp": "2025-01-01",
                "devices": [],
                "db_stats": {},
                "config": {},
                "backend_logs": ["line1", "line2"],
            },
            frontend_logs=[],
        )
        assert "Backend Logs (2 entries)" in result
        assert "line1" in result
        assert "line2" in result

    def test_with_frontend_logs(self):
        result = _build_log_text(
            diagnostics={
                "backend_version": "1.0.0",
                "timestamp": "2025-01-01",
                "devices": [],
                "db_stats": {},
                "config": {},
                "backend_logs": [],
            },
            frontend_logs=[
                {"timestamp": "12:00", "level": "ERROR", "message": "oops"},
            ],
        )
        assert "Frontend Logs (1 entries)" in result
        assert "[12:00] ERROR: oops" in result

    def test_with_extra_info(self):
        result = _build_log_text(
            diagnostics={
                "backend_version": "1.0.0",
                "timestamp": "2025-01-01",
                "devices": [],
                "db_stats": {},
                "config": {},
                "backend_logs": [],
            },
            frontend_logs=[],
            extra_info={"description": "Bug report", "browser": "Chrome"},
        )
        assert "description: Bug report" in result
        assert "browser: Chrome" in result

    def test_empty_diagnostics(self):
        result = _build_log_text(diagnostics={}, frontend_logs=[])
        assert "OCT Diagnostic Bundle" in result

    def test_frontend_logs_trimmed_to_500(self):
        logs = [
            {"timestamp": f"t{i}", "level": "INFO", "message": f"m{i}"}
            for i in range(600)
        ]
        result = _build_log_text(
            diagnostics={"backend_version": "?", "timestamp": "?"}, frontend_logs=logs
        )
        assert "Frontend Logs (500 entries)" in result

    def test_extra_info_skips_falsy_values(self):
        result = _build_log_text(
            diagnostics={"backend_version": "1.0.0", "timestamp": "now"},
            frontend_logs=[],
            extra_info={"present": "yes", "absent": "", "none": None},
        )
        assert "present: yes" in result
        assert "absent" not in result


# ---------------------------------------------------------------------------
# Diagnostics download endpoint
# ---------------------------------------------------------------------------


class TestDiagnosticsDownload:
    @patch("opencloudtouch.api.bug_report._collect_diagnostics")
    def test_returns_gzipped_response(self, mock_diag):
        import gzip

        from opencloudtouch.main import app

        mock_diag.return_value = {
            "backend_version": "1.0.0",
            "timestamp": "2025-01-01",
            "devices": [],
            "db_stats": {},
            "config": {},
            "backend_logs": ["test entry"],
        }

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/bug-report/diagnostics",
            json={
                "frontend_logs": [],
                "description": "test",
                "browser_info": "Chrome",
                "current_route": "/",
                "click_timestamp": 0,
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/gzip"
        assert "Content-Disposition" in response.headers
        decompressed = gzip.decompress(response.content).decode("utf-8")
        assert "test entry" in decompressed
