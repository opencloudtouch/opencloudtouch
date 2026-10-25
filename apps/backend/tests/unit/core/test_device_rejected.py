"""DeviceRejectedError: the speaker answered, but with HTTP >= 400."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opencloudtouch.core import error_codes
from opencloudtouch.core.exception_handlers import register_exception_handlers
from opencloudtouch.core.exceptions import DeviceConnectionError, DeviceRejectedError


def test_is_a_device_connection_error_with_status_code():
    error = DeviceRejectedError("192.168.1.10", 500)
    assert isinstance(error, DeviceConnectionError)
    assert error.status_code == 500
    assert error.device_ip == "192.168.1.10"


def test_handler_returns_502_with_code_and_fixed_detail():
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/api/x")
    async def raiser():
        raise DeviceRejectedError("192.168.1.10", 503)

    response = TestClient(app, raise_server_exceptions=False).post("/api/x")
    body = response.json()

    assert response.status_code == 502
    assert body["code"] == "device_rejected"
    assert body["type"] == "bad_gateway"
    assert "192.168.1.10" not in body["detail"]


def test_plain_connection_error_still_maps_to_device_unreachable():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/x")
    async def raiser():
        raise DeviceConnectionError("192.168.1.10")

    response = TestClient(app, raise_server_exceptions=False).get("/api/x")
    assert response.status_code == 503
    assert response.json()["code"] == "device_unreachable"


def test_registry_contains_the_settings_codes():
    for name, value in {
        "DEVICE_REJECTED": "device_rejected",
        "SETTING_NOT_AVAILABLE": "setting_not_available",
        "SETTINGS_LANGUAGE_INVALID": "settings_language_invalid",
        "SETTINGS_ENABLED_INVALID": "settings_enabled_invalid",
        "SETTINGS_TIME_FORMAT_INVALID": "settings_time_format_invalid",
        "SETTINGS_TIMEZONE_INVALID": "settings_timezone_invalid",
    }.items():
        assert getattr(error_codes, name) == value
