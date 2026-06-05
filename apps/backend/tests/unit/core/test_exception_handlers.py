"""
Tests for core/exception_handlers.py

Each handler is tested by calling it directly with a mock Request,
verifying RFC 7807 response structure and correct HTTP status codes.
"""

import asyncio
import json
from unittest.mock import MagicMock

from opencloudtouch.core.exception_handlers import (
    device_connection_error_handler,
    device_not_found_handler,
    discovery_error_handler,
    generic_exception_handler,
    http_exception_handler,
    oct_error_handler,
    radio_browser_connection_handler,
    radio_browser_timeout_handler,
    register_exception_handlers,
    starlette_http_exception_handler,
    validation_exception_handler,
)
from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DiscoveryError,
    OpenCloudTouchError,
)
from opencloudtouch.radio.providers.radiobrowser import (
    RadioBrowserConnectionError,
    RadioBrowserError,
    RadioBrowserTimeoutError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(path: str = "/api/test") -> MagicMock:
    req = MagicMock()
    req.url.path = path
    return req


def _body(response) -> dict:
    return json.loads(response.body.decode())


def _rfc7807_fields(data: dict) -> None:
    """Assert RFC 7807 required fields are present."""
    assert "type" in data
    assert "title" in data
    assert "status" in data
    assert "detail" in data
    assert "instance" in data


# ---------------------------------------------------------------------------
# starlette_http_exception_handler
# ---------------------------------------------------------------------------


class TestStarletteHttpExceptionHandler:
    """Handler for routing-level 404 / 405 from Starlette."""

    def test_404_returns_not_found_type(self):
        from starlette.exceptions import HTTPException as StarletteHTTPException

        exc = StarletteHTTPException(status_code=404, detail="Not Found")
        req = _make_request("/api/missing")
        resp = asyncio.run(starlette_http_exception_handler(req, exc))

        assert resp.status_code == 404
        data = _body(resp)
        _rfc7807_fields(data)
        assert data["type"] == "not_found"
        assert data["status"] == 404
        assert data["instance"] == "/api/missing"

    def test_405_maps_correct_type(self):
        from starlette.exceptions import HTTPException as StarletteHTTPException

        exc = StarletteHTTPException(status_code=405, detail="Method Not Allowed")
        req = _make_request("/api/devices")
        resp = asyncio.run(starlette_http_exception_handler(req, exc))

        assert resp.status_code == 405
        data = _body(resp)
        assert data["status"] == 405
        assert data["title"] == "Method Not Allowed"

    def test_404_instance_path_is_preserved(self):
        from starlette.exceptions import HTTPException as StarletteHTTPException

        exc = StarletteHTTPException(status_code=404, detail="Not Found")
        req = _make_request("/api/x")
        resp = asyncio.run(starlette_http_exception_handler(req, exc))

        data = _body(resp)
        assert data["instance"] == "/api/x"


# ---------------------------------------------------------------------------
# http_exception_handler
# ---------------------------------------------------------------------------


class TestHttpExceptionHandler:
    """Handler for FastAPI HTTPException."""

    def test_422_returns_correct_body(self):
        from fastapi import HTTPException

        exc = HTTPException(status_code=422, detail="Unprocessable")
        req = _make_request("/api/foo")
        resp = asyncio.run(http_exception_handler(req, exc))

        assert resp.status_code == 422
        data = _body(resp)
        _rfc7807_fields(data)
        assert data["title"] == "Unprocessable"

    def test_500_returns_server_error_type(self):
        from fastapi import HTTPException

        exc = HTTPException(status_code=500, detail="boom")
        req = _make_request("/api/foo")
        resp = asyncio.run(http_exception_handler(req, exc))

        assert resp.status_code == 500
        data = _body(resp)
        assert data["type"] == "server_error"


# ---------------------------------------------------------------------------
# validation_exception_handler
# ---------------------------------------------------------------------------


class TestValidationExceptionHandler:
    """Handler for Pydantic RequestValidationError."""

    def test_returns_422_with_errors_list(self):
        from fastapi.exceptions import RequestValidationError
        from pydantic import TypeAdapter, ValidationError

        # Build a real Pydantic v2 ValidationError for the handler
        ta = TypeAdapter(int)
        try:
            ta.validate_python("not-an-int")
        except ValidationError as pyd_exc:
            exc = RequestValidationError(errors=pyd_exc.errors())

        req = _make_request("/api/settings")
        resp = asyncio.run(validation_exception_handler(req, exc))

        assert resp.status_code == 422
        data = _body(resp)
        assert data["type"] == "validation_error"
        assert data["title"] == "Invalid Request Data"
        assert isinstance(data["errors"], list)
        assert len(data["errors"]) > 0

    def test_errors_contain_field_and_message(self):
        from fastapi.exceptions import RequestValidationError
        from pydantic import TypeAdapter, ValidationError

        ta = TypeAdapter(int)
        try:
            ta.validate_python("bad")
        except ValidationError as pyd_exc:
            exc = RequestValidationError(errors=pyd_exc.errors())

        req = _make_request("/api/settings")
        resp = asyncio.run(validation_exception_handler(req, exc))
        data = _body(resp)

        first_error = data["errors"][0]
        assert "field" in first_error
        assert "message" in first_error
        assert "type" in first_error


# ---------------------------------------------------------------------------
# device_not_found_handler
# ---------------------------------------------------------------------------


class TestDeviceNotFoundHandler:
    """Handler for DeviceNotFoundError."""

    def test_returns_404_with_device_id_in_detail(self):
        exc = DeviceNotFoundError("dev-abc")
        req = _make_request("/api/devices/dev-abc")
        resp = asyncio.run(device_not_found_handler(req, exc))

        assert resp.status_code == 404
        data = _body(resp)
        assert data["type"] == "not_found"
        assert "dev-abc" in data["detail"]


# ---------------------------------------------------------------------------
# device_connection_error_handler
# ---------------------------------------------------------------------------


class TestDeviceConnectionErrorHandler:
    """Handler for DeviceConnectionError."""

    def test_returns_503_with_ip_context(self):
        exc = DeviceConnectionError("192.168.1.100", "Timeout")
        req = _make_request("/api/devices/dev-x/info")
        resp = asyncio.run(device_connection_error_handler(req, exc))

        assert resp.status_code == 503
        data = _body(resp)
        assert data["type"] == "service_unavailable"
        assert "192.168.1.100" in data["detail"]


# ---------------------------------------------------------------------------
# discovery_error_handler
# ---------------------------------------------------------------------------


class TestDiscoveryErrorHandler:
    """Handler for DiscoveryError."""

    def test_returns_500_server_error(self):
        exc = DiscoveryError("SSDP timeout")
        req = _make_request("/api/devices/discover")
        resp = asyncio.run(discovery_error_handler(req, exc))

        assert resp.status_code == 500
        data = _body(resp)
        assert data["type"] == "server_error"
        assert data["title"] == "Device Discovery Failed"


# ---------------------------------------------------------------------------
# oct_error_handler
# ---------------------------------------------------------------------------


class TestOctErrorHandler:
    """Catch-all for OpenCloudTouchError subclasses."""

    def test_returns_500_for_domain_error(self):
        exc = OpenCloudTouchError("some domain problem")
        req = _make_request("/api/presets")
        resp = asyncio.run(oct_error_handler(req, exc))

        assert resp.status_code == 500
        data = _body(resp)
        assert data["type"] == "server_error"
        assert data["title"] == "Internal Error"
        assert "some domain problem" in data["detail"]


# ---------------------------------------------------------------------------
# generic_exception_handler
# ---------------------------------------------------------------------------


class TestGenericExceptionHandler:
    """Catch-all for unhandled exceptions."""

    def test_returns_500_with_exception_message(self):
        exc = RuntimeError("totally unexpected")
        req = _make_request("/api/anything")
        resp = asyncio.run(generic_exception_handler(req, exc))

        assert resp.status_code == 500
        data = _body(resp)
        assert data["type"] == "server_error"
        assert data["title"] == "Internal Server Error"
        assert data["detail"] == "An unexpected error occurred. Please try again later."
        assert "totally unexpected" not in data["detail"]


# ---------------------------------------------------------------------------
# radio_browser_timeout_handler
# ---------------------------------------------------------------------------


class TestRadioBrowserTimeoutHandler:
    """Handler for RadioBrowserTimeoutError → 504 Gateway Timeout."""

    def test_returns_504_with_gateway_timeout_type(self):
        exc = RadioBrowserTimeoutError("request timed out after 10s")
        req = _make_request("/api/radio/search")
        resp = asyncio.run(radio_browser_timeout_handler(req, exc))

        assert resp.status_code == 504
        data = _body(resp)
        _rfc7807_fields(data)
        assert data["type"] == "gateway_timeout"
        assert data["status"] == 504
        assert data["title"] == "Radio Service Timeout"
        assert data["instance"] == "/api/radio/search"

    def test_detail_does_not_expose_internal_message(self):
        """Detail must be a safe user-facing message, not the raw exception string."""
        exc = RadioBrowserTimeoutError("internal server details: 192.168.1.1")
        req = _make_request("/api/radio/search")
        resp = asyncio.run(radio_browser_timeout_handler(req, exc))

        data = _body(resp)
        assert "192.168.1.1" not in data["detail"]


# ---------------------------------------------------------------------------
# radio_browser_connection_handler
# ---------------------------------------------------------------------------


class TestRadioBrowserConnectionHandler:
    """Handler for RadioBrowserConnectionError and RadioBrowserError → 503."""

    def test_connection_error_returns_503(self):
        exc = RadioBrowserConnectionError("DNS resolution failed")
        req = _make_request("/api/radio/search")
        resp = asyncio.run(radio_browser_connection_handler(req, exc))

        assert resp.status_code == 503
        data = _body(resp)
        _rfc7807_fields(data)
        assert data["type"] == "service_unavailable"
        assert data["status"] == 503
        assert data["title"] == "Radio Service Unavailable"

    def test_base_error_returns_503(self):
        exc = RadioBrowserError("generic radio browser failure")
        req = _make_request("/api/radio/search")
        resp = asyncio.run(radio_browser_connection_handler(req, exc))

        assert resp.status_code == 503
        data = _body(resp)
        assert data["type"] == "service_unavailable"

    def test_detail_does_not_expose_internal_message(self):
        """Detail must be safe user-facing message, not raw exception."""
        exc = RadioBrowserConnectionError("internal host: radio.internal.corp")
        req = _make_request("/api/radio/search")
        resp = asyncio.run(radio_browser_connection_handler(req, exc))

        data = _body(resp)
        assert "radio.internal.corp" not in data["detail"]


# ---------------------------------------------------------------------------
# register_exception_handlers
# ---------------------------------------------------------------------------


class TestRegisterExceptionHandlers:
    """Smoke test: register_exception_handlers wires all handlers onto a FastAPI app."""

    def test_registers_handlers_on_app(self):
        from fastapi import FastAPI
        from starlette.exceptions import HTTPException as StarletteHTTPException

        app = FastAPI()
        register_exception_handlers(app)

        # FastAPI/Starlette stores handlers in app.exception_handlers dict
        assert StarletteHTTPException in app.exception_handlers
        assert Exception in app.exception_handlers
