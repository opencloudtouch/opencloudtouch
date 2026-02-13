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


class ConfigurationError(OpenCloudTouchError):
    """Raised when configuration is invalid."""

    pass


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


def map_status_to_type(status_code: int) -> str:
    """Map HTTP status code to error type string.

    Args:
        status_code: HTTP status code

    Returns:
        Error type string (e.g., 'not_found', 'validation_error')
    """
    if status_code == 400:
        return "bad_request"
    elif status_code == 401:
        return "unauthorized"
    elif status_code == 403:
        return "forbidden"
    elif status_code == 404:
        return "not_found"
    elif status_code == 409:
        return "conflict"
    elif status_code == 422:
        return "validation_error"
    elif status_code == 429:
        return "rate_limit_exceeded"
    elif status_code == 500:
        return "server_error"
    elif status_code == 502:
        return "bad_gateway"
    elif status_code == 503:
        return "service_unavailable"
    elif status_code == 504:
        return "gateway_timeout"
    else:
        return "error"
