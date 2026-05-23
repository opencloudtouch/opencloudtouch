"""Tests for extracted now-playing helper functions in routes.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.devices.api.routes import (
    _apply_icy_metadata,
    _enrich_from_icy,
    _enrich_from_presets,
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
