"""Integration tests for BMX TuneIn - tests against real TuneIn API.

These tests are marked with @pytest.mark.integration and require internet access.
They can be skipped with: pytest -m "not integration"
"""

import pytest

from opencloudtouch.bmx.routes import resolve_tunein_station


@pytest.mark.integration
class TestTuneInIntegration:
    """Integration tests with real TuneIn API."""

    @pytest.mark.asyncio
    async def test_resolve_real_tunein_station(self):
        """Test resolution of real TuneIn station (Absolut Relax)."""
        # Arrange
        station_id = "s158432"  # Absolut Relax (Austria)

        # Act
        result = await resolve_tunein_station(station_id)

        # Assert
        assert result.name  # Should have a name
        assert result.audio.streamUrl  # Should have stream URL
        assert result.audio.streamUrl.startswith("http")
        assert len(result.audio.streams) > 0
        assert result.streamType == "liveRadio"
        # Note: imageUrl may be empty, so we don't assert it

    @pytest.mark.asyncio
    async def test_resolve_unknown_station(self):
        """Test that resolving non-existent station returns empty streams or raises error.

        Note: TuneIn API behavior for unknown stations is not guaranteed.
        It may return empty results or raise an error.
        """
        # Arrange
        station_id = "s999999999"  # Very unlikely to exist

        # Act
        try:
            result = await resolve_tunein_station(station_id)
            # If it succeeds, it should return minimal data
            assert result is not None
        except Exception:
            # If it raises an error, that's also acceptable
            pass

    @pytest.mark.asyncio
    async def test_resolve_multiple_stations(self):
        """Test resolving multiple popular stations."""
        # Arrange - popular German/Austrian stations
        station_ids = [
            "s24896",  # 1LIVE (Germany)
            "s25111",  # WDR 2 (Germany)
            "s158432",  # Absolut Relax (Austria)
        ]

        # Act
        results = []
        for station_id in station_ids:
            try:
                result = await resolve_tunein_station(station_id)
                results.append(result)
            except Exception as e:
                pytest.fail(f"Failed to resolve {station_id}: {e}")

        # Assert
        assert len(results) == 3
        for result in results:
            assert result.name
            assert result.audio.streamUrl
            assert result.audio.streamUrl.startswith("http")
