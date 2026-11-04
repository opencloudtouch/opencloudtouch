"""Device settings endpoints: GET /settings and PUT language / clock / power-saving."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from opencloudtouch.core.dependencies import (
    get_device_service,
    get_device_state_manager,
)
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DeviceRejectedError,
)
from opencloudtouch.devices.client import (
    ClockSetting,
    LanguageSetting,
    PowerSavingSetting,
)
from opencloudtouch.devices.device_settings import (
    LANGUAGES,
    DeviceSettings,
    SettingWriteResult,
)
from opencloudtouch.devices.repository import Device
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.main import app

MOCK_DEVICE_ID = "AABBCC112233"


@pytest.fixture
def state_manager():
    manager = DeviceStateManager()
    manager.mark_device_offline = AsyncMock()
    return manager


@pytest.fixture
def stub_service():
    return AsyncMock()


@pytest.fixture
def stub_client(stub_service, state_manager):
    app.dependency_overrides[get_device_service] = lambda: stub_service
    app.dependency_overrides[get_device_state_manager] = lambda: state_manager
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_mode_client(monkeypatch, state_manager):
    """Real DeviceService + MockDeviceClient (OCT_MOCK_MODE=true)."""
    monkeypatch.setenv("OCT_MOCK_MODE", "true")
    repository = AsyncMock()
    repository.get_by_device_id.side_effect = lambda device_id: (
        Device(
            device_id=MOCK_DEVICE_ID,
            ip="192.168.1.100",
            name="Living Room",
            model="SoundTouch 20",
            mac_address=MOCK_DEVICE_ID,
            firmware_version="1.0",
        )
        if device_id == MOCK_DEVICE_ID
        else None
    )
    service = DeviceService(
        repository=repository, sync_service=AsyncMock(), discovery_adapter=AsyncMock()
    )
    app.dependency_overrides[get_device_service] = lambda: service
    app.dependency_overrides[get_device_state_manager] = lambda: state_manager
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestGetSettings:
    def test_response_shape(self, stub_client, stub_service):
        stub_service.get_device_settings.return_value = DeviceSettings(
            language=LanguageSetting(2, "Deutsch"),
            clock=ClockSetting(True, "24h", "Europe/Berlin", {"userUtcTime": "0"}),
            power_saving=PowerSavingSetting(False),
        )

        response = stub_client.get("/api/devices/AABB/settings")
        body = response.json()

        assert response.status_code == 200
        assert body["language"] == {"id": 2, "name": "Deutsch"}
        assert body["clock"] == {
            "enabled": True,
            "time_format": "24h",
            "timezone": "Europe/Berlin",
        }
        assert body["power_saving"] == {"enabled": False}
        assert body["available"] == {
            "language": True,
            "clock": True,
            "power_saving": True,
        }
        assert body["languages"][0] == {"id": 1, "name": "Dansk"}
        assert {entry["id"] for entry in body["languages"]} == set(LANGUAGES)
        assert "extra" not in str(body)

    def test_missing_setting_is_null_and_unavailable(self, stub_client, stub_service):
        stub_service.get_device_settings.return_value = DeviceSettings(
            language=LanguageSetting(99, None), clock=None, power_saving=None
        )

        body = stub_client.get("/api/devices/AABB/settings").json()

        assert body["language"] == {"id": 99, "name": None}
        assert body["clock"] is None
        assert body["power_saving"] is None
        assert body["available"] == {
            "language": True,
            "clock": False,
            "power_saving": False,
        }

    def test_unknown_device_is_404_device_not_found(self, stub_client, stub_service):
        stub_service.get_device_settings.side_effect = DeviceNotFoundError("nope")
        response = stub_client.get("/api/devices/nope/settings")
        assert response.status_code == 404
        assert response.json()["code"] == "device_not_found"

    def test_unreachable_device_is_503_and_marked_offline(
        self, stub_client, stub_service, state_manager
    ):
        stub_service.get_device_settings.side_effect = DeviceConnectionError(
            "192.168.1.100", "refused"
        )
        response = stub_client.get("/api/devices/AABB/settings")
        assert response.status_code == 503
        assert response.json()["code"] == "device_unreachable"
        state_manager.mark_device_offline.assert_awaited_once_with("AABB")

    def test_bass_endpoint_is_untouched(self, stub_client, stub_service):
        from opencloudtouch.devices.client import BassInfo

        stub_service.get_device_bass.return_value = BassInfo(actual=-2, target=-2)
        response = stub_client.get("/api/devices/AABB/settings/bass")
        assert response.json() == {"actual": -2, "target": -2}


class TestPutResponses:
    def test_language(self, stub_client, stub_service):
        stub_service.set_device_language.return_value = SettingWriteResult(
            True, LanguageSetting(12, "한국어")
        )
        response = stub_client.put(
            "/api/devices/AABB/settings/language", json={"language_id": 12}
        )
        assert response.status_code == 200
        assert response.json() == {
            "applied": True,
            "value": {"id": 12, "name": "한국어"},
        }
        stub_service.set_device_language.assert_awaited_once_with("AABB", 12)

    def test_clock_not_applied(self, stub_client, stub_service):
        stub_service.set_device_clock.return_value = SettingWriteResult(
            False, ClockSetting(True, "24h", "Europe/Berlin", {})
        )
        response = stub_client.put(
            "/api/devices/AABB/settings/clock",
            json={"enabled": True, "time_format": "12h", "timezone": "Asia/Tokyo"},
        )
        assert response.json() == {
            "applied": False,
            "value": {
                "enabled": True,
                "time_format": "24h",
                "timezone": "Europe/Berlin",
            },
        }
        stub_service.set_device_clock.assert_awaited_once_with(
            "AABB", True, "12h", "Asia/Tokyo"
        )

    def test_power_saving(self, stub_client, stub_service):
        stub_service.set_device_power_saving.return_value = SettingWriteResult(
            True, PowerSavingSetting(False)
        )
        response = stub_client.put(
            "/api/devices/AABB/settings/power-saving", json={"enabled": False}
        )
        assert response.json() == {"applied": True, "value": {"enabled": False}}

    def test_value_null_when_post_read_failed(self, stub_client, stub_service):
        stub_service.set_device_power_saving.return_value = SettingWriteResult(
            False, None
        )
        response = stub_client.put(
            "/api/devices/AABB/settings/power-saving", json={"enabled": True}
        )
        assert response.json() == {"applied": False, "value": None}

    def test_missing_fields_reach_the_service_as_none(self, stub_client, stub_service):
        stub_service.set_device_clock.return_value = SettingWriteResult(True, None)
        stub_client.put("/api/devices/AABB/settings/clock", json={})
        stub_service.set_device_clock.assert_awaited_once_with("AABB", None, None, None)


class TestPutErrors:
    def test_device_rejected_is_502_and_device_stays_online(
        self, stub_client, stub_service, state_manager
    ):
        stub_service.set_device_language.side_effect = DeviceRejectedError(
            "192.168.1.100", 500
        )
        response = stub_client.put(
            "/api/devices/AABB/settings/language", json={"language_id": 3}
        )
        assert response.status_code == 502
        assert response.json()["code"] == "device_rejected"
        state_manager.mark_device_offline.assert_not_awaited()

    def test_connection_error_is_503_and_marks_offline(
        self, stub_client, stub_service, state_manager
    ):
        stub_service.set_device_language.side_effect = DeviceConnectionError(
            "192.168.1.100", "refused"
        )
        response = stub_client.put(
            "/api/devices/AABB/settings/language", json={"language_id": 3}
        )
        assert response.status_code == 503
        state_manager.mark_device_offline.assert_awaited_once_with("AABB")

    def test_invalid_json_body_is_a_generic_validation_error(self, stub_client):
        response = stub_client.put(
            "/api/devices/AABB/settings/language",
            content="not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"


class TestMockModeEndToEnd:
    """OCT_MOCK_MODE=true: the three PUTs are reflected by GET /settings (A.3-8)."""

    def test_defaults(self, mock_mode_client):
        body = mock_mode_client.get(f"/api/devices/{MOCK_DEVICE_ID}/settings").json()
        assert body["language"] == {"id": 3, "name": "English"}
        assert body["clock"]["timezone"] == "Europe/Berlin"
        assert body["available"] == {
            "language": True,
            "clock": True,
            "power_saving": True,
        }

    def test_writes_are_reflected_and_applied(self, mock_mode_client):
        base = f"/api/devices/{MOCK_DEVICE_ID}/settings"

        language = mock_mode_client.put(f"{base}/language", json={"language_id": 12})
        clock = mock_mode_client.put(
            f"{base}/clock",
            json={"enabled": True, "time_format": "12h", "timezone": "Asia/Tokyo"},
        )
        power = mock_mode_client.put(f"{base}/power-saving", json={"enabled": True})

        assert language.json() == {
            "applied": True,
            "value": {"id": 12, "name": "한국어"},
        }
        assert clock.json()["applied"] is True
        assert power.json() == {"applied": True, "value": {"enabled": True}}

        body = mock_mode_client.get(base).json()
        assert body["language"]["id"] == 12
        assert body["clock"] == {
            "enabled": True,
            "time_format": "12h",
            "timezone": "Asia/Tokyo",
        }
        assert body["power_saving"] == {"enabled": True}

    def test_disabling_the_clock_keeps_format_and_zone(self, mock_mode_client):
        base = f"/api/devices/{MOCK_DEVICE_ID}/settings"
        mock_mode_client.put(f"{base}/clock", json={"enabled": False})
        clock = mock_mode_client.get(base).json()["clock"]
        assert clock == {
            "enabled": False,
            "time_format": "24h",
            "timezone": "Europe/Berlin",
        }

    @pytest.mark.parametrize(
        ("path", "body", "code", "field"),
        [
            (
                "language",
                {"language_id": 14},
                "settings_language_invalid",
                "language_id",
            ),
            (
                "language",
                {"language_id": True},
                "settings_language_invalid",
                "language_id",
            ),
            (
                "language",
                {"language_id": 3.5},
                "settings_language_invalid",
                "language_id",
            ),
            ("language", {}, "settings_language_invalid", "language_id"),
            ("clock", {"enabled": "yes"}, "settings_enabled_invalid", "enabled"),
            ("clock", {}, "settings_enabled_invalid", "enabled"),
            (
                "clock",
                {"enabled": True, "time_format": "13h", "timezone": "UTC"},
                "settings_time_format_invalid",
                "time_format",
            ),
            (
                "clock",
                {"enabled": True, "time_format": "24h", "timezone": "Europe/Atlantis"},
                "settings_timezone_invalid",
                "timezone",
            ),
            (
                "power-saving",
                {"enabled": "true"},
                "settings_enabled_invalid",
                "enabled",
            ),
        ],
    )
    def test_validation_errors_are_coded_with_field_path(
        self, mock_mode_client, path, body, code, field
    ):
        response = mock_mode_client.put(
            f"/api/devices/{MOCK_DEVICE_ID}/settings/{path}", json=body
        )
        payload = response.json()

        assert response.status_code == 422
        assert payload["code"] == code
        assert payload["errors"][0]["field"] == field
        assert payload["errors"][0]["path"] == field
        assert payload["errors"][0]["code"] == code

    def test_unknown_device(self, mock_mode_client):
        response = mock_mode_client.put(
            "/api/devices/NOPE/settings/power-saving", json={"enabled": True}
        )
        assert response.status_code == 404
        assert response.json()["code"] == "device_not_found"
