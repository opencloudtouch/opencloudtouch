"""Unit tests for preset stream and descriptor routes.

Covers:
- GET /device/{device_id}/preset/{preset_id}  — HTTP proxy stream
- GET /descriptor/device/{device_id}/preset/{preset_id} — XML/redirect descriptor
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_device_state_manager, get_preset_service
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.main import app
from opencloudtouch.presets.models import Preset


@pytest.fixture
def mock_preset_service():
    """Mock preset service."""
    return AsyncMock()


@pytest.fixture
def state_manager():
    """Real DeviceStateManager so tests can simulate now-playing transitions."""
    return DeviceStateManager()


@pytest.fixture
def client(mock_preset_service, state_manager):
    """TestClient with preset service + device state manager dependency overrides."""
    app.dependency_overrides[get_preset_service] = lambda: mock_preset_service
    app.dependency_overrides[get_device_state_manager] = lambda: state_manager
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_preset():
    """Sample configured preset."""
    return Preset(
        device_id="689E194F7D2F",
        preset_number=1,
        station_uuid="station-uuid-1234",
        station_name="Absolut Relax",
        station_url="https://stream.absolutradio.de/absolut-relax",
    )


class TestStreamDevicePreset:
    """Tests for GET /device/{device_id}/preset/{preset_id}."""

    def test_preset_not_found_returns_404(self, client, mock_preset_service):
        """Test 404 when preset not configured for device."""
        mock_preset_service.get_preset = AsyncMock(return_value=None)

        response = client.get("/device/UNKNOWN/preset/1")

        assert response.status_code == 404

    def test_stream_returns_streaming_response(
        self, client, mock_preset_service, sample_preset
    ):
        """Test successful stream returns 200 with audio/mpeg content type."""
        mock_preset_service.get_preset = AsyncMock(return_value=sample_preset)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.aclose = AsyncMock()

        async def mock_aiter_bytes(chunk_size=8192):
            yield b"audio_data_chunk_1"
            yield b"audio_data_chunk_2"

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_http_client = MagicMock()
        mock_http_client.send = AsyncMock(return_value=mock_response)
        mock_http_client.aclose = AsyncMock()

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.httpx.AsyncClient",
            return_value=mock_http_client,
        ), patch(
            "opencloudtouch.devices.api.preset_stream_routes.validate_stream_url",
        ):
            with client.stream("GET", "/device/689E194F7D2F/preset/1") as response:
                assert response.status_code == 200
                assert "audio" in response.headers.get("content-type", "")

    def test_stream_stops_when_device_no_longer_playing(
        self, client, mock_preset_service, sample_preset, state_manager
    ):
        """#416: once the device's now-playing state moves away from this
        preset (e.g. the user pressed Stop), the proxy must stop pulling
        from upstream instead of forwarding bytes forever."""
        mock_preset_service.get_preset = AsyncMock(return_value=sample_preset)
        device_id = sample_preset.device_id
        state_manager.update_now_playing(
            device_id,
            NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name=sample_preset.station_name,
            ),
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.aclose = AsyncMock()

        async def mock_aiter_bytes(chunk_size=8192):
            yield b"chunk_1"
            # Simulate the user pressing Stop mid-stream.
            state_manager.update_now_playing(
                device_id, NowPlayingInfo(source="STANDBY", state="STOP_STATE")
            )
            yield b"chunk_2"

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_http_client = MagicMock()
        mock_http_client.send = AsyncMock(return_value=mock_response)
        mock_http_client.aclose = AsyncMock()

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.httpx.AsyncClient",
            return_value=mock_http_client,
        ), patch(
            "opencloudtouch.devices.api.preset_stream_routes.validate_stream_url",
        ):
            with client.stream("GET", f"/device/{device_id}/preset/1") as response:
                body = b"".join(response.iter_bytes())

        assert body == b"chunk_1"
        mock_response.aclose.assert_awaited_once()
        mock_http_client.aclose.assert_awaited_once()

    def test_upstream_non_200_raises_502(
        self, client, mock_preset_service, sample_preset
    ):
        """Test 502 when upstream RadioBrowser returns non-200."""
        mock_preset_service.get_preset = AsyncMock(return_value=sample_preset)

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.headers = {}
        mock_response.aclose = AsyncMock()

        mock_http_client = MagicMock()
        mock_http_client.send = AsyncMock(return_value=mock_response)
        mock_http_client.aclose = AsyncMock()

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.httpx.AsyncClient",
            return_value=mock_http_client,
        ), patch(
            "opencloudtouch.devices.api.preset_stream_routes.validate_stream_url",
        ):
            response = client.get("/device/689E194F7D2F/preset/1")
            assert response.status_code == 502

    def test_httpx_request_error_raises_502(
        self, client, mock_preset_service, sample_preset
    ):
        """Test 502 when httpx.RequestError occurs connecting to upstream."""
        import httpx

        mock_preset_service.get_preset = AsyncMock(return_value=sample_preset)

        mock_http_client = MagicMock()
        mock_http_client.send = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_http_client.aclose = AsyncMock()

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.httpx.AsyncClient",
            return_value=mock_http_client,
        ), patch(
            "opencloudtouch.devices.api.preset_stream_routes.validate_stream_url",
        ):
            response = client.get("/device/689E194F7D2F/preset/1")
            assert response.status_code == 502


class TestValidateStreamUrl:
    """Tests for validate_stream_url SSRF protection."""

    def test_rejects_ftp_scheme(self):
        from opencloudtouch.devices.api.preset_stream_routes import validate_stream_url

        with pytest.raises(Exception) as exc_info:
            validate_stream_url("ftp://evil.com/stream")
        assert exc_info.value.status_code == 400

    def test_rejects_loopback(self):
        from opencloudtouch.devices.api.preset_stream_routes import validate_stream_url

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("127.0.0.1", 0))],
        ):
            with pytest.raises(Exception) as exc_info:
                validate_stream_url("https://evil.com/stream")
            assert exc_info.value.status_code == 400

    def test_rejects_link_local(self):
        from opencloudtouch.devices.api.preset_stream_routes import validate_stream_url

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("169.254.1.1", 0))],
        ):
            with pytest.raises(Exception) as exc_info:
                validate_stream_url("https://evil.com/stream")
            assert exc_info.value.status_code == 400

    def test_rejects_unresolvable_hostname(self):
        import socket as _socket

        from opencloudtouch.devices.api.preset_stream_routes import validate_stream_url

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.socket.getaddrinfo",
            side_effect=_socket.gaierror("Name resolution failed"),
        ):
            with pytest.raises(Exception) as exc_info:
                validate_stream_url("https://nonexistent.invalid/stream")
            assert exc_info.value.status_code == 400

    def test_allows_valid_public_url(self):
        from opencloudtouch.devices.api.preset_stream_routes import validate_stream_url

        with patch(
            "opencloudtouch.devices.api.preset_stream_routes.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("93.184.216.34", 0))],
        ):
            validate_stream_url("https://stream.example.com/audio.mp3")


class TestGetPresetDescriptor:
    """Tests for GET /descriptor/device/{device_id}/preset/{preset_id}."""

    def test_descriptor_found_returns_302_redirect(
        self, client, mock_preset_service, sample_preset
    ):
        """Test descriptor returns 302 redirect to stream URL."""
        mock_preset_service.get_preset = AsyncMock(return_value=sample_preset)

        response = client.get(
            "/descriptor/device/689E194F7D2F/preset/1",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["location"] == sample_preset.station_url

    def test_descriptor_not_found_returns_404(self, client, mock_preset_service):
        """Test descriptor returns 404 when preset not configured."""
        mock_preset_service.get_preset = AsyncMock(return_value=None)

        response = client.get(
            "/descriptor/device/UNKNOWN/preset/1",
            follow_redirects=False,
        )

        assert response.status_code == 404
