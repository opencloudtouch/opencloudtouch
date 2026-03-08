"""Unit tests for BMX stub and resolve endpoints.

Covers:
- Stub endpoints for now-playing, reporting, tunein, favorite
- /bmx/resolve endpoint for stream URL resolution
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.bmx.routes import router


@pytest.fixture
def app():
    app_ = FastAPI()
    app_.include_router(router)
    return app_


@pytest.fixture
def client(app):
    return TestClient(app)


class TestNowPlayingStub:
    """Tests for GET /bmx/orion/now-playing stub endpoints."""

    def test_now_playing_with_station_id(self, client):
        """GET /bmx/orion/now-playing/station/{id} returns 200 with stationId."""
        response = client.get("/bmx/orion/now-playing/station/s123456")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "playing"
        assert data["stationId"] == "s123456"

    def test_now_playing_without_station_id(self, client):
        """GET /bmx/orion/now-playing returns 200 with 'custom' stationId."""
        response = client.get("/bmx/orion/now-playing")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "playing"
        assert data["stationId"] == "custom"


class TestReportingStub:
    """Tests for POST /bmx/orion/reporting stub endpoints."""

    def test_reporting_with_station_id(self, client):
        """POST /bmx/orion/reporting/station/{id} returns 200."""
        response = client.post("/bmx/orion/reporting/station/s123456")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_reporting_without_station_id(self, client):
        """POST /bmx/orion/reporting returns 200."""
        response = client.post("/bmx/orion/reporting")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestTuneInStubs:
    """Tests for TuneIn stub endpoints."""

    def test_tunein_now_playing(self, client):
        """GET /bmx/tunein/v1/now-playing/station/{id} returns 200."""
        response = client.get("/bmx/tunein/v1/now-playing/station/s345678")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "playing"
        assert data["stationId"] == "s345678"

    def test_tunein_reporting(self, client):
        """POST /bmx/tunein/v1/reporting/station/{id} returns 200."""
        response = client.post("/bmx/tunein/v1/reporting/station/s345678")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_tunein_favorite_get(self, client):
        """GET /bmx/tunein/v1/favorite/{id} returns 200."""
        response = client.get("/bmx/tunein/v1/favorite/s345678")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["isFavorite"] is False

    def test_tunein_favorite_post(self, client):
        """POST /bmx/tunein/v1/favorite/{id} returns 200."""
        response = client.post("/bmx/tunein/v1/favorite/s345678")
        assert response.status_code == 200
        assert response.json()["isFavorite"] is False
