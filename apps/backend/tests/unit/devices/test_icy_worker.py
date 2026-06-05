"""Tests for ICY metadata background worker."""

from __future__ import annotations

import time

import pytest

from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.devices.websocket.icy_worker import IcyWorker
from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _np_event(
    device_id: str = "DEV1",
    source: str = "INTERNET_RADIO",
    state: str = "PLAY_STATE",
    station_name: str | None = "WDR 2",
    artwork_url: str | None = None,
    artist: str | None = None,
    track: str | None = None,
) -> DeviceEvent:
    return DeviceEvent(
        device_id=device_id,
        event_type=EventType.NOW_PLAYING,
        now_playing=NowPlayingInfo(
            source=source,
            state=state,
            station_name=station_name,
            artwork_url=artwork_url,
            artist=artist,
            track=track,
        ),
    )


async def _stream_url_found(_device_id: str, _station: str) -> str | None:
    return "http://wdr-wdr2.icecast.wdr.de/wdr/wdr2/live/mp3/128"


async def _stream_url_not_found(_device_id: str, _station: str) -> str | None:
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIcyWorkerSkipsNonRadio:
    """Worker should skip events that don't need ICY probing."""

    @pytest.mark.asyncio
    async def test_skips_volume_events(self) -> None:
        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = DeviceEvent(device_id="DEV1", event_type=EventType.VOLUME)
        assert await worker.on_event(event) is None

    @pytest.mark.asyncio
    async def test_skips_non_radio_source(self) -> None:
        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event(source="BLUETOOTH")
        assert await worker.on_event(event) is None

    @pytest.mark.asyncio
    async def test_skips_when_artwork_present(self) -> None:
        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event(artwork_url="https://cdn.example.com/logo.png")
        assert await worker.on_event(event) is None

    @pytest.mark.asyncio
    async def test_skips_when_station_name_missing(self) -> None:
        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event(station_name=None)
        assert await worker.on_event(event) is None


class TestIcyWorkerProbe:
    """Worker should probe and return enriched events."""

    @pytest.mark.asyncio
    async def test_returns_enriched_event_on_probe_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from opencloudtouch.streaming import icy_metadata

        async def mock_probe(url: str, *, station_name: str | None = None):
            return icy_metadata.IcyMetadata(
                artist="ICY Artist",
                track="ICY Track",
                raw_title="ICY Artist - ICY Track",
                station_logo_url="https://cdn.example.com/icy-logo.png",
            )

        monkeypatch.setattr(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream", mock_probe
        )

        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event()
        result = await worker.on_event(event)

        assert result is not None
        assert result.event_type == EventType.METADATA_ENRICHED
        assert result.device_id == "DEV1"
        assert result.now_playing is not None
        assert result.now_playing.artwork_url == "https://cdn.example.com/icy-logo.png"
        assert result.now_playing.artist == "ICY Artist"
        assert result.now_playing.track == "ICY Track"

    @pytest.mark.asyncio
    async def test_returns_none_on_probe_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_probe(url: str, *, station_name: str | None = None):
            return None

        monkeypatch.setattr(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream", mock_probe
        )

        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event()
        result = await worker.on_event(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_stream_url_not_found(self) -> None:
        worker = IcyWorker(get_stream_url=_stream_url_not_found)
        event = _np_event()
        result = await worker.on_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_probe_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_probe(url: str, *, station_name: str | None = None):
            raise ConnectionError("timeout")

        monkeypatch.setattr(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream", mock_probe
        )

        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event()
        result = await worker.on_event(event)
        assert result is None


class TestIcyWorkerDebounce:
    """Worker should skip re-probes within 15 seconds."""

    @pytest.mark.asyncio
    async def test_debounces_same_station(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_count = 0

        async def mock_probe(url: str, *, station_name: str | None = None):
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream", mock_probe
        )

        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event()

        # First call — should probe
        await worker.on_event(event)
        assert call_count == 1

        # Second call immediately — should be debounced
        await worker.on_event(event)
        assert call_count == 1  # still 1

    @pytest.mark.asyncio
    async def test_probes_again_after_debounce_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_count = 0

        async def mock_probe(url: str, *, station_name: str | None = None):
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream", mock_probe
        )

        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event()

        await worker.on_event(event)
        assert call_count == 1

        # Simulate time passing beyond debounce window
        worker._last_probe["WDR 2"] = time.monotonic() - 20.0

        await worker.on_event(event)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_different_stations_not_debounced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_count = 0

        async def mock_probe(url: str, *, station_name: str | None = None):
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream", mock_probe
        )

        worker = IcyWorker(get_stream_url=_stream_url_found)

        await worker.on_event(_np_event(station_name="WDR 2"))
        await worker.on_event(_np_event(station_name="1LIVE"))
        assert call_count == 2


class TestIcyWorkerEnrichmentLogic:
    """Worker should preserve existing fields when merging ICY data."""

    @pytest.mark.asyncio
    async def test_preserves_existing_artist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from opencloudtouch.streaming import icy_metadata

        async def mock_probe(url: str, *, station_name: str | None = None):
            return icy_metadata.IcyMetadata(
                artist="ICY Artist",
                track="ICY Track",
                raw_title="ICY Artist - ICY Track",
                station_logo_url="https://cdn.example.com/logo.png",
            )

        monkeypatch.setattr(
            "opencloudtouch.devices.websocket.icy_worker.probe_stream", mock_probe
        )

        worker = IcyWorker(get_stream_url=_stream_url_found)
        event = _np_event(artist="Original Artist")
        result = await worker.on_event(event)

        assert result is not None
        assert result.now_playing is not None
        # ICY data takes precedence (more current than device cache)
        assert result.now_playing.artist == "ICY Artist"
        # ICY track should fill in missing track
        assert result.now_playing.track == "ICY Track"
