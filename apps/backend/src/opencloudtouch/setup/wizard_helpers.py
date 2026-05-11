"""Shared helpers for Setup Wizard routes.

Provides SSH context manager and config snapshot utility used
across wizard route modules.
"""

import logging
import socket
import ssl
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import HTTPException
from fastapi import status as http_status

from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ssh_operation(
    device_ip: str, operation_name: str
) -> AsyncIterator[SoundTouchSSHClient]:
    """Async context manager: open SSH session, wrap errors as HTTPException.

    Yields:
        Connected SoundTouchSSHClient ready for commands

    Raises:
        HTTPException(503): When SSH connection is refused or unreachable
        HTTPException(500): On any other unexpected error
    """
    try:
        async with SoundTouchSSHClient(device_ip) as ssh:
            yield ssh
    except HTTPException:
        raise  # propagate intentional HTTP errors from business logic unchanged
    except (ConnectionError, ConnectionRefusedError, OSError) as e:
        logger.error(
            "[Wizard/%s] SSH unreachable on %s: %s", operation_name, device_ip, e
        )
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSH nicht erreichbar. Bitte USB-Stick prüfen oder SSH erneut aktivieren.",
        )
    except Exception as e:
        logger.error(
            "[Wizard/%s] failed on %s: %s",
            operation_name,
            device_ip,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Wizard operation '{operation_name}' failed. Check server logs for details.",
        )


async def snapshot_config_files(
    ssh: SoundTouchSSHClient,
    audit_repo,
    device_id: str,
    file_paths: list[str],
    trigger: str,
) -> None:
    """Take config snapshots for audit trail (best-effort, never raises)."""
    if not audit_repo:
        return
    try:
        for path in file_paths:
            r = await ssh.execute(f"cat {path} 2>/dev/null")
            if r.success and r.output:
                await audit_repo.add_config_snapshot(
                    device_id=device_id,
                    file_path=path,
                    content=r.output,
                    trigger=trigger,
                )
    except Exception as e:
        logger.debug("Snapshot failed (non-critical): %s", e)


def check_port_443(hostname: str) -> bool:
    """Try an SSL handshake on port 443 to detect a reverse proxy.

    SSL verification is intentionally disabled: this function only checks
    whether *any* service responds on 443, without sending sensitive data.
    The server may use a self-signed certificate.
    """
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # NOSONAR - intentional
        ctx.check_hostname = False  # NOSONAR - port detection only
        ctx.verify_mode = ssl.CERT_NONE  # NOSONAR - no sensitive data sent
        with socket.create_connection((hostname, 443), timeout=3) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname):
                return True
    except Exception:
        return False
