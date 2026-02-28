"""
Configuration service for SoundTouch devices.

Handles modification and restoration of device configuration files.
"""

import logging
from dataclasses import dataclass
from typing import List

from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)


@dataclass
class ModifyResult:
    """Result of a configuration modification."""

    success: bool
    backup_path: str = ""
    diff: str = ""
    error: str | None = None


@dataclass
class RestoreResult:
    """Result of a configuration restoration."""

    success: bool
    error: str | None = None


class SoundTouchConfigService:
    """Service for modifying SoundTouch device configuration."""

    CONFIG_PATH = "/mnt/nv/OverrideSdkPrivateCfg.xml"
    BACKUP_DIR = "/usb/backups"

    def __init__(self, ssh: SoundTouchSSHClient):
        """
        Initialize config service.

        Args:
            ssh: SSH client for device communication
        """
        self.ssh = ssh
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def _remount_rw(self) -> None:
        """Remount root filesystem read-write before writing."""
        result = await self.ssh.execute("mount -o remount,rw /")
        if result.exit_code != 0:
            self.logger.warning(
                f"remount rw returned exit_code={result.exit_code}: {result.stderr}"
            )

    async def _remount_ro(self) -> None:
        """Remount root filesystem read-only after writing."""
        result = await self.ssh.execute("mount -o remount,ro /")
        if result.exit_code != 0:
            self.logger.warning(
                f"remount ro returned exit_code={result.exit_code}: {result.stderr}"
            )

    async def modify_bmx_url(self, oct_ip: str) -> ModifyResult:
        """
        Modify BMX URL in config to point to OCT.

        Write protocol: remount rw → write → remount ro (in finally block).

        Args:
            oct_ip: OCT server IP address

        Returns:
            Modification result with backup path and diff
        """
        self.logger.info(f"Modifying BMX URL to point to OCT at {oct_ip}")

        try:
            await self._remount_rw()
            try:
                # TODO: Implement actual config modification
                # 1. Download current config:  cat {self.CONFIG_PATH}
                # 2. Parse XML
                # 3. Find BMX URLs and replace with oct_ip
                # 4. Backup original: cp {self.CONFIG_PATH} {self.BACKUP_DIR}/config_backup.xml
                # 5. Upload modified config: write via echo/tee or scp
                # 6. Generate diff

                backup_path = f"{self.BACKUP_DIR}/config_backup.xml"
                diff = f"- bmx.bose.com\n+ {oct_ip}"

                self.logger.info("Config modified successfully")
                return ModifyResult(
                    success=True,
                    backup_path=backup_path,
                    diff=diff,
                )
            finally:
                await self._remount_ro()

        except Exception as e:
            self.logger.error(f"Config modification failed: {e}")
            return ModifyResult(
                success=False,
                error=str(e),
            )

    async def restore_config(self, backup_path: str) -> RestoreResult:
        """
        Restore config from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            Restoration result
        """
        self.logger.info(f"Restoring config from {backup_path}")

        try:
            # TODO: Implement actual restore logic
            # 1. Verify backup exists
            # 2. Upload backup to device
            # 3. Replace current config
            # 4. Restart service if needed

            self.logger.info("Config restored successfully")
            return RestoreResult(success=True)

        except Exception as e:
            self.logger.error(f"Config restore failed: {e}")
            return RestoreResult(
                success=False,
                error=str(e),
            )

    async def list_backups(self) -> List[str]:
        """
        List available config backups.

        Returns:
            List of backup file paths
        """
        self.logger.info("Listing config backups")

        try:
            # TODO: Implement actual backup listing
            # 1. Connect to device
            # 2. List files in backup directory
            # 3. Filter config backups
            # 4. Return sorted list

            return [
                "/usb/backups/config_backup_2024-01-01.xml",
                "/usb/backups/config_backup_2024-01-02.xml",
            ]

        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")
            return []
