"""TuneIn Radio Provider.

Implements RadioProvider interface for the TuneIn OPML API.
Uses the public opml.radiotime.com endpoints for station search
and metadata retrieval.

API Endpoints:
- Search: http://opml.radiotime.com/Search.ashx?query=...
- Describe: https://opml.radiotime.com/Describe.ashx?id=...
- Stream: http://opml.radiotime.com/Tune.ashx?id=...&formats=mp3,aac,ogg
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import httpx

from opencloudtouch.radio.models import RadioStation
from opencloudtouch.radio.provider import RadioProvider
from opencloudtouch.core.exceptions import (
    RadioConnectionError,
    RadioError,
    RadioTimeoutError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TuneInError(RadioError):
    """Base exception for TuneIn provider errors."""


class TuneInTimeoutError(TuneInError, RadioTimeoutError):
    """Request timeout error."""


class TuneInConnectionError(TuneInError, RadioConnectionError):
    """Connection error."""


# ---------------------------------------------------------------------------
# Genre mapping (TuneIn genre_id → human-readable name)
# ---------------------------------------------------------------------------

GENRE_MAP: Dict[str, str] = {
    "g2": "Talk",
    "g3": "Sports",
    "g4": "News",
    "g5": "Music",
    "g10": "Easy Listening",
    "g11": "Country",
    "g12": "Latin",
    "g13": "R&B/Urban",
    "g14": "Hip Hop",
    "g15": "Oldies",
    "g16": "Reggae",
    "g17": "World",
    "g18": "Soundtracks",
    "g19": "Electronic",
    "g20": "Religious",
    "g21": "College",
    "g23": "Pop",
    "g42": "80s",
    "g43": "70s",
    "g44": "60s",
    "g45": "90s",
    "g46": "Classic Rock",
    "g47": "Smooth Jazz",
    "g48": "Blues",
    "g54": "Jazz",
    "g57": "Classical",
    "g59": "Rock",
    "g61": "German Pop",
    "g63": "Alternative",
    "g67": "Metal",
    "g79": "Chillout",
    "g115": "Ambient",
    "g132": "Dance",
    "g139": "Indie",
    "g3403": "Podcasts",
}


# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------


@dataclass
class TuneInStation:
    """Internal representation of a TuneIn station (from OPML attributes)."""

    guide_id: str
    name: str
    image: Optional[str] = None
    bitrate: Optional[int] = None
    subtext: Optional[str] = None
    genre_id: Optional[str] = None
    formats: Optional[str] = None
    # Extended fields from Describe API
    homepage: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    genre_name: Optional[str] = None

    @staticmethod
    def from_search_outline(attrs: Dict[str, Any]) -> "TuneInStation":
        """Create from OPML outline element attributes."""
        bitrate = None
        raw_bitrate = attrs.get("bitrate")
        if raw_bitrate:
            try:
                bitrate = int(raw_bitrate)
            except (ValueError, TypeError):
                pass

        return TuneInStation(
            guide_id=attrs["guide_id"],
            name=attrs.get("text", ""),
            image=attrs.get("image"),
            bitrate=bitrate,
            subtext=attrs.get("subtext"),
            genre_id=attrs.get("genre_id"),
            formats=attrs.get("formats"),
        )

    def to_unified(self) -> RadioStation:
        """Convert to unified RadioStation model."""
        tags = None
        if self.genre_id:
            genre_label = self.genre_name or GENRE_MAP.get(self.genre_id, self.genre_id)
            tags = [genre_label]

        return RadioStation(
            station_id=self.guide_id,
            name=self.name,
            url="",  # Stream URL resolved separately via Tune.ashx
            country=self.country or "",
            codec=self.formats,
            bitrate=self.bitrate,
            tags=tags,
            favicon=self.image,
            homepage=self.homepage,
            provider="tunein",
        )


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------

TUNEIN_BASE = "http://opml.radiotime.com"
TUNEIN_DESCRIBE = "https://opml.radiotime.com"


class TuneInProvider(RadioProvider):
    """TuneIn radio provider using the public OPML API.

    Provides station search and metadata via opml.radiotime.com.
    Stream resolution for playback is handled separately by bmx/tunein.py.
    """

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "tunein"

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                trust_env=False,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -------------------------------------------------------------------
    # Search methods
    # -------------------------------------------------------------------

    async def search_by_name(
        self, name: str, limit: int = 20, offset: int = 0
    ) -> List[RadioStation]:
        url = f"{TUNEIN_BASE}/Search.ashx"
        params = {"query": name}
        return await self._search(url, params, limit, offset)

    async def search_by_country(
        self, country: str, limit: int = 20, offset: int = 0
    ) -> List[RadioStation]:
        # TuneIn has no country-specific endpoint; use keyword search
        url = f"{TUNEIN_BASE}/Search.ashx"
        params = {"query": country}
        return await self._search(url, params, limit, offset)

    async def search_by_tag(
        self, tag: str, limit: int = 20, offset: int = 0
    ) -> List[RadioStation]:
        # TuneIn has no tag-specific endpoint; use keyword search
        url = f"{TUNEIN_BASE}/Search.ashx"
        params = {"query": tag}
        return await self._search(url, params, limit, offset)

    async def get_station_by_uuid(self, uuid: str) -> RadioStation:
        """Get station detail via Describe API."""
        url = f"{TUNEIN_DESCRIBE}/Describe.ashx"
        params = {"id": uuid}

        try:
            client = self._get_client()
            response = await client.get(url, params=params)
            response.raise_for_status()

            station = self._parse_describe_response(response.text, uuid)
            if station is None:
                raise TuneInError(f"Station {uuid} not found")
            return station.to_unified()

        except httpx.TimeoutException as e:
            raise TuneInTimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            raise TuneInConnectionError(f"Connection failed: {e}") from e
        except TuneInError:
            raise
        except httpx.HTTPStatusError as e:
            raise TuneInError(f"HTTP error {e.response.status_code}") from e

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    async def _search(
        self, url: str, params: Dict[str, Any], limit: int, offset: int = 0
    ) -> List[RadioStation]:
        """Execute search request and parse OPML response."""
        try:
            client = self._get_client()
            response = await client.get(url, params=params)
            response.raise_for_status()

            stations = self._parse_search_response(response.text)
            return [s.to_unified() for s in stations[offset : offset + limit]]

        except httpx.TimeoutException as e:
            raise TuneInTimeoutError(f"Request timed out: {e}") from e
        except httpx.ConnectError as e:
            raise TuneInConnectionError(f"Connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            raise TuneInError(f"HTTP error {e.response.status_code}") from e

    @staticmethod
    def _parse_search_response(xml_text: str) -> List[TuneInStation]:
        """Parse OPML search response into list of TuneInStation."""
        root = ElementTree.fromstring(xml_text)  # nosec B314
        body = root.find("body")
        if body is None:
            return []

        stations: List[TuneInStation] = []
        for outline in body.findall("outline"):
            # Only include stations (type="audio", item="station")
            if outline.get("item") != "station":
                continue
            if outline.get("type") != "audio":
                continue
            attrs = dict(outline.attrib)
            stations.append(TuneInStation.from_search_outline(attrs))

        return stations

    @staticmethod
    def _parse_describe_response(
        xml_text: str, station_id: str
    ) -> Optional[TuneInStation]:
        """Parse OPML describe response into a TuneInStation."""
        root = ElementTree.fromstring(xml_text)  # nosec B314
        body = root.find("body")
        if body is None:
            return None

        outline = body.find("outline")
        if outline is None:
            return None

        station_elem = outline.find("station")
        if station_elem is None:
            return None

        def _text(tag: str) -> Optional[str]:
            elem = station_elem.find(tag)  # type: ignore[union-attr]
            return elem.text if elem is not None and elem.text else None

        guide_id = _text("guide_id") or station_id
        name = _text("name") or outline.get("text") or "Unknown"

        return TuneInStation(
            guide_id=guide_id,
            name=name,
            image=_text("logo"),
            homepage=_text("url"),
            country=_text("location"),
            language=_text("language"),
            genre_name=_text("genre_name"),
            genre_id=_text("genre_id"),
            subtext=_text("slogan") or _text("description"),
        )
