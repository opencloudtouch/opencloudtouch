"""Account pairing service for SoundTouch devices.

Ensures the device has a margeAccountUUID. Without it, the device
cannot sync presets with the Marge server and preset playback fails
with INVALID_SOURCE (GitHub Issue #167).

The UUID is checked via the device's HTTP API (GET :8090/info).
If missing, it is written directly to the persistence file via SSH:
    /mnt/nv/BoseApp-Persistence/1/SystemConfigurationDB.xml
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional

import httpx
from defusedxml import ElementTree as ET

from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT as _DEFAULT_DEVICE_HTTP_PORT
from opencloudtouch.setup.persistence_service import (
    _PERSISTENCE_DIR,
    _file_exists,
    _write_file_atomic,
    build_system_config_xml,
)
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)

_INFO_TIMEOUT = 5.0
_SYS_CONFIG_PATH = f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml"


@dataclass
class AccountPairingResult:
    """Result of an account pairing attempt."""

    success: bool
    had_uuid: bool
    uuid: str = ""
    message: str = ""
    error: Optional[str] = None


def _generate_account_uuid() -> str:
    """Generate a 7-digit account UUID (matching Bose format)."""
    return str(random.randint(1_000_000, 9_999_999))  # noqa: S311


async def check_marge_account_uuid(
    device_ip: str, device_port: int = _DEFAULT_DEVICE_HTTP_PORT
) -> Optional[str]:
    """Check if device has a margeAccountUUID via GET /info.

    Args:
        device_ip: Device IP address
        device_port: Device HTTP API port (default 8090)

    Returns:
        The UUID string if present and non-empty, None otherwise
    """
    url = f"http://{device_ip}:{device_port}/info"  # NOSONAR — Bose devices only support HTTP
    try:
        async with httpx.AsyncClient(timeout=_INFO_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning("Cannot read /info from %s: %s", device_ip, e)
        return None

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        logger.warning("Invalid XML from %s/info", device_ip)
        return None

    elem = root.find("margeAccountUUID")
    if elem is None or not elem.text or not elem.text.strip():
        return None

    return elem.text.strip()


def _update_uuid_in_xml(xml_content: str, uuid: str) -> str:
    """Update AccountUUID, acctMode, isMultiDeviceAccount in existing XML."""
    from xml.etree.ElementTree import SubElement, tostring  # noqa: S405

    root = ET.fromstring(xml_content)

    uuid_elem = root.find("AccountUUID")
    if uuid_elem is None:
        uuid_elem = SubElement(root, "AccountUUID")
    uuid_elem.text = uuid

    acct_elem = root.find("acctMode")
    if acct_elem is None:
        acct_elem = SubElement(root, "acctMode")
    acct_elem.text = "global"

    multi_elem = root.find("isMultiDeviceAccount")
    if multi_elem is None:
        multi_elem = SubElement(root, "isMultiDeviceAccount")
    multi_elem.text = "true"

    return '<?xml version="1.0" encoding="UTF-8" ?>\n' + tostring(
        root, encoding="unicode"
    )


async def set_account_uuid_via_ssh(
    ssh: SoundTouchSSHClient,
    uuid: str,
    device_name: str = "SoundTouch",
) -> AccountPairingResult:
    """Set margeAccountUUID on device via SSH by writing SystemConfigurationDB.xml.

    Reads existing file (if present) and updates UUID in-place,
    or creates from template if missing. Also sets acctMode=global
    and isMultiDeviceAccount=true. Verifies write by reading back.

    /mnt/nv is always writable — no remount needed.

    Args:
        ssh: Connected SoundTouchSSHClient
        uuid: 7-digit account UUID to set
        device_name: Device name for template (used when creating new file)

    Returns:
        AccountPairingResult with success status
    """
    try:
        await ssh.execute(f"mkdir -p {_PERSISTENCE_DIR}")

        if await _file_exists(ssh, _SYS_CONFIG_PATH):
            read_result = await ssh.execute(f"cat {_SYS_CONFIG_PATH}")
            if read_result.success and read_result.output:
                xml_content = _update_uuid_in_xml(read_result.output.strip(), uuid)
            else:
                xml_content = build_system_config_xml(device_name, uuid)
        else:
            xml_content = build_system_config_xml(device_name, uuid)

        await _write_file_atomic(ssh, _SYS_CONFIG_PATH, xml_content)

        # Verify write
        verify = await ssh.execute(f"cat {_SYS_CONFIG_PATH}")
        if not verify.success or uuid not in (verify.output or ""):
            return AccountPairingResult(
                success=False,
                had_uuid=False,
                error=f"Verification failed: UUID {uuid} not found after write",
            )

        logger.info("Set margeAccountUUID=%s via SSH", uuid)
        return AccountPairingResult(
            success=True,
            had_uuid=False,
            uuid=uuid,
            message=f"Account UUID {uuid} set via SSH",
        )
    except Exception as e:
        logger.exception("Failed to set account UUID via SSH")
        return AccountPairingResult(
            success=False,
            had_uuid=False,
            error=f"SSH write failed: {e}",
        )


async def ensure_account_uuid(
    device_ip: str,
    device_port: int = _DEFAULT_DEVICE_HTTP_PORT,
    ssh: Optional[SoundTouchSSHClient] = None,
    device_name: str = "SoundTouch",
) -> AccountPairingResult:
    """Ensure device has a margeAccountUUID — set one if missing.

    1. GET /info → check <margeAccountUUID>
    2. If present → return success (no-op)
    3. If missing → generate UUID → write via SSH

    Args:
        device_ip: Device IP address
        device_port: Device HTTP API port
        ssh: Optional pre-connected SSH client (creates one if not provided)
        device_name: Device name for XML template

    Returns:
        AccountPairingResult
    """
    existing = await check_marge_account_uuid(device_ip, device_port)

    if existing:
        logger.info("Device %s already has margeAccountUUID=%s", device_ip, existing)
        return AccountPairingResult(
            success=True,
            had_uuid=True,
            uuid=existing,
            message=f"Device already has account UUID: {existing}",
        )

    uuid = _generate_account_uuid()
    logger.info(
        "Device %s has no margeAccountUUID — setting %s via SSH",
        device_ip,
        uuid,
    )

    if ssh:
        return await set_account_uuid_via_ssh(ssh, uuid, device_name)

    async with SoundTouchSSHClient(device_ip) as ssh_client:
        return await set_account_uuid_via_ssh(ssh_client, uuid, device_name)


async def ensure_account_uuid_unique(
    device_ip: str,
    device_id: str,
    device_repo,
    device_port: int = _DEFAULT_DEVICE_HTTP_PORT,
    ssh: Optional[SoundTouchSSHClient] = None,
    device_name: str = "SoundTouch",
    max_retries: int = 5,
) -> AccountPairingResult:
    """Ensure device has a unique margeAccountUUID with collision detection.

    Unlike ensure_account_uuid() which only checks presence, this function
    also verifies the UUID is not used by another device in the OCT database.

    Flow:
    1. GET /info -> read existing UUID
    2. If UUID exists: check for collision in device_repo
    3. If collision or no UUID: generate new, write via SSH
    4. Retry if generated UUID also collides (up to max_retries)

    Args:
        device_ip: Device IP address
        device_id: Device MAC address (stable identifier)
        device_repo: Device repository for collision detection
        device_port: Device HTTP API port
        ssh: Optional pre-connected SSH client
        device_name: Device name for XML template
        max_retries: Max attempts if generated UUID collides

    Returns:
        AccountPairingResult with collision info
    """
    existing = await check_marge_account_uuid(device_ip, device_port)

    if existing:
        # Check if another device owns this UUID
        owner = await device_repo.get_by_account_uuid(existing)
        if owner is None or owner.device_id == device_id:
            logger.info("Device %s has unique UUID=%s", device_id, existing)
            return AccountPairingResult(
                success=True,
                had_uuid=True,
                uuid=existing,
                message=f"Device has unique account UUID: {existing}",
            )

        logger.warning(
            "UUID collision: %s owns UUID=%s, generating new for %s",
            owner.device_id,
            existing,
            device_id,
        )

    async def _set_uuid(uuid: str) -> AccountPairingResult:
        if ssh:
            return await set_account_uuid_via_ssh(ssh, uuid, device_name)
        async with SoundTouchSSHClient(device_ip) as ssh_client:
            return await set_account_uuid_via_ssh(ssh_client, uuid, device_name)

    for attempt in range(1, max_retries + 1):
        new_uuid = _generate_account_uuid()

        collision = await device_repo.get_by_account_uuid(new_uuid)
        if collision is not None and collision.device_id != device_id:
            logger.warning(
                "Generated UUID=%s also collides (attempt %d/%d)",
                new_uuid,
                attempt,
                max_retries,
            )
            if attempt == max_retries:
                return AccountPairingResult(
                    success=False,
                    had_uuid=existing is not None,
                    error=f"UUID collision after {max_retries} attempts",
                )
            continue

        result = await _set_uuid(new_uuid)
        if not result.success:
            return result

        result.had_uuid = existing is not None
        return result

    return AccountPairingResult(
        success=False,
        had_uuid=existing is not None,
        error="UUID generation exhausted",
    )
