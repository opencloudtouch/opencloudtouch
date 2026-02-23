"""
Backup service for SoundTouch devices.

Handles backup and restore of device configuration and data.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List

from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)


class VolumeType(Enum):
    """Volume types for backup."""

    CONFIG = "config"
    SETTINGS = "settings"
    PRESETS = "presets"
    PLAYLISTS = "playlists"
    NETWORK = "network"


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
    """Service for backing up SoundTouch device data."""

    def __init__(self, ssh: SoundTouchSSHClient):
        """
        Initialize backup service.

        Args:
            ssh: SSH client for device communication
        """
        self.ssh = ssh
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def backup_all(self) -> List[BackupResult]:
        """
        Backup all device data to USB stick.

        Returns:
            List of backup results for each volume
        """
        self.logger.info("Starting backup of all volumes")

        volumes = [
            VolumeType.CONFIG,
            VolumeType.SETTINGS,
            VolumeType.PRESETS,
            VolumeType.PLAYLISTS,
            VolumeType.NETWORK,
        ]

        results = []
        for volume in volumes:
            try:
                result = await self._backup_volume(volume)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to backup {volume.value}: {e}")
                results.append(
                    BackupResult(
                        volume=volume,
                        success=False,
                        error=str(e),
                    )
                )

        return results

    async def _backup_volume(self, volume: VolumeType) -> BackupResult:
        """
        Backup a single volume.

        Args:
            volume: Volume type to backup

        Returns:
            Backup result
        """
        self.logger.info(f"Backing up volume: {volume.value}")

        # TODO: Implement actual backup logic
        # For now, return success with demo data
        return BackupResult(
            volume=volume,
            success=True,
            backup_path=f"/usb/{volume.value}_backup.tar.gz",
            size_bytes=1024 * 1024,  # 1 MB demo
            duration_seconds=2.0,
        )
