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

from opencloudtouch.setup.ssh_client import SoundTouchTelnetClient

logger = logging.getLogger(__name__)

_DEFAULT_DEVICE_HTTP_PORT = 8090
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
    url = f"http://{device_ip}:{device_port}/info"
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
