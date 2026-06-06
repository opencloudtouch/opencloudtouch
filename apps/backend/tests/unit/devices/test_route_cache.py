"""Tests for cache-first route behavior (now-playing + volume)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.devices.client import NowPlayingInfo, VolumeInfo
from opencloudtouch.devices.state import DeviceStateManager


@pytest.fixture
def state_manager():
    return DeviceStateManager()


@pytest.fixture
def mock_device_service():
    svc = AsyncMock()
    svc.get_now_playing = AsyncMock(
        return_value=NowPlayingInfo(
            source="AUX", state="PLAY_STATE", track="HTTP Track"
        )
    )
    svc.get_volume = AsyncMock(
        return_value=VolumeInfo(actual=77, target=77, muted=False)
    )
    return svc


@pytest.fixture
def mock_preset_service():
    svc = AsyncMock()
    svc.get_all_presets = AsyncMock(return_value=[])
    return svc


@pytest.fixture
def app(state_manager, mock_device_service, mock_preset_service):
    """Create a minimal FastAPI app with the device routes."""
    from opencloudtouch.devices.api.routes import router

    test_app = FastAPI()
    test_app.include_router(router)

    # Wire dependencies
    test_app.state.device_state_manager = state_manager
    test_app.state.device_service = mock_device_service
    test_app.state.preset_service = mock_preset_service

    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestNowPlayingCacheFirst:
    def test_cache_hit_returns_cached(self, client, state_manager, mock_device_service):
        """Fresh cache should return cached data without HTTP call."""
        np = NowPlayingInfo(source="RADIO", state="PLAY_STATE", track="Cached Song")
        state_manager.update_now_playing("D1", np)

        resp = client.get("/api/devices/D1/now-playing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track"] == "Cached Song"
        assert data["source"] == "RADIO"
        mock_device_service.get_now_playing.assert_not_called()

    def test_cache_miss_falls_back_to_http(
        self, client, state_manager, mock_device_service
    ):
        """No cached state should fall back to HTTP."""
        resp = client.get("/api/devices/D1/now-playing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track"] == "HTTP Track"
        mock_device_service.get_now_playing.assert_called_once()

    def test_stale_cache_falls_back_to_http(
        self, client, state_manager, mock_device_service
    ):
        """Stale cache (age > max_age) should fall back to HTTP."""
        np = NowPlayingInfo(source="RADIO", state="PLAY_STATE", track="Old")
        state_manager.update_now_playing("D1", np)
        # Age the state beyond max_age
        state_manager._states["D1"].last_update = time.time() - 20

        resp = client.get("/api/devices/D1/now-playing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track"] == "HTTP Track"
        mock_device_service.get_now_playing.assert_called_once()

    def test_response_format_identical(self, client, state_manager):
        """Cache hit response format must match pre-cache format."""
        np = NowPlayingInfo(
            source="BLUETOOTH",
            state="PAUSE_STATE",
            station_name="My Station",
            artist="Artist",
            track="Track",
            album="Album",
            artwork_url="http://img/art.jpg",
        )
        state_manager.update_now_playing("D1", np)

        resp = client.get("/api/devices/D1/now-playing")
        data = resp.json()
        expected_keys = {
            "source",
            "state",
            "station_name",
            "artist",
            "track",
            "album",
            "artwork_url",
        }
        assert set(data.keys()) == expected_keys


class TestVolumeCacheFirst:
    def test_cache_hit_returns_cached(self, client, state_manager, mock_device_service):
        """Fresh cache should return cached volume without HTTP call."""
        vol = VolumeInfo(actual=42, target=42, muted=True)
        state_manager.update_volume("D1", vol)

        resp = client.get("/api/devices/D1/volume")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"actual": 42, "target": 42, "muted": True}
        mock_device_service.get_volume.assert_not_called()

    def test_cache_miss_falls_back_to_http(
        self, client, state_manager, mock_device_service
    ):
        """No cached state should fall back to HTTP."""
        resp = client.get("/api/devices/D1/volume")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"actual": 77, "target": 77, "muted": False}
        mock_device_service.get_volume.assert_called_once()

    def test_stale_cache_falls_back_to_http(
        self, client, state_manager, mock_device_service
    ):
        """Stale cache should trigger HTTP fallback."""
        vol = VolumeInfo(actual=10, target=10, muted=False)
        state_manager.update_volume("D1", vol)
        state_manager._states["D1"].last_update = time.time() - 20

        resp = client.get("/api/devices/D1/volume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["actual"] == 77
        mock_device_service.get_volume.assert_called_once()

    def test_response_format_identical(self, client, state_manager):
        """Cache hit response must have same keys as HTTP response."""
        vol = VolumeInfo(actual=50, target=50, muted=False)
        state_manager.update_volume("D1", vol)

        resp = client.get("/api/devices/D1/volume")
        data = resp.json()
        assert set(data.keys()) == {"actual", "target", "muted"}
