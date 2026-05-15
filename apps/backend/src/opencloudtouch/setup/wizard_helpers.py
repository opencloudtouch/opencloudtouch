"""Shared helpers for Setup Wizard routes.

Provides SSH context manager and config snapshot utility used
across wizard route modules.
"""

import logging
import socket
import ssl
from contextlib import asynccontextmanager
from typing import AsyncIterator

from opencloudtouch.core.exceptions import SSHConnectionError, SSHOperationError
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ssh_operation(
    device_ip: str, operation_name: str
) -> AsyncIterator[SoundTouchSSHClient]:
    """Async context manager: open SSH session, wrap errors as domain exceptions.

    Yields:
        Connected SoundTouchSSHClient ready for commands

    Raises:
        SSHConnectionError: When SSH connection is refused or unreachable
        SSHOperationError: On any other unexpected error during the operation
    """
    try:
        async with SoundTouchSSHClient(device_ip) as ssh:
            yield ssh
    except (SSHConnectionError, SSHOperationError):
        raise  # propagate domain exceptions unchanged
    except OSError:
        logger.exception("[Wizard/%s] SSH unreachable on %s", operation_name, device_ip)
        raise SSHConnectionError(device_ip)
    except Exception as e:
        logger.exception(
            "[Wizard/%s] failed on %s",
            operation_name,
            device_ip,
        )
        raise SSHOperationError(device_ip, operation_name, str(e))


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
        with socket.create_connection((hostname, 443), timeout=3) as sock:  # NOSONAR
            with ctx.wrap_socket(sock, server_hostname=hostname):
                return True
    except Exception:
        return False
