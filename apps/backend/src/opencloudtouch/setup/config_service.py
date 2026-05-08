"""
Configuration service for SoundTouch devices.

Handles modification and restoration of OverrideSdkPrivateCfg.xml.

The config file controls which cloud servers the device contacts:
- bmxRegistryUrl: BMX service registry (stream resolution for presets)
- margeServerUrl: Account/preset sync
- swUpdateUrl: Firmware updates

Critical: bmxRegistryUrl must be HTTP (not HTTPS) because SoundTouch
devices cannot validate custom HTTPS certificates.
"""

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)

# XML tags that contain URLs to modify
_BMX_TAG = "bmxRegistryUrl"
_MARGE_TAG = "margeServerUrl"
_SWUPDATE_TAG = "swUpdateUrl"


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


@dataclass
class ConfigDiff:
    """Tracks old → new values for each modified tag."""

    changes: list[tuple[str, str, str]] = field(default_factory=list)

    def add(self, tag: str, old: str, new: str) -> None:
        self.changes.append((tag, old, new))

    def __str__(self) -> str:
        lines = []
        for tag, old, new in self.changes:
            lines.append(f"<{tag}>")
            lines.append(f"  - {old}")
            lines.append(f"  + {new}")
        return "\n".join(lines)


class SoundTouchConfigService:
    """Service for modifying SoundTouch device configuration."""

    # All known config file locations on Bose devices.
    # The FIRST found path becomes the primary (read source + write target).
    # ALL other paths that exist are kept in sync after modification.
    # We never know which file firmware actually reads on a given model,
    # so we modify ALL of them to be safe.
    # Note: OverrideSdkPrivateCfg.xml is ignored by firmware on ST10/ST300
    # (gesellix/Bose-SoundTouch#220, scheilch/opencloudtouch#139) but we
    # still sync it if present — never delete files on a foreign OS.
    CONFIG_CANDIDATES = [
        "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml",
        "/mnt/nv/OverrideSdkPrivateCfg.xml",
        "/mnt/nv/SoundTouchSdkPrivateCfg.xml",
    ]
    BACKUP_DIR = "/mnt/nv"

    def __init__(self, ssh: SoundTouchSSHClient):
        self.ssh = ssh
        self.config_path: str | None = None  # resolved by _detect_config_path
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def _detect_config_path(self) -> str:
        """Probe known config locations and return the first existing one.

        Raises RuntimeError if no config file is found on the device.
        """
        if self.config_path:
            return self.config_path

        for candidate in self.CONFIG_CANDIDATES:
            result = await self.ssh.execute(
                f"test -f {candidate} && echo 'found' || echo 'missing'"
            )
            if "found" in (result.output or ""):
                self.logger.info(f"Config file detected at {candidate}")
                self.config_path = candidate
                return candidate

        raise RuntimeError(
            f"Config file not found. Probed: {', '.join(self.CONFIG_CANDIDATES)}"
        )

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

    @staticmethod
    def _replace_tag_value(
        xml: str, tag: str, new_value: str
    ) -> tuple[str, Optional[str]]:
        """Replace the text content of an XML tag.

        Returns (modified_xml, old_value) or (original_xml, None) if tag
        was not found.
        """
        pattern = re.compile(
            rf"(<{re.escape(tag)}>)(.*?)(</{re.escape(tag)}>)", re.DOTALL
        )
        match = pattern.search(xml)
        if not match:
            return xml, None
        old_value = match.group(2)
        new_xml = pattern.sub(rf"\g<1>{new_value}\g<3>", xml, count=1)
        return new_xml, old_value

    @staticmethod
    def build_bmx_url(oct_host: str, port: int = 7777) -> str:
        """Build the BMX registry URL pointing to OCT.

        Always uses HTTP because SoundTouch cannot validate custom HTTPS certs.
        The domain remains content.api.bose.io (resolved via /etc/hosts).
        """
        return f"http://content.api.bose.io:{port}/bmx/registry/v1/services"

    @staticmethod
    def build_marge_url(oct_host: str, port: int = 7777) -> str:
        """Build the marge server URL pointing to OCT."""
        return f"http://content.api.bose.io:{port}"

    @staticmethod
    def build_swupdate_url(oct_host: str, port: int = 7777) -> str:
        """Build the swupdate URL pointing to OCT."""
        return f"http://content.api.bose.io:{port}/updates/soundtouch"

    async def _read_config(self) -> str:
        """Read current config file from device."""
        path = await self._detect_config_path()
        result = await self.ssh.execute(f"cat {path}")
        if not result.success:
            raise RuntimeError(
                f"Cannot read config file: {result.error or result.output}"
            )
        return result.output or ""

    async def _write_config(self, content: str) -> None:
        """Write config file atomically via base64 piping.

        Writes directly to the canonical path (/opt/Bose/etc/).
        Caller MUST have remounted rw before calling this.
        """
        path = await self._detect_config_path()

        b64 = base64.b64encode(content.encode()).decode()
        write_cmd = (
            f"echo '{b64}' | base64 -d > /tmp/config.new && "
            f"mv /tmp/config.new {path}"
        )
        result = await self.ssh.execute(write_cmd)
        if not result.success:
            raise RuntimeError(
                f"Failed to write config: {result.error or result.output}"
            )

    async def _verify_config(self) -> str:
        """Read back config and verify it's valid XML (has closing tag)."""
        content = await self._read_config()
        if "</SoundTouchSdkPrivateCfg>" not in content:
            raise RuntimeError("Config verification failed: missing closing XML tag")
        return content

    async def _ensure_backup(self, backup_path: str) -> None:
        """Create a backup only if none exists yet at this path."""
        path = await self._detect_config_path()
        check = await self.ssh.execute(
            f"test -f {backup_path} && echo 'exists' || echo 'missing'"
        )
        if "missing" in (check.output or ""):
            result = await self.ssh.execute(f"cp {path} {backup_path}")
            if not result.success:
                self.logger.warning(f"Backup may have failed: {result.error}")

    async def _sync_all_config_files(self, content: str) -> None:
        """Sync modified content to ALL existing config files (except the primary).

        We don't fully understand which file firmware reads on each model.
        Rather than guess, we write the modified content to every config file
        that exists on the device. NEVER create or delete files.

        Best-effort: failure here must not abort the main modify flow.
        """
        primary = await self._detect_config_path()
        for candidate in self.CONFIG_CANDIDATES:
            if candidate == primary:
                continue
            try:
                check = await self.ssh.execute(
                    f"test -f {candidate} && echo 'found' || echo 'missing'"
                )
                if "found" not in (check.output or ""):
                    continue

                self.logger.info(f"Syncing config: {candidate}")
                b64 = base64.b64encode(content.encode()).decode()
                write_cmd = (
                    f"echo '{b64}' | base64 -d > /tmp/cfg_sync.new && "
                    f"mv /tmp/cfg_sync.new {candidate}"
                )
                result = await self.ssh.execute(write_cmd)
                if not result.success:
                    self.logger.warning(
                        f"Sync failed for {candidate} (best-effort): {result.error}"
                    )
            except Exception as e:
                self.logger.warning(f"Sync error for {candidate} (best-effort): {e}")

    async def modify_bmx_url(self, oct_ip: str) -> ModifyResult:
        """Modify BMX URL (and optionally marge/swupdate) in config.

        Protocol: remount rw → backup → read → modify → write → verify → remount ro.

        Args:
            oct_ip: OCT server hostname or IP (used for URL building)

        Returns:
            ModifyResult with backup path and diff
        """
        self.logger.info(f"Modifying BMX URL to point to OCT at {oct_ip}")

        try:
            await self._remount_rw()
            try:
                # 1. Read current config
                original = await self._read_config()

                # 2. Backup (idempotent — only first time)
                config_filename = (await self._detect_config_path()).rsplit("/", 1)[-1]
                backup_path = f"{self.BACKUP_DIR}/{config_filename}.oct-backup"
                await self._ensure_backup(backup_path)

                # 3. Modify XML tags
                diff = ConfigDiff()
                modified = original

                new_bmx = self.build_bmx_url(oct_ip)
                modified, old = self._replace_tag_value(modified, _BMX_TAG, new_bmx)
                if old is not None:
                    diff.add(_BMX_TAG, old, new_bmx)

                new_marge = self.build_marge_url(oct_ip)
                modified, old = self._replace_tag_value(modified, _MARGE_TAG, new_marge)
                if old is not None:
                    diff.add(_MARGE_TAG, old, new_marge)

                new_sw = self.build_swupdate_url(oct_ip)
                modified, old = self._replace_tag_value(modified, _SWUPDATE_TAG, new_sw)
                if old is not None:
                    diff.add(_SWUPDATE_TAG, old, new_sw)

                if not diff.changes:
                    self.logger.info("No URL tags found in config — nothing to modify")
                    return ModifyResult(
                        success=True,
                        backup_path=backup_path,
                        diff="(no changes — tags not found in config)",
                    )

                # 4. Write atomically
                await self._write_config(modified)

                # 5. Verify write
                await self._verify_config()

                # 5b. Sync ALL other config files that exist (best-effort)
                await self._sync_all_config_files(modified)

                self.logger.info(
                    f"Config modified successfully ({len(diff.changes)} tags)"
                )
                return ModifyResult(
                    success=True,
                    backup_path=backup_path,
                    diff=str(diff),
                )
            finally:
                await self._remount_ro()

        except Exception as e:
            self.logger.error(f"Config modification failed: {e}")
            return ModifyResult(success=False, error=str(e))

    async def restore_config(self, backup_path: str) -> RestoreResult:
        """Restore config from backup.

        Protocol: verify backup exists → remount rw → copy → verify → remount ro.

        Args:
            backup_path: Path to backup file on device

        Returns:
            RestoreResult
        """
        self.logger.info(f"Restoring config from {backup_path}")

        try:
            # Verify backup exists
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
                config_path = await self._detect_config_path()
                result = await self.ssh.execute(f"cp {backup_path} {config_path}")
                if not result.success:
                    return RestoreResult(
                        success=False,
                        error=f"Copy failed: {result.error or result.output}",
                    )

                # Verify restored file is valid
                await self._verify_config()

                self.logger.info("Config restored successfully")
                return RestoreResult(success=True)
            finally:
                await self._remount_ro()

        except Exception as e:
            self.logger.error(f"Config restore failed: {e}")
            return RestoreResult(success=False, error=str(e))

    async def list_backups(self) -> list[str]:
        """List available config backups on the device.

        Returns:
            List of backup file paths, sorted newest first
        """
        self.logger.info("Listing config backups")

        try:
            result = await self.ssh.execute(
                f"ls -1t {self.BACKUP_DIR}/*SdkPrivateCfg.xml.* 2>/dev/null"
            )
            if not result.success or not result.output:
                return []

            paths = [
                line.strip()
                for line in result.output.strip().splitlines()
                if line.strip()
            ]
            return paths

        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")
            return []
