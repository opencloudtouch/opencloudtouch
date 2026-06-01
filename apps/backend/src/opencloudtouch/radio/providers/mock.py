"""
Mock Radio Provider for testing.

Provides 18 deterministic radio stations for E2E testing.
Station data is loaded from mock_stations.json at import time so that
test fixtures can be updated without modifying Python source code.

Supports error simulation via special query strings.
"""

import json
import logging
from pathlib import Path
from typing import List

from opencloudtouch.radio.models import RadioStation
from opencloudtouch.radio.provider import RadioProvider
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
)

logger = logging.getLogger(__name__)

_FIXTURES_PATH = Path(__file__).parent / "mock_stations.json"


def _load_stations() -> List[RadioStation]:
    """Load mock stations from the JSON fixture file."""
    with open(_FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [RadioStation(**item) for item in data["stations"]]


class MockRadioAdapter(RadioProvider):
    """
    Mock Radio Provider with 18 deterministic stations.

    Used for E2E testing without external API dependencies.
    Supports error simulation for testing error handling.

    Error Simulation:
    - query="ERROR_503" → RadioBrowserConnectionError
    - query="ERROR_504" → RadioBrowserTimeoutError
    - query="ERROR_500" → RadioBrowserError
    """

    # Loaded at class-definition time so all instances share the same list.
    # Re-read the file only if the module is reloaded (e.g. in tests via importlib).
    MOCK_STATIONS: List[RadioStation] = _load_stations()

    @property
    def provider_name(self) -> str:
        return "mock"

    async def search_by_name(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> List[RadioStation]:
        """
        Filter mock stations by name (case-insensitive).

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching RadioStation objects

        Raises:
            RadioBrowserConnectionError: For ERROR_503 query
            RadioBrowserTimeoutError: For ERROR_504 query
            RadioBrowserError: For ERROR_500 query
        """
        logger.info("[MOCK] Searching stations by name: %s", query)

        # Error simulation
        if query == "ERROR_503":
            raise RadioBrowserConnectionError("Service unavailable (503)")
        if query == "ERROR_504":
            raise RadioBrowserTimeoutError("Gateway timeout (504)")
        if query == "ERROR_500":
            raise RadioBrowserError("Internal server error (500)")

        # Filter
        query_lower = query.lower()
        results = [s for s in self.MOCK_STATIONS if query_lower in s.name.lower()]

        logger.info("[MOCK] Found %d stations matching '%s'", len(results), query)
        return results[offset : offset + limit]

    async def search_by_country(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> List[RadioStation]:
        """
        Filter mock stations by country (case-insensitive).

        Args:
            query: Country name
            limit: Max results

        Returns:
            List of matching RadioStation objects
        """
        logger.info("[MOCK] Searching stations by country: %s", query)

        query_lower = query.lower()
        results = [s for s in self.MOCK_STATIONS if query_lower in s.country.lower()]

        logger.info("[MOCK] Found %d stations in %s", len(results), query)
        return results[offset : offset + limit]

    async def search_by_tag(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> List[RadioStation]:
        """
        Filter mock stations by tag (case-insensitive).

        Args:
            query: Tag name
            limit: Max results

        Returns:
            List of matching RadioStation objects
        """
        logger.info("[MOCK] Searching stations by tag: %s", query)

        query_lower = query.lower()
        results = [
            s
            for s in self.MOCK_STATIONS
            if s.tags and any(query_lower in tag.lower() for tag in s.tags)
        ]

        logger.info("[MOCK] Found %d stations with tag '%s'", len(results), query)
        return results[offset : offset + limit]

    async def get_by_uuid(self, uuid: str) -> RadioStation:
        """
        Get station by UUID (station_id in models).

        Args:
            uuid: Station UUID

        Returns:
            RadioStation if found, raises error otherwise
        """
        logger.info("[MOCK] Getting station by UUID: %s", uuid)

        for station in self.MOCK_STATIONS:
            if station.station_id == uuid:
                return station

        raise RadioBrowserError(f"Station not found: {uuid}")

    async def get_station_by_uuid(self, uuid: str) -> RadioStation:
        """Implement RadioProvider abstract method — delegates to get_by_uuid."""
        return await self.get_by_uuid(uuid)
