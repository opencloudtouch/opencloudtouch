"""Unit tests for BMX Orion adapter (LOCAL_INTERNET_RADIO playback).

This module tests the custom stream playback functionality that enables
preset playback after the Bose Cloud shutdown.

Tested endpoint:
    GET /core02/svc-bmx-adapter-orion/prod/orion/station?data={base64}
"""

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.bmx.models import BmxAudio, BmxPlaybackResponse, BmxStream
from opencloudtouch.bmx.routes import router


@pytest.fixture
def app():
    """Create FastAPI app with BMX router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def encode_stream_data(stream_url: str, name: str, image_url: str = "") -> str:
    """Helper to encode stream data as base64."""
    data = {
        "streamUrl": stream_url,
        "name": name,
        "imageUrl": image_url,
    }
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


class TestOrionStationPlayback:
    """Unit tests for /core02/svc-bmx-adapter-orion/prod/orion/station endpoint."""

    def test_valid_stream_returns_playback_response(self, client):
        """Test successful stream resolution with valid base64 data."""
        # Arrange
        stream_url = (
            "http://absolut-relax.live-sm.absolutradio.de/absolut-relax/stream/mp3"
        )
        name = "Absolut Relax"
        image_url = "https://example.com/logo.png"
        data = encode_stream_data(stream_url, name, image_url)

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == name
        assert body["imageUrl"] == image_url
        assert body["streamType"] == "liveRadio"
        assert body["audio"]["streamUrl"] == stream_url
        assert len(body["audio"]["streams"]) == 1
        assert body["audio"]["streams"][0]["streamUrl"] == stream_url

    def test_minimal_stream_data(self, client):
        """Test resolution with minimal data (no imageUrl)."""
        # Arrange
        stream_url = "http://stream.example.com/radio.mp3"
        name = "Test Radio"
        data = encode_stream_data(stream_url, name)

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == name
        assert body["imageUrl"] == ""
        assert body["audio"]["streamUrl"] == stream_url

    def test_missing_data_parameter_returns_400(self, client):
        """Test that missing data parameter returns 400 error."""
        # Act
        response = client.get("/core02/svc-bmx-adapter-orion/prod/orion/station")

        # Assert
        assert response.status_code == 400
        body = response.json()
        assert "error" in body
        assert "Missing data parameter" in body["error"]

    def test_empty_data_parameter_returns_400(self, client):
        """Test that empty data parameter returns 400 error."""
        # Act
        response = client.get("/core02/svc-bmx-adapter-orion/prod/orion/station?data=")

        # Assert
        assert response.status_code == 400

    def test_invalid_base64_returns_500(self, client):
        """Test that invalid base64 data returns 500 error."""
        # Act
        response = client.get(
            "/core02/svc-bmx-adapter-orion/prod/orion/station?data=not-valid-base64!!!"
        )

        # Assert
        assert response.status_code == 500
        body = response.json()
        assert "error" in body

    def test_invalid_json_returns_500(self, client):
        """Test that valid base64 with invalid JSON returns 500 error."""
        # Arrange
        invalid_json = "this is not json"
        data = base64.urlsafe_b64encode(invalid_json.encode()).decode()

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 500
        body = response.json()
        assert "error" in body

    def test_response_includes_required_audio_fields(self, client):
        """Test that response includes all required audio fields for device."""
        # Arrange
        data = encode_stream_data("http://stream.example.com/radio.mp3", "Test")

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        audio = response.json()["audio"]
        assert "hasPlaylist" in audio
        assert "isRealtime" in audio
        assert "maxTimeout" in audio
        assert "streamUrl" in audio
        assert "streams" in audio
        assert audio["hasPlaylist"] is True
        assert audio["isRealtime"] is True
        assert audio["maxTimeout"] == 60

    def test_response_includes_links(self, client):
        """Test that response includes _links for now_playing and reporting."""
        # Arrange
        data = encode_stream_data("http://stream.example.com/radio.mp3", "Test")

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        # Note: Pydantic model uses links, serialized as _links
        assert "links" in body or "_links" in body

    def test_cors_header_present(self, client):
        """Test that CORS header is present in response."""
        # Arrange
        data = encode_stream_data("http://stream.example.com/radio.mp3", "Test")

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.headers.get("Access-Control-Allow-Origin") == "*"

    def test_default_name_when_missing(self, client):
        """Test that default name is used when not provided."""
        # Arrange
        data_dict = {"streamUrl": "http://stream.example.com/radio.mp3"}
        data = base64.urlsafe_b64encode(json.dumps(data_dict).encode()).decode()

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Custom Station"

    def test_stream_object_includes_required_fields(self, client):
        """Test that stream objects include all required fields."""
        # Arrange
        stream_url = "http://stream.example.com/radio.mp3"
        data = encode_stream_data(stream_url, "Test")

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        stream = response.json()["audio"]["streams"][0]
        assert stream["streamUrl"] == stream_url
        assert stream["hasPlaylist"] is True
        assert stream["isRealtime"] is True

    def test_https_stream_converted_to_http(self, client):
        """Test that HTTPS streams are automatically converted to HTTP.

        Bose SoundTouch devices cannot play HTTPS streams directly.
        The Orion adapter should convert https:// to http://.
        """
        # Arrange - HTTPS stream URL
        https_url = "https://ukw.hoerradar.de/DESNLEJ002APO08920"
        name = "Campusradio Leipzig"
        data = encode_stream_data(https_url, name)

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert - URL should be converted to HTTP
        assert response.status_code == 200
        body = response.json()
        assert (
            body["audio"]["streamUrl"] == "http://ukw.hoerradar.de/DESNLEJ002APO08920"
        )
        assert (
            body["audio"]["streams"][0]["streamUrl"]
            == "http://ukw.hoerradar.de/DESNLEJ002APO08920"
        )

    def test_http_stream_not_modified(self, client):
        """Test that HTTP streams are not modified."""
        # Arrange - HTTP stream URL (should stay unchanged)
        http_url = "http://stream.example.com/radio.mp3"
        name = "Test Radio"
        data = encode_stream_data(http_url, name)

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert - URL should remain HTTP
        assert response.status_code == 200
        body = response.json()
        assert body["audio"]["streamUrl"] == http_url


class TestBmxModels:
    """Unit tests for BMX Pydantic models."""

    def test_bmx_stream_defaults(self):
        """Test BmxStream default values."""
        stream = BmxStream(streamUrl="http://example.com/stream")
        assert stream.hasPlaylist is True
        assert stream.isRealtime is True
        assert stream.maxTimeout == 60
        assert stream.bufferingTimeout == 20
        assert stream.connectingTimeout == 10

    def test_bmx_audio_with_streams(self):
        """Test BmxAudio with multiple streams."""
        streams = [
            BmxStream(streamUrl="http://example.com/stream1.mp3"),
            BmxStream(streamUrl="http://example.com/stream2.aac"),
        ]
        audio = BmxAudio(streamUrl="http://example.com/stream1.mp3", streams=streams)
        assert len(audio.streams) == 2
        assert audio.streams[0].streamUrl == "http://example.com/stream1.mp3"
        assert audio.streams[1].streamUrl == "http://example.com/stream2.aac"

    def test_bmx_playback_response_serialization(self):
        """Test BmxPlaybackResponse JSON serialization."""
        stream = BmxStream(streamUrl="http://example.com/stream")
        audio = BmxAudio(streamUrl="http://example.com/stream", streams=[stream])
        response = BmxPlaybackResponse(
            audio=audio,
            name="Test Station",
            imageUrl="http://example.com/logo.png",
        )

        # Test that model serializes correctly
        data = response.model_dump()
        assert data["name"] == "Test Station"
        assert data["imageUrl"] == "http://example.com/logo.png"
        assert data["streamType"] == "liveRadio"
        assert data["isFavorite"] is False


class TestEncodeDecodeRoundtrip:
    """Test that encoding/decoding stream data works correctly."""

    def test_roundtrip_simple(self, client):
        """Test simple encode/decode roundtrip."""
        # Arrange
        original = {
            "streamUrl": "http://stream.example.com/radio.mp3",
            "name": "My Radio",
            "imageUrl": "http://example.com/logo.png",
        }
        data = base64.urlsafe_b64encode(json.dumps(original).encode()).decode()

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == original["name"]
        assert body["imageUrl"] == original["imageUrl"]
        assert body["audio"]["streamUrl"] == original["streamUrl"]

    def test_roundtrip_with_special_characters(self, client):
        """Test encode/decode with special characters in name."""
        # Arrange
        original = {
            "streamUrl": "http://stream.example.com/radio.mp3",
            "name": "Café Müller – Öffentlich-Rechtlich",
            "imageUrl": "",
        }
        data = base64.urlsafe_b64encode(json.dumps(original).encode()).decode()

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == original["name"]

    def test_roundtrip_with_url_encoding(self, client):
        """Test encode/decode with URL-encoded characters in streamUrl."""
        # Arrange
        original = {
            "streamUrl": "http://stream.example.com/radio?type=mp3&quality=high",
            "name": "Test Radio",
            "imageUrl": "",
        }
        data = base64.urlsafe_b64encode(json.dumps(original).encode()).decode()

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["audio"]["streamUrl"] == original["streamUrl"]


class TestRealWorldStations:
    """Integration-style tests with real radio station data."""

    @pytest.mark.parametrize(
        "name,stream_url",
        [
            (
                "Absolut Relax",
                "http://absolut-relax.live-sm.absolutradio.de/absolut-relax/stream/mp3",
            ),
            (
                "Bayern 3",
                "http://streams.br.de/bayern3_2.m3u",
            ),
            (
                "WDR 2",
                "http://wdr-wdr2-ruhrgebiet.icecast.wdr.de/wdr/wdr2/ruhrgebiet/mp3/128/stream.mp3",
            ),
            (
                "1LIVE",
                "http://wdr-1live-live.icecast.wdr.de/wdr/1live/live/mp3/128/stream.mp3",
            ),
        ],
    )
    def test_german_radio_stations(self, client, name, stream_url):
        """Test that common German radio stations work correctly."""
        # Arrange
        data = encode_stream_data(stream_url, name)

        # Act
        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == name
        assert body["audio"]["streamUrl"] == stream_url


def encode_tunein_data(tunein_id: str, name: str, image_url: str = "") -> str:
    """Helper to encode TuneIn station data as base64 (empty streamUrl + tuneinId)."""
    data = {
        "streamUrl": "",
        "name": name,
        "imageUrl": image_url,
        "tuneinId": tunein_id,
    }
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


class TestOrionTuneInResolution:
    """Tests for dynamic TuneIn stream resolution via Orion adapter."""

    def test_tunein_station_resolves_dynamically(self, client):
        """TuneIn preset with empty streamUrl + tuneinId resolves at playback time."""
        data = encode_tunein_data("s158432", "Absolut Relax")
        mock_response = BmxPlaybackResponse(
            audio=BmxAudio(
                streamUrl="http://stream.absolut.at/relax.mp3",
                streams=[BmxStream(streamUrl="http://stream.absolut.at/relax.mp3")],
            ),
            imageUrl="https://cdn.tunein.com/s158432q.png",
            name="Absolut Relax",
        )

        with patch(
            "opencloudtouch.bmx.routes.resolve_tunein_station",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_resolve:
            response = client.get(
                f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
            )

            assert response.status_code == 200
            body = response.json()
            assert body["audio"]["streamUrl"] == "http://stream.absolut.at/relax.mp3"
            assert body["name"] == "Absolut Relax"
            mock_resolve.assert_called_once_with("s158432")

    def test_tunein_resolution_failure_returns_500(self, client):
        """TuneIn resolution failure returns 500 with error details."""
        data = encode_tunein_data("s999999", "Unknown Station")

        with patch(
            "opencloudtouch.bmx.routes.resolve_tunein_station",
            new_callable=AsyncMock,
            side_effect=ValueError("No stream URLs found for station s999999"),
        ):
            response = client.get(
                f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
            )

            assert response.status_code == 500
            body = response.json()
            assert "error" in body
            assert "TuneIn resolution failed" in body["error"]

    def test_regular_stream_still_works_with_tunein_id_absent(self, client):
        """Regular stream (no tuneinId) continues to work as before."""
        stream_url = "http://stream.example.com/radio.mp3"
        data = encode_stream_data(stream_url, "Normal Radio")

        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["audio"]["streamUrl"] == stream_url

    def test_tunein_id_with_streamurl_uses_streamurl(self, client):
        """When both tuneinId and streamUrl are present, use streamUrl directly."""
        data_dict = {
            "streamUrl": "http://direct.example.com/stream.mp3",
            "name": "Station",
            "imageUrl": "",
            "tuneinId": "s158432",
        }
        data = base64.urlsafe_b64encode(json.dumps(data_dict).encode()).decode()

        response = client.get(
            f"/core02/svc-bmx-adapter-orion/prod/orion/station?data={data}"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["audio"]["streamUrl"] == "http://direct.example.com/stream.mp3"
