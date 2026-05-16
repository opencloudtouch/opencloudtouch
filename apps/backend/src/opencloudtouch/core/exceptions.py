"""
Custom exceptions for OpenCloudTouch

Unified exception hierarchy — all domain exceptions inherit from
OpenCloudTouchError so they can be caught uniformly by global handlers.

Hierarchy:
    OpenCloudTouchError
    ├── DeviceNotFoundError          → 404
    ├── DeviceConnectionError        → 503
    ├── DiscoveryError               → 500
    ├── DomainValidationError        → 400
    ├── RadioError                   → 500
    │   ├── RadioTimeoutError        → 504
    │   └── RadioConnectionError     → 503
    ├── SSHError                     → 500
    │   ├── SSHConnectionError       → 503
    │   └── SSHOperationError        → 500
    └── ExternalServiceError         → 502

Includes RFC 7807-inspired standardized error responses.
"""

from typing import Any

from pydantic import BaseModel


class OpenCloudTouchError(Exception):
    """Base exception for all OpenCloudTouch errors."""

    pass


# ============================================================================
# Device Exceptions
# ============================================================================


class DeviceNotFoundError(OpenCloudTouchError):
    """Raised when a requested device is not found in the database."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        super().__init__(f"Device not found: {device_id}")


class DeviceConnectionError(OpenCloudTouchError):
    """Raised when connection to a streaming device fails."""

    def __init__(self, device_ip: str, message: str = "Device unreachable"):
        self.device_ip = device_ip
        super().__init__(f"{message}: {device_ip}")


class DiscoveryError(OpenCloudTouchError):
    """Raised when device discovery fails."""

    pass


# ============================================================================
# Domain Validation Exceptions (replaces bare ValueError in services)
# ============================================================================


class DomainValidationError(OpenCloudTouchError):
    """Raised when domain-level validation fails (invalid input to service layer).

    Maps to HTTP 400 Bad Request.
    """

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


# ============================================================================
# Radio Provider Exceptions
# ============================================================================


class RadioError(OpenCloudTouchError):
    """Base exception for radio provider errors (RadioBrowser, TuneIn)."""

    pass


class RadioTimeoutError(RadioError):
    """Raised when radio provider API times out. Maps to 504."""

    pass


class RadioConnectionError(RadioError):
    """Raised when connection to radio provider fails. Maps to 503."""

    pass


# ============================================================================
# SSH / Setup Exceptions
# ============================================================================


class SSHError(OpenCloudTouchError):
    """Base exception for SSH operations."""

    def __init__(self, device_ip: str, message: str = "SSH operation failed"):
        self.device_ip = device_ip
        super().__init__(f"{message}: {device_ip}")


class SSHConnectionError(SSHError):
    """Raised when SSH connection to device fails. Maps to 503."""

    def __init__(self, device_ip: str, message: str = "SSH connection refused"):
        super().__init__(device_ip, message)


class SSHOperationError(SSHError):
    """Raised when an SSH command fails on the device. Maps to 500."""

    def __init__(self, device_ip: str, operation: str, message: str = ""):
        self.operation = operation
        detail = f"SSH operation '{operation}' failed"
        if message:
            detail += f": {message}"
        super().__init__(device_ip, detail)


# ============================================================================
# Restore Wizard Exceptions
# ============================================================================


class RestoreError(OpenCloudTouchError):
    """Raised when a restore operation fails."""

    def __init__(self, device_ip: str, step: str, message: str = ""):
        self.device_ip = device_ip
        self.step = step
        detail = f"Restore step '{step}' failed on {device_ip}"
        if message:
            detail += f": {message}"
        super().__init__(detail)


class BackupScanError(OpenCloudTouchError):
    """Raised when backup scan on USB stick fails."""

    def __init__(self, device_ip: str, message: str = "Backup scan failed"):
        self.device_ip = device_ip
        super().__init__(f"{message}: {device_ip}")


# ============================================================================
# External Service Exceptions
# ============================================================================


class ExternalServiceError(OpenCloudTouchError):
    """Raised when an external service (GitHub, etc.) fails. Maps to 502."""

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
