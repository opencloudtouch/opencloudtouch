"""
NTP server configuration service for SoundTouch devices.

Handles patching and restoring /etc/ntpservers.txt, following the same
remount + backup + base64-write pattern as SoundTouchHostsService.
"""

import base64
import logging
import shlex
from dataclasses import dataclass

from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)


@dataclass
class PatchResult:
    """Result of an NTP server patch.

    `success` reflects the persistent effect (the file write); `synced`
    reflects the best-effort immediate resync, which may fail independently
    (unreachable server, DNS hiccup) without the patch itself having failed.
    """

    success: bool
    synced: bool = True
    backup_path: str = ""
    diff: str = ""
    error: str | None = None


class SoundTouchNtpService:
    """Service for patching SoundTouch device NTP server configuration."""

    NTP_PATH = "/etc/ntpservers.txt"
    BACKUP_DIR = "/mnt/nv"
    BACKUP_NAME = "ntpservers_backup"
    NTPD_RESYNC_TIMEOUT = 15.0

    # Public pool fallbacks appended after the chosen server, so time sync
    # still has somewhere to go if the chosen server becomes unreachable.
    FALLBACK_SERVERS = ("0.pool.ntp.org", "1.pool.ntp.org")

    def __init__(self, ssh: SoundTouchSSHClient):
        """
        Initialize NTP service.

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

    async def patch_ntp(self, ntp_server: str) -> PatchResult:
        """
        Write ntp_server to /etc/ntpservers.txt and resync via ntpd.

        Write protocol: remount rw → write → remount ro (in finally block,
        so a cancelled request still leaves the filesystem read-only).

        Args:
            ntp_server: NTP server hostname or IP to use first

        Returns:
            Patch result with backup path and diff
        """
        self.logger.info("Patching NTP server to %s", ntp_server)

        try:
            await self._remount_rw()
            try:
                backup_path = f"{self.BACKUP_DIR}/{self.BACKUP_NAME}"
                await self._ensure_backup(backup_path)

                servers = [ntp_server, *self.FALLBACK_SERVERS]
                new_content = "\n".join(servers) + "\n"
                await self._write_ntp_servers(new_content)

                # The file write is the persistent effect; resync is
                # best-effort — a failure here must not be reported as a
                # failed patch, since the device already has the new config.
                sync_result = await self.ssh.execute(
                    f"/bin/ntpd -q -n -p {shlex.quote(ntp_server)}",
                    timeout=self.NTPD_RESYNC_TIMEOUT,
                )
                synced = sync_result.success
                if not synced:
                    self.logger.warning(
                        "ntpd resync failed (file already patched to %s): %s",
                        ntp_server,
                        sync_result.error,
                    )

                diff = "\n".join(f"+ {s}" for s in servers)
                self.logger.info("NTP server patched successfully to %s", ntp_server)
                return PatchResult(
                    success=True, synced=synced, backup_path=backup_path, diff=diff
                )
            finally:
                await self._remount_ro()

        except Exception as e:
            self.logger.error("NTP patch failed: %s", e)
            return PatchResult(success=False, error=str(e))

    async def _ensure_backup(self, backup_path: str) -> None:
        """Create a backup of the NTP servers file if none exists yet."""
        check = await self.ssh.execute(
            f"test -f {backup_path} && echo 'exists' || echo 'missing'"
        )
        if "missing" in (check.output or ""):
            backup_result = await self.ssh.execute(f"cp {self.NTP_PATH} {backup_path}")
            if not backup_result.success:
                # Unlike /etc/hosts (restorable by stripping OCT's markers),
                # this backup is the only way back for NTP — abort before
                # overwriting the original rather than patch unrecoverably.
                raise RuntimeError(
                    f"Cannot back up {self.NTP_PATH}: {backup_result.error}"
                )

    async def _write_ntp_servers(self, content: str) -> None:
        """Write NTP servers file content atomically via base64 piping."""
        b64 = base64.b64encode(content.encode()).decode()
        write_cmd = (
            f"echo '{b64}' | base64 -d > /tmp/ntpservers.new && "
            f"mv /tmp/ntpservers.new {self.NTP_PATH}"
        )
        write_result = await self.ssh.execute(write_cmd)
        if not write_result.success:
            raise RuntimeError(
                f"Failed to write NTP servers file: "
                f"{write_result.error or write_result.output}"
            )
