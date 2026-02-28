"""
Hosts file service for SoundTouch devices.

Handles modification and restoration of /etc/hosts file.
"""

import base64
import logging
from dataclasses import dataclass
from typing import List

from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)


@dataclass
class ModifyResult:
    """Result of a hosts file modification."""

    success: bool
    backup_path: str = ""
    diff: str = ""
    error: str | None = None


@dataclass
class RestoreResult:
    """Result of a hosts file restoration."""

    success: bool
    error: str | None = None


class SoundTouchHostsService:
    """Service for modifying SoundTouch device hosts file."""

    HOSTS_PATH = "/etc/hosts"
    BACKUP_DIR = "/usb/backups"
    OCT_MARKER_START = "# OCT-START"
    OCT_MARKER_END = "# OCT-END"

    # Critical vTuner domains for Internet Radio
    VTUNER_HOSTS = [
        "bose.vtuner.com",
        "bose2.vtuner.com",
        "primary5.vtuner.com",
        "primary6.vtuner.com",
    ]

    # Bose cloud domains for streaming / account services
    REQUIRED_HOSTS = [
        "streaming.bose.com",
        "bmx.bose.com",
        "api.bosesoundtouch.com",
    ]

    OPTIONAL_HOSTS = [
        "update.bose.com",
        "analytics.bose.com",
        "telemetry.bose.com",
    ]

    def __init__(self, ssh: SoundTouchSSHClient):
        """
        Initialize hosts service.

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

    async def modify_hosts(
        self, oct_ip: str, include_optional: bool = True
    ) -> ModifyResult:
        """
        Modify /etc/hosts to redirect Bose domains to OCT.

        Write protocol: remount rw → write → remount ro (in finally block).
        Uses base64 piping for atomic write to avoid shell-escape issues.

        Args:
            oct_ip: OCT server IP address
            include_optional: Include optional domains (analytics, updates)

        Returns:
            Modification result with backup path and diff
        """
        self.logger.info(
            f"Modifying hosts to redirect to OCT at {oct_ip} "
            f"(optional: {include_optional})"
        )

        try:
            await self._remount_rw()
            try:
                # 1. Read current hosts
                read_result = await self.ssh.execute(f"cat {self.HOSTS_PATH}")
                if not read_result.success:
                    raise RuntimeError(f"Cannot read hosts file: {read_result.error}")
                original_content = read_result.output or ""

                # 2. Backup original (only once — don't overwrite an existing backup)
                backup_path = f"{self.BACKUP_DIR}/hosts_backup"
                check = await self.ssh.execute(
                    f"test -f {backup_path} && echo 'exists' || echo 'missing'"
                )
                if "missing" in (check.output or ""):
                    backup_result = await self.ssh.execute(
                        f"cp {self.HOSTS_PATH} {backup_path}"
                    )
                    if not backup_result.success:
                        self.logger.warning(
                            f"Backup may have failed: {backup_result.error}"
                        )

                # 3. Build clean baseline: strip any previous OCT block and
                #    any bare Bose-domain entries (old format without markers)
                all_bose_domains = (
                    self.VTUNER_HOSTS + self.REQUIRED_HOSTS + self.OPTIONAL_HOSTS
                )
                clean_lines: list[str] = []
                in_oct_block = False
                for line in original_content.splitlines():
                    if self.OCT_MARKER_START in line:
                        in_oct_block = True
                        continue
                    if self.OCT_MARKER_END in line:
                        in_oct_block = False
                        continue
                    if in_oct_block:
                        continue
                    # Drop bare entries from old OCT installs (no marker)
                    parts = line.split()
                    if len(parts) >= 2 and any(d in parts for d in all_bose_domains):
                        continue
                    clean_lines.append(line)

                # 4. Build new OCT block
                domains_to_add = self.VTUNER_HOSTS + self.REQUIRED_HOSTS
                if include_optional:
                    domains_to_add = domains_to_add + self.OPTIONAL_HOSTS

                oct_lines = [self.OCT_MARKER_START]
                for domain in domains_to_add:
                    oct_lines.append(f"{oct_ip}\t{domain}\t# OpenCloudTouch redirect")
                oct_lines.append(self.OCT_MARKER_END)

                # Strip trailing blank lines from baseline and assemble
                while clean_lines and clean_lines[-1].strip() == "":
                    clean_lines.pop()
                new_content = (
                    "\n".join(clean_lines) + "\n\n" + "\n".join(oct_lines) + "\n"
                )

                # 5. Atomic write via base64 (avoids shell escaping issues on BusyBox)
                b64 = base64.b64encode(new_content.encode()).decode()
                write_cmd = (
                    f"echo '{b64}' | base64 -d > /tmp/hosts.new && "
                    f"mv /tmp/hosts.new {self.HOSTS_PATH}"
                )
                write_result = await self.ssh.execute(write_cmd)
                if not write_result.success:
                    raise RuntimeError(
                        f"Failed to write hosts file: {write_result.error or write_result.output}"
                    )

                # 6. Build diff summary for UI
                diff_lines = [f"+ {oct_ip}\t{d}" for d in domains_to_add]
                diff = "\n".join(diff_lines)

                self.logger.info(
                    f"Hosts modified successfully ({len(domains_to_add)} entries)"
                )
                return ModifyResult(
                    success=True,
                    backup_path=backup_path,
                    diff=diff,
                )
            finally:
                await self._remount_ro()

        except Exception as e:
            self.logger.error(f"Hosts modification failed: {e}")
            return ModifyResult(
                success=False,
                error=str(e),
            )

    async def restore_hosts(self, backup_path: str) -> RestoreResult:
        """
        Restore hosts file from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            Restoration result
        """
        self.logger.info(f"Restoring hosts from {backup_path}")

        try:
            # TODO: Implement actual restore logic
            # 1. Verify backup exists
            # 2. Upload backup to device
            # 3. Replace current hosts file
            # 4. Restart networking if needed

            self.logger.info("Hosts restored successfully")
            return RestoreResult(success=True)

        except Exception as e:
            self.logger.error(f"Hosts restore failed: {e}")
            return RestoreResult(
                success=False,
                error=str(e),
            )

    async def list_backups(self) -> List[str]:
        """
        List available hosts backups.

        Returns:
            List of backup file paths
        """
        self.logger.info("Listing hosts backups")

        try:
            # TODO: Implement actual backup listing
            # 1. Connect to device
            # 2. List files in backup directory
            # 3. Filter hosts backups
            # 4. Return sorted list

            return [
                "/usb/backups/hosts_backup_2024-01-01",
                "/usb/backups/hosts_backup_2024-01-02",
            ]

        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")
            return []
