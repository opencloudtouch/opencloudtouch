"""Data models for the Restore Wizard.

Domain models for backup scanning, validation, and restore execution.
API request/response DTOs are in api_models.py (added separately).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ValidationStatus(str, Enum):
    """Archive validation result."""

    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


class RestoreStepName(str, Enum):
    """Steps in the restore sequence."""

    PRE_SNAPSHOT = "pre_snapshot"
    CONFIG = "config"
    PRESETS = "presets"
    HOSTS = "hosts"
    REMOTE_SERVICES = "remote_services"
    REBOOT = "reboot"


class StepStatus(str, Enum):
    """Status of an individual restore step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class BackupFileInfo:
    """A single backup archive file found on USB."""

    filename: str
    volume_type: str  # "rootfs", "persistent", or "update"
    file_path: str
    size_bytes: int = 0
    device_id: Optional[str] = None
    backup_date: Optional[str] = None
    is_pre_restore: bool = False
    validation_status: ValidationStatus = ValidationStatus.VALID
    validation_message: str = ""


@dataclass
class BackupSet:
    """A group of backup files belonging to the same device/date."""

    device_id: Optional[str] = None
    backup_date: Optional[str] = None
    files: list = field(default_factory=list)
    is_legacy: bool = False
    is_match: bool = False


@dataclass
class BackupScanResult:
    """Result of scanning USB stick for backup files."""

    usb_mounted: bool = False
    backup_dir: str = "/media/sda1/oct-backup"
    selected_set: Optional[BackupSet] = None
    all_sets: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RestoreStep:
    """Status of one step in the restore sequence."""

    name: RestoreStepName
    status: StepStatus = StepStatus.PENDING
    message: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class RestoreResult:
    """Result of the entire restore operation."""

    success: bool = False
    restore_type: str = "clean"
    steps: list = field(default_factory=list)
    pre_restore_snapshot: Optional[dict] = None
    snapshot_skipped: bool = False
    device_rebooted: bool = False
    total_duration_seconds: float = 0.0
