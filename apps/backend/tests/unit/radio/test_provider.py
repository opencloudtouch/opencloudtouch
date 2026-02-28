"""
Tests for RadioProvider Abstract Base Class

Tests the RadioProvider interface and RadioStation dataclass.
Validates that concrete implementations must implement all abstract methods.
"""

import pytest

from opencloudtouch.radio.provider import (
    RadioProvider,
    RadioProviderConnectionError,
    RadioProviderError,
    RadioProviderTimeoutError,
    RadioStation,
)


class TestRadioStationDataclass:
    """Tests for RadioStation dataclass."""

    def test_radio_station_minimal(self):
        """Test RadioStation with minimal required fields."""
        station = RadioStation(
            station_id="123",
            name="Test Station",
            url="http://stream.example.com/radio",
            country="DE",
        )

        assert station.station_id == "123"
        assert station.name == "Test Station"
        assert station.url == "http://stream.example.com/radio"
        assert station.country == "DE"
        assert station.codec is None
        assert station.bitrate is None
        assert station.tags is None
        assert station.favicon is None
        assert station.homepage is None
        assert station.provider == "unknown"

    def test_radio_station_full(self):
        """Test RadioStation with all fields populated."""
        station = RadioStation(
            station_id="456",
            name="Full Test Station",
            url="http://full.example.com/stream",
            country="US",
            codec="MP3",
            bitrate=128,
            tags=["rock", "classic"],
            favicon="http://example.com/logo.png",
            homepage="http://example.com",
            provider="radiobrowser",
        )

        assert station.station_id == "456"
        assert station.name == "Full Test Station"
        assert station.codec == "MP3"
        assert station.bitrate == 128
        assert station.tags == ["rock", "classic"]
        assert station.favicon == "http://example.com/logo.png"
        assert station.homepage == "http://example.com"
        assert station.provider == "radiobrowser"


class TestRadioProviderExceptions:
    """Tests for RadioProvider exception hierarchy."""

    def test_radio_provider_error_base(self):
        """Test RadioProviderError is raised correctly."""
        with pytest.raises(RadioProviderError):
            raise RadioProviderError("Generic error")

    def test_radio_provider_timeout_error(self):
        """Test RadioProviderTimeoutError inherits from RadioProviderError."""
        with pytest.raises(RadioProviderError):  # Should catch parent class
            raise RadioProviderTimeoutError("Timeout")

        with pytest.raises(RadioProviderTimeoutError):  # Should catch specific class
            raise RadioProviderTimeoutError("Timeout")

    def test_radio_provider_connection_error(self):
        """Test RadioProviderConnectionError inherits from RadioProviderError."""
        with pytest.raises(RadioProviderError):  # Should catch parent class
            raise RadioProviderConnectionError("Connection failed")

        with pytest.raises(RadioProviderConnectionError):  # Should catch specific class
            raise RadioProviderConnectionError("Connection failed")


class TestRadioProviderInterface:
    """Tests for RadioProvider abstract interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that RadioProvider cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc:
            RadioProvider()  # type: ignore

        assert "Can't instantiate abstract class" in str(exc.value)

    def test_concrete_implementation_must_implement_all_methods(self):
        """Test that concrete class must implement all abstract methods."""

        # Incomplete implementation (missing methods)
        class IncompleteProvider(RadioProvider):
            @property
            def provider_name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError) as exc:
            IncompleteProvider()  # type: ignore

        assert "Can't instantiate abstract class" in str(exc.value)

    @pytest.mark.asyncio
    async def test_concrete_implementation_works(self):
        """Test that complete concrete implementation works."""

        class TestProvider(RadioProvider):
            @property
            def provider_name(self) -> str:
                return "test"

            async def search_by_name(self, name: str, limit: int = 20):
                return [
                    RadioStation(
                        station_id="1",
                        name=name,
                        url="http://test.com",
                        country="DE",
                        provider="test",
                    )
                ]

            async def search_by_country(self, country: str, limit: int = 20):
                return [
                    RadioStation(
                        station_id="2",
                        name="Country Station",
                        url="http://test.com",
                        country=country,
                        provider="test",
                    )
                ]

            async def search_by_tag(self, tag: str, limit: int = 20):
                return [
                    RadioStation(
                        station_id="3",
                        name="Tagged Station",
                        url="http://test.com",
                        country="DE",
                        provider="test",
                        tags=[tag],
                    )
                ]

            async def get_station_by_uuid(self, uuid: str):
                return RadioStation(
                    station_id=uuid,
                    name="Test Station",
                    url="http://test.com",
                    country="DE",
                    provider="test",
                )

        # Should be able to instantiate
        provider = TestProvider()
        assert provider.provider_name == "test"

        # Should be able to call methods
        results = await provider.search_by_name("Test")
        assert len(results) == 1
        assert results[0].name == "Test"
        assert results[0].provider == "test"

        results = await provider.search_by_country("US")
        assert len(results) == 1
        assert results[0].country == "US"

        results = await provider.search_by_tag("rock")
        assert len(results) == 1
        assert results[0].tags == ["rock"]

    @pytest.mark.asyncio
    async def test_default_resolve_stream_url_implementation(self):
        """Test that default resolve_stream_url returns URL unchanged."""

        class SimpleProvider(RadioProvider):
            @property
            def provider_name(self) -> str:
                return "simple"

            async def search_by_name(self, name: str, limit: int = 20):
                return []

            async def search_by_country(self, country: str, limit: int = 20):
                return []

            async def search_by_tag(self, tag: str, limit: int = 20):
                return []

            async def get_station_by_uuid(self, uuid: str):
                raise NotImplementedError

        provider = SimpleProvider()
        station = RadioStation(
            station_id="1",
            name="Test",
            url="http://original.com/stream.m3u",
            country="DE",
            provider="simple",
        )

        # Default implementation should return URL unchanged
        resolved_url = await provider.resolve_stream_url(station)
        assert resolved_url == "http://original.com/stream.m3u"
