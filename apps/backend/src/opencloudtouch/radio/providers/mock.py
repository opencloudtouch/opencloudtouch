"""
Mock Radio Provider for testing.

Provides 20 deterministic radio stations for E2E testing.
Supports error simulation via special query strings.
"""

import logging
from typing import List

from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserError,
    RadioBrowserTimeoutError,
    RadioBrowserConnectionError,
    RadioStation,
)
from opencloudtouch.radio.provider import RadioProvider

logger = logging.getLogger(__name__)


class MockRadioAdapter(RadioProvider):
    """
    Mock Radio Provider with 20 deterministic stations.

    Used for E2E testing without external API dependencies.
    Supports error simulation for testing error handling.

    Error Simulation:
    - query="ERROR_503" → RadioBrowserConnectionError
    - query="ERROR_504" → RadioBrowserTimeoutError
    - query="ERROR_500" → RadioBrowserError
    """

    MOCK_STATIONS = [
        RadioStation(
            station_uuid="mock-bbc-1",
            name="BBC Radio 1",
            url="https://stream.bbc.co.uk/radio1",
            url_resolved="https://stream.bbc.co.uk/radio1",
            homepage="https://bbc.co.uk/radio1",
            favicon="https://bbc.co.uk/favicon-radio1.png",
            tags="public,bbc,uk,news,music",
            country="United Kingdom",
            countrycode="GB",
            state="England",
            language="English",
            languagecodes="en",
            votes=8500,
            codec="mp3",
            bitrate=192,
            hls=False,
            lastcheckok=True,
            clickcount=125000,
            clicktrend=50,
        ),
        RadioStation(
            station_uuid="mock-npr-1",
            name="NPR (National Public Radio)",
            url="https://stream.npr.org/live",
            url_resolved="https://stream.npr.org/live",
            homepage="https://npr.org",
            favicon="https://npr.org/favicon.png",
            tags="public,us,news,talk",
            country="United States",
            countrycode="US",
            state="Washington DC",
            language="English",
            languagecodes="en",
            votes=7200,
            codec="aac",
            bitrate=128,
            hls=True,
            lastcheckok=True,
            clickcount=95000,
            clicktrend=45,
        ),
        RadioStation(
            station_uuid="mock-france-inter",
            name="France Inter",
            url="https://stream.radiofrance.fr/inter",
            url_resolved="https://stream.radiofrance.fr/inter",
            homepage="https://radiofrance.fr/inter",
            favicon="https://radiofrance.fr/favicon.png",
            tags="public,france,news,culture",
            country="France",
            countrycode="FR",
            state="Paris",
            language="French",
            languagecodes="fr",
            votes=6800,
            codec="mp3",
            bitrate=192,
            hls=False,
            lastcheckok=True,
            clickcount=75000,
            clicktrend=40,
        ),
        RadioStation(
            station_uuid="mock-dw-1",
            name="Deutsche Welle Radio",
            url="https://stream.dw.com/radio",
            url_resolved="https://stream.dw.com/radio",
            homepage="https://dw.com",
            favicon="https://dw.com/favicon.png",
            tags="public,germany,news,international",
            country="Germany",
            countrycode="DE",
            state="Berlin",
            language="English",
            languagecodes="en,de",
            votes=5900,
            codec="aac",
            bitrate=96,
            hls=True,
            lastcheckok=True,
            clickcount=65000,
            clicktrend=35,
        ),
        RadioStation(
            station_uuid="mock-bbc-4",
            name="BBC Radio 4",
            url="https://stream.bbc.co.uk/radio4",
            url_resolved="https://stream.bbc.co.uk/radio4",
            homepage="https://bbc.co.uk/radio4",
            favicon="https://bbc.co.uk/favicon-radio4.png",
            tags="public,bbc,uk,drama,talk",
            country="United Kingdom",
            countrycode="GB",
            state="England",
            language="English",
            languagecodes="en",
            votes=5400,
            codec="mp3",
            bitrate=128,
            hls=False,
            lastcheckok=True,
            clickcount=55000,
            clicktrend=30,
        ),
        RadioStation(
            station_uuid="mock-abc-australia",
            name="ABC Radio National",
            url="https://stream.abc.net.au/radio",
            url_resolved="https://stream.abc.net.au/radio",
            homepage="https://abc.net.au",
            favicon="https://abc.net.au/favicon.png",
            tags="public,australia,news,documentary",
            country="Australia",
            countrycode="AU",
            state="Sydney",
            language="English",
            languagecodes="en",
            votes=4100,
            codec="aac",
            bitrate=64,
            hls=True,
            lastcheckok=True,
            clickcount=45000,
            clicktrend=25,
        ),
        RadioStation(
            station_uuid="mock-rfi",
            name="RFI Savoirs",
            url="https://stream.rfi.fr",
            url_resolved="https://stream.rfi.fr",
            homepage="https://rfi.fr",
            favicon="https://rfi.fr/favicon.png",
            tags="public,france,international,news",
            country="France",
            countrycode="FR",
            state="Paris",
            language="French",
            languagecodes="fr",
            votes=3900,
            codec="mp3",
            bitrate=128,
            hls=False,
            lastcheckok=True,
            clickcount=35000,
            clicktrend=20,
        ),
        RadioStation(
            station_uuid="mock-swissinfo",
            name="Swissinfo Radio",
            url="https://stream.swissinfo.org/radio",
            url_resolved="https://stream.swissinfo.org/radio",
            homepage="https://swissinfo.org",
            favicon="https://swissinfo.org/favicon.png",
            tags="public,switzerland,news,culture",
            country="Switzerland",
            countrycode="CH",
            state="Bern",
            language="German",
            languagecodes="de",
            votes=2850,
            codec="aac",
            bitrate=96,
            hls=True,
            lastcheckok=True,
            clickcount=25000,
            clicktrend=15,
        ),
        RadioStation(
            station_uuid="mock-radio-sweden",
            name="Radio Sweden",
            url="https://stream.sverigesradio.se",
            url_resolved="https://stream.sverigesradio.se",
            homepage="https://sverigesradio.se",
            favicon="https://sverigesradio.se/favicon.png",
            tags="public,sweden,news,music",
            country="Sweden",
            countrycode="SE",
            state="Stockholm",
            language="Swedish",
            languagecodes="sv",
            votes=2100,
            codec="mp3",
            bitrate=192,
            hls=False,
            lastcheckok=True,
            clickcount=18000,
            clicktrend=12,
        ),
        RadioStation(
            station_uuid="mock-rte-ireland",
            name="RTE Radio 1 Ireland",
            url="https://stream.rte.ie/radio1",
            url_resolved="https://stream.rte.ie/radio1",
            homepage="https://rte.ie",
            favicon="https://rte.ie/favicon.png",
            tags="public,ireland,news,talk",
            country="Ireland",
            countrycode="IE",
            state="Dublin",
            language="English",
            languagecodes="en",
            votes=1950,
            codec="aac",
            bitrate=128,
            hls=True,
            lastcheckok=True,
            clickcount=15000,
            clicktrend=10,
        ),
        RadioStation(
            station_uuid="mock-cbc-canada",
            name="CBC Radio One",
            url="https://stream.cbc.ca/radio1",
            url_resolved="https://stream.cbc.ca/radio1",
            homepage="https://cbc.ca",
            favicon="https://cbc.ca/favicon.png",
            tags="public,canada,news,talk",
            country="Canada",
            countrycode="CA",
            state="Toronto",
            language="English",
            languagecodes="en",
            votes=1800,
            codec="mp3",
            bitrate=128,
            hls=False,
            lastcheckok=True,
            clickcount=12000,
            clicktrend=8,
        ),
        RadioStation(
            station_uuid="mock-nz-radio",
            name="RNZ National",
            url="https://stream.rnz.co.nz/national",
            url_resolved="https://stream.rnz.co.nz/national",
            homepage="https://rnz.co.nz",
            favicon="https://rnz.co.nz/favicon.png",
            tags="public,newzealand,news,talk",
            country="New Zealand",
            countrycode="NZ",
            state="Wellington",
            language="English",
            languagecodes="en",
            votes=1350,
            codec="aac",
            bitrate=96,
            hls=True,
            lastcheckok=True,
            clickcount=9500,
            clicktrend=6,
        ),
        RadioStation(
            station_uuid="mock-yle-finland",
            name="Yle Radio 1",
            url="https://stream.yle.fi/radio1",
            url_resolved="https://stream.yle.fi/radio1",
            homepage="https://yle.fi",
            favicon="https://yle.fi/favicon.png",
            tags="public,finland,news,culture",
            country="Finland",
            countrycode="FI",
            state="Helsinki",
            language="Finnish",
            languagecodes="fi",
            votes=1200,
            codec="mp3",
            bitrate=192,
            hls=False,
            lastcheckok=True,
            clickcount=8000,
            clicktrend=5,
        ),
        RadioStation(
            station_uuid="mock-svt-norway",
            name="NRK Radio",
            url="https://stream.nrk.no/radio",
            url_resolved="https://stream.nrk.no/radio",
            homepage="https://nrk.no",
            favicon="https://nrk.no/favicon.png",
            tags="public,norway,news,music",
            country="Norway",
            countrycode="NO",
            state="Oslo",
            language="Norwegian",
            languagecodes="no",
            votes=900,
            codec="aac",
            bitrate=128,
            hls=True,
            lastcheckok=True,
            clickcount=6000,
            clicktrend=4,
        ),
        RadioStation(
            station_uuid="mock-rtp-portugal",
            name="RTP Antena 1",
            url="https://stream.rtp.pt/antena1",
            url_resolved="https://stream.rtp.pt/antena1",
            homepage="https://rtp.pt",
            favicon="https://rtp.pt/favicon.png",
            tags="public,portugal,news,music",
            country="Portugal",
            countrycode="PT",
            state="Lisbon",
            language="Portuguese",
            languagecodes="pt",
            votes=750,
            codec="mp3",
            bitrate=128,
            hls=False,
            lastcheckok=True,
            clickcount=5000,
            clicktrend=3,
        ),
        RadioStation(
            station_uuid="mock-tvp-poland",
            name="Polskie Radio 1",
            url="https://stream.polskieradio.pl/radio1",
            url_resolved="https://stream.polskieradio.pl/radio1",
            homepage="https://polskieradio.pl",
            favicon="https://polskieradio.pl/favicon.png",
            tags="public,poland,news,talk",
            country="Poland",
            countrycode="PL",
            state="Warsaw",
            language="Polish",
            languagecodes="pl",
            votes=650,
            codec="aac",
            bitrate=96,
            hls=True,
            lastcheckok=True,
            clickcount=4000,
            clicktrend=2,
        ),
        RadioStation(
            station_uuid="mock-ctvn-czech",
            name="ČRo Radiožurnál",
            url="https://stream.rozhlas.cz/radiozurnal",
            url_resolved="https://stream.rozhlas.cz/radiozurnal",
            homepage="https://rozhlas.cz",
            favicon="https://rozhlas.cz/favicon.png",
            tags="public,czech,news,culture",
            country="Czech Republic",
            countrycode="CZ",
            state="Prague",
            language="Czech",
            languagecodes="cs",
            votes=520,
            codec="mp3",
            bitrate=192,
            hls=False,
            lastcheckok=True,
            clickcount=3500,
            clicktrend=1,
        ),
        RadioStation(
            station_uuid="mock-mrt-malta",
            name="Malta Public Radio",
            url="https://stream.mrt.com.mt/radio",
            url_resolved="https://stream.mrt.com.mt/radio",
            homepage="https://mrt.com.mt",
            favicon="https://mrt.com.mt/favicon.png",
            tags="public,malta,news,culture",
            country="Malta",
            countrycode="MT",
            state="Valletta",
            language="English",
            languagecodes="en",
            votes=380,
            codec="aac",
            bitrate=64,
            hls=True,
            lastcheckok=True,
            clickcount=2000,
            clicktrend=0,
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
        results = [
            s
            for s in self.MOCK_STATIONS
            if query_lower in s.country.lower()
            or (s.countrycode and query_lower == s.countrycode.lower())
        ]

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
            s for s in self.MOCK_STATIONS if s.tags and query_lower in s.tags.lower()
        ]

        logger.info(f"[MOCK] Found {len(results)} stations with tag '{query}'")
        return results[:limit]

    async def get_by_uuid(self, uuid: str) -> RadioStation:
        """
        Get station by UUID.

        Args:
            uuid: Station UUID

        Returns:
            RadioStation if found, raises error otherwise
        """
        logger.info(f"[MOCK] Getting station by UUID: {uuid}")

        for station in self.MOCK_STATIONS:
            if station.station_uuid == uuid:
                return station

        raise RadioBrowserError(f"Station not found: {uuid}")
