"""
Configuration service for SoundTouch devices.

Handles modification and restoration of OverrideSdkPrivateCfg.xml.

The config file controls which cloud servers the device contacts:
- bmxRegistryUrl: BMX service registry (stream resolution for presets)
- margeServerUrl: Account/preset sync
- swUpdateUrl: Firmware updates
- statsServerUrl: Telemetry/analytics

Critical: ALL URLs must be HTTP (not HTTPS) because SoundTouch
devices cannot validate custom HTTPS certificates. An unrewritten
statsServerUrl (https://events.api.bosecm.com) causes the device to
hang on a TLS handshake to the OCT IP, delaying boot and potentially
blocking the BMX registry load. See GitHub Issue #167.
"""

import base64
import ipaddress
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from opencloudtouch.core.config import DEFAULT_PORT
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)

# XML tags that contain URLs to modify
_BMX_TAG = "bmxRegistryUrl"
_MARGE_TAG = "margeServerUrl"
_SWUPDATE_TAG = "swUpdateUrl"
_STATS_TAG = "statsServerUrl"

# Canonical config paths on SoundTouch devices
OVERRIDE_PATH = "/mnt/nv/OverrideSdkPrivateCfg.xml"
BASE_CONFIG_PATH = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"

# Hostname validation: alphanumeric, hyphens, dots; must start/end with alnum
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$")
# Characters unsafe for XML text content
_XML_UNSAFE_RE = re.compile(r'[<>&"\'\x00-\x1f]')


def _validate_oct_ip(value: str) -> str:
    """Validate oct_ip is a valid IP address or hostname. Returns stripped value."""
    if not value or not value.strip():
        raise ValueError("oct_ip must not be empty")

    value = value.strip()

    # Try IPv4/IPv6 first
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass

    # Hostname validation
    if len(value) > 253:
        raise ValueError(f"Hostname too long: {len(value)} chars (max 253)")

    if _XML_UNSAFE_RE.search(value):
        raise ValueError(f"Invalid characters in hostname: {value}")

    if not _HOSTNAME_RE.match(value):
        raise ValueError(f"Invalid hostname format: {value}")

    return value


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
    """Service for modifying SoundTouch device configuration.

    Always writes to OVERRIDE_PATH (/mnt/nv/OverrideSdkPrivateCfg.xml).
    The /mnt/nv/ partition is persistent and always writable.
    If the override doesn't exist, it is created by copying from
    BASE_CONFIG_PATH (/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml).
    """

    # Config files on /mnt/nv/ that are synced after modification.
    # OVERRIDE_PATH is the primary write target (always).
    # Other /mnt/nv/ variants are synced if they exist on the device.
    CONFIG_CANDIDATES = [
        OVERRIDE_PATH,
        "/mnt/nv/SoundTouchSdkPrivateCfg.xml",
    ]
    BACKUP_DIR = "/mnt/nv"

    def __init__(self, ssh: SoundTouchSSHClient):
        self.ssh = ssh
        self.config_path: str | None = None  # resolved by _ensure_override_config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def _ensure_override_config(self) -> str:
        """Ensure override config exists at OVERRIDE_PATH and return it.

        If the override doesn't exist but the base config does, copy it.
        Always returns OVERRIDE_PATH as the write target.
        The /mnt/nv/ partition is always writable — no remount needed.

        Raises RuntimeError if no config source is available.
        """
        if self.config_path:
            self.logger.debug("Config path already resolved: %s", self.config_path)
            return self.config_path

        # Check if override already exists
        result = await self.ssh.execute(
            f"test -f {OVERRIDE_PATH} && echo 'found' || echo 'missing'"
        )
        if "found" in (result.output or ""):
            self.config_path = OVERRIDE_PATH
            self.logger.info("Override config exists at %s", OVERRIDE_PATH)
            return OVERRIDE_PATH

        # Override missing — try to copy from base config
        self.logger.info(
            "Override missing, checking base config at %s", BASE_CONFIG_PATH
        )
        result = await self.ssh.execute(
            f"test -f {BASE_CONFIG_PATH} && echo 'found' || echo 'missing'"
        )
        if "found" in (result.output or ""):
            cp_result = await self.ssh.execute(f"cp {BASE_CONFIG_PATH} {OVERRIDE_PATH}")
            if not cp_result.success:
                raise RuntimeError(
                    f"Failed to copy base config to override: "
                    f"{cp_result.error or cp_result.output}"
                )
            self.config_path = OVERRIDE_PATH
            self.logger.info(
                "Copied base config %s → %s", BASE_CONFIG_PATH, OVERRIDE_PATH
            )
            return OVERRIDE_PATH

        raise RuntimeError(
            f"No config source found. Checked: {OVERRIDE_PATH}, {BASE_CONFIG_PATH}"
        )

    async def _remount_rw(self) -> None:
        """Remount root filesystem read-write before writing."""
        result = await self.ssh.execute("mount -o remount,rw /")
        if result.exit_code != 0:
            self.logger.warning(
                "remount rw returned exit_code=%d: %s",
                result.exit_code,
                result.stderr,
            )

    async def _remount_ro(self) -> None:
        """Remount root filesystem read-only after writing."""
        result = await self.ssh.execute("mount -o remount,ro /")
        if result.exit_code != 0:
            self.logger.warning(
                "remount ro returned exit_code=%d: %s",
                result.exit_code,
                result.stderr,
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
        logger.debug("<%s> %s → %s", tag, old_value[:120], new_value[:120])
        return new_xml, old_value

    @staticmethod
    def build_bmx_url(oct_host: str, port: int = DEFAULT_PORT) -> str:
        """Build the BMX registry URL pointing to OCT.

        Always uses HTTP because SoundTouch cannot validate custom HTTPS certs.
        Uses the user-specified hostname or IP directly so the device config
        matches what the user entered in the wizard.
        """
        return f"http://{oct_host}:{port}/bmx/registry/v1/services"  # noqa: S324

    @staticmethod
    def build_marge_url(oct_host: str, port: int = DEFAULT_PORT) -> str:
        """Build the marge server URL pointing to OCT."""
        return f"http://{oct_host}:{port}"  # noqa: S324

    @staticmethod
    def build_swupdate_url(oct_host: str, port: int = DEFAULT_PORT) -> str:
        """Build the swupdate URL pointing to OCT."""
        return f"http://{oct_host}:{port}/updates/soundtouch"  # noqa: S324

    @staticmethod
    def build_stats_url(oct_host: str, port: int = DEFAULT_PORT) -> str:
        """Build the stats/telemetry URL pointing to OCT.

        Without this, the device retains https://events.api.bosecm.com
        and hangs on TLS handshake to OCT IP (Issue #167).
        """
        return f"http://{oct_host}:{port}"  # noqa: S324

    async def _read_config(self) -> str:
        """Read current config file from device."""
        path = await self._ensure_override_config()
        self.logger.debug("Reading config from %s", path)
        result = await self.ssh.execute(f"cat {path}")
        if not result.success:
            raise RuntimeError(
                f"Cannot read config file: {result.error or result.output}"
            )
        content = result.output or ""
        self.logger.debug("Config read: %d bytes", len(content))
        return content

    async def _write_config(self, content: str) -> None:
        """Write config file atomically via base64 piping.

        Always writes to OVERRIDE_PATH (/mnt/nv/ is always writable).
        """
        path = await self._ensure_override_config()

        b64 = base64.b64encode(content.encode()).decode()
        self.logger.debug(
            "Writing config to %s (%d bytes, base64 %d chars)",
            path,
            len(content),
            len(b64),
        )
        write_cmd = (
            f"echo '{b64}' | base64 -d > /tmp/config.new && "
            f"mv /tmp/config.new {path}"
        )
        result = await self.ssh.execute(write_cmd)
        if not result.success:
            raise RuntimeError(
                f"Failed to write config: {result.error or result.output}"
            )
        self.logger.debug("Config written successfully to %s", path)

    async def _verify_config(self) -> str:
        """Read back config and verify it's valid XML (has closing tag)."""
        content = await self._read_config()
        if "</SoundTouchSdkPrivateCfg>" not in content:
            raise RuntimeError("Config verification failed: missing closing XML tag")
        return content

    async def _ensure_backup(self, backup_path: str) -> None:
        """Create a backup only if none exists yet at this path."""
        path = await self._ensure_override_config()
        check = await self.ssh.execute(
            f"test -f {backup_path} && echo 'exists' || echo 'missing'"
        )
        if "missing" in (check.output or ""):
            result = await self.ssh.execute(f"cp {path} {backup_path}")
            if not result.success:
                self.logger.warning("Backup may have failed: %s", result.error)

    async def _sync_all_config_files(self, content: str) -> None:
        """Sync modified content to other /mnt/nv/ config file variants.

        Writes to /mnt/nv/SoundTouchSdkPrivateCfg.xml if it exists.
        Never writes to /opt/Bose/etc/ — only /mnt/nv/ is used.

        Best-effort: failure here must not abort the main modify flow.
        """
        primary = await self._ensure_override_config()
        non_primary = [c for c in self.CONFIG_CANDIDATES if c != primary]
        if not non_primary:
            return

        self.logger.debug(
            "Syncing config from primary %s to %d candidates",
            primary,
            len(non_primary),
        )

        # Batch existence check: single SSH call for all candidates
        check_parts = [
            f'test -f {c} && echo "{c}:found" || echo "{c}:missing"'
            for c in non_primary
        ]
        check_result = await self.ssh.execute("; ".join(check_parts))
        check_output = check_result.output or ""

        existing = {c for c in non_primary if f"{c}:found" in check_output}

        for candidate in non_primary:
            if candidate not in existing:
                self.logger.debug("Skipping %s (does not exist)", candidate)
                continue
            try:
                self.logger.info("Syncing config: %s", candidate)
                b64 = base64.b64encode(content.encode()).decode()
                write_cmd = (
                    f"echo '{b64}' | base64 -d > /tmp/cfg_sync.new && "
                    f"mv /tmp/cfg_sync.new {candidate}"
                )
                result = await self.ssh.execute(write_cmd)
                if not result.success:
                    self.logger.warning(
                        "Sync failed for %s (best-effort): %s",
                        candidate,
                        result.error,
                    )
                else:
                    self.logger.debug("Sync OK: %s", candidate)
            except Exception as e:
                self.logger.warning("Sync error for %s (best-effort): %s", candidate, e)

    async def modify_bmx_url(
        self, oct_ip: str, port: int = DEFAULT_PORT
    ) -> ModifyResult:
        """Modify BMX URL (and optionally marge/swupdate) in config.

        Protocol: ensure override exists → backup → read → modify → write → verify.
        /mnt/nv/ is always writable — no remount needed.

        Args:
            oct_ip: OCT server hostname or IP (used for URL building)

        Returns:
            ModifyResult with backup path and diff
        """
        self.logger.info("Modifying BMX URL to point to OCT at %s", oct_ip)

        oct_ip = _validate_oct_ip(oct_ip)

        try:
            # 1. Read current config (ensures override exists)
            original = await self._read_config()

            # 2. Backup (idempotent — only first time)
            config_filename = (await self._ensure_override_config()).rsplit("/", 1)[-1]
            backup_path = f"{self.BACKUP_DIR}/{config_filename}.oct-backup"
            await self._ensure_backup(backup_path)

            # 3. Modify XML tags
            diff = ConfigDiff()
            modified = original

            new_bmx = self.build_bmx_url(oct_ip, port=port)
            modified, old = self._replace_tag_value(modified, _BMX_TAG, new_bmx)
            if old is not None:
                diff.add(_BMX_TAG, old, new_bmx)

            new_marge = self.build_marge_url(oct_ip, port=port)
            modified, old = self._replace_tag_value(modified, _MARGE_TAG, new_marge)
            if old is not None:
                diff.add(_MARGE_TAG, old, new_marge)

            new_sw = self.build_swupdate_url(oct_ip, port=port)
            modified, old = self._replace_tag_value(modified, _SWUPDATE_TAG, new_sw)
            if old is not None:
                diff.add(_SWUPDATE_TAG, old, new_sw)

            new_stats = self.build_stats_url(oct_ip, port=port)
            modified, old = self._replace_tag_value(modified, _STATS_TAG, new_stats)
            if old is not None:
                diff.add(_STATS_TAG, old, new_stats)

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

            # 5b. Sync other /mnt/nv/ config files (best-effort)
            await self._sync_all_config_files(modified)

            self.logger.info(
                "Config modified successfully (%d tags)", len(diff.changes)
            )
            return ModifyResult(
                success=True,
                backup_path=backup_path,
                diff=str(diff),
            )

        except Exception as e:
            self.logger.error("Config modification failed: %s", e)
            return ModifyResult(success=False, error=str(e))

    async def restore_config(self, backup_path: str) -> RestoreResult:
        """Restore config from backup.

        Protocol: verify backup exists → copy to override path → verify.
        /mnt/nv/ is always writable — no remount needed.

        Args:
            backup_path: Path to backup file on device

        Returns:
            RestoreResult
        """
        self.logger.info("Restoring config from %s", backup_path)

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

            config_path = await self._ensure_override_config()
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

        except Exception as e:
            self.logger.error("Config restore failed: %s", e)
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
            self.logger.error("Failed to list backups: %s", e)
            return []
