"""Tests for NowPlaying enrichment from preset DB and ICY metadata.

Covers Phase 0 + Phase 3 of spec 008-metadata-stream:
- artwork_url populated from station_favicon when device returns None
- artist/track populated from ICY probe when device returns None
- No enrichment when device already provides data
- No enrichment for non-radio sources
- Graceful handling when no matching preset found
- Cache behavior for ICY probes
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_device_service, get_preset_service
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.main import app
from opencloudtouch.presets.models import Preset
from opencloudtouch.streaming.icy_metadata import IcyMetadata


def _make_preset(**overrides) -> Preset:
    defaults = dict(
        device_id="DEV1",
        preset_number=1,
        station_uuid="uuid-abc",
        station_name="Test Radio",
        station_url="http://stream.test/radio.mp3",
        station_homepage=None,
        station_favicon="http://radio.test/logo.png",
        source="LOCAL_INTERNET_RADIO",
    )
    defaults.update(overrides)
    preset = Preset(**defaults)
    preset.id = overrides.get("id", 1)
    return preset


def _make_now_playing(**overrides) -> NowPlayingInfo:
    defaults = dict(
        source="LOCAL_INTERNET_RADIO",
        state="PLAY_STATE",
        station_name="Test Radio",
        artist=None,
        track=None,
        album=None,
        artwork_url=None,
    )
    defaults.update(overrides)
    return NowPlayingInfo(**defaults)


@pytest.fixture
def mock_device_service():
    return AsyncMock()


@pytest.fixture
def mock_preset_service():
    return AsyncMock()


@pytest.fixture
def client(mock_device_service, mock_preset_service):
    # Clear ICY metadata cache between tests
    from opencloudtouch.devices.api.routes import _metadata_cache

    _metadata_cache.invalidate_all()

    app.dependency_overrides[get_device_service] = lambda: mock_device_service
    app.dependency_overrides[get_preset_service] = lambda: mock_preset_service
    yield TestClient(app)
    app.dependency_overrides.clear()
    _metadata_cache.invalidate_all()


class TestNowPlayingArtworkEnrichment:
    """Tests for artwork fallback from preset DB."""

    def test_artwork_enriched_from_preset_db(
        self, client, mock_device_service, mock_preset_service
    ):
        """When device returns no artwork for radio source, use station_favicon."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[_make_preset()])

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] == "http://radio.test/logo.png"

    def test_no_enrichment_when_device_has_artwork(
        self, client, mock_device_service, mock_preset_service
    ):
        """Device artwork takes priority — artwork not overwritten from DB."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(artwork_url="http://device.art/cover.jpg")
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[_make_preset()])

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] == "http://device.art/cover.jpg"

    def test_no_enrichment_for_non_radio_source(
        self, client, mock_device_service, mock_preset_service
    ):
        """Non-radio sources (BLUETOOTH, AUX) should not trigger preset lookup."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(source="BLUETOOTH")
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] is None
        mock_preset_service.get_all_presets.assert_not_called()

    def test_no_enrichment_when_no_matching_preset(
        self, client, mock_device_service, mock_preset_service
    ):
        """No matching station_name in presets → artwork stays None."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(station_name="Unknown Station")
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[_make_preset(station_name="Different Radio")]
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] is None

    def test_no_enrichment_when_preset_has_no_favicon(
        self, client, mock_device_service, mock_preset_service
    ):
        """Matching preset but no favicon → artwork stays None."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[_make_preset(station_favicon=None)]
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] is None

    def test_enrichment_survives_preset_service_error(
        self, client, mock_device_service, mock_preset_service
    ):
        """Preset service failure should not break NowPlaying response."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] is None

    def test_internet_radio_source_also_enriched(
        self, client, mock_device_service, mock_preset_service
    ):
        """INTERNET_RADIO source should also trigger enrichment."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(source="INTERNET_RADIO")
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[_make_preset(station_name="Test Radio")]
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] == "http://radio.test/logo.png"

    def test_no_enrichment_when_station_name_is_none(
        self, client, mock_device_service, mock_preset_service
    ):
        """No station_name from device → can't match preset, skip enrichment."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(station_name=None)
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] is None
        mock_preset_service.get_all_presets.assert_not_called()


class TestNowPlayingIcyEnrichment:
    """Tests for artist/track enrichment from ICY metadata probe."""

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_artist_track_enriched_from_icy_probe(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """When device returns no artist/track, ICY probe fills them."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[_make_preset()])
        mock_probe.return_value = IcyMetadata(
            artist="Kygo", track="Save my love", raw_title="Kygo - Save my love"
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        data = r.json()
        assert data["artist"] == "Kygo"
        assert data["track"] == "Save my love"
        mock_probe.assert_called_once()

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_device_artist_track_takes_priority(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """Device data has priority — ICY probe should not override existing fields."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(
                artist="Device Artist",
                track="Device Track",
                artwork_url="http://device.art/cover.jpg",
            )
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[_make_preset()])

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        data = r.json()
        assert data["artist"] == "Device Artist"
        assert data["track"] == "Device Track"
        assert data["artwork_url"] == "http://device.art/cover.jpg"
        mock_probe.assert_not_called()

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_icy_probe_cached_on_second_call(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """Second poll should use cached ICY data, not probe again."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[_make_preset()])
        mock_probe.return_value = IcyMetadata(
            artist="Kygo", track="Save my love", raw_title="Kygo - Save my love"
        )

        # First call — probes
        r1 = client.get("/api/devices/DEV1/now-playing")
        assert r1.json()["artist"] == "Kygo"
        assert mock_probe.call_count == 1

        # Second call — uses cache
        r2 = client.get("/api/devices/DEV1/now-playing")
        assert r2.json()["artist"] == "Kygo"
        assert mock_probe.call_count == 1  # NOT called again

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_icy_probe_failure_does_not_break_response(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """ICY probe exception should not break NowPlaying response."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[_make_preset()])
        mock_probe.side_effect = RuntimeError("Connection refused")

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artist"] is None

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_no_icy_probe_without_matching_preset(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """No matching preset → no stream_url → no ICY probe."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(station_name="Unknown Station")
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[_make_preset(station_name="Different Radio")]
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        mock_probe.assert_not_called()

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_no_metadata_stream_not_reprobed(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """Stream that returns None from probe should not be re-probed."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[_make_preset()])
        mock_probe.return_value = None  # No ICY support

        # First call — probes, gets None
        r1 = client.get("/api/devices/DEV1/now-playing")
        assert r1.status_code == 200
        assert mock_probe.call_count == 1

        # Second call — should NOT probe again (cached as no-metadata)
        r2 = client.get("/api/devices/DEV1/now-playing")
        assert r2.status_code == 200
        assert mock_probe.call_count == 1

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_icy_logo_url_used_as_artwork_fallback(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """When no artwork from device or DB, use icy-url header as fallback."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(
                artist="Nickelback", track="How You Remind Me"
            )
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[_make_preset(station_favicon=None)]
        )
        mock_probe.return_value = IcyMetadata(
            artist="Nickelback",
            track="How You Remind Me",
            raw_title="Nickelback - How You Remind Me",
            station_logo_url="http://radio-station.com/logo.png",
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] == "http://radio-station.com/logo.png"

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_preset_favicon_takes_priority_over_icy_logo(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """Preset favicon from DB has higher priority than icy-url logo."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing()
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[_make_preset()]  # has station_favicon
        )
        mock_probe.return_value = IcyMetadata(
            artist="Kygo",
            track="Save my love",
            raw_title="Kygo - Save my love",
            station_logo_url="http://icy-fallback.com/logo.png",
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        # Preset favicon wins (set in DB enrichment before ICY probe)
        assert r.json()["artwork_url"] == "http://radio.test/logo.png"


class TestIsImageUrl:
    """Tests for _is_image_url heuristic that filters non-image artwork URLs."""

    def test_accepts_png_extension(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        assert _is_image_url("https://example.com/logo.png") is True

    def test_accepts_jpg_extension(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        assert _is_image_url("https://example.com/art.jpg") is True

    def test_accepts_tunein_cdn(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        url = "https://cdn-profiles.tunein.com/s158432/images/logoq.png?t=123"
        assert _is_image_url(url) is True

    def test_accepts_path_with_images_segment(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        assert _is_image_url("https://example.com/images/logo") is True

    def test_accepts_favicon_path(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        assert _is_image_url("https://example.com/favicon") is True

    def test_rejects_homepage_url(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        assert _is_image_url("https://absolutradio.de/relax") is False

    def test_rejects_plain_domain(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        assert _is_image_url("https://example.com/") is False

    def test_rejects_html_page(self):
        from opencloudtouch.devices.api.routes import _is_image_url

        assert _is_image_url("https://radio.de/sender/swr3.html") is False


class TestArtworkFiltering:
    """Test that non-image artwork_url from device gets filtered to null."""

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_homepage_url_filtered_to_null(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """Device returns homepage as artwork → should be filtered to null, then enriched from DB."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(artwork_url="https://absolutradio.de/relax")
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[_make_preset()]  # has station_favicon=logo.png
        )
        mock_probe.return_value = None

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        # Homepage filtered → preset favicon used instead
        assert r.json()["artwork_url"] == "http://radio.test/logo.png"

    @patch("opencloudtouch.devices.api.routes.probe_stream")
    def test_real_image_url_not_filtered(
        self, mock_probe, client, mock_device_service, mock_preset_service
    ):
        """Device returns actual image URL → should be kept."""
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(
                artwork_url="https://cdn.example.com/cover.jpg"
            )
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[])

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["artwork_url"] == "https://cdn.example.com/cover.jpg"


_UDN = "uuid:4D696E69-444C-164E-9D41-0000000000A1/0"


class TestStoredMusicNowPlaying:
    """Decision 31: DLNA now-playing is matched by location + account."""

    def test_stored_music_route_marks_slot_without_icy(
        self, client, mock_device_service, mock_preset_service
    ):
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(
                source="STORED_MUSIC", location="1$4", source_account=_UDN
            )
        )
        mock_preset_service.get_all_presets = AsyncMock(
            return_value=[
                _make_preset(
                    preset_number=3,
                    station_url="1$4",
                    source="STORED_MUSIC",
                    source_account=_UDN.upper(),
                    station_favicon="http://nas.test/cover.jpg",
                )
            ]
        )

        with patch("opencloudtouch.devices.api.routes.probe_stream") as probe:
            r = client.get("/api/devices/DEV1/now-playing")

        body = r.json()
        assert body["dlna"] is True
        assert body["preset_number"] == 3
        assert body["artwork_url"] == "http://nas.test/cover.jpg"
        probe.assert_not_called()

    def test_no_preset_null_slot(
        self, client, mock_device_service, mock_preset_service
    ):
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(
                source="STORED_MUSIC", location="1$4", source_account=_UDN
            )
        )
        mock_preset_service.get_all_presets = AsyncMock(return_value=[])

        body = client.get("/api/devices/DEV1/now-playing").json()

        assert body["dlna"] is True
        assert body["preset_number"] is None

    def test_radio_route_dlna_false(
        self, client, mock_device_service, mock_preset_service
    ):
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(source="BLUETOOTH")
        )

        body = client.get("/api/devices/DEV1/now-playing").json()

        assert body["dlna"] is False
        assert body["preset_number"] is None

    def test_sse_now_playing_has_dlna_fields(self):
        import json

        from opencloudtouch.devices.api.event_routes import (
            _event_to_sse,
            _snapshot_to_sse,
        )
        from opencloudtouch.devices.state import DeviceState
        from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

        info = _make_now_playing(source="STORED_MUSIC", location="1$4")
        event = DeviceEvent(
            device_id="DEV1", event_type=EventType.NOW_PLAYING, now_playing=info
        )
        state = DeviceState(device_id="DEV1", now_playing=info)
        for sse in (_event_to_sse(event), _snapshot_to_sse("DEV1", state)):
            data = json.loads(sse.split("data: ")[1].split("\n")[0])
            assert data["dlna"] is True
            assert data["preset_number"] is None


def _dlna_preset(number: int = 3) -> Preset:
    return _make_preset(
        preset_number=number,
        station_url="1$4",
        source="STORED_MUSIC",
        source_account=_UDN.upper(),
    )


async def _collect_sse(preset_service) -> list[dict]:
    """Run the SSE generator over one snapshot and one queued event."""
    import asyncio
    import json
    from unittest.mock import MagicMock

    from opencloudtouch.devices.api.event_routes import _stream_events
    from opencloudtouch.devices.state import DeviceState
    from opencloudtouch.devices.websocket.parser import DeviceEvent, EventType

    info = _make_now_playing(source="STORED_MUSIC", location="1$4", source_account=_UDN)
    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait(
        DeviceEvent(
            device_id="DEV1", event_type=EventType.NOW_PLAYING, now_playing=info
        )
    )
    state_manager = MagicMock()
    state_manager.subscribe.return_value = queue
    state_manager.get_all_states.return_value = {
        "DEV1": DeviceState(device_id="DEV1", now_playing=info)
    }
    request = MagicMock()
    request.is_disconnected = AsyncMock(side_effect=[False, True])

    messages = [m async for m in _stream_events(request, state_manager, preset_service)]
    return [json.loads(m.split("data: ")[1].split("\n")[0]) for m in messages]


class TestSSEPresetSlot:
    @pytest.mark.asyncio
    async def test_sse_event_and_snapshot_mark_matching_slot(self):
        service = AsyncMock()
        service.get_all_presets.return_value = [_dlna_preset(3)]

        snapshot, event = await _collect_sse(service)

        assert snapshot["preset_number"] == 3
        assert event["preset_number"] == 3
        assert event["dlna"] is True

    @pytest.mark.asyncio
    async def test_sse_lookup_failure_null_slot(self):
        service = AsyncMock()
        service.get_all_presets.side_effect = RuntimeError("speaker offline")

        snapshot, event = await _collect_sse(service)

        assert snapshot["preset_number"] is None
        assert event["preset_number"] is None


class TestRouteLookupFailure:
    def test_stored_music_lookup_failure_null_slot(
        self, client, mock_device_service, mock_preset_service
    ):
        mock_device_service.get_now_playing = AsyncMock(
            return_value=_make_now_playing(
                source="STORED_MUSIC", location="1$4", source_account=_UDN
            )
        )
        mock_preset_service.get_all_presets = AsyncMock(
            side_effect=RuntimeError("speaker offline")
        )

        r = client.get("/api/devices/DEV1/now-playing")

        assert r.status_code == 200
        assert r.json()["preset_number"] is None
