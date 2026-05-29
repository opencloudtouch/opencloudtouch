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
from opencloudtouch.radio.provider import RadioProvider


from opencloudtouch.core.exceptions import (
    RadioConnectionError,
    RadioError,
    RadioTimeoutError,
)


# Provider-specific aliases (inherit from unified hierarchy)
class RadioBrowserError(RadioError):
    """Base exception for RadioBrowser errors."""

    pass


class RadioBrowserTimeoutError(RadioBrowserError, RadioTimeoutError):
    """Request timeout error."""

    pass


class RadioBrowserConnectionError(RadioBrowserError, RadioConnectionError):
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


class RadioBrowserAdapter(RadioProvider):
    """
    Adapter for RadioBrowser.info API.

    Provides search and retrieval of radio stations from the RadioBrowser database.
    Uses multiple API servers for redundancy with automatic failover.
    Maintains a shared httpx.AsyncClient for DNS caching and connection pooling.
    """

    # Known RadioBrowser API servers (load-balanced)
    API_SERVERS = [
        "https://de1.api.radio-browser.info",
        "https://nl1.api.radio-browser.info",
        "https://at1.api.radio-browser.info",
    ]

    def __init__(self, timeout: float = 10.0, max_retries: int = 2):
        """
        Initialize RadioBrowser adapter.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts per server
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._server_index = random.randint(0, len(self.API_SERVERS) - 1)
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        """Current API server URL."""
        return self.API_SERVERS[self._server_index % len(self.API_SERVERS)]

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create shared httpx client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                trust_env=False,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def provider_name(self) -> str:
        """Unique identifier for this provider."""
        return "radiobrowser"

    def _default_params(self, limit: int, offset: int = 0) -> Dict[str, Any]:
        """Build default query params for RadioBrowser API requests."""
        return {
            "limit": limit,
            "offset": offset,
            "hidebroken": "true",
            "order": "votes",
            "reverse": "true",
        }

    async def search_by_name(
        self, name: str, limit: int = 10, offset: int = 0
    ) -> List[RadioStation]:
        """
        Search stations by name.

        Args:
            name: Station name to search for
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of matching RadioStation objects
        """
        endpoint = f"/json/stations/byname/{name}"
        params = self._default_params(limit, offset)

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
        self, country: str, limit: int = 10, offset: int = 0
    ) -> List[RadioStation]:
        """
        Search stations by country.

        Args:
            country: Country name to search for
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of matching RadioStation objects
        """
        endpoint = f"/json/stations/bycountry/{country}"
        params = self._default_params(limit, offset)

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

    async def search_by_tag(
        self, tag: str, limit: int = 10, offset: int = 0
    ) -> List[RadioStation]:
        """
        Search stations by tag/genre.

        Args:
            tag: Tag/genre to search for
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of matching RadioStation objects
        """
        endpoint = f"/json/stations/bytag/{tag}"
        params = self._default_params(limit, offset)

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
        Make HTTP request to RadioBrowser API with server failover.

        Tries the current server with retries, then fails over to other servers.
        Uses a shared httpx.AsyncClient for connection pooling and DNS caching.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            RadioBrowserError: On API errors
            RadioBrowserTimeoutError: On timeout (all servers exhausted)
            RadioBrowserConnectionError: On connection errors (all servers exhausted)
        """
        client = self._get_client()
        last_exception: Exception | None = None
        servers_tried = 0

        for server_offset in range(len(self.API_SERVERS)):
            server_idx = (self._server_index + server_offset) % len(self.API_SERVERS)
            server_url = self.API_SERVERS[server_idx]
            url = f"{server_url}{endpoint}"
            servers_tried += 1

            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url, params=params or {})
                    response.raise_for_status()
                    # Success — remember this server for next time
                    self._server_index = server_idx
                    return response.json()
                except httpx.ConnectError as e:
                    last_exception = e
                    # DNS/connection failure — skip to next server immediately
                    break
                except httpx.TimeoutException as e:
                    last_exception = e
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    # Exhausted retries for this server, try next
                    break
                except httpx.HTTPStatusError:
                    raise

        # All servers exhausted
        if isinstance(last_exception, httpx.TimeoutException):
            raise last_exception
        if isinstance(last_exception, httpx.ConnectError):
            raise last_exception
        raise RadioBrowserError(  # pragma: no cover
            f"Request failed after trying {servers_tried} servers"
        )
