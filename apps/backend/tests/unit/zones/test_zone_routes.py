"""Unit tests for zone API routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import get_zone_service
from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceNotFoundError
from opencloudtouch.main import app
from opencloudtouch.zones.models import ZoneMemberInfo, ZoneStatus


def _make_zone_status(master_id="DEV001", master_ip="192.168.1.100"):
    return ZoneStatus(
        master_id=master_id,
        master_ip=master_ip,
        is_master=True,
        members=[
            ZoneMemberInfo(
                device_id=master_id,
                ip_address=master_ip,
                role="master",
                name="Speaker 1",
            ),
            ZoneMemberInfo(
                device_id="DEV002",
                ip_address="192.168.1.101",
                role="slave",
                name="Speaker 2",
            ),
        ],
    )


@pytest.fixture
def mock_service():
    return AsyncMock()


@pytest.fixture
def client(mock_service):
    app.dependency_overrides[get_zone_service] = lambda: mock_service
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestGetAllZones:
    """Tests for GET /api/zones."""

    def test_returns_200_with_zones(self, client, mock_service):
        mock_service.get_all_zones.return_value = [_make_zone_status()]
        r = client.get("/api/zones")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_returns_empty_list(self, client, mock_service):
        mock_service.get_all_zones.return_value = []
        r = client.get("/api/zones")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_500_on_error(self, client, mock_service):
        mock_service.get_all_zones.side_effect = RuntimeError("DB error")
        r = client.get("/api/zones")
        assert r.status_code == 500


class TestCreateZone:
    """Tests for POST /api/zones."""

    def test_returns_201_on_success(self, client, mock_service):
        mock_service.create_zone.return_value = _make_zone_status()
        r = client.post(
            "/api/zones", json={"master_id": "DEV001", "slave_ids": ["DEV002"]}
        )
        assert r.status_code == 201
        assert r.json()["master_id"] == "DEV001"

    def test_returns_404_when_device_not_found(self, client, mock_service):
        mock_service.create_zone.side_effect = DeviceNotFoundError("UNKNOWN")
        r = client.post(
            "/api/zones", json={"master_id": "UNKNOWN", "slave_ids": ["DEV002"]}
        )
        assert r.status_code == 404

    def test_returns_503_on_connection_error(self, client, mock_service):
        mock_service.create_zone.side_effect = DeviceConnectionError("192.168.1.100")
        r = client.post(
            "/api/zones", json={"master_id": "DEV001", "slave_ids": ["DEV002"]}
        )
        assert r.status_code == 503

    def test_returns_422_on_value_error(self, client, mock_service):
        mock_service.create_zone.side_effect = ValueError("Invalid")
        r = client.post(
            "/api/zones", json={"master_id": "DEV001", "slave_ids": ["DEV002"]}
        )
        assert r.status_code == 422


class TestDissolveZone:
    """Tests for DELETE /api/zones/{master_id}."""

    def test_returns_204_on_success(self, client, mock_service):
        mock_service.delete_zone.return_value = None
        r = client.delete("/api/zones/DEV001")
        assert r.status_code == 204

    def test_returns_404_when_device_not_found(self, client, mock_service):
        mock_service.delete_zone.side_effect = DeviceNotFoundError("UNKNOWN")
        r = client.delete("/api/zones/UNKNOWN")
        assert r.status_code == 404


class TestAddZoneMembers:
    """Tests for POST /api/zones/{master_id}/members."""

    def test_returns_200_on_success(self, client, mock_service):
        mock_service.add_members.return_value = None
        r = client.post("/api/zones/DEV001/members", json={"device_ids": ["DEV003"]})
        assert r.status_code == 200

    def test_returns_404_when_device_not_found(self, client, mock_service):
        mock_service.add_members.side_effect = DeviceNotFoundError("DEV003")
        r = client.post("/api/zones/DEV001/members", json={"device_ids": ["DEV003"]})
        assert r.status_code == 404


class TestRemoveZoneMembers:
    """Tests for DELETE /api/zones/{master_id}/members."""

    def test_returns_204_on_success(self, client, mock_service):
        mock_service.remove_members.return_value = None
        r = client.request(
            "DELETE", "/api/zones/DEV001/members", json={"device_ids": ["DEV002"]}
        )
        assert r.status_code == 204


class TestChangeMaster:
    """Tests for PUT /api/zones/{master_id}/master."""

    def test_returns_200_on_success(self, client, mock_service):
        new_zone = _make_zone_status("DEV002", "192.168.1.101")
        mock_service.change_master.return_value = new_zone
        r = client.put("/api/zones/DEV001/master", json={"new_master_id": "DEV002"})
        assert r.status_code == 200
        assert r.json()["master_id"] == "DEV002"

    def test_returns_404_when_device_not_found(self, client, mock_service):
        mock_service.change_master.side_effect = DeviceNotFoundError("UNKNOWN")
        r = client.put("/api/zones/UNKNOWN/master", json={"new_master_id": "DEV002"})
        assert r.status_code == 404


class TestGetDeviceZone:
    """Tests for GET /api/devices/{device_id}/zone."""

    def test_returns_200_with_zone(self, client, mock_service):
        mock_service.get_zone_status.return_value = _make_zone_status()
        r = client.get("/api/devices/DEV001/zone")
        assert r.status_code == 200
        assert r.json()["master_id"] == "DEV001"

    def test_returns_200_null_when_no_zone(self, client, mock_service):
        mock_service.get_zone_status.return_value = None
        r = client.get("/api/devices/DEV001/zone")
        assert r.status_code == 200

    def test_returns_404_when_device_not_found(self, client, mock_service):
        mock_service.get_zone_status.side_effect = DeviceNotFoundError("UNKNOWN")
        r = client.get("/api/devices/UNKNOWN/zone")
        assert r.status_code == 404
