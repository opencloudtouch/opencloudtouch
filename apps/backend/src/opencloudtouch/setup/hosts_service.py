"""
Hosts file service for SoundTouch devices.

Handles modification and restoration of /etc/hosts file.
"""

import base64
import ipaddress
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
    BACKUP_DIR = "/mnt/nv"
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
        "content.api.bose.io",
        "events.api.bosecm.com",
        "worldwide.bose.com",
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
                "remount rw returned exit_code=%s: %s", result.exit_code, result.stderr
            )

    async def _remount_ro(self) -> None:
        """Remount root filesystem read-only after writing."""
        result = await self.ssh.execute("mount -o remount,ro /")
        if result.exit_code != 0:
            self.logger.warning(
                "remount ro returned exit_code=%s: %s", result.exit_code, result.stderr
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
        # /etc/hosts requires a numeric IP address in the first field.
        # Reject hostnames early to prevent broken entries like "hera  bose.vtuner.com".
        try:
            ipaddress.ip_address(oct_ip)
        except ValueError:
            self.logger.debug("IP validation failed for '%s'", oct_ip)
            return ModifyResult(
                success=False,
                error=(
                    f"'{oct_ip}' is not a valid IP address. "
                    f"/etc/hosts requires a numeric IP (e.g. 192.168.1.100)."
                ),
            )

        self.logger.info(
            "Modifying hosts to redirect to OCT at %s (optional: %s)",
            oct_ip,
            include_optional,
        )

        try:
            await self._remount_rw()
            try:
                original_content = await self._read_hosts()
                backup_path = f"{self.BACKUP_DIR}/hosts_backup"
                await self._ensure_backup(backup_path)

                domains_to_add = self.VTUNER_HOSTS + self.REQUIRED_HOSTS
                if include_optional:
                    domains_to_add = domains_to_add + self.OPTIONAL_HOSTS

                self.logger.debug(
                    "Hosts: %d domains to add (vtuner=%d, required=%d, optional=%d)",
                    len(domains_to_add),
                    len(self.VTUNER_HOSTS),
                    len(self.REQUIRED_HOSTS),
                    len(self.OPTIONAL_HOSTS) if include_optional else 0,
                )

                all_bose_domains = (
                    self.VTUNER_HOSTS + self.REQUIRED_HOSTS + self.OPTIONAL_HOSTS
                )
                clean_lines = self._build_clean_lines(
                    original_content, all_bose_domains
                )
                oct_block = self._build_oct_block(oct_ip, domains_to_add)
                new_content = self._assemble_hosts_content(clean_lines, oct_block)

                await self._write_hosts(new_content)

                diff = "\n".join(f"+ {oct_ip}\t{d}" for d in domains_to_add)
                self.logger.info(
                    "Hosts modified successfully (%d entries)", len(domains_to_add)
                )
                return ModifyResult(success=True, backup_path=backup_path, diff=diff)
            finally:
                await self._remount_ro()

        except Exception as e:
            self.logger.error("Hosts modification failed: %s", e)
            return ModifyResult(success=False, error=str(e))

    async def _read_hosts(self) -> str:
        """Read current hosts file from device."""
        read_result = await self.ssh.execute(f"cat {self.HOSTS_PATH}")
        if not read_result.success:
            raise RuntimeError(f"Cannot read hosts file: {read_result.error}")
        return read_result.output or ""

    async def _ensure_backup(self, backup_path: str) -> None:
        """Create a backup of the hosts file if none exists yet."""
        check = await self.ssh.execute(
            f"test -f {backup_path} && echo 'exists' || echo 'missing'"
        )
        if "missing" in (check.output or ""):
            backup_result = await self.ssh.execute(
                f"cp {self.HOSTS_PATH} {backup_path}"
            )
            if not backup_result.success:
                self.logger.warning("Backup may have failed: %s", backup_result.error)

    def _build_clean_lines(
        self, original_content: str, all_bose_domains: List[str]
    ) -> list[str]:
        """Strip existing OCT blocks and bare Bose-domain entries from hosts."""
        clean_lines: list[str] = []
        in_oct_block = False
        removed = 0
        for line in original_content.splitlines():
            if self.OCT_MARKER_START in line:
                in_oct_block = True
                continue
            if self.OCT_MARKER_END in line:
                in_oct_block = False
                continue
            if in_oct_block:
                removed += 1
                continue
            parts = line.split()
            if len(parts) >= 2 and any(d in parts for d in all_bose_domains):
                removed += 1
                continue
            clean_lines.append(line)
        self.logger.debug(
            "Hosts cleanup: %d original lines, %d kept, %d removed",
            len(original_content.splitlines()),
            len(clean_lines),
            removed,
        )
        return clean_lines

    def _build_oct_block(self, oct_ip: str, domains: List[str]) -> list[str]:
        """Build the OCT marker block lines."""
        lines = [self.OCT_MARKER_START]
        lines.extend(f"{oct_ip}\t{d}\t# OpenCloudTouch redirect" for d in domains)
        lines.append(self.OCT_MARKER_END)
        return lines

    def _assemble_hosts_content(
        self, clean_lines: list[str], oct_block: list[str]
    ) -> str:
        """Combine cleaned baseline and new OCT block into hosts file content."""
        while clean_lines and clean_lines[-1].strip() == "":
            clean_lines.pop()
        return "\n".join(clean_lines) + "\n\n" + "\n".join(oct_block) + "\n"

    async def _write_hosts(self, content: str) -> None:
        """Write hosts file content atomically via base64 piping."""
        b64 = base64.b64encode(content.encode()).decode()
        write_cmd = (
            f"echo '{b64}' | base64 -d > /tmp/hosts.new && "
            f"mv /tmp/hosts.new {self.HOSTS_PATH}"
        )
        write_result = await self.ssh.execute(write_cmd)
        if not write_result.success:
            raise RuntimeError(
                f"Failed to write hosts file: {write_result.error or write_result.output}"
            )

    async def restore_hosts(self, backup_path: str) -> RestoreResult:
        """Restore hosts file from backup.

        Protocol: verify backup exists → remount rw → copy → remount ro.

        Args:
            backup_path: Path to backup file on device

        Returns:
            Restoration result
        """
        self.logger.info("Restoring hosts from %s", backup_path)

        try:
            check = await self.ssh.execute(
                f"test -f {backup_path} && echo 'exists' || echo 'missing'"
            )
            if "missing" in (check.output or ""):
                return RestoreResult(
                    success=False,
                    error=f"Backup not found: {backup_path}",
                )

            await self._remount_rw()
            try:
                result = await self.ssh.execute(f"cp {backup_path} {self.HOSTS_PATH}")
                if not result.success:
                    return RestoreResult(
                        success=False,
                        error=f"Copy failed: {result.error or result.output}",
                    )

                self.logger.info("Hosts restored successfully")
                return RestoreResult(success=True)
            finally:
                await self._remount_ro()

        except Exception as e:
            self.logger.error("Hosts restore failed: %s", e)
            return RestoreResult(
                success=False,
                error=str(e),
            )

    async def list_backups(self) -> List[str]:
        """List available hosts backups on the device.

        Returns:
            List of backup file paths, sorted newest first
        """
        self.logger.info("Listing hosts backups")

        try:
            result = await self.ssh.execute(
                f"ls -1t {self.BACKUP_DIR}/hosts_backup* 2>/dev/null"
            )
            if not result.success or not result.output:
                return []

            return [
                line.strip()
                for line in result.output.strip().splitlines()
                if line.strip()
            ]

        except Exception as e:
            self.logger.error("Failed to list backups: %s", e)
            return []
