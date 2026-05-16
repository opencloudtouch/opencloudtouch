"""Shared helpers for Setup Wizard routes.

Provides SSH context manager and config snapshot utility used
across wizard route modules.
"""

import logging
import socket
import ssl
import urllib.request
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
    """Detect a reverse proxy on port 443 that actually fronts OCT.

    Two-phase check:
    1. TLS handshake on port 443 (is anything listening?)
    2. HTTPS GET to /health — does OCT respond behind the proxy?

    Only returns True when OCT is confirmed behind the proxy.
    A random service on 443 (Portainer, Traefik dashboard, etc.)
    will fail phase 2 and correctly return False.

    SSL verification is intentionally disabled: the proxy may use
    a self-signed certificate. No sensitive data is sent.
    """
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # NOSONAR - intentional
        ctx.check_hostname = False  # NOSONAR - port detection only
        ctx.verify_mode = ssl.CERT_NONE  # NOSONAR - no sensitive data sent

        # Phase 1: TLS handshake
        with socket.create_connection((hostname, 443), timeout=3) as sock:  # NOSONAR
            with ctx.wrap_socket(sock, server_hostname=hostname):
                pass  # TLS OK — something listens on 443

        # Phase 2: Verify OCT is behind the proxy
        # OCT's /health returns {"service": "opencloudtouch", ...}.
        # We match the unique "opencloudtouch" service identifier —
        # no other software will ever return this string.
        url = f"https://{hostname}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(
            req, timeout=5, context=ctx
        ) as resp:  # nosec B310  # NOSONAR
            body = resp.read(512).decode("utf-8", errors="replace")
            if resp.status == 200 and '"opencloudtouch"' in body:
                logger.info(
                    "Reverse proxy on %s:443 confirmed — OCT fingerprint "
                    '"opencloudtouch" found in /health',
                    hostname,
                )
                return True

        logger.info(
            "Port 443 open on %s but /health not OCT — not a valid OCT proxy",
            hostname,
        )
        return False

    except Exception:
        return False
