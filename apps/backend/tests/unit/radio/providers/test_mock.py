"""Unit tests for MockRadioAdapter."""

import pytest

from opencloudtouch.radio.providers.mock import MockRadioAdapter


class TestMockRadioAdapterSearchByTag:
    """Tests for search_by_tag method (lines 320-330)."""

    @pytest.mark.asyncio
    async def test_search_by_tag_returns_matching_stations(self):
        """search_by_tag filters MOCK_STATIONS by tag (lines 320-330)."""
        adapter = MockRadioAdapter()

        # MOCK_STATIONS contains stations with tags — search for "pop"
        results = await adapter.search_by_tag("pop")

        # Should return stations that have "pop" in their tags
        assert isinstance(results, list)
        # All returned stations must have a tag matching "pop"
        for station in results:
            assert station.tags is not None
            assert any("pop" in tag.lower() for tag in station.tags)

    @pytest.mark.asyncio
    async def test_search_by_tag_empty_results_when_no_match(self):
        """search_by_tag returns empty list for unknown tag."""
        adapter = MockRadioAdapter()

        results = await adapter.search_by_tag("zzzunknowntagzzz")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_by_tag_respects_limit(self):
        """search_by_tag respects the limit parameter (line 330)."""
        adapter = MockRadioAdapter()

        results_limited = await adapter.search_by_tag("", limit=1)

        # Limited result should have at most 1 item
        assert len(results_limited) <= 1
