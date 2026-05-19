"""Account pairing service for SoundTouch devices.

Ensures the device has a margeAccountUUID. Without it, the device
cannot sync presets with the Marge server and preset playback fails
with INVALID_SOURCE (GitHub Issue #167).

The UUID is checked via the device's HTTP API (GET :8090/info).
If missing, it is set via Telnet port 17000 using:
    envswitch accountid set <uuid>
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional

import httpx
from defusedxml import ElementTree as ET

from opencloudtouch.discovery import SOUNDTOUCH_HTTP_PORT as _DEFAULT_DEVICE_HTTP_PORT
from opencloudtouch.setup.ssh_client import SoundTouchTelnetClient

logger = logging.getLogger(__name__)

_DEFAULT_TELNET_PORT = 17000
_INFO_TIMEOUT = 5.0
_TELNET_TIMEOUT = 10.0


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


async def set_account_uuid_via_telnet(
    device_ip: str,
    uuid: str,
    telnet_port: int = _DEFAULT_TELNET_PORT,
) -> AccountPairingResult:
    """Set margeAccountUUID on device via Telnet envswitch command.

    Args:
        device_ip: Device IP address
        uuid: 7-digit account UUID to set
        telnet_port: Telnet port (default 17000)

    Returns:
        AccountPairingResult with success status
    """
    telnet = SoundTouchTelnetClient(device_ip, port=telnet_port)
    try:
        conn = await telnet.connect(timeout=_TELNET_TIMEOUT)
        if not conn.success:
            return AccountPairingResult(
                success=False,
                had_uuid=False,
                error=f"Telnet connection failed: {conn.error}",
            )

        result = await telnet.execute(f"envswitch accountid set {uuid}", timeout=5.0)
        if not result.success:
            return AccountPairingResult(
                success=False,
                had_uuid=False,
                error=f"envswitch command failed: {result.error or result.output}",
            )

        logger.info("Set margeAccountUUID=%s on %s via Telnet", uuid, device_ip)
        return AccountPairingResult(
            success=True,
            had_uuid=False,
            uuid=uuid,
            message=f"Account UUID {uuid} set via Telnet",
        )
    finally:
        await telnet.close()


async def ensure_account_uuid(
    device_ip: str,
    device_port: int = _DEFAULT_DEVICE_HTTP_PORT,
    telnet_port: int = _DEFAULT_TELNET_PORT,
) -> AccountPairingResult:
    """Ensure device has a margeAccountUUID — set one if missing.

    1. GET /info → check <margeAccountUUID>
    2. If present → return success (no-op)
    3. If missing → generate UUID → set via Telnet envswitch

    Args:
        device_ip: Device IP address
        device_port: Device HTTP API port
        telnet_port: Device Telnet port

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
        "Device %s has no margeAccountUUID — setting %s via Telnet",
        device_ip,
        uuid,
    )
    return await set_account_uuid_via_telnet(device_ip, uuid, telnet_port)


async def ensure_account_uuid_unique(
    device_ip: str,
    device_id: str,
    device_repo,
    device_port: int = _DEFAULT_DEVICE_HTTP_PORT,
    telnet_port: int = _DEFAULT_TELNET_PORT,
    max_retries: int = 5,
) -> AccountPairingResult:
    """Ensure device has a unique margeAccountUUID with collision detection.

    Unlike ensure_account_uuid() which only checks presence, this function
    also verifies the UUID is not used by another device in the OCT database.

    Flow:
    1. GET /info -> read existing UUID
    2. If UUID exists: check for collision in device_repo
    3. If collision or no UUID: generate new, set via Telnet
    4. Retry if generated UUID also collides (up to max_retries)

    Args:
        device_ip: Device IP address
        device_id: Device MAC address (stable identifier)
        device_repo: Device repository for collision detection
        device_port: Device HTTP API port
        telnet_port: Device Telnet port
        max_retries: Max attempts if generated UUID collides

    Returns:
        AccountPairingResult with collision info
    """
    existing = await check_marge_account_uuid(device_ip, device_port)

    if existing:
        # Check if another device owns this UUID
        owner = await device_repo.get_by_account_uuid(existing)
        if owner is None or owner.device_id == device_id:
            # UUID is unique (or belongs to this device already)
            logger.info("Device %s has unique UUID=%s", device_id, existing)
            return AccountPairingResult(
                success=True,
                had_uuid=True,
                uuid=existing,
                message=f"Device has unique account UUID: {existing}",
            )

        # Collision: another device owns this UUID
        logger.warning(
            "UUID collision: %s owns UUID=%s, generating new for %s",
            owner.device_id,
            existing,
            device_id,
        )

    # Generate new UUID (with collision retry)
    for attempt in range(1, max_retries + 1):
        new_uuid = _generate_account_uuid()

        # Check if the new UUID is already taken
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

        # Set via Telnet
        result = await set_account_uuid_via_telnet(device_ip, new_uuid, telnet_port)
        if not result.success:
            return result

        # Override had_uuid to reflect original state
        result.had_uuid = existing is not None
        return result

    # Should not reach here, but satisfy type checker
    return AccountPairingResult(
        success=False,
        had_uuid=existing is not None,
        error="UUID generation exhausted",
    )
