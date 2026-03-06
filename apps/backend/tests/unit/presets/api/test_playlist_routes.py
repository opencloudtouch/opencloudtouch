"""
Tests for M3U/PLS Playlist API endpoints.

Tests cover:
- M3U success (200, correct content-type and body format)
- PLS success (200, correct content-type and body format)
- 404 when preset not found
- 500 when preset has no stream URL
- 500 on unexpected service exception
- station_name fallback to "Unknown Station" when None
- Valid preset numbers 1-6, invalid rejected
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_preset_service
from opencloudtouch.main import app
from opencloudtouch.presets.models import Preset

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_preset(
    device_id: str = "DEVICE123",
    preset_number: int = 1,
    station_name: str | None = "Test Radio",
    station_url: str | None = "http://stream.example.com/radio.mp3",
) -> Preset:
    return Preset(
        device_id=device_id,
        preset_number=preset_number,
        station_uuid="uuid-abc",
        station_name=station_name,
        station_url=station_url or "",
        station_homepage="",
        station_favicon="",
        source="INTERNET_RADIO",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_preset_service():
    return AsyncMock()


@pytest.fixture
def client(mock_preset_service):
    app.dependency_overrides[get_preset_service] = lambda: mock_preset_service
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# M3U endpoint
# ---------------------------------------------------------------------------


class TestGetPlaylistM3u:
    """Tests for GET /playlist/{device_id}/{preset_number}.m3u"""

    def test_m3u_returns_200_with_correct_content_type(
        self, client, mock_preset_service
    ):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        response = client.get("/playlist/DEVICE123/1.m3u")

        assert response.status_code == 200
        assert "audio/x-mpegurl" in response.headers["content-type"]

    def test_m3u_body_format(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(
                station_name="Cool Radio",
                station_url="http://cool.stream/live.mp3",
            )
        )

        response = client.get("/playlist/DEVICE123/2.m3u")

        assert response.status_code == 200
        body = response.text
        assert body.startswith("#EXTM3U\n")
        assert "#EXTINF:-1,Cool Radio\n" in body
        assert "http://cool.stream/live.mp3\n" in body

    def test_m3u_cache_control_header(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        response = client.get("/playlist/DEVICE123/1.m3u")

        assert "no-cache" in response.headers.get("cache-control", "")

    def test_m3u_content_disposition_header(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(preset_number=3)
        )

        response = client.get("/playlist/DEVICE123/3.m3u")

        disposition = response.headers.get("content-disposition", "")
        assert "preset3.m3u" in disposition

    def test_m3u_404_when_preset_not_found(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=None)

        response = client.get("/playlist/DEVICE123/1.m3u")

        assert response.status_code == 404
        # RFC 7807 response: check type field
        body = response.json()
        assert body.get("type") == "not_found" or body.get("status") == 404

    def test_m3u_500_when_no_stream_url(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(station_url=None)
        )

        response = client.get("/playlist/DEVICE123/1.m3u")

        assert response.status_code == 500
        body = response.json()
        assert body.get("type") == "server_error" or body.get("status") == 500

    def test_m3u_500_on_unexpected_exception(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(side_effect=RuntimeError("DB down"))

        response = client.get("/playlist/DEVICE123/1.m3u")

        assert response.status_code == 500
        body = response.json()
        assert body.get("type") == "server_error" or body.get("status") == 500

    def test_m3u_station_name_falls_back_to_unknown(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(
                station_name=None, station_url="http://x.com/s.mp3"
            )
        )

        response = client.get("/playlist/DEVICE123/1.m3u")

        assert response.status_code == 200
        assert "Unknown Station" in response.text

    def test_m3u_rejects_preset_number_zero(self, client, mock_preset_service):
        response = client.get("/playlist/DEVICE123/0.m3u")

        assert response.status_code == 422

    def test_m3u_rejects_preset_number_seven(self, client, mock_preset_service):
        response = client.get("/playlist/DEVICE123/7.m3u")

        assert response.status_code == 422

    def test_m3u_all_valid_preset_numbers(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        for n in range(1, 7):
            response = client.get(f"/playlist/DEVICE123/{n}.m3u")
            assert response.status_code == 200, f"preset {n} should be valid"

    def test_m3u_passes_correct_args_to_service(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        client.get("/playlist/MY_DEVICE/4.m3u")

        mock_preset_service.get_preset.assert_called_once_with("MY_DEVICE", 4)


# ---------------------------------------------------------------------------
# PLS endpoint
# ---------------------------------------------------------------------------


class TestGetPlaylistPls:
    """Tests for GET /playlist/{device_id}/{preset_number}.pls"""

    def test_pls_returns_200_with_correct_content_type(
        self, client, mock_preset_service
    ):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        response = client.get("/playlist/DEVICE123/1.pls")

        assert response.status_code == 200
        assert "audio/x-scpls" in response.headers["content-type"]

    def test_pls_body_format(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(
                station_name="Jazz FM",
                station_url="http://jazz.stream/live.aac",
            )
        )

        response = client.get("/playlist/DEVICE123/2.pls")

        assert response.status_code == 200
        body = response.text
        assert "[playlist]" in body
        assert "File1=http://jazz.stream/live.aac" in body
        assert "Title1=Jazz FM" in body
        assert "Length1=-1" in body
        assert "NumberOfEntries=1" in body
        assert "Version=2" in body

    def test_pls_cache_control_header(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        response = client.get("/playlist/DEVICE123/1.pls")

        assert "no-cache" in response.headers.get("cache-control", "")

    def test_pls_content_disposition_header(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(preset_number=5)
        )

        response = client.get("/playlist/DEVICE123/5.pls")

        disposition = response.headers.get("content-disposition", "")
        assert "preset5.pls" in disposition

    def test_pls_404_when_preset_not_found(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=None)

        response = client.get("/playlist/DEVICE123/1.pls")

        assert response.status_code == 404
        body = response.json()
        assert body.get("type") == "not_found" or body.get("status") == 404

    def test_pls_500_when_no_stream_url(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(station_url=None)
        )

        response = client.get("/playlist/DEVICE123/1.pls")

        assert response.status_code == 500
        body = response.json()
        assert body.get("type") == "server_error" or body.get("status") == 500

    def test_pls_500_on_unexpected_exception(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(side_effect=ValueError("bad data"))

        response = client.get("/playlist/DEVICE123/1.pls")

        assert response.status_code == 500
        body = response.json()
        assert body.get("type") == "server_error" or body.get("status") == 500

    def test_pls_station_name_falls_back_to_unknown(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(
            return_value=_make_preset(
                station_name=None, station_url="http://x.com/s.mp3"
            )
        )

        response = client.get("/playlist/DEVICE123/1.pls")

        assert response.status_code == 200
        assert "Unknown Station" in response.text

    def test_pls_rejects_preset_number_zero(self, client, mock_preset_service):
        response = client.get("/playlist/DEVICE123/0.pls")

        assert response.status_code == 422

    def test_pls_rejects_preset_number_seven(self, client, mock_preset_service):
        response = client.get("/playlist/DEVICE123/7.pls")

        assert response.status_code == 422

    def test_pls_all_valid_preset_numbers(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        for n in range(1, 7):
            response = client.get(f"/playlist/DEVICE123/{n}.pls")
            assert response.status_code == 200, f"preset {n} should be valid"

    def test_pls_passes_correct_args_to_service(self, client, mock_preset_service):
        mock_preset_service.get_preset = AsyncMock(return_value=_make_preset())

        client.get("/playlist/DEVICE123/6.pls")

        mock_preset_service.get_preset.assert_called_once_with("DEVICE123", 6)
