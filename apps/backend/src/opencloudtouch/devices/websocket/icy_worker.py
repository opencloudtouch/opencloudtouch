"""ICY metadata background worker for radio streams.

Listens for ``now_playing`` events where the source is internet radio
and the artwork URL is missing.  Triggers an asynchronous ICY probe and
publishes a ``metadata_enriched`` event via the state manager on success.

Debounce: re-probes for the same station are skipped within 15 s.
"""

from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.streaming.icy_metadata import IcyMetadata, probe_stream
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

logger = logging.getLogger(__name__)

_RADIO_SOURCES = {"LOCAL_INTERNET_RADIO", "INTERNET_RADIO"}
_DEBOUNCE_SECONDS = 15.0

# Callback type: (device_id, station_name) -> stream_url | None
GetStreamUrl = Callable[[str, str], Awaitable[str | None]]


class IcyWorker:
    """Background worker that probes radio streams for ICY metadata.

    Args:
        get_stream_url: Async callable that resolves a station name to
            a stream URL via the preset database.
    """

    def __init__(self, get_stream_url: GetStreamUrl) -> None:
        self._get_stream_url = get_stream_url
        self._last_probe: dict[str, float] = {}  # station_name -> timestamp

    async def on_event(self, event: DeviceEvent) -> DeviceEvent | None:
        """Process a device event.  Returns a ``metadata_enriched`` event
        if ICY probe succeeds, or ``None`` otherwise.

        This is called from the state manager pipeline *after* the event
        has been stored and published.
        """
        if event.event_type != EventType.NOW_PLAYING:
            return None
        if not event.now_playing:
            return None

        info = event.now_playing
        if info.source not in _RADIO_SOURCES:
            return None

        # Already have artwork — no probe needed
        if info.artwork_url:
            return None

        if not info.station_name:
            return None

        # Debounce: skip if probed recently
        now = time.monotonic()
        last = self._last_probe.get(info.station_name, 0.0)
        if (now - last) < _DEBOUNCE_SECONDS:
            logger.debug(
                "ICY probe debounced for %s (%.1fs ago)",
                info.station_name,
                now - last,
            )
            return None

        self._last_probe[info.station_name] = now

        # Resolve stream URL from preset DB
        stream_url = await self._get_stream_url(event.device_id, info.station_name)
        if not stream_url:
            logger.debug(
                "No stream URL found for station %r on device %s",
                info.station_name,
                event.device_id,
            )
            return None

        # Probe in background — don't block the event pipeline
        icy = await self._probe(stream_url, info.station_name)
        if not icy:
            return None

        # Build enriched NowPlayingInfo with ICY data merged
        enriched = NowPlayingInfo(
            source=info.source,
            state=info.state,
            station_name=info.station_name,
            artist=icy.artist if not info.artist else info.artist,
            track=icy.track if not info.track else info.track,
            album=info.album,
            artwork_url=icy.station_logo_url or info.artwork_url,
        )

        return DeviceEvent(
            device_id=event.device_id,
            event_type=EventType.METADATA_ENRICHED,
            now_playing=enriched,
        )

    async def _probe(
        self, stream_url: str, station_name: str | None
    ) -> IcyMetadata | None:
        """Run ICY probe with error handling."""
        try:
            return await probe_stream(stream_url, station_name=station_name)
        except Exception:
            logger.debug("ICY probe failed for %s", stream_url, exc_info=True)
            return None
