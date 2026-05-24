"""Persistence initialization service for SoundTouch devices.

Factory-reset devices lack the BoseApp-Persistence files that the
firmware requires for proper preset playback and source initialization.
Without these files the device never fully initialises its playback
state, causing INVALID_SOURCE on preset recall (GitHub Issue #167).

This service creates the minimal persistence files needed:
- SystemConfigurationDB.xml  (account UUID, device name, acctMode)
- Sources.xml                (available music sources)

Discovery credit: @Zimbo88 (GitHub Issue #167 comment, 2026-05-12).
"""

import base64
import logging
from dataclasses import dataclass
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from opencloudtouch.core.source_types import BASE_SOURCES
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)

_PERSISTENCE_DIR = "/mnt/nv/BoseApp-Persistence/1"


@dataclass
class PersistenceInitResult:
    """Result of persistence initialization."""

    success: bool
    created_files: list[str]
    skipped_files: list[str]
    message: str = ""
    error: Optional[str] = None


def build_system_config_xml(
    device_name: str,
    account_uuid: str,
) -> str:
    """Build minimal SystemConfigurationDB.xml.

    Args:
        device_name: Human-readable device name (from /info)
        account_uuid: margeAccountUUID (7-digit, from account pairing)
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" ?>\n'
        "<SystemConfiguration>\n"
        "    <Password />\n"
        f"    <DeviceName>{xml_escape(device_name)}</DeviceName>\n"
        "    <AccountAssociatedEMail />\n"
        f"    <AccountUUID>{xml_escape(account_uuid)}</AccountUUID>\n"
        "    <Locale />\n"
        "    <acctMode>local</acctMode>\n"
        "    <isMultiDeviceAccount>true</isMultiDeviceAccount>\n"
        "    <margeAuthServerToken />\n"
        '    <powerSavingSettings powersaving_en="true" />\n'
        "</SystemConfiguration>\n"
    )


def build_sources_xml() -> str:
    """Build Sources.xml content for Bose SoundTouch devices.

    Uses the centrally defined BASE_SOURCES from core.source_types.
    BLUETOOTH is deliberately excluded there.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8" ?>', "<sources>"]
    for src in BASE_SOURCES:
        lines.append(
            f'    <source displayName="{src.display_name}" secret="" secretType="{src.secret_type}">'
        )
        lines.append(f'        <sourceKey type="{src.source_type}" account="{src.account}" />')
        lines.append("    </source>")
    lines.append("</sources>")
    return "\n".join(lines) + "\n"


# Source types that firmware requires for preset playback.
# Subset of BASE_SOURCES — these are checked during setup verification.
REQUIRED_SOURCE_TYPES = {src.source_type for src in BASE_SOURCES}


@dataclass
class ForceWriteResult:
    """Result of a force-write operation."""

    success: bool
    backup_path: str = ""
    written_path: str = ""
    had_existing: bool = False
    message: str = ""
    error: Optional[str] = None


async def force_write_sources_xml(
    ssh: SoundTouchSSHClient,
    backup: bool = True,
) -> ForceWriteResult:
    """Force-write Sources.xml with firmware-safe content.

    Unlike ensure_persistence_files() which skips existing files, this
    function ALWAYS overwrites -- needed when existing Sources.xml is
    incomplete (e.g. only has AUX, missing TUNEIN).

    Args:
        ssh: Connected SSH client (filesystem must be mounted rw)
        backup: If True, back up existing file to Sources.xml.bak

    Returns:
        ForceWriteResult with backup path and written path
    """
    path = f"{_PERSISTENCE_DIR}/Sources.xml"
    backup_path = f"{path}.bak"
    had_existing = False

    try:
        await ssh.execute(f"mkdir -p {_PERSISTENCE_DIR}")
        had_existing = await _file_exists(ssh, path)

        if had_existing and backup:
            result = await ssh.execute(f"cp {path} {backup_path}")
            if not result.success:
                logger.warning("Failed to backup Sources.xml: %s", result.error)

        content = build_sources_xml()
        exit_code = await _write_file_atomic(ssh, path, content)
        logger.info(
            "Force-wrote Sources.xml (backup=%s, had_existing=%s, exit_code=%d)",
            backup,
            had_existing,
            exit_code,
        )

        if exit_code != 0:
            return ForceWriteResult(
                success=False,
                had_existing=had_existing,
                error=f"Write returned non-zero exit code: {exit_code}",
            )

        return ForceWriteResult(
            success=True,
            backup_path=backup_path if had_existing and backup else "",
            written_path=path,
            had_existing=had_existing,
            message=(
                f"Sources.xml written to {path}"
                + (f" (backup: {backup_path})" if had_existing else "")
            ),
        )
    except Exception as e:
        logger.exception("Failed to force-write Sources.xml")
        return ForceWriteResult(
            success=False,
            had_existing=had_existing,
            error=str(e),
        )


async def _file_exists(ssh: SoundTouchSSHClient, path: str) -> bool:
    """Check if a file exists on the device."""
    result = await ssh.execute(f"test -f {path} && echo 'exists' || echo 'missing'")
    return "exists" in (result.output or "")


async def _read_file_content(ssh: SoundTouchSSHClient, path: str) -> Optional[str]:
    """Read file content from device, return None if not readable."""
    result = await ssh.execute(f"cat {path} 2>/dev/null")
    if not result.success or not result.output:
        return None
    return result.output.strip()


def parse_system_config_xml(xml_content: str) -> dict[str, str]:
    """Extract DeviceName and AccountUUID from existing SystemConfigurationDB.xml.

    Returns:
        Dict with 'device_name' and 'account_uuid' (empty string if missing).
    """
    from defusedxml import ElementTree as ET

    extracted: dict[str, str] = {"device_name": "", "account_uuid": ""}
    try:
        root = ET.fromstring(xml_content)
        name_elem = root.find("DeviceName")
        if name_elem is not None and name_elem.text:
            extracted["device_name"] = name_elem.text.strip()
        uuid_elem = root.find("AccountUUID")
        if uuid_elem is not None and uuid_elem.text:
            extracted["account_uuid"] = uuid_elem.text.strip()
    except Exception:
        logger.warning("Failed to parse existing SystemConfigurationDB.xml")
    return extracted


async def _write_file_atomic(ssh: SoundTouchSSHClient, path: str, content: str) -> int:
    """Write content to device atomically via base64 piping.

    Returns:
        Exit code of the write command (0 = success).

    Raises:
        RuntimeError: If the write command fails.
    """
    b64 = base64.b64encode(content.encode()).decode()
    write_cmd = (
        f"echo '{b64}' | base64 -d > /tmp/persist.new && mv /tmp/persist.new {path}"
    )
    result = await ssh.execute(write_cmd)
    if not result.success:
        raise RuntimeError(f"Failed to write {path}: {result.error or result.output}")
    return result.exit_code


async def ensure_persistence_files(
    ssh: SoundTouchSSHClient,
    device_name: str,
    account_uuid: str,
) -> PersistenceInitResult:
    """Ensure minimal persistence files exist on the device.

    Only creates files that are missing — never overwrites existing ones.
    This preserves user data on devices that already have valid state.

    Must be called AFTER:
    - Config modification (SDK URLs rewritten)
    - Hosts modification (domains redirected)
    - Account pairing (margeAccountUUID set)
    - Filesystem remounted rw

    Args:
        ssh: Connected SSH client
        device_name: Device name (from GET :8090/info <name>)
        account_uuid: margeAccountUUID (from account pairing)

    Returns:
        PersistenceInitResult
    """
    created: list[str] = []
    skipped: list[str] = []

    files_to_ensure = [
        (
            "SystemConfigurationDB.xml",
            lambda: build_system_config_xml(device_name, account_uuid),
        ),
        ("Sources.xml", lambda: build_sources_xml()),  # Default: include all sources
    ]

    try:
        # Ensure directory exists
        await ssh.execute(f"mkdir -p {_PERSISTENCE_DIR}")

        for filename, content_fn in files_to_ensure:
            path = f"{_PERSISTENCE_DIR}/{filename}"
            if await _file_exists(ssh, path):
                logger.info("%s already exists — skipping", filename)
                skipped.append(path)
            else:
                logger.info("Creating %s", filename)
                await _write_file_atomic(ssh, path, content_fn())
                created.append(path)

        msg_parts = []
        if created:
            msg_parts.append(f"Created: {', '.join(created)}")
        if skipped:
            msg_parts.append(f"Skipped (already exist): {', '.join(skipped)}")

        return PersistenceInitResult(
            success=True,
            created_files=created,
            skipped_files=skipped,
            message=" | ".join(msg_parts) or "No action needed",
        )

    except Exception as e:
        logger.exception("Persistence initialization failed")
        return PersistenceInitResult(
            success=False,
            created_files=created,
            skipped_files=skipped,
            error=str(e),
        )
