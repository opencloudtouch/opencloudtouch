"""
Backup service for SoundTouch devices.

Handles backup and restore of device configuration and data.

Real partition layout (ST10, Firmware 27.x):
  ubi0:rootfs       81.4 MB  → /                (system binaries, Bose app)
  ubi1:persistent   31.5 MB  → /mnt/nv          (presets, tokens, WiFi config)
  ubi2:update        7.9 MB  → /mnt/update       (firmware installer cache)

Backup sizes (compressed tar.gz):
  soundtouch-rootfs.tgz   ~58 MB
  soundtouch-nv.tgz       ~10 KB
  soundtouch-update.tgz   ~0.9 MB

BusyBox v1.19.4 limitations:
  - No --one-file-system flag for tar
  - No --exclude with absolute paths
  - Must use explicit directory list for rootfs
"""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import List

from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)


class VolumeType(Enum):
    """Physical volume types on SoundTouch devices."""

    ROOTFS = "rootfs"
    PERSISTENT = "persistent"
    UPDATE = "update"


# SSH command timeouts per volume (rootfs ~58 MB takes longest)
_BACKUP_TIMEOUTS: dict[VolumeType, float] = {
    VolumeType.ROOTFS: 180.0,
    VolumeType.PERSISTENT: 30.0,
    VolumeType.UPDATE: 60.0,
}

# tar commands per volume (BusyBox-compatible, explicit directory list)
_BACKUP_COMMANDS: dict[VolumeType, str] = {
    VolumeType.ROOTFS: "cd / && tar czf {path} bin boot etc home lib mnt opt sbin srv usr var 2>/dev/null",
    VolumeType.PERSISTENT: "tar czf {path} /mnt/nv 2>/dev/null",
    VolumeType.UPDATE: "tar czf {path} /mnt/update 2>/dev/null",
}

_BACKUP_VOLUME_SUFFIXES: dict[VolumeType, str] = {
    VolumeType.ROOTFS: "rootfs",
    VolumeType.PERSISTENT: "nv",
    VolumeType.UPDATE: "update",
}


def _backup_filename(volume: VolumeType, device_id: str | None = None) -> str:
    """Build a unique backup filename with device ID and date.

    Format: soundtouch-{device_id}-{YYYYMMDD}-{volume}.tgz
    Fallback (no device_id): soundtouch-{volume}.tgz (legacy)
    """
    suffix = _BACKUP_VOLUME_SUFFIXES[volume]
    if device_id:
        date_str = datetime.now(UTC).strftime("%Y%m%d")
        safe_id = device_id.replace(":", "").replace(" ", "_")[:20]
        return f"soundtouch-{safe_id}-{date_str}-{suffix}.tgz"
    return f"soundtouch-{suffix}.tgz"


@dataclass
class BackupResult:
    """Result of a backup operation."""

    volume: VolumeType
    success: bool
    backup_path: str = ""
    size_bytes: int = 0
    duration_seconds: float = 0.0
    error: str | None = None


class SoundTouchBackupService:
    """
    Service for backing up SoundTouch device data via SSH.

    SSHes into the device and creates tar.gz archives of each partition
    directly onto the USB stick (mounted at /media/sda1 or similar).
    """

    def __init__(self, ssh: SoundTouchSSHClient):
        self.ssh = ssh
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def backup_all(self, device_id: str | None = None) -> List[BackupResult]:
        """
        Backup all device partitions to USB stick.

        Discovers the USB mount point, creates a backup directory,
        then runs tar for each volume (rootfs, persistent, update).

        Args:
            device_id: Optional device identifier for unique filenames.
                       Prevents backups of different devices overwriting each other.

        Returns:
            List of BackupResult for each volume.
        """
        self.logger.info(
            "Starting backup of all partitions (device=%s)", device_id or "unknown"
        )

        usb_path = await self._find_usb_mount()
        self.logger.info("USB mount point: %s", usb_path)

        backup_dir = f"{usb_path}/oct-backup"
        mkdir_result = await self.ssh.execute(f"mkdir -p {backup_dir}")
        if not mkdir_result.success:
            self.logger.warning(
                "mkdir failed (may already exist): %s", mkdir_result.error
            )

        results: List[BackupResult] = []
        for volume in [VolumeType.ROOTFS, VolumeType.PERSISTENT, VolumeType.UPDATE]:
            try:
                result = await self._backup_volume(volume, backup_dir, device_id)
                results.append(result)
                self.logger.info(
                    "Backed up %s: %.2f MB in %.1fs",
                    volume.value,
                    result.size_bytes / 1024 / 1024,
                    result.duration_seconds,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to backup %s: %s", volume.value, e, exc_info=True
                )
                results.append(BackupResult(volume=volume, success=False, error=str(e)))

        return results

    async def _find_usb_mount(self) -> str:
        """
        Detect USB stick mount point from /proc/mounts.

        SoundTouch mounts USB at /media/sda1 (or /media/usb on some firmware).
        Falls back to /media/sda1 if detection fails.
        """
        result = await self.ssh.execute(
            "grep '/media/' /proc/mounts | awk '{print $2}' | head -1"
        )
        if result.success and result.output.strip():
            mount_path = result.output.strip()
            self.logger.debug("Detected USB mount: %s", mount_path)
            return mount_path

        self.logger.warning(
            "USB mount not found in /proc/mounts, falling back to /media/sda1"
        )
        return "/media/sda1"

    async def _backup_volume(
        self, volume: VolumeType, backup_dir: str, device_id: str | None = None
    ) -> BackupResult:
        """
        Create a tar.gz backup of one volume on the device.

        Args:
            volume: Which partition to back up.
            backup_dir: Destination directory on USB (e.g. /media/sda1/oct-backup).
            device_id: Optional device identifier for unique filenames.

        Returns:
            BackupResult with real size and duration.
        """
        backup_file = f"{backup_dir}/{_backup_filename(volume, device_id)}"
        cmd = _BACKUP_COMMANDS[volume].format(path=backup_file)
        timeout = _BACKUP_TIMEOUTS[volume]

        self.logger.info("Backing up %s → %s", volume.value, backup_file)
        start_time = time.time()

        tar_result = await self.ssh.execute(cmd, timeout=timeout)
        duration = time.time() - start_time

        # tar on BusyBox often exits 1 for minor warnings (e.g. socket files) —
        # check whether the archive was actually written instead of trusting exit code.
        size_result = await self.ssh.execute(
            f"wc -c {backup_file} 2>/dev/null | awk '{{print $1}}'"
        )
        size_bytes = 0
        if size_result.success and size_result.output.strip().isdigit():
            size_bytes = int(size_result.output.strip())

        if size_bytes == 0:
            error = (
                tar_result.error or tar_result.output or "Archive is empty after tar"
            )
            self.logger.error("Backup of %s failed: %s", volume.value, error)
            return BackupResult(
                volume=volume,
                success=False,
                backup_path=backup_file,
                duration_seconds=duration,
                error=error,
            )

        return BackupResult(
            volume=volume,
            success=True,
            backup_path=backup_file,
            size_bytes=size_bytes,
            duration_seconds=duration,
        )
