"""
Mock Radio Provider for testing.

Provides 18 deterministic radio stations for E2E testing.
Supports error simulation via special query strings.
"""

import logging
from typing import List

from opencloudtouch.radio.models import RadioStation
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserError,
    RadioBrowserTimeoutError,
    RadioBrowserConnectionError,
)
from opencloudtouch.radio.provider import RadioProvider

logger = logging.getLogger(__name__)


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

    MOCK_STATIONS = [
        RadioStation(
            station_id="mock-bbc-1",
            name="BBC Radio 1",
            url="https://stream.bbc.co.uk/radio1",
            country="United Kingdom",
            codec="mp3",
            bitrate=192,
            tags=["public", "bbc", "uk", "news", "music"],
            favicon="https://bbc.co.uk/favicon-radio1.png",
            homepage="https://bbc.co.uk/radio1",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-npr-1",
            name="NPR (National Public Radio)",
            url="https://stream.npr.org/live",
            country="United States",
            codec="aac",
            bitrate=128,
            tags=["public", "us", "news", "talk"],
            favicon="https://npr.org/favicon.png",
            homepage="https://npr.org",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-france-inter",
            name="France Inter",
            url="https://stream.radiofrance.fr/inter",
            country="France",
            codec="mp3",
            bitrate=192,
            tags=["public", "france", "news", "culture"],
            favicon="https://radiofrance.fr/favicon.png",
            homepage="https://radiofrance.fr/inter",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-dw-1",
            name="Deutsche Welle Radio",
            url="https://stream.dw.com/radio",
            country="Germany",
            codec="aac",
            bitrate=96,
            tags=["public", "germany", "news", "international"],
            favicon="https://dw.com/favicon.png",
            homepage="https://dw.com",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-bbc-4",
            name="BBC Radio 4",
            url="https://stream.bbc.co.uk/radio4",
            country="United Kingdom",
            codec="mp3",
            bitrate=128,
            tags=["public", "bbc", "uk", "drama", "talk"],
            favicon="https://bbc.co.uk/favicon-radio4.png",
            homepage="https://bbc.co.uk/radio4",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-abc-australia",
            name="ABC Radio National",
            url="https://stream.abc.net.au/radio",
            country="Australia",
            codec="aac",
            bitrate=64,
            tags=["public", "australia", "news", "documentary"],
            favicon="https://abc.net.au/favicon.png",
            homepage="https://abc.net.au",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-rfi",
            name="RFI Savoirs",
            url="https://stream.rfi.fr",
            country="France",
            codec="mp3",
            bitrate=128,
            tags=["public", "france", "international", "news"],
            favicon="https://rfi.fr/favicon.png",
            homepage="https://rfi.fr",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-swissinfo",
            name="Swissinfo Radio",
            url="https://stream.swissinfo.org/radio",
            country="Switzerland",
            codec="aac",
            bitrate=96,
            tags=["public", "switzerland", "news", "culture"],
            favicon="https://swissinfo.org/favicon.png",
            homepage="https://swissinfo.org",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-radio-sweden",
            name="Radio Sweden",
            url="https://stream.sverigesradio.se",
            country="Sweden",
            codec="mp3",
            bitrate=192,
            tags=["public", "sweden", "news", "music"],
            favicon="https://sverigesradio.se/favicon.png",
            homepage="https://sverigesradio.se",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-rte-ireland",
            name="RTE Radio 1 Ireland",
            url="https://stream.rte.ie/radio1",
            country="Ireland",
            codec="aac",
            bitrate=128,
            tags=["public", "ireland", "news", "talk"],
            favicon="https://rte.ie/favicon.png",
            homepage="https://rte.ie",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-cbc-canada",
            name="CBC Radio One",
            url="https://stream.cbc.ca/radio1",
            country="Canada",
            codec="mp3",
            bitrate=128,
            tags=["public", "canada", "news", "talk"],
            favicon="https://cbc.ca/favicon.png",
            homepage="https://cbc.ca",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-nz-radio",
            name="RNZ National",
            url="https://stream.rnz.co.nz/national",
            country="New Zealand",
            codec="aac",
            bitrate=96,
            tags=["public", "newzealand", "news", "talk"],
            favicon="https://rnz.co.nz/favicon.png",
            homepage="https://rnz.co.nz",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-yle-finland",
            name="Yle Radio 1",
            url="https://stream.yle.fi/radio1",
            country="Finland",
            codec="mp3",
            bitrate=192,
            tags=["public", "finland", "news", "culture"],
            favicon="https://yle.fi/favicon.png",
            homepage="https://yle.fi",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-nrk-norway",
            name="NRK Radio",
            url="https://stream.nrk.no/radio",
            country="Norway",
            codec="aac",
            bitrate=128,
            tags=["public", "norway", "news", "music"],
            favicon="https://nrk.no/favicon.png",
            homepage="https://nrk.no",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-rtp-portugal",
            name="RTP Antena 1",
            url="https://stream.rtp.pt/antena1",
            country="Portugal",
            codec="mp3",
            bitrate=128,
            tags=["public", "portugal", "news", "music"],
            favicon="https://rtp.pt/favicon.png",
            homepage="https://rtp.pt",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-tvp-poland",
            name="Polskie Radio 1",
            url="https://stream.polskieradio.pl/radio1",
            country="Poland",
            codec="aac",
            bitrate=96,
            tags=["public", "poland", "news", "talk"],
            favicon="https://polskieradio.pl/favicon.png",
            homepage="https://polskieradio.pl",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-ctvn-czech",
            name="ČRo Radiožurnál",
            url="https://stream.rozhlas.cz/radiozurnal",
            country="Czech Republic",
            codec="mp3",
            bitrate=192,
            tags=["public", "czech", "news", "culture"],
            favicon="https://rozhlas.cz/favicon.png",
            homepage="https://rozhlas.cz",
            provider="mock",
        ),
        RadioStation(
            station_id="mock-mrt-malta",
            name="Malta Public Radio",
            url="https://stream.mrt.com.mt/radio",
            country="Malta",
            codec="aac",
            bitrate=64,
            tags=["public", "malta", "news", "culture"],
            favicon="https://mrt.com.mt/favicon.png",
            homepage="https://mrt.com.mt",
            provider="mock",
        ),
    ]

    @property
    def provider_name(self) -> str:
        return "mock"

    async def search_by_name(self, query: str, limit: int = 10) -> List[RadioStation]:
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
        logger.info(f"[MOCK] Searching stations by name: {query}")

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

        logger.info(f"[MOCK] Found {len(results)} stations matching '{query}'")
        return results[:limit]

    async def search_by_country(
        self, query: str, limit: int = 10
    ) -> List[RadioStation]:
        """
        Filter mock stations by country (case-insensitive).

        Args:
            query: Country name
            limit: Max results

        Returns:
            List of matching RadioStation objects
        """
        logger.info(f"[MOCK] Searching stations by country: {query}")

        query_lower = query.lower()
        results = [s for s in self.MOCK_STATIONS if query_lower in s.country.lower()]

        logger.info(f"[MOCK] Found {len(results)} stations in {query}")
        return results[:limit]

    async def search_by_tag(self, query: str, limit: int = 10) -> List[RadioStation]:
        """
        Filter mock stations by tag (case-insensitive).

        Args:
            query: Tag name
            limit: Max results

        Returns:
            List of matching RadioStation objects
        """
        logger.info(f"[MOCK] Searching stations by tag: {query}")

        query_lower = query.lower()
        results = [
            s
            for s in self.MOCK_STATIONS
            if s.tags and any(query_lower in tag.lower() for tag in s.tags)
        ]

        logger.info(f"[MOCK] Found {len(results)} stations with tag '{query}'")
        return results[:limit]

    async def get_by_uuid(self, uuid: str) -> RadioStation:
        """
        Get station by UUID (station_id in models).

        Args:
            uuid: Station UUID

        Returns:
            RadioStation if found, raises error otherwise
        """
        logger.info(f"[MOCK] Getting station by UUID: {uuid}")

        for station in self.MOCK_STATIONS:
            if station.station_id == uuid:
                return station

        raise RadioBrowserError(f"Station not found: {uuid}")
