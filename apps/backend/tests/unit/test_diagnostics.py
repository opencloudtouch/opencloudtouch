"""Unit tests for the diagnostics API route."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.devices.repository import Device
from opencloudtouch.main import app


def _make_device(
    device_id: str = "AABBCCDDEEFF",
    name: str = "Living Room",
    model: str = "SoundTouch 30",
    ip: str = "192.168.1.100",
    firmware_version: str = "24.0.5",
    setup_status: str = "complete",
    last_seen: datetime | None = None,
    setup_completed_at: datetime | None = None,
    ssh_permanent: bool = False,
) -> Device:
    return Device(
        device_id=device_id,
        ip=ip,
        name=name,
        model=model,
        mac_address=device_id,
        firmware_version=firmware_version,
        setup_status=setup_status,
        last_seen=last_seen,
        setup_completed_at=setup_completed_at,
        ssh_permanent=ssh_permanent,
    )


@pytest.fixture()
def mock_repos():
    """Set up mocked device_repo and preset_repo on app.state."""
    device_repo = AsyncMock()
    preset_repo = AsyncMock()
    device_repo.get_all = AsyncMock(return_value=[])
    preset_repo.get_all_presets = AsyncMock(return_value=[])
    app.state.device_repo = device_repo
    app.state.preset_repo = preset_repo
    return device_repo, preset_repo


@pytest.fixture()
def client(mock_repos):
    """FastAPI TestClient with mocked repos."""
    return TestClient(app)


class TestGetDiagnostics:
    """Tests for GET /api/diagnostics."""

    @patch("opencloudtouch.api.diagnostics.get_config")
    def test_returns_200_with_server_info(self, mock_config, client, mock_repos):
        cfg = MagicMock()
        cfg.discovery_enabled = True
        cfg.mock_mode = False
        cfg.log_level = "INFO"
        cfg.manual_device_ips = []
        mock_config.return_value = cfg

        resp = client.get("/api/diagnostics")

        assert resp.status_code == 200
        data = resp.json()
        assert "server" in data
        server = data["server"]
        assert "version" in server
        assert "python_version" in server
        assert "platform" in server
        assert "discovery_enabled" in server
        assert "mock_mode" in server
        assert "log_level" in server
        assert "manual_device_ips" in server
        assert "timestamp" in server

    @patch("opencloudtouch.api.diagnostics.get_config")
    def test_returns_device_list(self, mock_config, client, mock_repos):
        cfg = MagicMock()
        cfg.discovery_enabled = True
        cfg.mock_mode = False
        cfg.log_level = "INFO"
        cfg.manual_device_ips = []
        mock_config.return_value = cfg

        device_repo, preset_repo = mock_repos
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        device_repo.get_all.return_value = [
            _make_device(
                device_id="AABBCCDDEEFF",
                name="Living Room",
                last_seen=now,
                setup_completed_at=now,
                ssh_permanent=True,
            ),
            _make_device(
                device_id="112233445566",
                name="Kitchen",
                model="SoundTouch 10",
            ),
        ]

        resp = client.get("/api/diagnostics")

        assert resp.status_code == 200
        devices = resp.json()["devices"]
        assert len(devices) == 2
        assert devices[0]["device_id"] == "AABBCCDDEEFF"
        assert devices[0]["name"] == "Living Room"
        assert devices[0]["ssh_permanent"] is True
        assert devices[1]["device_id"] == "112233445566"
        assert devices[1]["model"] == "SoundTouch 10"

    @patch("opencloudtouch.api.diagnostics.get_config")
    def test_returns_db_stats(self, mock_config, client, mock_repos):
        cfg = MagicMock()
        cfg.discovery_enabled = False
        cfg.mock_mode = True
        cfg.log_level = "DEBUG"
        cfg.manual_device_ips = ["192.168.1.50"]
        mock_config.return_value = cfg

        device_repo, preset_repo = mock_repos
        device_repo.get_all.return_value = [
            _make_device(device_id="AAA"),
            _make_device(device_id="BBB"),
        ]
        preset_repo.get_all_presets.side_effect = [
            [MagicMock(), MagicMock(), MagicMock()],  # 3 presets for AAA
            [MagicMock(), MagicMock()],  # 2 presets for BBB
        ]

        resp = client.get("/api/diagnostics")

        assert resp.status_code == 200
        db_stats = resp.json()["db_stats"]
        assert db_stats["devices"] == 2
        assert db_stats["presets"] == 5

    @patch("opencloudtouch.api.diagnostics.get_config")
    def test_handles_device_repo_exception(self, mock_config, client, mock_repos):
        cfg = MagicMock()
        cfg.discovery_enabled = True
        cfg.mock_mode = False
        cfg.log_level = "INFO"
        cfg.manual_device_ips = []
        mock_config.return_value = cfg

        device_repo, _ = mock_repos
        device_repo.get_all.side_effect = RuntimeError("DB connection lost")

        resp = client.get("/api/diagnostics")

        assert resp.status_code == 200
        data = resp.json()
        assert data["devices"] == []
        assert data["db_stats"]["devices"] == 0

    @patch("opencloudtouch.api.diagnostics.get_config")
    def test_handles_preset_repo_exception(self, mock_config, client, mock_repos):
        cfg = MagicMock()
        cfg.discovery_enabled = True
        cfg.mock_mode = False
        cfg.log_level = "INFO"
        cfg.manual_device_ips = []
        mock_config.return_value = cfg

        device_repo, preset_repo = mock_repos
        device_repo.get_all.return_value = [_make_device()]
        preset_repo.get_all_presets.side_effect = RuntimeError("Preset DB error")

        resp = client.get("/api/diagnostics")

        assert resp.status_code == 200
        assert resp.json()["db_stats"]["presets"] == 0

    @patch("opencloudtouch.api.diagnostics.get_config")
    def test_handles_none_last_seen_and_setup_completed_at(
        self, mock_config, client, mock_repos
    ):
        cfg = MagicMock()
        cfg.discovery_enabled = True
        cfg.mock_mode = False
        cfg.log_level = "INFO"
        cfg.manual_device_ips = []
        mock_config.return_value = cfg

        device_repo, _ = mock_repos
        device_repo.get_all.return_value = [
            _make_device(last_seen=None, setup_completed_at=None),
        ]

        resp = client.get("/api/diagnostics")

        assert resp.status_code == 200
        device = resp.json()["devices"][0]
        # last_seen defaults to datetime.now(UTC) in Device.__init__,
        # so it won't be None. But setup_completed_at should be null.
        assert device["setup_completed_at"] is None
