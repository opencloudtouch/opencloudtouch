"""
Custom exceptions for OpenCloudTouch
Provides a unified exception hierarchy for better error handling
Includes RFC 7807-inspired standardized error responses
"""

from typing import Any

from pydantic import BaseModel


class OpenCloudTouchError(Exception):
    """Base exception for all OpenCloudTouch errors."""

    pass


class DiscoveryError(OpenCloudTouchError):
    """Raised when device discovery fails."""

    pass


class DeviceConnectionError(OpenCloudTouchError):
    """Raised when connection to a streaming device fails."""

    def __init__(self, device_ip: str, message: str = "Device unreachable"):
        self.device_ip = device_ip
        super().__init__(f"{message}: {device_ip}")


class DeviceNotFoundError(OpenCloudTouchError):
    """Raised when a requested device is not found in the database."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        super().__init__(f"Device not found: {device_id}")


# ============================================================================
# Standardized Error Response Models (RFC 7807-inspired)
# ============================================================================


class ErrorDetail(BaseModel):
    """Standardized error response format (RFC 7807-inspired).

    Provides consistent error structure across all API endpoints.

    Attributes:
        type: Error category (validation_error, not_found, server_error, etc.)
        title: Human-readable error title
        status: HTTP status code
        detail: Detailed error message
        instance: Request path that triggered error (optional)
        errors: Field-level validation errors (optional, for 422 responses)

    Example:
        {
            "type": "not_found",
            "title": "Device Not Found",
            "status": 404,
            "detail": "Device with ID 'abc123' does not exist",
            "instance": "/api/devices/abc123"
        }
    """

    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    errors: list[dict[str, Any]] | None = None


_HTTP_STATUS_TYPE_MAP: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "server_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}


def map_status_to_type(status_code: int) -> str:
    """Map HTTP status code to error type string.

    Args:
        status_code: HTTP status code

    Returns:
        Error type string (e.g., 'not_found', 'validation_error')
    """
    return _HTTP_STATUS_TYPE_MAP.get(status_code, "error")
