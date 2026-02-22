"""Unit tests for BMX TuneIn playback resolution."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.responses import JSONResponse

from opencloudtouch.bmx.routes import (
    resolve_tunein_station,
    bmx_tunein_playback,
    BmxPlaybackResponse,
    BmxAudio,
    BmxStream,
)


class TestResolveTuneInStation:
    """Unit tests for resolve_tunein_station function."""

    @pytest.mark.asyncio
    async def test_resolve_station_success(self):
        """Test successful TuneIn station resolution."""
        # Arrange
        station_id = "s158432"
        describe_xml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1">
  <body>
    <outline>
      <station>
        <name>Absolut Relax</name>
        <logo>https://cdn-radiotime-logos.tunein.com/s158432q.png</logo>
      </station>
    </outline>
  </body>
</opml>"""
        stream_urls = (
            "http://stream.example.com/relax.mp3\nhttp://backup.example.com/relax.aac"
        )

        mock_response_describe = MagicMock()
        mock_response_describe.text = describe_xml

        mock_response_stream = MagicMock()
        mock_response_stream.text = stream_urls

        with patch("opencloudtouch.bmx.routes.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=[mock_response_describe, mock_response_stream]
            )
            mock_client.return_value = mock_context

            # Act
            result = await resolve_tunein_station(station_id)

            # Assert
            assert isinstance(result, BmxPlaybackResponse)
            assert result.name == "Absolut Relax"
            assert (
                result.imageUrl == "https://cdn-radiotime-logos.tunein.com/s158432q.png"
            )
            assert isinstance(result.audio, BmxAudio)
            assert result.audio.streamUrl == "http://stream.example.com/relax.mp3"
            assert len(result.audio.streams) == 2
            assert (
                result.audio.streams[0].streamUrl
                == "http://stream.example.com/relax.mp3"
            )
            assert (
                result.audio.streams[1].streamUrl
                == "http://backup.example.com/relax.aac"
            )
            assert result.streamType == "liveRadio"

    @pytest.mark.asyncio
    async def test_resolve_station_minimal_xml(self):
        """Test resolution with minimal XML (missing logo)."""
        # Arrange
        station_id = "s12345"
        describe_xml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1">
  <body>
    <outline>
      <station>
        <name>Test Radio</name>
      </station>
    </outline>
  </body>
</opml>"""
        stream_urls = "http://stream.test.com/radio.mp3"

        mock_response_describe = MagicMock()
        mock_response_describe.text = describe_xml

        mock_response_stream = MagicMock()
        mock_response_stream.text = stream_urls

        with patch("opencloudtouch.bmx.routes.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=[mock_response_describe, mock_response_stream]
            )
            mock_client.return_value = mock_context

            # Act
            result = await resolve_tunein_station(station_id)

            # Assert
            assert result.name == "Test Radio"
            assert result.imageUrl == ""
            assert result.audio.streamUrl == "http://stream.test.com/radio.mp3"
            assert len(result.audio.streams) == 1

    @pytest.mark.asyncio
    async def test_resolve_station_no_streams(self):
        """Test error when no stream URLs returned."""
        # Arrange
        station_id = "s99999"
        describe_xml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1">
  <body>
    <outline>
      <station>
        <name>Empty Station</name>
      </station>
    </outline>
  </body>
</opml>"""
        stream_urls = ""  # Empty response

        mock_response_describe = MagicMock()
        mock_response_describe.text = describe_xml

        mock_response_stream = MagicMock()
        mock_response_stream.text = stream_urls

        with patch("opencloudtouch.bmx.routes.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=[mock_response_describe, mock_response_stream]
            )
            mock_client.return_value = mock_context

            # Act & Assert
            with pytest.raises(ValueError, match="No stream URLs found"):
                await resolve_tunein_station(station_id)

    @pytest.mark.asyncio
    async def test_resolve_station_invalid_xml(self):
        """Test error handling for invalid XML."""
        # Arrange
        station_id = "s12345"
        invalid_xml = "This is not XML"

        mock_response = MagicMock()
        mock_response.text = invalid_xml

        with patch("opencloudtouch.bmx.routes.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            # Act & Assert
            with pytest.raises(Exception):  # ElementTree.ParseError or similar
                await resolve_tunein_station(station_id)

    @pytest.mark.asyncio
    async def test_resolve_station_malformed_xml_structure(self):
        """Test handling of XML with unexpected structure."""
        # Arrange
        station_id = "s12345"
        malformed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1">
  <body>
    <!-- Missing outline/station elements -->
  </body>
</opml>"""
        stream_urls = "http://stream.test.com/radio.mp3"

        mock_response_describe = MagicMock()
        mock_response_describe.text = malformed_xml

        mock_response_stream = MagicMock()
        mock_response_stream.text = stream_urls

        with patch("opencloudtouch.bmx.routes.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=[mock_response_describe, mock_response_stream]
            )
            mock_client.return_value = mock_context

            # Act
            result = await resolve_tunein_station(station_id)

            # Assert - should fallback to defaults
            assert result.name == "Unknown Station"
            assert result.imageUrl == ""

    @pytest.mark.asyncio
    async def test_resolve_station_network_error(self):
        """Test handling of network errors."""
        # Arrange
        station_id = "s12345"

        with patch("opencloudtouch.bmx.routes.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Network timeout")
            )
            mock_client.return_value = mock_context

            # Act & Assert
            with pytest.raises(Exception, match="Network timeout"):
                await resolve_tunein_station(station_id)


class TestBmxTuneInPlaybackEndpoint:
    """Unit tests for bmx_tunein_playback endpoint."""

    @pytest.mark.asyncio
    async def test_tunein_playback_success(self):
        """Test successful endpoint call."""
        # Arrange
        station_id = "s158432"
        mock_response = BmxPlaybackResponse(
            audio=BmxAudio(
                streamUrl="http://stream.example.com/test.mp3",
                streams=[BmxStream(streamUrl="http://stream.example.com/test.mp3")],
            ),
            imageUrl="https://example.com/logo.png",
            name="Test Station",
        )

        with patch(
            "opencloudtouch.bmx.routes.resolve_tunein_station",
            AsyncMock(return_value=mock_response),
        ):
            # Act
            result = await bmx_tunein_playback(station_id)

            # Assert
            assert isinstance(result, JSONResponse)
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_tunein_playback_error(self):
        """Test error handling in endpoint."""
        # Arrange
        station_id = "s99999"

        with patch(
            "opencloudtouch.bmx.routes.resolve_tunein_station",
            AsyncMock(side_effect=Exception("TuneIn API unavailable")),
        ):
            # Act
            result = await bmx_tunein_playback(station_id)

            # Assert
            assert isinstance(result, JSONResponse)
            assert result.status_code == 500
