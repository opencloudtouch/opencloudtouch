"""Unit tests for BMX Registry and Custom Stream endpoints."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from opencloudtouch.bmx.routes import bmx_services, custom_stream_playback


class TestBmxRegistry:
    """Unit tests for BMX services registry endpoint."""

    @pytest.mark.asyncio
    async def test_bmx_services_default_url(self):
        """Test registry returns services with default OCT URL."""
        # Act
        result = await bmx_services()

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 200

        # Parse response content
        content = json.loads(result.body.decode())
        assert "bmx_services" in content
        assert len(content["bmx_services"]) == 2

        # Check TUNEIN service
        tunein = next(s for s in content["bmx_services"] if s["id"]["name"] == "TUNEIN")
        assert tunein["assets"]["name"] == "TuneIn"
        assert "liveRadio" in tunein["streamTypes"]

        # Check LOCAL_INTERNET_RADIO service
        local = next(
            s
            for s in content["bmx_services"]
            if s["id"]["name"] == "LOCAL_INTERNET_RADIO"
        )
        assert local["assets"]["name"] == "Custom Stations"
        assert "liveRadio" in local["streamTypes"]

    @pytest.mark.asyncio
    async def test_bmx_services_custom_url(self):
        """Test registry uses custom OCT_BACKEND_URL if set."""
        # Arrange
        custom_url = "http://192.168.1.100:8888"

        with patch.dict("os.environ", {"OCT_BACKEND_URL": custom_url}):
            # Act
            result = await bmx_services()

            # Assert
            content = json.loads(result.body.decode())
            tunein = next(
                s for s in content["bmx_services"] if s["id"]["name"] == "TUNEIN"
            )
            assert tunein["baseUrl"] == f"{custom_url}/bmx/tunein"

            local = next(
                s
                for s in content["bmx_services"]
                if s["id"]["name"] == "LOCAL_INTERNET_RADIO"
            )
            assert local["baseUrl"].startswith(custom_url)


class TestCustomStreamPlayback:
    """Unit tests for custom stream playback (Orion adapter)."""

    @pytest.mark.asyncio
    async def test_custom_stream_success(self):
        """Test successful custom stream playback."""
        # Arrange
        stream_data = {
            "streamUrl": "http://example.com/stream.mp3",
            "imageUrl": "https://example.com/logo.png",
            "name": "My Custom Station",
        }
        json_str = json.dumps(stream_data)
        encoded_data = base64.urlsafe_b64encode(json_str.encode()).decode()

        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"data": encoded_data}

        # Act
        result = await custom_stream_playback(mock_request)

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 200

        content = json.loads(result.body.decode())
        assert content["name"] == "My Custom Station"
        assert content["imageUrl"] == "https://example.com/logo.png"
        assert content["audio"]["streamUrl"] == "http://example.com/stream.mp3"
        assert content["streamType"] == "liveRadio"
        assert len(content["audio"]["streams"]) == 1
        assert (
            content["audio"]["streams"][0]["streamUrl"]
            == "http://example.com/stream.mp3"
        )

    @pytest.mark.asyncio
    async def test_custom_stream_minimal_data(self):
        """Test custom stream with minimal data (no image)."""
        # Arrange
        stream_data = {
            "streamUrl": "http://minimal.com/stream.mp3",
        }
        json_str = json.dumps(stream_data)
        encoded_data = base64.urlsafe_b64encode(json_str.encode()).decode()

        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"data": encoded_data}

        # Act
        result = await custom_stream_playback(mock_request)

        # Assert
        assert result.status_code == 200
        content = json.loads(result.body.decode())
        assert content["name"] == "Custom Station"  # Default name
        assert content["imageUrl"] == ""
        assert content["audio"]["streamUrl"] == "http://minimal.com/stream.mp3"

    @pytest.mark.asyncio
    async def test_custom_stream_missing_data_param(self):
        """Test error when data parameter is missing."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}

        # Act
        result = await custom_stream_playback(mock_request)

        # Assert
        assert result.status_code == 400
        content = json.loads(result.body.decode())
        assert "error" in content
        assert "Missing data parameter" in content["error"]

    @pytest.mark.asyncio
    async def test_custom_stream_invalid_base64(self):
        """Test error handling for invalid base64."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"data": "not-valid-base64!!!"}

        # Act
        result = await custom_stream_playback(mock_request)

        # Assert
        assert result.status_code == 500
        content = json.loads(result.body.decode())
        assert "error" in content

    @pytest.mark.asyncio
    async def test_custom_stream_invalid_json(self):
        """Test error handling for invalid JSON."""
        # Arrange
        invalid_json = "This is not JSON"
        encoded_data = base64.urlsafe_b64encode(invalid_json.encode()).decode()

        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"data": encoded_data}

        # Act
        result = await custom_stream_playback(mock_request)

        # Assert
        assert result.status_code == 500
        content = json.loads(result.body.decode())
        assert "error" in content

    @pytest.mark.asyncio
    async def test_custom_stream_with_special_characters(self):
        """Test custom stream with special characters in name."""
        # Arrange
        stream_data = {
            "streamUrl": "http://example.com/ström.mp3",
            "name": "Müller's Rädio Stätiön",
        }
        json_str = json.dumps(stream_data)
        encoded_data = base64.urlsafe_b64encode(json_str.encode()).decode()

        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"data": encoded_data}

        # Act
        result = await custom_stream_playback(mock_request)

        # Assert
        assert result.status_code == 200
        content = json.loads(result.body.decode())
        assert content["name"] == "Müller's Rädio Stätiön"
        assert content["audio"]["streamUrl"] == "http://example.com/ström.mp3"
