"""
RadioBrowser API Adapter

Implements RadioProvider interface for RadioBrowser.info public API.
Provides access to 30,000+ community-maintained radio stations worldwide.

API Documentation: https://api.radio-browser.info/

Features:
- Async HTTP client with retry logic
- Exponential backoff on failures
- Multiple API server support
- Provider abstraction for easy extension
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from opencloudtouch.radio.models import RadioStation


# Custom Exceptions
class RadioBrowserError(Exception):
    """Base exception for RadioBrowser errors."""

    pass


class RadioBrowserTimeoutError(RadioBrowserError):
    """Request timeout error."""

    pass


class RadioBrowserConnectionError(RadioBrowserError):
    """Connection error."""

    pass


@dataclass
class RadioBrowserStation:
    """Represents a radio station from RadioBrowser API (internal model)."""

    station_uuid: str
    name: str
    url: str
    url_resolved: Optional[str] = None
    homepage: Optional[str] = None
    favicon: Optional[str] = None
    tags: Optional[str] = None
    country: str = ""
    countrycode: Optional[str] = None
    state: Optional[str] = None
    language: Optional[str] = None
    languagecodes: Optional[str] = None
    votes: Optional[int] = None
    codec: str = ""
    bitrate: Optional[int] = None
    hls: bool = False
    lastcheckok: bool = False
    clickcount: Optional[int] = None
    clicktrend: Optional[int] = None

    @staticmethod
    def from_api_response(data: Dict[str, Any]) -> "RadioBrowserStation":
        """Create RadioBrowserStation from API response dict."""
        return RadioBrowserStation(
            station_uuid=data["stationuuid"],
            name=data["name"],
            url=data["url"],
            url_resolved=data.get("url_resolved"),
            homepage=data.get("homepage"),
            favicon=data.get("favicon"),
            tags=data.get("tags"),
            country=data["country"],
            countrycode=data.get("countrycode"),
            state=data.get("state"),
            language=data.get("language"),
            languagecodes=data.get("languagecodes"),
            votes=data.get("votes"),
            codec=data["codec"],
            bitrate=data.get("bitrate"),
            hls=bool(data.get("hls", 0)),
            lastcheckok=bool(data.get("lastcheckok", 0)),
            clickcount=data.get("clickcount"),
            clicktrend=data.get("clicktrend"),
        )

    def to_unified(self) -> RadioStation:
        """Convert RadioBrowserStation to unified RadioStation model."""
        # Parse tags string to list
        tags_list = None
        if self.tags:
            tags_list = [tag.strip() for tag in self.tags.split(",") if tag.strip()]

        return RadioStation(
            station_id=self.station_uuid,
            name=self.name,
            url=self.url_resolved or self.url,  # Prefer resolved URL
            country=self.country,
            codec=self.codec or None,
            bitrate=self.bitrate,
            tags=tags_list,
            favicon=self.favicon,
            homepage=self.homepage,
            provider="radiobrowser",
        )


class RadioBrowserAdapter:
    """
    Adapter for RadioBrowser.info API.

    Provides search and retrieval of radio stations from the RadioBrowser database.
    Uses multiple API servers for redundancy.
    """

    # Known RadioBrowser API servers (load-balanced)
    # Using all.api.radio-browser.info which resolves to multiple IPs
    API_SERVERS = [
        "https://all.api.radio-browser.info",
        "https://de1.api.radio-browser.info",
        "https://nl1.api.radio-browser.info",
        "https://at1.api.radio-browser.info",
    ]

    def __init__(self, timeout: float = 10.0, max_retries: int = 3):
        """
        Initialize RadioBrowser adapter.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = random.choice(self.API_SERVERS)

    async def search_by_name(self, name: str, limit: int = 10) -> List[RadioStation]:
        """
        Search stations by name.

        Args:
            name: Station name to search for
            limit: Maximum number of results

        Returns:
            List of matching RadioStation objects
        """
        endpoint = f"/json/stations/byname/{name}"
        params = {"limit": limit}

        try:
            data = await self._make_request(endpoint, params)
            return [
                RadioBrowserStation.from_api_response(item).to_unified()
                for item in data
            ]
        except httpx.TimeoutException as e:
            raise RadioBrowserTimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            raise RadioBrowserConnectionError(f"Connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise RadioBrowserError(
                f"HTTP error {e.response.status_code}: {e.response.text}"
            ) from e

    async def search_by_country(
        self, country: str, limit: int = 10
    ) -> List[RadioStation]:
        """
        Search stations by country.

        Args:
            country: Country name to search for
            limit: Maximum number of results

        Returns:
            List of matching RadioStation objects
        """
        endpoint = f"/json/stations/bycountry/{country}"
        params = {"limit": limit}

        try:
            data = await self._make_request(endpoint, params)
            return [
                RadioBrowserStation.from_api_response(item).to_unified()
                for item in data
            ]
        except httpx.TimeoutException as e:
            raise RadioBrowserTimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            raise RadioBrowserConnectionError(f"Connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise RadioBrowserError(
                f"HTTP error {e.response.status_code}: {e.response.text}"
            ) from e

    async def search_by_tag(self, tag: str, limit: int = 10) -> List[RadioStation]:
        """
        Search stations by tag/genre.

        Args:
            tag: Tag/genre to search for
            limit: Maximum number of results

        Returns:
            List of matching RadioStation objects
        """
        endpoint = f"/json/stations/bytag/{tag}"
        params = {"limit": limit}

        try:
            data = await self._make_request(endpoint, params)
            return [
                RadioBrowserStation.from_api_response(item).to_unified()
                for item in data
            ]
        except httpx.TimeoutException as e:
            raise RadioBrowserTimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            raise RadioBrowserConnectionError(f"Connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise RadioBrowserError(
                f"HTTP error {e.response.status_code}: {e.response.text}"
            ) from e

    async def get_station_by_uuid(self, uuid: str) -> RadioStation:
        """
        Get station detail by UUID.

        Args:
            uuid: Station UUID

        Returns:
            RadioStation object

        Raises:
            RadioBrowserError: If station not found
        """
        endpoint = f"/json/stations/byuuid/{uuid}"

        try:
            data = await self._make_request(endpoint)

            if not data:
                raise RadioBrowserError(f"Station {uuid} not found")

            # API returns list, take first item
            station_data = data[0] if isinstance(data, list) else data
            return RadioBrowserStation.from_api_response(station_data).to_unified()
        except httpx.TimeoutException as e:
            raise RadioBrowserTimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            raise RadioBrowserConnectionError(f"Connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise RadioBrowserError(
                f"HTTP error {e.response.status_code}: {e.response.text}"
            ) from e

    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Make HTTP request to RadioBrowser API with retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            RadioBrowserError: On API errors
            RadioBrowserTimeoutError: On timeout
            RadioBrowserConnectionError: On connection errors
        """
        url = f"{self.base_url}{endpoint}"

        # trust_env=False to avoid Windows proxy/DNS issues
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url, params=params or {})
                    response.raise_for_status()
                    return response.json()
                except (httpx.TimeoutException, httpx.ConnectError):
                    if attempt < self.max_retries - 1:
                        # Exponential backoff
                        wait_time = 2**attempt
                        await asyncio.sleep(wait_time)
                        continue
                    raise
                except httpx.HTTPStatusError:
                    raise

        # Should not reach here
        raise RadioBrowserError("Request failed after retries")
