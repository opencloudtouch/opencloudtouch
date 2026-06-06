"""Tests for IcyWorker — ICY metadata background worker."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.websocket.icy_worker import _DEBOUNCE_SECONDS, IcyWorker
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType
from opencloudtouch.streaming.icy_metadata import IcyMetadata


def _np(
    source="INTERNET_RADIO",
    state="PLAY_STATE",
    station_name="WDR 2",
    artwork_url=None,
    artist=None,
    track=None,
) -> NowPlayingInfo:
    return NowPlayingInfo(
        source=source,
        state=state,
        station_name=station_name,
        artwork_url=artwork_url,
        artist=artist,
        track=track,
    )


def _event(device_id="D1", np=None, event_type=EventType.NOW_PLAYING) -> DeviceEvent:
    return DeviceEvent(device_id=device_id, event_type=event_type, now_playing=np)


class TestIcyWorkerOnEvent:
    @pytest.mark.asyncio
    async def test_skip_non_now_playing_event(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(event_type=EventType.VOLUME, np=None)
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_no_now_playing_data(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(np=None)
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_non_radio_source(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(np=_np(source="BLUETOOTH"))
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_local_internet_radio_with_artwork(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(
            np=_np(source="LOCAL_INTERNET_RADIO", artwork_url="http://art.png")
        )
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_no_station_name(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(np=_np(station_name=None))
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_debounce_skips_recent_probe(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)
        worker._last_probe["WDR 2"] = time.monotonic()

        event = _event(np=_np())
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_stream_url_returns_none(self):
        get_url = AsyncMock(return_value=None)
        worker = IcyWorker(get_stream_url=get_url)

        event = _event(np=_np())
        result = await worker.on_event(event)
        assert result is None
        get_url.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_probe_returns_none_metadata(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=None,
        ):
            event = _event(np=_np())
            result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_probe_success_returns_enriched_event(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        icy = IcyMetadata(
            artist="Test Artist",
            track="Test Track",
            raw_title="Test Artist - Test Track",
            station_logo_url="http://logo.png",
        )
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np(artist="Old", track="Old"))
            result = await worker.on_event(event)

        assert result is not None
        assert result.event_type == EventType.METADATA_ENRICHED
        assert result.device_id == "D1"
        assert result.now_playing.artist == "Test Artist"
        assert result.now_playing.track == "Test Track"
        assert result.now_playing.artwork_url == "http://logo.png"

    @pytest.mark.asyncio
    async def test_probe_exception_returns_none(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            event = _event(np=_np())
            result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_debounce_allows_after_timeout(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)
        worker._last_probe["WDR 2"] = time.monotonic() - _DEBOUNCE_SECONDS - 1

        icy = IcyMetadata(artist="A", track="T", raw_title="A - T")
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np())
            result = await worker.on_event(event)
        assert result is not None

    @pytest.mark.asyncio
    async def test_local_internet_radio_source_accepted(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        icy = IcyMetadata(artist="A", track="T", raw_title="A - T")
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np(source="LOCAL_INTERNET_RADIO"))
            result = await worker.on_event(event)
        assert result is not None

    @pytest.mark.asyncio
    async def test_enriched_preserves_original_fields(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        icy = IcyMetadata(artist=None, track=None, raw_title="", station_logo_url=None)
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(
                np=_np(artist="OrigArtist", track="OrigTrack", artwork_url=None)
            )
            result = await worker.on_event(event)

        assert result is not None
        assert result.now_playing.artist == "OrigArtist"
        assert result.now_playing.track == "OrigTrack"


class TestIcyWorkerPollStream:
    @pytest.mark.asyncio
    async def test_poll_skip_no_now_playing(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(np=None)
        result = await worker.poll_stream(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_skip_non_radio(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(np=_np(source="AUX"))
        result = await worker.poll_stream(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_skip_no_station_name(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(np=_np(station_name=None))
        result = await worker.poll_stream(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_skip_no_stream_url(self):
        get_url = AsyncMock(return_value=None)
        worker = IcyWorker(get_stream_url=get_url)
        event = _event(np=_np())
        result = await worker.poll_stream(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_skip_no_icy_metadata(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=None,
        ):
            event = _event(np=_np())
            result = await worker.poll_stream(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_skip_unchanged_metadata(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)
        worker._last_metadata["D1"] = ("Artist", "Track")

        icy = IcyMetadata(artist="Artist", track="Track", raw_title="Artist - Track")
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np())
            result = await worker.poll_stream(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_emits_on_changed_metadata(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)
        worker._last_metadata["D1"] = ("Old Artist", "Old Track")

        icy = IcyMetadata(
            artist="New Artist",
            track="New Track",
            raw_title="New Artist - New Track",
            station_logo_url="http://logo.png",
        )
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np())
            result = await worker.poll_stream(event)

        assert result is not None
        assert result.event_type == EventType.METADATA_ENRICHED
        assert result.now_playing.artist == "New Artist"
        assert result.now_playing.track == "New Track"
        assert worker._last_metadata["D1"] == ("New Artist", "New Track")

    @pytest.mark.asyncio
    async def test_poll_emits_first_time(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        icy = IcyMetadata(artist="A", track="T", raw_title="A - T")
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np())
            result = await worker.poll_stream(event)
        assert result is not None


class TestIcyWorkerTuneInSource:
    """Regression: TUNEIN source was excluded from RADIO_SOURCES,
    causing no artwork enrichment for TuneIn presets via WebSocket."""

    @pytest.mark.asyncio
    async def test_tunein_source_accepted(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        icy = IcyMetadata(
            artist="Artist",
            track="Track",
            raw_title="Artist - Track",
            station_logo_url="http://logo.png",
        )
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np(source="TUNEIN"))
            result = await worker.on_event(event)

        assert result is not None
        assert result.event_type == EventType.METADATA_ENRICHED
        assert result.now_playing.artwork_url == "http://logo.png"

    @pytest.mark.asyncio
    async def test_tunein_source_with_existing_artwork_skipped(self):
        worker = IcyWorker(get_stream_url=AsyncMock())
        event = _event(np=_np(source="TUNEIN", artwork_url="http://existing-art.png"))
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_tunein_poll_stream_accepted(self):
        get_url = AsyncMock(return_value="http://stream.example.com/radio")
        worker = IcyWorker(get_stream_url=get_url)

        icy = IcyMetadata(
            artist="A",
            track="T",
            raw_title="A - T",
            station_logo_url="http://logo.png",
        )
        with patch(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream",
            new_callable=AsyncMock,
            return_value=icy,
        ):
            event = _event(np=_np(source="TUNEIN"))
            result = await worker.poll_stream(event)

        assert result is not None
        assert result.event_type == EventType.METADATA_ENRICHED
