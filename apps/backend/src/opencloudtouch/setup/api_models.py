"""API request and response models for Setup Wizard endpoints.

These Pydantic models define the HTTP API contract for the device setup
wizard. Domain models (SetupStatus, SetupStep, SetupProgress) live in
setup/models.py; this file holds only the request/response DTOs.
"""

import ipaddress
import re

from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Hostname: letters, digits, hyphens, dots — NO shell metacharacters
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.-]{0,253}[a-zA-Z0-9])?$")
_DEVICE_IP_DESC = "Device IP address"
_DEVICE_ID_DESC = "Device ID (MAC address)"


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
    ip: str = Field(..., description=_DEVICE_IP_DESC)
    make_permanent: bool = Field(
        default=True, description="Copy remote_services to /mnt/nv/ for persistence"
    )


class ConnectivityCheckRequest(BaseModel):
    """Request to check device connectivity."""

    ip: str


# === Manual Modification Request/Response Models ===


class PortCheckRequest(WizardDeviceRequest):
    """Request to check SSH port."""

    timeout: float = Field(default=10.0, ge=1.0, le=60.0)


class PortCheckResponse(BaseModel):
    """Response with port check results."""

    success: bool
    message: str
    has_ssh: bool = False


class BackupRequest(WizardDeviceRequest):
    """Request to create device backup."""

    device_id: str | None = Field(
        default=None,
        description="Device identifier for unique backup filenames",
    )


class BackupResponse(BaseModel):
    """Response with backup results."""

    success: bool
    message: str
    volumes: list[dict] = Field(default_factory=list)
    total_size_mb: float = 0.0
    total_duration_seconds: float = 0.0


def _normalize_target_addr(v: str) -> str:
    """Normalize target address: add protocol/port defaults, validate format.

    Accepts:
    - Full URL: http://192.168.1.100:7777, https://oct.local:8080
    - Hostname with port: oct.local:7777
    - Hostname without port: oct.local (adds :7777)
    - IP without port: 192.168.1.100 (adds :7777)

    Returns normalized URL with protocol and port.
    """
    v = v.strip()
    if not v:
        raise ValueError("Target address cannot be empty")

    # Pattern: (protocol)?(hostname|ip)(:port)?
    # Examples: http://myserver:7777, 192.168.1.100, oct.local, myserver:8080
    pattern = r"^((?P<protocol>https?)://)?(?P<host>[a-zA-Z0-9][a-zA-Z0-9.-]*|[\d.]+)(:(?P<port>\d+))?$"
    match = re.match(pattern, v)

    if not match:
        raise ValueError(
            f"Invalid target address: '{v}'. "
            f"Expected format: (http://)hostname(:port) or (http://)IP(:port). "
            f"Examples: http://192.168.1.100:7777, oct.local, 192.168.1.100:8080"
        )

    protocol = match.group("protocol") or "http"
    host = match.group("host")
    port = match.group("port") or "7777"

    # Validate hostname/IP
    if "." in host and all(c.isdigit() or c == "." for c in host):
        # Looks like IP - validate it
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise ValueError(f"Invalid IP address: '{host}'")
    elif not _HOSTNAME_RE.match(host):
        raise ValueError(f"Invalid hostname: '{host}'")

    # Validate port
    try:
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            raise ValueError(f"Port must be between 1-65535, got: {port}")
    except ValueError as e:
        raise ValueError(f"Invalid port: {e}")

    return f"{protocol}://{host}:{port}"


class ConfigModifyRequest(WizardDeviceRequest):
    """Request to modify config file."""

    target_addr: str = Field(
        ...,
        description="OCT server URL (e.g., http://192.168.1.100:7777 or oct.local)",
    )

    @field_validator("target_addr")
    @classmethod
    def validate_target_addr(cls, v: str) -> str:
        """Validate and normalize target address."""
        return _normalize_target_addr(v)


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

    target_addr: str = Field(
        ...,
        description="OCT server URL (e.g., http://192.168.1.100:7777)",
    )
    include_optional: bool = True

    @field_validator("target_addr")
    @classmethod
    def validate_target_addr(cls, v: str) -> str:
        """Validate and normalize target address."""
        return _normalize_target_addr(v)


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
    expected_ip: str = ""
    matches_expected: bool = False
    message: str


class ListBackupsRequest(WizardDeviceRequest):
    """Request to list backups."""


class ListBackupsResponse(BaseModel):
    """Response with backup list."""

    success: bool
    config_backups: list[str] = Field(default_factory=list)
    hosts_backups: list[str] = Field(default_factory=list)


class WizardCompleteRequest(BaseModel):
    """Request to mark wizard setup as complete for a device."""

    device_id: str = Field(..., description="Device ID")


class WizardCompleteResponse(BaseModel):
    """Response after marking wizard setup as complete."""

    success: bool
    device_id: str
    setup_status: str
    message: str


class DetectStrategyResponse(BaseModel):
    """Response with detected setup strategy."""

    proxy_available: bool = Field(
        description="True if HTTPS reverse proxy detected on port 443"
    )
    strategy: str = Field(
        description="Recommended strategy: 'hosts_only' or 'bmx_and_hosts'"
    )
    message: str


class AccountPairingRequest(BaseModel):
    """Request to ensure device has a margeAccountUUID."""

    device_ip: str = Field(..., description=_DEVICE_IP_DESC)
    device_id: str = Field(..., description=_DEVICE_ID_DESC)


class AccountPairingResponse(BaseModel):
    """Response from account pairing."""

    success: bool
    had_uuid: bool = Field(
        default=False, description="True if UUID was already present"
    )
    uuid: str = Field(default="", description="The current or newly set UUID")
    message: str = ""


class InitPersistenceRequest(BaseModel):
    """Request to initialize persistence files on a factory-reset device."""

    device_ip: str = Field(..., description=_DEVICE_IP_DESC)
    device_name: str = Field(
        max_length=100,
        description="Device name from GET :8090/info <name>",
    )
    account_uuid: str = Field(
        pattern=r"^\d{1,10}$",
        description="margeAccountUUID (7-digit numeric, from account pairing)",
    )


class InitPersistenceResponse(BaseModel):
    """Response from persistence initialization."""

    success: bool
    created_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    message: str = ""
    error: Optional[str] = None


# Aliases for backward compatibility with main's naming
EnsureAccountRequest = AccountPairingRequest
EnsureAccountResponse = AccountPairingResponse


# ============================================================================
# Restore Wizard Models (separate from existing RestoreRequest/RestoreResponse
# which serve the granular restore-config/restore-hosts endpoints)
# ============================================================================


class ScanBackupsRequest(WizardDeviceRequest):
    """Request to scan USB stick for backup files."""

    device_id: str = Field(..., description="Target device ID for backup matching")


class BackupFileInfoResponse(BaseModel):
    """Single backup file info in scan response."""

    filename: str
    volume_type: str
    file_path: str
    size_bytes: int = 0
    device_id: Optional[str] = None
    backup_date: Optional[str] = None
    is_pre_restore: bool = False
    validation_status: str = "valid"
    validation_message: str = ""


class BackupSetResponse(BaseModel):
    """Backup set in scan response."""

    device_id: Optional[str] = None
    backup_date: Optional[str] = None
    files: list[BackupFileInfoResponse] = Field(default_factory=list)
    is_legacy: bool = False
    is_match: bool = False


class ScanBackupsResponse(BaseModel):
    """Response from backup scan."""

    usb_mounted: bool
    backup_dir: str = "/media/sda1/oct-backup"
    selected_set: Optional[BackupSetResponse] = None
    all_sets: list[BackupSetResponse] = Field(default_factory=list)
    error: Optional[str] = None


class RestoreWizardFileRef(BaseModel):
    """Reference to a backup file for restore execution."""

    file_path: str
    volume_type: str


class RestoreWizardBackupSet(BaseModel):
    """Backup set reference for restore execution."""

    device_id: Optional[str] = None
    backup_date: Optional[str] = None
    files: list[RestoreWizardFileRef] = Field(default_factory=list)


class RestoreWizardRequest(WizardDeviceRequest):
    """Request to execute restore wizard."""

    device_id: str = Field(..., description="Target device ID")
    restore_type: str = Field(
        ..., description="'backup' or 'clean'", pattern=r"^(backup|clean)$"
    )
    backup_set: Optional[RestoreWizardBackupSet] = None
    skip_snapshot: bool = Field(
        default=False, description="Skip pre-restore safety snapshot"
    )


class RestoreStepResponse(BaseModel):
    """Status of one restore step."""

    name: str
    status: str
    message: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0


class RestoreWizardResponse(BaseModel):
    """Response from restore wizard execution."""

    success: bool
    restore_type: str
    steps: list[RestoreStepResponse] = Field(default_factory=list)
    pre_restore_snapshot: Optional[dict] = None
    snapshot_skipped: bool = False
    device_rebooted: bool = False
    total_duration_seconds: float = 0.0


# ============================================================================
# Finalize & Verify Models (Issue #184 — post-wizard device setup)
# ============================================================================


class FinalizeRequest(WizardDeviceRequest):
    """Request to finalize device setup (UUID + Sources.xml)."""

    device_id: str = Field(..., description=_DEVICE_ID_DESC)


class FinalizeResponse(BaseModel):
    """Response from device finalization."""

    success: bool
    uuid: str = ""
    had_uuid: bool = False
    uuid_was_collision: bool = False
    sources_written: bool = False
    sources_backup_path: str = ""
    system_config_written: bool = False
    message: str = ""
    error: Optional[str] = None


class VerifyCheck(BaseModel):
    """Single verification check result."""

    name: str
    passed: bool
    message: str
    details: dict = Field(default_factory=dict)


class VerifySetupRequest(WizardDeviceRequest):
    """Request to verify device setup completeness."""

    device_id: str = Field(..., description=_DEVICE_ID_DESC)
    expected_oct_ip: str = Field(..., description="Expected OCT server IP")

    @field_validator("expected_oct_ip")
    @classmethod
    def validate_oct_ip(cls, v: str) -> str:
        return _validate_ip_field(v)


class VerifySetupResponse(BaseModel):
    """Response from device setup verification."""

    success: bool
    checks: list[VerifyCheck] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    message: str = ""
