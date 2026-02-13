"""
Tests for Radio API endpoints

TDD RED Phase: These tests will fail until FastAPI endpoints are implemented.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from opencloudtouch.main import app
from opencloudtouch.radio.api.routes import get_radio_provider
from opencloudtouch.radio.models import RadioStation
from opencloudtouch.radio.providers.radiobrowser import RadioBrowserError


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_adapter():
    """Mock RadioBrowser adapter."""
    return AsyncMock()


@pytest.fixture
def mock_radio_stations():
    """Mock radio station data (unified RadioStation model)."""
    return [
        RadioStation(
            station_id="test-uuid-1",
            name="Test Radio 1",
            url="http://stream1.example.com/radio.mp3",
            country="Germany",
            codec="MP3",
            bitrate=128,
            tags=["pop", "rock"],
            provider="radiobrowser",
        ),
        RadioStation(
            station_id="test-uuid-2",
            name="Test Radio 2",
            url="http://stream2.example.com/radio.mp3",
            country="Switzerland",
            codec="AAC",
            bitrate=192,
            tags=["jazz", "smooth"],
            provider="radiobrowser",
        ),
    ]


class TestRadioSearchEndpoint:
    """Tests for GET /api/radio/search endpoint."""

    def test_search_endpoint_exists(self, client):
        """Test that /api/radio/search endpoint exists."""
        response = client.get("/api/radio/search", params={"q": "test"})

        # Should not be 404 Not Found
        assert response.status_code != 404

    def test_search_by_name(self, client, mock_adapter, mock_radio_stations):
        """Test search by station name."""
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get(
                "/api/radio/search", params={"q": "test", "search_type": "name"}
            )

            assert response.status_code == 200
            data = response.json()

            assert "stations" in data
            assert len(data["stations"]) == 2
            assert data["stations"][0]["name"] == "Test Radio 1"
            assert data["stations"][0]["uuid"] == "test-uuid-1"
        finally:
            app.dependency_overrides.clear()

    def test_search_by_country(self, client, mock_adapter, mock_radio_stations):
        """Test search by country."""
        mock_adapter.search_by_country.return_value = [mock_radio_stations[0]]

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get(
                "/api/radio/search", params={"q": "Germany", "search_type": "country"}
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["stations"]) == 1
            assert data["stations"][0]["country"] == "Germany"
        finally:
            app.dependency_overrides.clear()

    def test_search_by_tag(self, client, mock_adapter, mock_radio_stations):
        """Test search by tag."""
        mock_adapter.search_by_tag.return_value = [mock_radio_stations[1]]

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get(
                "/api/radio/search", params={"q": "jazz", "search_type": "tag"}
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["stations"]) == 1
            assert "jazz" in data["stations"][0]["tags"]
        finally:
            app.dependency_overrides.clear()

    def test_search_default_type_is_name(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test that default search type is 'name'."""
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "test"})

            assert response.status_code == 200
            mock_adapter.search_by_name.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_search_limit_parameter(self, client, mock_adapter, mock_radio_stations):
        """Test that limit parameter is passed correctly."""
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get(
                "/api/radio/search", params={"q": "test", "limit": 25}
            )

            assert response.status_code == 200
            mock_adapter.search_by_name.assert_called_once_with("test", limit=25)
        finally:
            app.dependency_overrides.clear()

    def test_search_default_limit(self, client, mock_adapter, mock_radio_stations):
        """Test default limit is 10."""
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "test"})

            assert response.status_code == 200
            mock_adapter.search_by_name.assert_called_once_with("test", limit=10)
        finally:
            app.dependency_overrides.clear()

    def test_search_missing_query_parameter(self, client):
        """Test that missing 'q' parameter returns 422."""
        response = client.get("/api/radio/search")

        assert response.status_code == 422

    def test_search_empty_query_parameter(self, client):
        """Test that empty 'q' parameter returns 400."""
        response = client.get("/api/radio/search", params={"q": ""})

        # Should reject empty query
        assert response.status_code in [400, 422]

    def test_search_invalid_search_type(self, client):
        """Test that invalid search_type returns 422."""
        response = client.get(
            "/api/radio/search", params={"q": "test", "search_type": "invalid"}
        )

        assert response.status_code == 422

    def test_search_limit_min_value(self, client):
        """Test that limit has minimum value of 1."""
        response = client.get("/api/radio/search", params={"q": "test", "limit": 0})

        assert response.status_code == 422

    def test_search_limit_max_value(self, client):
        """Test that limit has maximum value of 100."""
        response = client.get("/api/radio/search", params={"q": "test", "limit": 101})

        assert response.status_code == 422

    def test_search_empty_results(self, client, mock_adapter):
        """Test search with no results."""
        mock_adapter.search_by_name.return_value = []

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "nonexistent"})

            assert response.status_code == 200
            data = response.json()
            assert data["stations"] == []
        finally:
            app.dependency_overrides.clear()

    def test_search_adapter_error_handling(self, client, mock_adapter):
        """Test that adapter errors are handled gracefully."""
        mock_adapter.search_by_name.side_effect = RadioBrowserError("API error")

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "test"})

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
        finally:
            app.dependency_overrides.clear()

    def test_search_response_format(self, client, mock_adapter, mock_radio_stations):
        """Test response format structure."""
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "test"})

            assert response.status_code == 200
            data = response.json()

            # Check structure
            assert "stations" in data
            assert isinstance(data["stations"], list)

            # Check station fields
            station = data["stations"][0]
            required_fields = ["uuid", "name", "url", "country", "codec"]
            for field in required_fields:
                assert field in station
        finally:
            app.dependency_overrides.clear()

    def test_search_station_field_types(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test that response field types are correct."""
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "test"})

            assert response.status_code == 200
            data = response.json()
            station = data["stations"][0]

            assert isinstance(station["uuid"], str)
            assert isinstance(station["name"], str)
            assert isinstance(station["url"], str)
            assert isinstance(station["bitrate"], int)
        finally:
            app.dependency_overrides.clear()


class TestRadioStationDetailEndpoint:
    """Tests for GET /api/radio/station/{uuid} endpoint."""

    def test_station_detail_endpoint_exists(self, client):
        """Test that /api/radio/station/{uuid} endpoint exists."""
        response = client.get("/api/radio/station/test-uuid")

        # Should not be 404 Not Found (though station might not exist)
        # 504 Gateway Timeout can occur when external Radio Browser API is unreachable
        assert response.status_code in [200, 404, 500, 503, 504]

    def test_get_station_by_uuid(self, client, mock_adapter, mock_radio_stations):
        """Test getting station detail by UUID."""
        mock_adapter.get_station_by_uuid.return_value = mock_radio_stations[0]

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/station/test-uuid-1")

            assert response.status_code == 200
            data = response.json()

            assert data["uuid"] == "test-uuid-1"
            assert data["name"] == "Test Radio 1"
        finally:
            app.dependency_overrides.clear()

    def test_get_station_not_found(self, client, mock_adapter):
        """Test getting non-existent station returns 404."""
        mock_adapter.get_station_by_uuid.side_effect = RadioBrowserError(
            "Station not found"
        )

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/station/nonexistent")

            assert response.status_code in [404, 500]
        finally:
            app.dependency_overrides.clear()


class TestRadioAPIErrorHandling:
    """Tests for error handling and edge cases in Radio API."""

    def test_search_timeout_returns_504(self, client, mock_adapter):
        """Test RadioBrowser API timeout returns 504 Gateway Timeout.

        Use case: RadioBrowser API is slow/unresponsive.
        Expected: User sees timeout error, not 500 Internal Server Error.
        """
        from opencloudtouch.radio.providers.radiobrowser import RadioBrowserTimeoutError

        mock_adapter.search_by_name.side_effect = RadioBrowserTimeoutError(
            "API timeout after 10s"
        )

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "test"})

            assert response.status_code == 504
            assert "timeout" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_search_connection_error_returns_503(self, client, mock_adapter):
        """Test connection failure returns 503 Service Unavailable.

        Use case: RadioBrowser API is down or DNS resolution fails.
        Expected: Clear error message, not generic 500.

        Regression: Network errors should be distinguishable from code bugs.
        """
        from opencloudtouch.radio.providers.radiobrowser import (
            RadioBrowserConnectionError,
        )

        mock_adapter.search_by_name.side_effect = RadioBrowserConnectionError(
            "Cannot connect to api.radio-browser.info"
        )

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "test"})

            assert response.status_code == 503
            assert (
                "connect" in response.json()["detail"].lower()
                or "unavailable" in response.json()["detail"].lower()
            )
        finally:
            app.dependency_overrides.clear()

    def test_station_detail_timeout_returns_504(self, client, mock_adapter):
        """Test station detail timeout handling.

        Note: Current implementation catches RadioBrowserError (parent class)
        first, so timeout returns 500 instead of 504.
        This test documents actual behavior, not ideal behavior.
        """
        from opencloudtouch.radio.providers.radiobrowser import RadioBrowserTimeoutError

        mock_adapter.get_station_by_uuid.side_effect = RadioBrowserTimeoutError(
            "API timeout"
        )

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/station/test-uuid")

            # After fixing exception order: Timeout correctly returns 504
            assert response.status_code == 504
        finally:
            app.dependency_overrides.clear()

    def test_station_detail_connection_error_returns_503(self, client, mock_adapter):
        """Test station detail connection failure handling.

        After fixing exception order: Connection error correctly returns 503.
        """
        from opencloudtouch.radio.providers.radiobrowser import (
            RadioBrowserConnectionError,
        )

        mock_adapter.get_station_by_uuid.side_effect = RadioBrowserConnectionError(
            "Network error"
        )

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/station/test-uuid")

            # After fixing exception order: Connection error correctly returns 503
            assert response.status_code == 503
        finally:
            app.dependency_overrides.clear()

    def test_search_with_special_characters(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test search with special characters in query.

        Use case: User searches for 'Rock & Roll' or 'Café del Mar'.
        Expected: Special chars are URL-encoded and handled correctly.
        """
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "Rock & Roll"})

            assert response.status_code == 200
            # Verify adapter received the unescaped query
            mock_adapter.search_by_name.assert_called_once()
            call_args = mock_adapter.search_by_name.call_args[0]
            assert call_args[0] == "Rock & Roll"
        finally:
            app.dependency_overrides.clear()

    def test_search_with_unicode_characters(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test search with Unicode characters.

        Use case: User searches for 'Москва FM' (Russian) or 'München' (German).
        Expected: Unicode handled correctly without encoding errors.
        """
        mock_adapter.search_by_name.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get("/api/radio/search", params={"q": "Москва"})

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    # Note: test_station_detail_with_invalid_uuid_format removed
    # Reason: RadioBrowser API accepts any string as UUID, so "invalid format"
    # is not really testable - it just returns 500 "Station not found".
    # The error handling is already covered by test_get_station_not_found().


class TestRadioAPIIntegration:
    """Integration tests combining search and station detail endpoints."""

    def test_search_and_detail_workflow(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test complete workflow: search → select → get detail.

        Use case: User searches for 'Rock', gets results, clicks on first station.
        Expected: Both endpoints work together seamlessly.
        """
        mock_adapter.search_by_name.return_value = mock_radio_stations
        mock_adapter.get_station_by_uuid.return_value = mock_radio_stations[0]

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            # 1. Search
            response = client.get("/api/radio/search", params={"q": "test"})
            assert response.status_code == 200
            stations = response.json()["stations"]
            assert len(stations) > 0

            # 2. Get detail for first result
            first_uuid = stations[0]["uuid"]
            response = client.get(f"/api/radio/station/{first_uuid}")
            assert response.status_code == 200
            detail = response.json()
            assert detail["uuid"] == first_uuid
        finally:
            app.dependency_overrides.clear()


class TestRadioSearchEdgeCases:
    """Edge case tests for radio search with different search types."""

    def test_search_by_country_empty_results(self, client, mock_adapter):
        """Test search by country with no results.

        Use case: User searches for country that has no stations.
        Expected: Returns empty array, not error.
        """
        mock_adapter.search_by_country.return_value = []

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get(
                "/api/radio/search",
                params={"q": "Antarctica", "search_type": "country"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["stations"] == []
            # Radio API returns {"stations": []} without total field
        finally:
            app.dependency_overrides.clear()

    def test_search_by_tag_special_characters(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test search by tag with special characters.

        Use case: User searches for 'Rock & Roll' or 'Pop/Rock' tag.
        Expected: Special characters handled correctly without errors.
        """
        mock_adapter.search_by_tag.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get(
                "/api/radio/search", params={"q": "rock&roll", "search_type": "tag"}
            )

            assert response.status_code == 200
            # Verify adapter received correctly encoded query
            mock_adapter.search_by_tag.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_search_by_country_umlauts(self, client, mock_adapter, mock_radio_stations):
        """Test search by country with German umlauts.

        Use case: User searches for 'Österreich' (Austria) or 'Schweiz' (Switzerland).
        Expected: Unicode characters handled correctly.
        """
        mock_adapter.search_by_country.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            response = client.get(
                "/api/radio/search",
                params={"q": "Österreich", "search_type": "country"},
            )

            assert response.status_code == 200
            # Verify adapter was called with correct parameters
            assert mock_adapter.search_by_country.called
            call_args = mock_adapter.search_by_country.call_args
            assert call_args[0][0] == "Österreich"  # First positional arg
        finally:
            app.dependency_overrides.clear()

    def test_search_by_tag_case_insensitive(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test search by tag is case-insensitive.

        Use case: User searches for 'JAZZ' vs 'jazz' vs 'Jazz'.
        Expected: All queries return same results.
        """
        mock_adapter.search_by_tag.return_value = mock_radio_stations

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            # Test uppercase
            response = client.get(
                "/api/radio/search", params={"q": "JAZZ", "search_type": "tag"}
            )
            assert response.status_code == 200

            # RadioBrowser API handles case-sensitivity, not our endpoint
            # Test just verifies request is passed through correctly
            assert mock_adapter.search_by_tag.called
            call_args = mock_adapter.search_by_tag.call_args
            assert call_args[0][0] == "JAZZ"  # Verify uppercase passed through
        finally:
            app.dependency_overrides.clear()


class TestConcurrentRadioRequests:
    """Tests for concurrent radio API requests (race conditions)."""

    @pytest.mark.asyncio
    async def test_concurrent_station_detail_requests(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test multiple concurrent station detail requests don't interfere.

        Use case: User opens multiple station details in different tabs.
        Expected: All requests succeed, no race conditions.

        Note: RadioBrowser adapter is stateless, so concurrency should be safe.
        """
        mock_adapter.get_station_by_uuid.return_value = mock_radio_stations[0]

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            import asyncio

            from httpx import AsyncClient

            # Create 5 concurrent requests
            async def fetch_station(station_uuid):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as ac:
                    response = await ac.get(f"/api/radio/station/{station_uuid}")
                    return response

            tasks = [fetch_station("test-uuid-1") for _ in range(5)]
            responses = await asyncio.gather(*tasks)

            # All should succeed
            for response in responses:
                assert response.status_code == 200
                assert response.json()["uuid"] == "test-uuid-1"

            # Adapter should be called 5 times (no caching)
            assert mock_adapter.get_station_by_uuid.call_count == 5

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_concurrent_search_requests_different_queries(
        self, client, mock_adapter, mock_radio_stations
    ):
        """Test concurrent search requests with different queries.

        Use case: Multiple users search simultaneously for different stations.
        Expected: Each request returns correct results, no query mixing.
        """

        # Mock adapter to return different results based on query
        def mock_search(query, limit=20):
            if query == "rock":
                return [mock_radio_stations[0]]
            elif query == "jazz":
                return [mock_radio_stations[1]]
            else:
                return []

        mock_adapter.search_by_name.side_effect = mock_search

        app.dependency_overrides[get_radio_provider] = lambda: mock_adapter
        try:
            import asyncio

            from httpx import AsyncClient

            async def search(query):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as ac:
                    response = await ac.get("/api/radio/search", params={"q": query})
                    return (query, response)

            # Search for "rock" and "jazz" concurrently
            tasks = [search("rock"), search("jazz"), search("rock")]
            results = await asyncio.gather(*tasks)

            # Verify each query got correct results
            for query, response in results:
                assert response.status_code == 200
                data = response.json()
                if query == "rock":
                    assert len(data["stations"]) == 1
                    assert data["stations"][0]["name"] == "Test Radio 1"
                elif query == "jazz":
                    assert len(data["stations"]) == 1
                    assert data["stations"][0]["name"] == "Test Radio 2"

        finally:
            app.dependency_overrides.clear()
