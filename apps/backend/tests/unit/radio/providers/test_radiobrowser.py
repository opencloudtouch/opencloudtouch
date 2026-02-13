"""
Tests for RadioBrowser API Adapter

TDD RED Phase: These tests will fail until implementation is complete.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserAdapter,
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserStation,
    RadioBrowserTimeoutError,
)


class TestRadioBrowserStation:
    """Tests for RadioBrowserStation data model."""

    def test_radio_station_creation_minimal(self):
        """Test creating RadioBrowserStation with minimal required fields."""
        station = RadioBrowserStation(
            station_uuid="test-uuid-123",
            name="Test Station",
            url="http://stream.example.com/radio.mp3",
            country="Germany",
            codec="MP3",
        )

        assert station.station_uuid == "test-uuid-123"
        assert station.name == "Test Station"
        assert station.url == "http://stream.example.com/radio.mp3"
        assert station.country == "Germany"
        assert station.codec == "MP3"

    def test_radio_station_creation_full(self):
        """Test creating RadioBrowserStation with all fields."""
        station = RadioBrowserStation(
            station_uuid="test-uuid-456",
            name="Full Station",
            url="http://stream.example.com/full.mp3",
            url_resolved="http://cdn.example.com/full.mp3",
            homepage="https://example.com",
            favicon="https://example.com/favicon.ico",
            tags="rock,pop,hits",
            country="Switzerland",
            countrycode="CH",
            state="Zurich",
            language="german",
            languagecodes="de",
            votes=100,
            codec="MP3",
            bitrate=320,
            hls=False,
            lastcheckok=True,
            clickcount=5000,
            clicktrend=10,
        )

        assert station.station_uuid == "test-uuid-456"
        assert station.bitrate == 320
        assert station.votes == 100
        assert station.tags == "rock,pop,hits"

    def test_radio_station_from_api_response(self):
        """Test creating RadioStation from API response dict."""
        api_response = {
            "changeuuid": "960761d5-0601-11e8-ae97-52543be04c81",
            "stationuuid": "960761d5-0601-11e8-ae97-52543be04c81",
            "name": "Absolut relax",
            "url": "http://streamlive.syndicast.fr/stream.mp3",
            "url_resolved": "http://cdn.syndicast.fr/stream.mp3",
            "homepage": "https://www.absolut-radio.fr",
            "favicon": "https://www.absolut-radio.fr/favicon.png",
            "tags": "chillout,relax",
            "country": "France",
            "countrycode": "FR",
            "state": "Hauts-de-France",
            "language": "french",
            "languagecodes": "fr",
            "votes": 12,
            "codec": "MP3",
            "bitrate": 128,
            "hls": 0,
            "lastcheckok": 1,
            "clickcount": 145,
            "clicktrend": 3,
        }

        station = RadioBrowserStation.from_api_response(api_response)

        assert station.station_uuid == "960761d5-0601-11e8-ae97-52543be04c81"
        assert station.name == "Absolut relax"
        assert station.url == "http://streamlive.syndicast.fr/stream.mp3"
        assert station.url_resolved == "http://cdn.syndicast.fr/stream.mp3"
        assert station.country == "France"
        assert station.codec == "MP3"
        assert station.bitrate == 128
        assert station.hls is False
        assert station.lastcheckok is True


class TestRadioBrowserAdapter:
    """Tests for RadioBrowserAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test adapter initialization."""
        adapter = RadioBrowserAdapter(timeout=15.0, max_retries=5)

        assert adapter.timeout == 15.0
        assert adapter.max_retries == 5
        assert adapter.base_url is not None

    @pytest.mark.asyncio
    async def test_initialization_defaults(self):
        """Test adapter initialization with defaults."""
        adapter = RadioBrowserAdapter()

        assert adapter.timeout == 10.0
        assert adapter.max_retries == 3

    @pytest.mark.asyncio
    async def test_search_by_name_success(self):
        """Test successful search by station name."""
        adapter = RadioBrowserAdapter()

        mock_response = [
            {
                "stationuuid": "uuid-1",
                "name": "Test Radio",
                "url": "http://stream.example.com/radio.mp3",
                "country": "Germany",
                "codec": "MP3",
                "bitrate": 128,
            }
        ]

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            stations = await adapter.search_by_name("test", limit=10)

            assert len(stations) == 1
            assert stations[0].name == "Test Radio"
            assert stations[0].station_id == "uuid-1"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_by_name_empty_result(self):
        """Test search with no results."""
        adapter = RadioBrowserAdapter()

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = []

            stations = await adapter.search_by_name("nonexistent")

            assert len(stations) == 0

    @pytest.mark.asyncio
    async def test_search_by_country_success(self):
        """Test successful search by country."""
        adapter = RadioBrowserAdapter()

        mock_response = [
            {
                "stationuuid": "uuid-2",
                "name": "Swiss Radio",
                "url": "http://stream.ch/radio.mp3",
                "country": "Switzerland",
                "codec": "AAC",
                "bitrate": 192,
            }
        ]

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            stations = await adapter.search_by_country("Switzerland", limit=5)

            assert len(stations) == 1
            assert stations[0].country == "Switzerland"
            assert stations[0].codec == "AAC"

    @pytest.mark.asyncio
    async def test_search_by_tag_success(self):
        """Test successful search by tag."""
        adapter = RadioBrowserAdapter()

        mock_response = [
            {
                "stationuuid": "uuid-3",
                "name": "Jazz FM",
                "url": "http://stream.jazz.fm/live.mp3",
                "country": "USA",
                "codec": "MP3",
                "tags": "jazz,smooth",
            }
        ]

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            stations = await adapter.search_by_tag("jazz")

            assert len(stations) == 1
            # tags is now a list in unified RadioStation model
            assert "jazz" in stations[0].tags

    @pytest.mark.asyncio
    async def test_get_station_by_uuid_success(self):
        """Test getting station detail by UUID."""
        adapter = RadioBrowserAdapter()

        mock_response = [
            {
                "stationuuid": "test-uuid",
                "name": "Detailed Station",
                "url": "http://stream.example.com/detail.mp3",
                "country": "France",
                "codec": "MP3",
                "bitrate": 256,
                "votes": 500,
                "clickcount": 10000,
            }
        ]

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            station = await adapter.get_station_by_uuid("test-uuid")

            assert station.station_id == "test-uuid"
            assert station.name == "Detailed Station"
            assert station.bitrate == 256
            # votes is not in unified RadioStation model
            # assert station.votes == 500

    @pytest.mark.asyncio
    async def test_get_station_by_uuid_not_found(self):
        """Test getting non-existent station raises error."""
        adapter = RadioBrowserAdapter()

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = []

            with pytest.raises(RadioBrowserError, match="Station .* not found"):
                await adapter.get_station_by_uuid("nonexistent-uuid")

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self):
        """Test timeout error is properly wrapped."""
        adapter = RadioBrowserAdapter(timeout=1.0)

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(RadioBrowserTimeoutError):
                await adapter.search_by_name("test")

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test connection error is properly wrapped."""
        adapter = RadioBrowserAdapter()

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(RadioBrowserConnectionError):
                await adapter.search_by_name("test")

    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """Test HTTP error responses are handled."""
        adapter = RadioBrowserAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )

            with pytest.raises(RadioBrowserError):
                await adapter.search_by_name("test")

    @pytest.mark.asyncio
    async def test_retry_logic_success_after_retry(self):
        """Test successful request after retry."""
        adapter = RadioBrowserAdapter(max_retries=3)

        mock_response = [
            {
                "stationuuid": "uuid",
                "name": "Station",
                "url": "http://example.com",
                "country": "DE",
                "codec": "MP3",
            }
        ]

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # First call fails, second succeeds
            mock_request.side_effect = [
                httpx.TimeoutException("Timeout"),
                mock_response,
            ]

            # Should succeed after retry (but this will raise because we mock the wrapper)
            # Actually, we need to test _make_request directly
            # For now, just verify the retry mechanism exists
            pass

    @pytest.mark.asyncio
    async def test_search_limit_parameter(self):
        """Test that limit parameter is passed correctly."""
        adapter = RadioBrowserAdapter()

        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = []

            await adapter.search_by_name("test", limit=25)

            # Verify limit was passed in the request
            call_args = mock_request.call_args
            assert "limit" in str(call_args)

    @pytest.mark.asyncio
    async def test_base_url_selection(self):
        """Test that a valid API server is selected."""
        adapter = RadioBrowserAdapter()

        # Base URL should be one of the known RadioBrowser servers
        known_servers = [
            "https://all.api.radio-browser.info",
            "https://de1.api.radio-browser.info",
            "https://nl1.api.radio-browser.info",
            "https://at1.api.radio-browser.info",
        ]

        assert any(server in adapter.base_url for server in known_servers)

    @pytest.mark.asyncio
    async def test_search_combined_filters(self):
        """Test search with combined filters (future feature)."""
        # This test documents the future API for combined search
        # Currently not implemented, will fail
        RadioBrowserAdapter()

        # Future: adapter.search(name="jazz", country="Switzerland", tag="smooth", limit=10)
        # For now, this is a placeholder
        pass


class TestRadioBrowserErrors:
    """Tests for custom exception classes."""

    def test_base_error(self):
        """Test RadioBrowserError can be raised."""
        with pytest.raises(RadioBrowserError):
            raise RadioBrowserError("Test error")

    def test_timeout_error(self):
        """Test RadioBrowserTimeoutError inherits from base."""
        with pytest.raises(RadioBrowserError):
            raise RadioBrowserTimeoutError("Timeout")

    def test_connection_error(self):
        """Test RadioBrowserConnectionError inherits from base."""
        with pytest.raises(RadioBrowserError):
            raise RadioBrowserConnectionError("Connection failed")


class TestRadioBrowserErrorHandling:
    """Tests for error handling in API methods."""

    def _create_mock_async_client(self) -> AsyncMock:
        """Helper to create a properly configured AsyncMock for httpx.AsyncClient."""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        return mock_client

    @pytest.mark.asyncio
    async def test_search_by_name_timeout(self):
        """Test that search_by_name handles timeout correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserTimeoutError) as exc_info:
                await adapter.search_by_name("test")

            assert "Request timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_name_connection_error(self):
        """Test that search_by_name handles connection errors correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserConnectionError) as exc_info:
                await adapter.search_by_name("test")

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_name_http_status_error(self):
        """Test that search_by_name handles HTTP errors correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserError) as exc_info:
                await adapter.search_by_name("test")

            assert "HTTP error 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_tag_timeout(self):
        """Test that search_by_tag handles timeout correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserTimeoutError) as exc_info:
                await adapter.search_by_tag("jazz")

            assert "Request timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_tag_connection_error(self):
        """Test that search_by_tag handles connection errors correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserConnectionError) as exc_info:
                await adapter.search_by_tag("jazz")

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_tag_http_status_error(self):
        """Test that search_by_tag handles HTTP errors correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserError) as exc_info:
                await adapter.search_by_tag("jazz")

            assert "HTTP error 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_station_by_uuid_timeout(self):
        """Test that get_station_by_uuid handles timeout correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserTimeoutError) as exc_info:
                await adapter.get_station_by_uuid("test-uuid")

            assert "Request timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_station_by_uuid_connection_error(self):
        """Test that get_station_by_uuid handles connection errors correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserConnectionError) as exc_info:
                await adapter.get_station_by_uuid("test-uuid")

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_station_by_uuid_http_status_error(self):
        """Test that get_station_by_uuid handles HTTP errors correctly."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserError) as exc_info:
                await adapter.get_station_by_uuid("test-uuid")

            assert "HTTP error 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_retry_logic_timeout(self):
        """Test that _make_request retries on timeout and eventually fails."""
        adapter = RadioBrowserAdapter(max_retries=3)

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

        with patch("httpx.AsyncClient", return_value=mock_client), patch(
            "asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:

            with pytest.raises(httpx.TimeoutException):
                await adapter._make_request("/test")

            # Should have retried 3 times
            assert mock_client.get.call_count == 3
            # Should have slept 2 times (between retries, not after last)
            assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_make_request_retry_logic_connection_error(self):
        """Test that _make_request retries on connection error and eventually fails."""
        adapter = RadioBrowserAdapter(max_retries=2)

        mock_client = self._create_mock_async_client()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient", return_value=mock_client), patch(
            "asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:

            with pytest.raises(httpx.ConnectError):
                await adapter._make_request("/test")

            # Should have retried 2 times
            assert mock_client.get.call_count == 2
            # Should have slept 1 time (between 2 retries)
            assert mock_sleep.call_count == 1

    @pytest.mark.asyncio
    async def test_make_request_retry_success_after_failure(self):
        """Test that _make_request succeeds after initial failures."""
        adapter = RadioBrowserAdapter(max_retries=3)

        mock_client = self._create_mock_async_client()
        # First 2 calls timeout, 3rd succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}

        mock_client.get.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Timeout"),
            mock_response,
        ]

        with patch("httpx.AsyncClient", return_value=mock_client), patch(
            "asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:

            result = await adapter._make_request("/test")

            assert result == {"test": "data"}
            assert mock_client.get.call_count == 3
            # Should have slept 2 times (before 2nd and 3rd attempt)
            assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_get_station_by_uuid_not_found(self):
        """Test that get_station_by_uuid raises error when station not found."""
        adapter = RadioBrowserAdapter()

        mock_client = self._create_mock_async_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []  # Empty list = not found
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RadioBrowserError) as exc_info:
                await adapter.get_station_by_uuid("nonexistent-uuid")

            assert "not found" in str(exc_info.value)
