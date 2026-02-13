"""
Unit tests for RFC 7807 ErrorDetail exception handlers.

Tests all exception handlers in main.py to ensure consistent
RFC 7807-compliant error responses across all error scenarios.
"""

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from opencloudtouch.core.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    DiscoveryError,
    OpenCloudTouchError,
    map_status_to_type,
)
from opencloudtouch.main import (
    http_exception_handler,
    validation_exception_handler,
    device_not_found_handler,
    device_connection_error_handler,
    discovery_error_handler,
    oct_error_handler,
    generic_exception_handler,
)


@pytest.fixture
def mock_request():
    """Create mock request for testing."""

    class MockURL:
        path = "/api/test/endpoint"

    class MockRequest:
        url = MockURL()

    return MockRequest()


class TestHTTPExceptionHandler:
    """Tests for HTTPException handler (most common errors)."""

    @pytest.mark.asyncio
    async def test_500_internal_server_error(self, mock_request):
        """Test 500 Internal Server Error returns RFC 7807 ErrorDetail."""
        exc = HTTPException(status_code=500, detail="RadioBrowser API error")
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 500
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "server_error"
        assert error["title"] == "RadioBrowser API error"
        assert error["status"] == 500
        assert error["detail"] == "RadioBrowser API error"
        assert error["instance"] == "/api/test/endpoint"

    @pytest.mark.asyncio
    async def test_503_service_unavailable(self, mock_request):
        """Test 503 Service Unavailable returns RFC 7807 ErrorDetail."""
        exc = HTTPException(
            status_code=503, detail="Cannot connect to RadioBrowser API"
        )
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 503
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "service_unavailable"
        assert error["status"] == 503
        assert "RadioBrowser" in error["detail"]

    @pytest.mark.asyncio
    async def test_504_gateway_timeout(self, mock_request):
        """Test 504 Gateway Timeout returns RFC 7807 ErrorDetail."""
        exc = HTTPException(status_code=504, detail="RadioBrowser API timeout")
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 504
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "gateway_timeout"
        assert error["status"] == 504

    @pytest.mark.asyncio
    async def test_404_not_found(self, mock_request):
        """Test 404 Not Found returns RFC 7807 ErrorDetail."""
        exc = HTTPException(status_code=404, detail="Device not found: abc123")
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 404
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "not_found"
        assert error["status"] == 404


class TestRequestValidationErrorHandler:
    """Tests for RequestValidationError handler (422 Unprocessable Entity)."""

    @pytest.mark.asyncio
    async def test_validation_error_with_field_details(self, mock_request):
        """Test validation error includes field-level error details."""

        # Create Pydantic model to trigger validation error
        class TestModel(BaseModel):
            station_id: str
            preset_number: int

        try:
            TestModel(station_id="", preset_number="not_a_number")
        except ValidationError as pydantic_error:
            # Convert to FastAPI RequestValidationError
            exc = RequestValidationError(errors=pydantic_error.errors())
            response = await validation_exception_handler(mock_request, exc)

            assert response.status_code == 422
            data = response.body.decode("utf-8")
            import json

            error = json.loads(data)

            assert error["type"] == "validation_error"
            assert error["title"] == "Invalid Request Data"
            assert error["status"] == 422
            assert error["detail"] == "Request validation failed"
            assert "errors" in error
            assert len(error["errors"]) > 0

            # Check field-level error structure
            field_error = error["errors"][0]
            assert "field" in field_error
            assert "message" in field_error
            assert "type" in field_error


class TestDeviceNotFoundErrorHandler:
    """Tests for DeviceNotFoundError handler (404 Not Found)."""

    @pytest.mark.asyncio
    async def test_device_not_found_returns_404(self, mock_request):
        """Test DeviceNotFoundError returns 404 with RFC 7807 ErrorDetail."""
        exc = DeviceNotFoundError(device_id="unknown-device-123")
        response = await device_not_found_handler(mock_request, exc)

        assert response.status_code == 404
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "not_found"
        assert error["title"] == "Device Not Found"
        assert error["status"] == 404
        assert "unknown-device-123" in error["detail"]
        assert error["instance"] == "/api/test/endpoint"


class TestDeviceConnectionErrorHandler:
    """Tests for DeviceConnectionError handler (503 Service Unavailable)."""

    @pytest.mark.asyncio
    async def test_device_connection_error_returns_503(self, mock_request):
        """Test DeviceConnectionError returns 503 with RFC 7807 ErrorDetail."""
        exc = DeviceConnectionError(
            device_ip="192.168.1.100", message="Connection refused"
        )
        response = await device_connection_error_handler(mock_request, exc)

        assert response.status_code == 503
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "service_unavailable"
        assert error["title"] == "Device Unavailable"
        assert error["status"] == 503
        assert "192.168.1.100" in error["detail"]


class TestDiscoveryErrorHandler:
    """Tests for DiscoveryError handler (500 Internal Server Error)."""

    @pytest.mark.asyncio
    async def test_discovery_error_returns_500(self, mock_request):
        """Test DiscoveryError returns 500 with RFC 7807 ErrorDetail."""
        exc = DiscoveryError("SSDP discovery timeout")
        response = await discovery_error_handler(mock_request, exc)

        assert response.status_code == 500
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "server_error"
        assert error["title"] == "Device Discovery Failed"
        assert error["status"] == 500
        assert "SSDP" in error["detail"]


class TestOpenCloudTouchErrorHandler:
    """Tests for OpenCloudTouchError base class handler (500)."""

    @pytest.mark.asyncio
    async def test_generic_oct_error_returns_500(self, mock_request):
        """Test generic OpenCloudTouchError returns 500 with RFC 7807 ErrorDetail."""
        exc = OpenCloudTouchError("Unexpected domain error")
        response = await oct_error_handler(mock_request, exc)

        assert response.status_code == 500
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "server_error"
        assert error["title"] == "Internal Error"
        assert error["status"] == 500
        assert "Unexpected domain error" in error["detail"]


class TestGenericExceptionHandler:
    """Tests for catch-all Exception handler (500)."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self, mock_request):
        """Test unhandled exception returns 500 with RFC 7807 ErrorDetail."""
        exc = ValueError("Unexpected ValueError from code")
        response = await generic_exception_handler(mock_request, exc)

        assert response.status_code == 500
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "server_error"
        assert error["title"] == "Internal Server Error"
        assert error["status"] == 500
        assert "ValueError" in error["detail"]

    @pytest.mark.asyncio
    async def test_zero_division_error_returns_500(self, mock_request):
        """Test ZeroDivisionError returns 500 with RFC 7807 ErrorDetail."""
        exc = ZeroDivisionError("division by zero")
        response = await generic_exception_handler(mock_request, exc)

        assert response.status_code == 500
        data = response.body.decode("utf-8")
        import json

        error = json.loads(data)

        assert error["type"] == "server_error"
        assert error["status"] == 500


class TestMapStatusToType:
    """Tests for map_status_to_type helper function."""

    def test_maps_all_common_status_codes(self):
        """Test map_status_to_type maps all common HTTP status codes."""
        assert map_status_to_type(400) == "bad_request"
        assert map_status_to_type(401) == "unauthorized"
        assert map_status_to_type(403) == "forbidden"
        assert map_status_to_type(404) == "not_found"
        assert map_status_to_type(409) == "conflict"
        assert map_status_to_type(422) == "validation_error"
        assert map_status_to_type(429) == "rate_limit_exceeded"
        assert map_status_to_type(500) == "server_error"
        assert map_status_to_type(502) == "bad_gateway"
        assert map_status_to_type(503) == "service_unavailable"
        assert map_status_to_type(504) == "gateway_timeout"

    def test_unknown_status_code_returns_generic_error(self):
        """Test unknown status codes map to generic 'error' type."""
        assert map_status_to_type(999) == "error"
        assert map_status_to_type(418) == "error"  # I'm a teapot
