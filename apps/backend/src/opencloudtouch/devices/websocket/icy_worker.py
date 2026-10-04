"""ICY metadata background worker for radio streams.

Listens for ``now_playing`` events where the source is internet radio
and the artwork URL is missing.  Triggers an asynchronous ICY probe and
publishes a ``metadata_enriched`` event via the state manager on success.

Debounce: re-probes for the same device/station are skipped within 15 s.
Periodic polling uses the same debounce and only emits when artist/track
actually changed.

Memory leak fix (#366): Both _last_probe and _last_metadata now use
LRU eviction with max 100 entries to prevent unbounded growth.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Awaitable, Callable

from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.streaming.icy_metadata import IcyMetadata, probe_stream

logger = logging.getLogger(__name__)

RADIO_SOURCES = frozenset({"LOCAL_INTERNET_RADIO", "INTERNET_RADIO", "TUNEIN"})
_DEBOUNCE_SECONDS = 15.0
_MAX_PROBE_HISTORY = 100  # Max entries for _last_probe and _last_metadata

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
        # LRU dicts with bounded size to prevent memory leak (#366)
        self._last_probe: OrderedDict[tuple[str, str], float] = OrderedDict()
        self._last_metadata: OrderedDict[str, tuple[str | None, str | None]] = (
            OrderedDict()
        )

    def _evict_if_needed(self, cache: OrderedDict) -> None:
        """Evict oldest entry if cache exceeds max size."""
        if len(cache) > _MAX_PROBE_HISTORY:
            oldest_key = next(iter(cache))
            cache.pop(oldest_key)

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
        if info.source not in RADIO_SOURCES:
            logger.debug(
                "ICY skip: source %s not radio for %s",
                info.source,
                event.device_id,
            )
            return None

        if info.state != "PLAY_STATE":
            logger.debug(
                "ICY skip: playback state %s for %s",
                info.state,
                event.device_id,
            )
            return None

        # Already have artwork — no probe needed
        if info.artwork_url:
            logger.debug(
                "ICY skip: artwork already present for %s (%s)",
                info.station_name,
                event.device_id,
            )
            return None

        if not info.station_name:
            logger.debug("ICY skip: no station_name for %s", event.device_id)
            return None

        # Debounce per device/station so multiple devices do not block
        # each other, while repeated probes for the same playback are limited.
        probe_key = (event.device_id, info.station_name)
        now = time.monotonic()
        last = self._last_probe.get(probe_key, 0.0)
        if (now - last) < _DEBOUNCE_SECONDS:
            logger.debug(
                "ICY probe debounced for %s on %s (%.1fs ago)",
                info.station_name,
                event.device_id,
                now - last,
            )
            return None

        self._last_probe[probe_key] = now
        self._last_probe.move_to_end(probe_key)
        self._evict_if_needed(self._last_probe)

        # Resolve stream URL from preset DB
        stream_url = await self._get_stream_url(event.device_id, info.station_name)
        if not stream_url:
            logger.debug(
                "No stream URL found for station %r on device %s",
                info.station_name,
                event.device_id,
            )
            return None

        logger.debug(
            "ICY probing %s for station %r on device %s",
            stream_url,
            info.station_name,
            event.device_id,
        )

        # Probe in background — don't block the event pipeline
        icy = await self._probe(stream_url, info.station_name)
        if not icy:
            logger.debug(
                "ICY probe returned no metadata for %s",
                info.station_name,
            )
            return None

        logger.debug(
            "ICY probe success for %s: artist=%s track=%s logo=%s",
            info.station_name,
            icy.artist,
            icy.track,
            bool(icy.station_logo_url),
        )

        # Build enriched NowPlayingInfo with ICY data merged
        enriched = NowPlayingInfo(
            source=info.source,
            state=info.state,
            station_name=info.station_name,
            artist=icy.artist or info.artist,
            track=icy.track or info.track,
            album=info.album,
            artwork_url=icy.station_logo_url or info.artwork_url,
        )

        return DeviceEvent(
            device_id=event.device_id,
            event_type=EventType.METADATA_ENRICHED,
            now_playing=enriched,
        )

    async def poll_stream(self, event: DeviceEvent) -> DeviceEvent | None:
        """Periodic poll with per-device/station debounce.

        Called by the state manager's periodic poll loop.  Network probes
        are limited to at most once per 15 s for the same device/station.
        """
        if not event.now_playing:
            return None

        info = event.now_playing
        if info.state != "PLAY_STATE":
            logger.debug(
                "ICY poll skip: playback state %s for %s",
                info.state,
                event.device_id,
            )
            return None
        if info.source not in RADIO_SOURCES:
            return None
        if not info.station_name:
            return None

        probe_key = (event.device_id, info.station_name)
        now = time.monotonic()
        last = self._last_probe.get(probe_key, 0.0)
        if (now - last) < _DEBOUNCE_SECONDS:
            logger.debug(
                "ICY poll debounced for %s on %s (%.1fs ago)",
                info.station_name,
                event.device_id,
                now - last,
            )
            return None

        self._last_probe[probe_key] = now
        self._last_probe.move_to_end(probe_key)
        self._evict_if_needed(self._last_probe)

        stream_url = await self._get_stream_url(event.device_id, info.station_name)
        if not stream_url:
            return None

        icy = await self._probe(stream_url, info.station_name)
        if not icy:
            return None

        # Only emit if metadata actually changed
        new_meta = (icy.artist, icy.track)
        old_meta = self._last_metadata.get(event.device_id)
        if new_meta == old_meta:
            return None

        self._last_metadata[event.device_id] = new_meta
        self._last_metadata.move_to_end(event.device_id)
        self._evict_if_needed(self._last_metadata)
        logger.debug(
            "ICY poll change for %s on %s: %s - %s",
            info.station_name,
            event.device_id,
            icy.artist,
            icy.track,
        )

        enriched = NowPlayingInfo(
            source=info.source,
            state=info.state,
            station_name=info.station_name,
            artist=icy.artist or info.artist,
            track=icy.track or info.track,
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
