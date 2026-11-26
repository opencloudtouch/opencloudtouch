"""Tests for extracted now-playing helper functions in routes.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.devices.api.routes import (
    _apply_icy_metadata,
    _enrich_from_icy,
    _enrich_from_presets,
    _now_playing_to_dict,
)
from opencloudtouch.devices.client import NowPlayingInfo
from opencloudtouch.presets.models import Preset
from opencloudtouch.streaming.icy_metadata import IcyMetadata


class TestApplyIcyMetadata:
    """Tests for _apply_icy_metadata."""

    def test_fills_missing_artist(self):
        result: dict[str, object] = {
            "artist": None,
            "track": "X",
            "artwork_url": "http://art",
        }
        icy = IcyMetadata(artist="ICY Artist", track="ICY Track", raw_title="t")
        _apply_icy_metadata(result, icy, None, "X")
        assert result["artist"] == "ICY Artist"

    def test_does_not_overwrite_existing_artist(self):
        result: dict[str, object] = {
            "artist": "Orig",
            "track": None,
            "artwork_url": None,
        }
        icy = IcyMetadata(artist="ICY Artist", track="ICY Track", raw_title="t")
        _apply_icy_metadata(result, icy, "Orig", None)
        assert result["artist"] == "Orig"

    def test_fills_missing_track(self):
        result: dict[str, object] = {"artist": "A", "track": None, "artwork_url": None}
        icy = IcyMetadata(artist="ICY A", track="ICY Track", raw_title="t")
        _apply_icy_metadata(result, icy, "A", None)
        assert result["track"] == "ICY Track"

    def test_does_not_overwrite_existing_track(self):
        result: dict[str, object] = {
            "artist": None,
            "track": "Orig",
            "artwork_url": None,
        }
        icy = IcyMetadata(artist="A", track="T", raw_title="t")
        _apply_icy_metadata(result, icy, None, "Orig")
        assert result["track"] == "Orig"

    def test_fills_missing_artwork(self):
        result: dict[str, object] = {"artist": "A", "track": "T", "artwork_url": None}
        icy = IcyMetadata(
            artist="A", track="T", raw_title="t", station_logo_url="http://logo"
        )
        _apply_icy_metadata(result, icy, "A", "T")
        assert result["artwork_url"] == "http://logo"

    def test_does_not_overwrite_existing_artwork(self):
        result: dict[str, object] = {
            "artist": "A",
            "track": "T",
            "artwork_url": "http://existing",
        }
        icy = IcyMetadata(
            artist="A", track="T", raw_title="t", station_logo_url="http://new"
        )
        _apply_icy_metadata(result, icy, "A", "T")
        assert result["artwork_url"] == "http://existing"

    def test_no_icy_data_no_change(self):
        result: dict[str, object] = {"artist": None, "track": None, "artwork_url": None}
        icy = IcyMetadata(artist=None, track=None, raw_title="")
        _apply_icy_metadata(result, icy, None, None)
        assert result["artist"] is None
        assert result["track"] is None


class TestEnrichFromPresets:
    """Tests for _enrich_from_presets."""

    @pytest.mark.asyncio
    async def test_returns_none_for_non_radio_source(self):
        info = NowPlayingInfo(source="BLUETOOTH", state="PLAY_STATE")
        mock_service = AsyncMock()
        result: dict[str, object] = {"artwork_url": None}
        preset = await _enrich_from_presets(result, info, "dev1", mock_service)
        assert preset is None
        mock_service.get_all_presets.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_without_station_name(self):
        info = NowPlayingInfo(
            source="INTERNET_RADIO", state="PLAY_STATE", station_name=None
        )
        mock_service = AsyncMock()
        result: dict[str, object] = {"artwork_url": None}
        preset = await _enrich_from_presets(result, info, "dev1", mock_service)
        assert preset is None

    @pytest.mark.asyncio
    async def test_returns_matching_preset(self):
        info = NowPlayingInfo(
            source="INTERNET_RADIO", state="PLAY_STATE", station_name="Jazz FM"
        )
        mock_preset = Preset(
            device_id="dev1",
            preset_number=1,
            station_uuid="uuid1",
            station_name="Jazz FM",
            station_url="http://jazz.fm/stream",
            station_favicon="http://jazz.fm/logo.png",
        )
        mock_service = AsyncMock()
        mock_service.get_all_presets.return_value = [mock_preset]
        result: dict[str, object] = {"artwork_url": None}
        preset = await _enrich_from_presets(result, info, "dev1", mock_service)
        assert preset is mock_preset
        assert result["artwork_url"] == "http://jazz.fm/logo.png"

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_artwork(self):
        info = NowPlayingInfo(
            source="INTERNET_RADIO", state="PLAY_STATE", station_name="Jazz FM"
        )
        mock_preset = Preset(
            device_id="dev1",
            preset_number=1,
            station_uuid="uuid1",
            station_name="Jazz FM",
            station_url="http://jazz.fm/stream",
            station_favicon="http://jazz.fm/logo.png",
        )
        mock_service = AsyncMock()
        mock_service.get_all_presets.return_value = [mock_preset]
        result: dict[str, object] = {"artwork_url": "http://existing.png"}
        preset = await _enrich_from_presets(result, info, "dev1", mock_service)
        assert preset is mock_preset
        assert result["artwork_url"] == "http://existing.png"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_preset_matches(self):
        info = NowPlayingInfo(
            source="INTERNET_RADIO", state="PLAY_STATE", station_name="Jazz FM"
        )
        mock_preset = Preset(
            device_id="dev1",
            preset_number=1,
            station_uuid="uuid1",
            station_name="Rock FM",
            station_url="http://rock.fm/stream",
        )
        mock_service = AsyncMock()
        mock_service.get_all_presets.return_value = [mock_preset]
        result: dict[str, object] = {"artwork_url": None}
        preset = await _enrich_from_presets(result, info, "dev1", mock_service)
        assert preset is None

    @pytest.mark.asyncio
    async def test_handles_service_exception(self):
        info = NowPlayingInfo(
            source="INTERNET_RADIO", state="PLAY_STATE", station_name="Jazz FM"
        )
        mock_service = AsyncMock()
        mock_service.get_all_presets.side_effect = RuntimeError("db down")
        result: dict[str, object] = {"artwork_url": None}
        preset = await _enrich_from_presets(result, info, "dev1", mock_service)
        assert preset is None


class TestEnrichFromIcy:
    """Tests for _enrich_from_icy."""

    @pytest.mark.asyncio
    async def test_cache_hit_applies_metadata(self):
        icy = IcyMetadata(artist="Cached Artist", track="Cached Track", raw_title="t")
        result: dict[str, object] = {"artist": None, "track": None, "artwork_url": None}
        with patch("opencloudtouch.devices.api.routes._metadata_cache") as mock_cache:
            mock_cache.get.return_value = icy
            await _enrich_from_icy(result, "http://stream", None, None, None)
        assert result["artist"] == "Cached Artist"
        assert result["track"] == "Cached Track"

    @pytest.mark.asyncio
    async def test_cache_miss_probes_and_caches(self):
        from opencloudtouch.streaming.metadata_cache import MISSING

        icy = IcyMetadata(artist="Probed", track="Track", raw_title="t")
        result: dict[str, object] = {"artist": None, "track": None, "artwork_url": None}
        with (
            patch("opencloudtouch.devices.api.routes._metadata_cache") as mock_cache,
            patch(
                "opencloudtouch.devices.api.routes.probe_stream", new_callable=AsyncMock
            ) as mock_probe,
        ):
            mock_cache.get.return_value = MISSING
            mock_probe.return_value = icy
            await _enrich_from_icy(result, "http://stream", None, None, None)
        assert result["artist"] == "Probed"
        mock_cache.put.assert_called_once_with("http://stream", icy)

    @pytest.mark.asyncio
    async def test_cache_miss_probe_failure_handled(self):
        from opencloudtouch.streaming.metadata_cache import MISSING

        result: dict[str, object] = {"artist": None, "track": None, "artwork_url": None}
        with (
            patch("opencloudtouch.devices.api.routes._metadata_cache") as mock_cache,
            patch(
                "opencloudtouch.devices.api.routes.probe_stream", new_callable=AsyncMock
            ) as mock_probe,
        ):
            mock_cache.get.return_value = MISSING
            mock_probe.side_effect = RuntimeError("network error")
            await _enrich_from_icy(result, "http://stream", None, None, None)
        assert result["artist"] is None

    @pytest.mark.asyncio
    async def test_cache_none_does_nothing(self):
        result: dict[str, object] = {"artist": None, "track": None, "artwork_url": None}
        with patch("opencloudtouch.devices.api.routes._metadata_cache") as mock_cache:
            mock_cache.get.return_value = None
            await _enrich_from_icy(result, "http://stream", None, None, None)
        assert result["artist"] is None


_UDN = "uuid:4D696E69-444C-164E-9D41-0000000000A1/0"
_LOC = "1$4$7"


def _dlna_preset(number: int, **overrides) -> Preset:
    fields: dict = dict(
        device_id="dev1",
        preset_number=number,
        station_uuid=f"dlna-{number}",
        station_name="Album",
        station_url=_LOC,
        source="STORED_MUSIC",
        source_account=_UDN,
    )
    fields.update(overrides)
    return Preset(**fields)


def _dlna_info(**overrides) -> NowPlayingInfo:
    fields: dict = dict(
        source="STORED_MUSIC",
        state="PLAY_STATE",
        station_name="Album",
        location=_LOC,
        source_account=_UDN.lower(),
    )
    fields.update(overrides)
    return NowPlayingInfo(**fields)


class TestStoredMusicPresetMatch:
    """Decision 31: match by ContentItem location + source account, never by name."""

    @pytest.mark.asyncio
    async def test_stored_music_matches_slot_by_location_and_account(self):
        presets = [
            _dlna_preset(1, station_url="other"),
            _dlna_preset(4),
            _dlna_preset(5),  # duplicate: at most one slot wins
        ]
        service = AsyncMock()
        service.get_all_presets.return_value = presets
        result: dict[str, object] = {"artwork_url": None, "preset_number": None}
        matched = await _enrich_from_presets(result, _dlna_info(), "dev1", service)
        assert matched is presets[1]
        assert result["preset_number"] == 4

    @pytest.mark.asyncio
    async def test_same_name_different_location_no_match(self):
        service = AsyncMock()
        service.get_all_presets.return_value = [
            _dlna_preset(2, station_url="1$9"),
            _dlna_preset(3, source_account="uuid:other/0"),
        ]
        result: dict[str, object] = {"artwork_url": None, "preset_number": None}
        matched = await _enrich_from_presets(result, _dlna_info(), "dev1", service)
        assert matched is None
        assert result["preset_number"] is None

    @pytest.mark.asyncio
    async def test_no_location_skips_lookup(self):
        service = AsyncMock()
        result: dict[str, object] = {"artwork_url": None, "preset_number": None}
        matched = await _enrich_from_presets(
            result, _dlna_info(location=None), "dev1", service
        )
        assert matched is None
        service.get_all_presets.assert_not_called()

    @pytest.mark.parametrize(
        ("speaker_art", "favicon", "expected"),
        [
            ("http://art/cover.jpg", "http://fav.png", "http://art/cover.jpg"),
            (None, "http://fav.png", "http://fav.png"),
            (None, None, None),
        ],
    )
    @pytest.mark.asyncio
    async def test_artwork_priority(self, speaker_art, favicon, expected):
        service = AsyncMock()
        service.get_all_presets.return_value = [
            _dlna_preset(1, station_favicon=favicon)
        ]
        result: dict[str, object] = {"artwork_url": speaker_art, "preset_number": None}
        await _enrich_from_presets(result, _dlna_info(), "dev1", service)
        assert result["artwork_url"] == expected


class TestNowPlayingDlnaFields:
    def test_radio_dlna_false(self):
        data = _now_playing_to_dict(
            NowPlayingInfo(source="INTERNET_RADIO", state="PLAY_STATE"), online=True
        )
        assert data["dlna"] is False
        assert data["preset_number"] is None

    def test_stored_music_dlna_true(self):
        data = _now_playing_to_dict(_dlna_info(), online=True)
        assert data["dlna"] is True

    @pytest.mark.parametrize(
        ("source", "account", "expected"),
        [
            ("STORED_MUSIC", "Udn-1/0", True),
            ("STORED_MUSIC", "", True),
            ("INVALID_SOURCE", "", False),
            ("TUNEIN", None, False),
        ],
    )
    def test_rest_and_sse_share_one_rule(self, source, account, expected):
        """REST and SSE disagreed on an account-less STORED_MUSIC item (T22 5d)."""
        from opencloudtouch.devices.api.event_routes import _dlna_fields

        info = NowPlayingInfo(source=source, state="STOP_STATE", source_account=account)
        assert info.is_dlna is expected
        assert _now_playing_to_dict(info, online=True)["dlna"] is expected
        assert _dlna_fields(info, None)["dlna"] is expected


class TestContentItemParsing:
    def test_parser_fills_location_and_account(self):
        import xml.etree.ElementTree as ET

        from opencloudtouch.devices.websocket.parser import _parse_now_playing

        xml = (
            '<nowPlayingUpdated><nowPlaying source="STORED_MUSIC">'
            f'<ContentItem source="STORED_MUSIC" location="{_LOC}" '
            f'sourceAccount="{_UDN}" isPresetable="true"/>'
            "<playStatus>PLAY_STATE</playStatus></nowPlaying></nowPlayingUpdated>"
        )
        info = _parse_now_playing(ET.fromstring(xml))  # noqa: S314 - test literal
        assert info.location == _LOC
        assert info.source_account == _UDN

    def test_parser_without_content_item(self):
        import xml.etree.ElementTree as ET

        from opencloudtouch.devices.websocket.parser import _parse_now_playing

        xml = '<nowPlayingUpdated><nowPlaying source="AUX"/></nowPlayingUpdated>'
        info = _parse_now_playing(ET.fromstring(xml))  # noqa: S314 - test literal
        assert info.location is None
        assert info.source_account is None

    @pytest.mark.asyncio
    async def test_adapter_fills_location_and_account(self):
        from unittest.mock import MagicMock

        from opencloudtouch.devices.client_adapter import BoseDeviceClientAdapter

        with (
            patch("opencloudtouch.devices.client_adapter.SoundTouchDevice"),
            patch("opencloudtouch.devices.client_adapter.BoseClient"),
        ):
            adapter = BoseDeviceClientAdapter("http://192.0.2.10:8090")
        status = MagicMock(PlayStatus="PLAY_STATE", Source="STORED_MUSIC")
        status.ContentItem.Location = _LOC
        status.ContentItem.SourceAccount = _UDN
        adapter._client.GetNowPlayingStatus.return_value = status
        info = await adapter.get_now_playing()
        assert info.location == _LOC
        assert info.source_account == _UDN

        status.ContentItem = None
        info = await adapter.get_now_playing()
        assert info.location is None


def test_now_playing_dict_includes_settings():
    from opencloudtouch.devices.api.routes import _now_playing_to_dict

    info = NowPlayingInfo(
        source="STORED_MUSIC",
        state="PLAY_STATE",
        shuffle_setting="SHUFFLE_OFF",
        repeat_setting="REPEAT_ALL",
    )
    result = _now_playing_to_dict(info, online=True)
    assert result["shuffle_setting"] == "SHUFFLE_OFF"
    assert result["repeat_setting"] == "REPEAT_ALL"
    plain = _now_playing_to_dict(NowPlayingInfo(source="AUX", state="X"), online=True)
    assert plain["shuffle_setting"] is None
