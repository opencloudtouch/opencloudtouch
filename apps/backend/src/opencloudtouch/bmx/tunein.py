"""TuneIn integration for BMX service.

Handles resolution of TuneIn station IDs to playable stream URLs,
as a replacement for the Bose Cloud TuneIn integration.
"""

import logging
import os
import re
from xml.etree import ElementTree

import httpx

from opencloudtouch.bmx.models import BmxAudio, BmxPlaybackResponse, BmxStream
from opencloudtouch.bmx.stream_utils import convert_https_to_http

logger = logging.getLogger(__name__)

TUNEIN_DESCRIBE_URL = "https://opml.radiotime.com/describe.ashx?id=%s"
TUNEIN_STREAM_URL = "http://opml.radiotime.com/Tune.ashx?id=%s&formats=mp3,aac,ogg"

_STATION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def get_oct_base_url() -> str:
    """Get OCT backend URL from environment.

    Returns hostname-based URL so device can resolve via /etc/hosts.
    Device knows 'content.api.bose.io' from modified /etc/hosts.
    """
    return os.getenv("OCT_BACKEND_URL", "http://content.api.bose.io:7777")


def _parse_tunein_describe_xml(describe_xml: str) -> tuple[str, str]:
    """Parse station name and logo URL from TuneIn describe XML response.

    Returns:
        Tuple of (station_name, logo_url), using sane defaults on missing data.
    """
    root = ElementTree.fromstring(describe_xml)  # nosec B314
    body = root.find("body")
    outline = body.find("outline") if body is not None else None
    station_elem = outline.find("station") if outline is not None else None

    if station_elem is None:
        return "Unknown Station", ""

    name_elem = station_elem.find("name")
    logo_elem = station_elem.find("logo")
    name = (name_elem.text if name_elem is not None else None) or "Unknown Station"
    logo = (logo_elem.text if logo_elem is not None else None) or ""
    return name, logo


def _build_tunein_playback_response(
    station_id: str, stream_urls: list[str], name: str, logo: str
) -> BmxPlaybackResponse:
    """Build a BmxPlaybackResponse from resolved TuneIn stream data."""
    primary_url = stream_urls[0]
    base_url = get_oct_base_url()
    bmx_reporting = f"{base_url}/bmx/tunein/v1/reporting/station/{station_id}"

    streams = [
        BmxStream(streamUrl=url, links={"bmx_reporting": {"href": bmx_reporting}})
        for url in stream_urls
    ]
    audio = BmxAudio(streamUrl=primary_url, streams=streams)
    links = {
        "bmx_nowplaying": {
            "href": f"{base_url}/bmx/tunein/v1/now-playing/station/{station_id}",
            "useInternalClient": "ALWAYS",
        },
        "bmx_reporting": {"href": bmx_reporting},
        "bmx_favorite": {"href": f"{base_url}/bmx/tunein/v1/favorite/{station_id}"},
    }
    return BmxPlaybackResponse(audio=audio, links=links, imageUrl=logo, name=name)


async def resolve_tunein_station(station_id: str) -> BmxPlaybackResponse:
    """Resolve TuneIn station ID to playable stream URL.

    Args:
        station_id: TuneIn station ID (e.g., "s158432" for Absolut Relax)

    Returns:
        BmxPlaybackResponse with stream URLs
    """
    logger.info(f"[BMX TUNEIN] Resolving station: {station_id}")

    if not _STATION_ID_RE.match(station_id):
        raise ValueError(f"Invalid station ID format: {station_id}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            describe_resp = await client.get(TUNEIN_DESCRIBE_URL % station_id)
            name, logo = _parse_tunein_describe_xml(describe_resp.text)

            stream_resp = await client.get(TUNEIN_STREAM_URL % station_id)
            stream_urls = [
                convert_https_to_http(u.strip())
                for u in stream_resp.text.splitlines()
                if u.strip()
            ]

            if not stream_urls:
                raise ValueError(f"No stream URLs found for station {station_id}")

            logger.info(f"[BMX TUNEIN] Resolved {station_id} → {stream_urls[0]}")
            return _build_tunein_playback_response(station_id, stream_urls, name, logo)

    except Exception as e:
        logger.error(f"[BMX TUNEIN] Error resolving {station_id}: {e}")
        raise
