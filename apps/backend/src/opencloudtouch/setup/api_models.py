"""API request and response models for Setup Wizard endpoints.

These Pydantic models define the HTTP API contract for the device setup
wizard. Domain models (SetupStatus, SetupStep, SetupProgress) live in
setup/models.py; this file holds only the request/response DTOs.
"""

import ipaddress
import re

from pydantic import BaseModel, Field, field_validator

# Hostname: letters, digits, hyphens, dots — NO shell metacharacters
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.-]{0,253}[a-zA-Z0-9])?$")


def _validate_ip_field(v: str) -> str:
    """Validate that a string is a valid IPv4 or IPv6 address."""
    try:
        return str(ipaddress.ip_address(v.strip()))
    except ValueError:
        raise ValueError(f"Invalid IP address: {v!r}")


class WizardDeviceRequest(BaseModel):
    """Base class for wizard requests that require a device IP address.

    Validates that ``device_ip`` is a valid IPv4 or IPv6 address,
    protecting against SSRF and providing clear validation errors.
    """

    device_ip: str

    @field_validator("device_ip")
    @classmethod
    def validate_device_ip(cls, v: str) -> str:
        return _validate_ip_field(v)


class EnablePermanentSSHRequest(BaseModel):
    """Request to enable permanent SSH access on device."""

    device_id: str = Field(..., description="Device ID")
    ip: str = Field(..., description="Device IP address")
    make_permanent: bool = Field(
        default=True, description="Copy remote_services to /mnt/nv/ for persistence"
    )


class SetupRequest(BaseModel):
    """Request to start device setup."""

    device_id: str
    ip: str
    model: str


class ConnectivityCheckRequest(BaseModel):
    """Request to check device connectivity."""

    ip: str


# === Manual Modification Request/Response Models ===


class PortCheckRequest(WizardDeviceRequest):
    """Request to check SSH/Telnet ports."""

    timeout: float = Field(default=10.0, ge=1.0, le=60.0)


class PortCheckResponse(BaseModel):
    """Response with port check results."""

    success: bool
    message: str
    has_ssh: bool = False
    has_telnet: bool = False


class BackupRequest(WizardDeviceRequest):
    """Request to create device backup."""


class BackupResponse(BaseModel):
    """Response with backup results."""

    success: bool
    message: str
    volumes: list[dict] = Field(default_factory=list)
    total_size_mb: float = 0.0
    total_duration_seconds: float = 0.0


class ConfigModifyRequest(WizardDeviceRequest):
    """Request to modify config file."""

    oct_ip: str

    @field_validator("oct_ip")
    @classmethod
    def validate_oct_ip(cls, v: str) -> str:
        return _validate_ip_field(v)


class ConfigModifyResponse(BaseModel):
    """Response with config modification result."""

    success: bool
    message: str
    backup_path: str = ""
    diff: str = ""
    old_url: str = ""
    new_url: str = ""


class HostsModifyRequest(WizardDeviceRequest):
    """Request to modify hosts file."""

    oct_ip: str
    include_optional: bool = True

    @field_validator("oct_ip")
    @classmethod
    def validate_oct_ip(cls, v: str) -> str:
        return _validate_ip_field(v)


class HostsModifyResponse(BaseModel):
    """Response with hosts modification result."""

    success: bool
    message: str
    backup_path: str = ""
    diff: str = ""


class RestoreRequest(WizardDeviceRequest):
    """Request to restore from backup."""

    backup_path: str


class RestoreResponse(BaseModel):
    """Response with restore result."""

    success: bool
    message: str


class VerifyRedirectRequest(WizardDeviceRequest):
    """Request to verify domain redirect from device."""

    domain: str
    expected_ip: str  # OCT hostname or IP as seen by browser

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain is a safe hostname (prevents shell injection via f-string)."""
        v = v.strip()
        if not _HOSTNAME_RE.match(v):
            raise ValueError(
                f"Invalid domain: {v!r}. Only letters, digits, dots and hyphens allowed."
            )
        return v

    @field_validator("expected_ip")
    @classmethod
    def validate_expected_ip(cls, v: str) -> str:
        """Validate expected_ip is a valid IP address or hostname."""
        v = v.strip()
        # Try as IP first
        try:
            return str(ipaddress.ip_address(v))
        except ValueError:
            pass
        # Fall back to hostname validation
        if not _HOSTNAME_RE.match(v):
            raise ValueError(
                f"Invalid expected_ip: {v!r}. Must be a valid IP or hostname."
            )
        return v


class VerifyRedirectResponse(BaseModel):
    """Response with domain redirect verification result."""

    success: bool
    domain: str
    resolved_ip: str = ""
    matches_expected: bool = False
    message: str


class ListBackupsRequest(WizardDeviceRequest):
    """Request to list backups."""


class ListBackupsResponse(BaseModel):
    """Response with backup list."""

    success: bool
    config_backups: list[str] = Field(default_factory=list)
    hosts_backups: list[str] = Field(default_factory=list)
