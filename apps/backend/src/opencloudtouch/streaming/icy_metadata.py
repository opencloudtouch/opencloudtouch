"""ICY stream metadata probe and parser.

Connects to a radio stream URL, extracts ICY metadata (artist, track)
from the first metadata block, then closes the connection immediately.

This is a **separate probe** — it does NOT interfere with the audio
stream proxy in preset_stream_routes.py.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Maximum bytes to read before giving up (256 KB should be enough for any metaint)
_MAX_PROBE_BYTES = 256 * 1024

# Common separators between artist and track in StreamTitle
# Order matters: try " - " first (most common), then " / "
_SEPARATORS = (" - ", " / ")


@dataclass(frozen=True, slots=True)
class IcyMetadata:
    """Parsed ICY metadata from a radio stream."""

    artist: str | None
    track: str | None
    raw_title: str  # Original StreamTitle value, unmodified
    station_logo_url: str | None = None  # From icy-url header (station homepage/logo)


def parse_stream_title(raw_title: str, station_name: str | None = None) -> IcyMetadata:
    """Parse a StreamTitle string into artist/track.

    Handles these real-world formats (from sample collection):
      - "Kygo with Khalid  - Save my love"  → artist="Kygo with Khalid", track="Save my love"
      - "Save my love / Kygo with Khalid"   → artist="Kygo with Khalid", track="Save my love"
      - "Free The Robots - Jazzhole"         → artist="Free The Robots", track="Jazzhole"
      - "Siouxsie and the Banshees - Spellbound (12 mix)" → preserves parenthetical
      - "Die junge Nacht der ARD"            → artist=None, track="Die junge Nacht der ARD"
      - "" or whitespace                     → returns None for both
      - Title == station_name                → skip (not real metadata)
      - "9999999 - 9999999"                  → passes through (we don't filter dummy data)

    Args:
        raw_title: The raw StreamTitle value from ICY metadata.
        station_name: If provided, titles matching station_name are treated as
                      "no metadata" (station just echoes its own name).

    Returns:
        IcyMetadata with parsed artist/track, or None values if unparseable.
    """
    title = raw_title.strip()

    if not title:
        return IcyMetadata(artist=None, track=None, raw_title=raw_title)

    # Skip if title is just the station name echoed back
    if station_name and title.lower() == station_name.lower():
        return IcyMetadata(artist=None, track=None, raw_title=raw_title)

    # Try each separator
    for sep in _SEPARATORS:
        if sep in title:
            parts = title.split(sep, 1)
            left = parts[0].strip()
            right = parts[1].strip()
            if left and right:
                if sep == " / ":
                    # "Track / Artist" format (observed in SWR3)
                    return IcyMetadata(artist=right, track=left, raw_title=raw_title)
                # "Artist - Track" format (most common)
                return IcyMetadata(artist=left, track=right, raw_title=raw_title)

    # No separator found — treat entire string as track name
    return IcyMetadata(artist=None, track=title, raw_title=raw_title)


def _extract_stream_title(meta_text: str) -> str | None:
    """Extract StreamTitle value from an ICY metadata string.

    ICY metadata format: StreamTitle='value';StreamUrl='value';
    Values may contain escaped single quotes.
    """
    match = re.search(r"StreamTitle='(.*?)';", meta_text)
    if match:
        return match.group(1)
    # Fallback: some servers don't terminate with ;
    match = re.search(r"StreamTitle='(.*?)'", meta_text)
    if match:
        return match.group(1)
    return None


def _decode_icy_bytes(raw: bytes) -> str:
    """Decode ICY metadata bytes, handling encoding variations.

    ICY protocol historically uses Latin-1, but many modern servers
    send UTF-8. Try UTF-8 first, fall back to Latin-1.
    """
    try:
        return raw.decode("utf-8").rstrip("\x00")
    except UnicodeDecodeError:
        return raw.decode("latin-1").rstrip("\x00")


async def probe_stream(
    url: str,
    timeout: float = 5.0,
    station_name: str | None = None,
) -> IcyMetadata | None:
    """Probe a radio stream for ICY metadata.

    Opens an HTTP connection with Icy-MetaData:1, reads until the first
    non-empty metadata block, parses it, and closes the connection.

    Args:
        url: Stream URL to probe.
        timeout: Maximum time in seconds for the entire probe.
        station_name: Optional station name to filter echo-back titles.

    Returns:
        IcyMetadata if metadata was found, None if stream doesn't
        support ICY or no metadata block was found within limits.
    """
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=3.0),
            follow_redirects=True,
        ) as client:
            async with client.stream(
                "GET",
                url,
                headers={
                    "Icy-MetaData": "1",
                    "User-Agent": "OCT-ICY-Probe/1.0",
                },
            ) as response:
                # Extract station logo URL from icy-url header
                icy_logo_url = response.headers.get("icy-url") or None

                metaint_str = response.headers.get("icy-metaint")
                if not metaint_str:
                    logger.debug("No icy-metaint header for %s", url)
                    return None

                try:
                    metaint = int(metaint_str)
                except ValueError:
                    logger.debug(
                        "Invalid icy-metaint value %r for %s", metaint_str, url
                    )
                    return None

                if metaint <= 0:
                    logger.debug("icy-metaint <= 0 for %s", url)
                    return None

                # Read stream and find first non-empty metadata block
                buffer = bytearray()
                bytes_consumed = 0

                async for chunk in response.aiter_bytes(4096):
                    buffer.extend(chunk)

                    # Process complete audio+metadata cycles
                    while len(buffer) > metaint:
                        # Skip audio data
                        buffer = buffer[metaint:]
                        bytes_consumed += metaint

                        if not buffer:
                            break

                        # Read metadata length byte
                        meta_length = buffer[0] * 16
                        if meta_length == 0:
                            # Empty metadata block — skip length byte, continue
                            buffer = buffer[1:]
                            bytes_consumed += 1
                            continue

                        if len(buffer) < 1 + meta_length:
                            # Need more data for the full metadata block
                            break

                        # Extract and decode metadata
                        raw_meta = bytes(buffer[1 : 1 + meta_length])
                        buffer = buffer[1 + meta_length :]
                        bytes_consumed += 1 + meta_length

                        meta_text = _decode_icy_bytes(raw_meta)
                        if not meta_text:
                            continue

                        title = _extract_stream_title(meta_text)
                        if title is not None:
                            result = parse_stream_title(title, station_name)
                            # Attach station logo from icy-url header
                            if icy_logo_url:
                                result = IcyMetadata(
                                    artist=result.artist,
                                    track=result.track,
                                    raw_title=result.raw_title,
                                    station_logo_url=icy_logo_url,
                                )
                            logger.debug(
                                "ICY probe %s: artist=%r track=%r logo=%r (raw=%r)",
                                url,
                                result.artist,
                                result.track,
                                result.station_logo_url,
                                result.raw_title,
                            )
                            return result

                    # Safety limit
                    if bytes_consumed > _MAX_PROBE_BYTES:
                        logger.debug(
                            "ICY probe hit %d byte limit for %s", _MAX_PROBE_BYTES, url
                        )
                        break

        logger.debug("ICY probe found no metadata for %s", url)
        return None

    except httpx.TimeoutException:
        logger.debug("ICY probe timeout for %s (%.1fs)", url, timeout)
        return None
    except httpx.ConnectError:
        logger.debug("ICY probe connection failed for %s", url)
        return None
    except Exception:
        logger.debug("ICY probe error for %s", url, exc_info=True)
        return None
