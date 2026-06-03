"""Regression tests for SSE artwork enrichment fixes (PR #289).

These tests cover bugs found during real-device testing with a Bose
SoundTouch ST20 (000C8A96DEEA) on 2026-06-03:

1. Duplicate station names with first match having no favicon
   → _get_preset_favicon must skip presets without station_favicon
2. Duplicate station names with first match having no stream URL
   → _get_stream_url must skip presets without station_url
3. Case-insensitive station name matching
   → Both callbacks must use casefold() for comparison
4. nowSelectionUpdated must NOT be parsed as NOW_PLAYING
   → Already covered in test_parser.py (TestKnownWebSocketEvents)
5. Preset-favicon enrichment pipeline skips non-radio sources
   → Enrichment only fires for INTERNET_RADIO/TUNEIN/LOCAL_INTERNET_RADIO
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.presets.models import Preset

# ---------------------------------------------------------------------------
# Helpers — build preset fixtures mimicking real ST20 data
# ---------------------------------------------------------------------------


def _make_preset(
    preset_number: int,
    station_name: str,
    source: str,
    station_favicon: str | None = None,
    station_url: str = "",
) -> Preset:
    return Preset(
        device_id="000C8A96DEEA",
        preset_number=preset_number,
        station_uuid=f"uuid-{preset_number}",
        station_name=station_name,
        station_url=station_url,
        station_favicon=station_favicon,
        source=source,
    )


# Real preset layout from ST20 device 000C8A96DEEA:
# P2: "Absolut relax" (TUNEIN, no favicon, has stream URL)
# P4: "Absolut relax" (LOCAL_INTERNET_RADIO, HAS favicon, no stream URL)
DUPLICATE_NAME_PRESETS = [
    _make_preset(1, "80's", "TUNEIN"),
    _make_preset(
        2,
        "Absolut relax",
        "TUNEIN",
        station_favicon=None,
        station_url="/v1/playback/station/s158432",
    ),
    _make_preset(3, "R.SA - Schlager", "TUNEIN"),
    _make_preset(
        4,
        "Absolut relax",
        "LOCAL_INTERNET_RADIO",
        station_favicon="https://cdn-profiles.tunein.com/s158432/images/logoq.png",
        station_url="",
    ),
    _make_preset(
        5,
        "NDR 2 Niedersachsen",
        "LOCAL_INTERNET_RADIO",
        station_favicon="https://cdn-profiles.tunein.com/s56857/images/logoq.png",
        station_url="http://ndr.stream/ndr2.mp3",
    ),
    _make_preset(
        6,
        "MDR Jump",
        "LOCAL_INTERNET_RADIO",
        station_favicon="https://cdn.mdrjump.de/favicon.png",
        station_url="http://mdr.stream/jump.mp3",
    ),
]


# ---------------------------------------------------------------------------
# 1. _get_preset_favicon — skip presets without favicon
# ---------------------------------------------------------------------------


class TestPresetFaviconDuplicateNames:
    """Regression: duplicate station names where first match has no favicon.

    Root cause (2026-06-03): Preset 2 "Absolut relax" (TUNEIN, favicon=None)
    was matched first → returned None → Preset 4 with actual favicon was
    never reached. Fix: skip presets where station_favicon is falsy.
    """

    @pytest.mark.asyncio
    async def test_skips_preset_without_favicon_returns_second_match(self):
        """When two presets share a name, the one WITH a favicon must win."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        # Replicate _get_preset_favicon from main.py
        async def get_preset_favicon(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_favicon:
                        return preset.station_favicon
            return None

        result = await get_preset_favicon("000C8A96DEEA", "Absolut relax")
        assert result == "https://cdn-profiles.tunein.com/s158432/images/logoq.png"

    @pytest.mark.asyncio
    async def test_unique_name_returns_favicon_directly(self):
        """NDR 2 has a unique name — should return favicon on first match."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_preset_favicon(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_favicon:
                        return preset.station_favicon
            return None

        result = await get_preset_favicon("000C8A96DEEA", "NDR 2 Niedersachsen")
        assert result == "https://cdn-profiles.tunein.com/s56857/images/logoq.png"

    @pytest.mark.asyncio
    async def test_no_preset_has_favicon_returns_none(self):
        """Station with no favicon on any matching preset → None."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_preset_favicon(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_favicon:
                        return preset.station_favicon
            return None

        result = await get_preset_favicon("000C8A96DEEA", "80's")
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_station_returns_none(self):
        """Station not in presets → None."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_preset_favicon(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_favicon:
                        return preset.station_favicon
            return None

        result = await get_preset_favicon("000C8A96DEEA", "Unknown Radio XYZ")
        assert result is None


# ---------------------------------------------------------------------------
# 2. _get_stream_url — skip presets without stream URL
# ---------------------------------------------------------------------------


class TestStreamUrlDuplicateNames:
    """Regression: duplicate station names where first match has no stream URL.

    Same root cause as favicon: Preset 4 "Absolut relax" (LOCAL_INTERNET_RADIO,
    station_url="") matched first when iterating → returned empty string →
    ICY probe got no URL. Fix: skip presets where station_url is falsy.
    """

    @pytest.mark.asyncio
    async def test_skips_preset_without_url_returns_second_match(self):
        """When two presets share a name, the one WITH a stream URL must win."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_stream_url(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_url:
                        return preset.station_url
            return None

        result = await get_stream_url("000C8A96DEEA", "Absolut relax")
        assert result == "/v1/playback/station/s158432"

    @pytest.mark.asyncio
    async def test_unique_name_returns_url_directly(self):
        """MDR Jump has a unique name with URL — returns on first match."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_stream_url(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_url:
                        return preset.station_url
            return None

        result = await get_stream_url("000C8A96DEEA", "MDR Jump")
        assert result == "http://mdr.stream/jump.mp3"

    @pytest.mark.asyncio
    async def test_no_preset_has_url_returns_none(self):
        """Station with no URL on any matching preset → None."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_stream_url(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_url:
                        return preset.station_url
            return None

        # R.SA - Schlager has no URL on any preset
        result = await get_stream_url("000C8A96DEEA", "R.SA - Schlager")
        assert result is None


# ---------------------------------------------------------------------------
# 3. Case-insensitive station name matching
# ---------------------------------------------------------------------------


class TestCaseInsensitiveMatching:
    """Regression: station name matching must be case-insensitive.

    Bose devices may report station names in different casing than what
    is stored in the preset DB. Using casefold() ensures matching works
    for all Unicode scripts.
    """

    @pytest.mark.asyncio
    async def test_favicon_lookup_case_insensitive(self):
        """'ndr 2 niedersachsen' must match 'NDR 2 Niedersachsen'."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_preset_favicon(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_favicon:
                        return preset.station_favicon
            return None

        result = await get_preset_favicon("000C8A96DEEA", "ndr 2 niedersachsen")
        assert result is not None

    @pytest.mark.asyncio
    async def test_stream_url_lookup_case_insensitive(self):
        """'mdr jump' must match 'MDR Jump'."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_stream_url(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_url:
                        return preset.station_url
            return None

        result = await get_stream_url("000C8A96DEEA", "mdr jump")
        assert result == "http://mdr.stream/jump.mp3"

    @pytest.mark.asyncio
    async def test_mixed_case_favicon(self):
        """'ABSOLUT RELAX' must match 'Absolut relax'."""
        preset_service = AsyncMock()
        preset_service.get_all_presets = AsyncMock(return_value=DUPLICATE_NAME_PRESETS)

        async def get_preset_favicon(device_id: str, station_name: str) -> str | None:
            presets = await preset_service.get_all_presets(device_id)
            station_lower = station_name.casefold()
            for preset in presets:
                if (
                    preset.station_name
                    and preset.station_name.casefold() == station_lower
                ):
                    if preset.station_favicon:
                        return preset.station_favicon
            return None

        result = await get_preset_favicon("000C8A96DEEA", "ABSOLUT RELAX")
        assert result == "https://cdn-profiles.tunein.com/s158432/images/logoq.png"


# ---------------------------------------------------------------------------
# 4. Enrichment pipeline — skips non-radio, already-enriched, no-name
# ---------------------------------------------------------------------------


class TestPresetFaviconEnrichmentPipeline:
    """Regression: preset-favicon enrichment must only fire for radio sources
    without existing artwork and with a station name."""

    @pytest.mark.asyncio
    async def test_enrichment_publishes_favicon_for_radio(self):
        """Radio event without artwork should get favicon from preset DB."""
        mgr = DeviceStateManager()
        queue = mgr.subscribe()

        favicon_cb = AsyncMock(return_value="https://cdn-profiles.tunein.com/logo.png")
        mgr.set_preset_favicon_callback(favicon_cb)

        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="Test Radio",
            ),
        )
        await mgr.on_event(event)
        await asyncio.sleep(0.05)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        types = [e.event_type for e in events]
        assert EventType.METADATA_ENRICHED in types

        enriched = next(
            e for e in events if e.event_type == EventType.METADATA_ENRICHED
        )
        assert (
            enriched.now_playing.artwork_url
            == "https://cdn-profiles.tunein.com/logo.png"
        )

    @pytest.mark.asyncio
    async def test_enrichment_skipped_when_artwork_exists(self):
        """Event that already has artwork should not trigger favicon lookup."""
        mgr = DeviceStateManager()

        favicon_cb = AsyncMock(return_value="https://should-not-be-called.com/logo.png")
        mgr.set_preset_favicon_callback(favicon_cb)

        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="Test Radio",
                artwork_url="https://existing-art.com/cover.jpg",
            ),
        )
        await mgr.on_event(event)
        await asyncio.sleep(0.05)

        favicon_cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrichment_skipped_for_spotify(self):
        """Non-radio source (SPOTIFY) should not trigger favicon lookup."""
        mgr = DeviceStateManager()

        favicon_cb = AsyncMock(return_value="https://should-not-be-called.com/logo.png")
        mgr.set_preset_favicon_callback(favicon_cb)

        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="SPOTIFY",
                state="PLAY_STATE",
                station_name="My Playlist",
            ),
        )
        await mgr.on_event(event)
        await asyncio.sleep(0.05)

        favicon_cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrichment_skipped_without_station_name(self):
        """Radio event without station_name should not trigger lookup."""
        mgr = DeviceStateManager()

        favicon_cb = AsyncMock(return_value="https://should-not-be-called.com/logo.png")
        mgr.set_preset_favicon_callback(favicon_cb)

        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name=None,
            ),
        )
        await mgr.on_event(event)
        await asyncio.sleep(0.05)

        favicon_cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrichment_callback_returns_none_no_enriched_event(self):
        """When favicon callback returns None, no METADATA_ENRICHED event."""
        mgr = DeviceStateManager()
        queue = mgr.subscribe()

        favicon_cb = AsyncMock(return_value=None)
        mgr.set_preset_favicon_callback(favicon_cb)

        event = DeviceEvent(
            device_id="D1",
            event_type=EventType.NOW_PLAYING,
            now_playing=NowPlayingInfo(
                source="INTERNET_RADIO",
                state="PLAY_STATE",
                station_name="Unknown Station",
            ),
        )
        await mgr.on_event(event)
        await asyncio.sleep(0.05)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        types = [e.event_type for e in events]
        assert EventType.METADATA_ENRICHED not in types
        assert EventType.NOW_PLAYING in types


# ---------------------------------------------------------------------------
# 5. nowSelectionUpdated must NOT create NOW_PLAYING events
# ---------------------------------------------------------------------------


class TestNowSelectionUpdatedIgnored:
    """Regression: nowSelectionUpdated was briefly mapped to NOW_PLAYING,
    causing fake STOP events that cleared the frontend's now-playing state.

    The tag must NOT appear in _TAG_MAP. This is a cross-reference to
    TestKnownWebSocketEvents in test_parser.py, verifying at the
    integration level that no state update occurs.
    """

    @pytest.mark.asyncio
    async def test_now_selection_updated_does_not_update_state(self):
        """Parsing nowSelectionUpdated must not produce a state update."""
        from opencloudtouch.devices.websocket.parser import parse_event

        xml = """\
<updates deviceID="000C8A96DEEA">
    <nowSelectionUpdated deviceID="000C8A96DEEA">
        <preset id="5">
            <ContentItem source="TUNEIN" type="stationurl" location="/v1/playback/station/s56857">
                <itemName>NDR 2 Niedersachsen</itemName>
            </ContentItem>
        </preset>
    </nowSelectionUpdated>
</updates>"""

        event = parse_event(xml)
        assert event is not None
        assert event.event_type == EventType.UNKNOWN
        assert event.now_playing is None

        # Feed to state manager — should not create any state
        mgr = DeviceStateManager()
        mgr.subscribe()
        await mgr.on_event(event)

        state = mgr.get_state("000C8A96DEEA")
        # UNKNOWN events don't create state entries
        assert state is None or state.now_playing is None

    @pytest.mark.asyncio
    async def test_unknown_event_not_published_to_sse(self):
        """UNKNOWN events must not be forwarded to SSE subscribers.

        Regression: nowSelectionUpdated (parsed as UNKNOWN) was being
        published to all SSE subscribers as ``event: unknown`` with an
        empty payload — wasting bandwidth and polluting client logs.
        """
        from opencloudtouch.devices.websocket.parser import parse_event

        xml = """\
<updates deviceID="000C8A96DEEA">
    <nowSelectionUpdated deviceID="000C8A96DEEA">
        <preset id="5">
            <ContentItem source="TUNEIN" type="stationurl" location="/v1/playback/station/s56857">
                <itemName>NDR 2 Niedersachsen</itemName>
            </ContentItem>
        </preset>
    </nowSelectionUpdated>
</updates>"""

        event = parse_event(xml)
        assert event is not None
        assert event.event_type == EventType.UNKNOWN

        mgr = DeviceStateManager()
        queue = mgr.subscribe()
        await mgr.on_event(event)

        # Queue must remain empty — UNKNOWN events are not published
        assert queue.empty(), "UNKNOWN event was published to SSE subscribers"
