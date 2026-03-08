"""
Setup Wizard API Routes

SSH-driven step-by-step wizard endpoints for device configuration.
Extracted from setup/routes.py (STORY-304) to separate the wizard
concern from general setup routes.

All endpoints require a reachable SoundTouch device with SSH access.
"""

import logging
import re
import shlex
import socket
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status

from opencloudtouch.setup.api_models import (
    BackupRequest,
    BackupResponse,
    ConfigModifyRequest,
    ConfigModifyResponse,
    ConnectivityCheckRequest,
    HostsModifyRequest,
    HostsModifyResponse,
    ListBackupsRequest,
    ListBackupsResponse,
    PortCheckRequest,
    PortCheckResponse,
    RestoreRequest,
    RestoreResponse,
    VerifyRedirectRequest,
    VerifyRedirectResponse,
)
from opencloudtouch.setup.backup_service import SoundTouchBackupService
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.ssh_client import (
    SoundTouchSSHClient,
    check_ssh_port,
    check_telnet_port,
)

logger = logging.getLogger(__name__)

wizard_router = APIRouter(prefix="/api/setup", tags=["Setup Wizard"])


@asynccontextmanager
async def ssh_operation(
    device_ip: str, operation_name: str
) -> AsyncIterator[SoundTouchSSHClient]:
    """Async context manager: open SSH session, wrap errors as HTTPException.

    Yields:
        Connected SoundTouchSSHClient ready for commands

    Raises:
        HTTPException(500): On any error opening SSH connection or during the operation
    """
    try:
        async with SoundTouchSSHClient(device_ip) as ssh:
            yield ssh
    except HTTPException:
        raise  # propagate intentional HTTP errors from business logic unchanged
    except Exception as e:
        logger.error(
            f"[Wizard/{operation_name}] failed on {device_ip}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Wizard operation '{operation_name}' failed. Check server logs for details.",
        )


@wizard_router.get("/wizard/server-info")
async def wizard_server_info(request: Request) -> Dict[str, Any]:
    """Get OCT server info for auto-filling wizard forms.

    Returns server URL that frontend can use as default.
    Detects host/port from incoming HTTP request headers.
    """
    # Extract from actual HTTP request
    url = request.url
    server_url = f"{url.scheme}://{url.hostname}:{url.port or 7777}"

    return {
        "server_url": server_url,
        "default_port": 7777,
        "supported_protocols": ["http", "https"],
    }


@wizard_router.post("/wizard/check-ports", response_model=PortCheckResponse)
async def wizard_check_ports(request: PortCheckRequest):
    """Check if SSH/Telnet ports accessible (Wizard Step 3)."""
    logger.info(f"Checking ports on {request.device_ip}")

    has_ssh = await check_ssh_port(request.device_ip, timeout=request.timeout)
    has_telnet = await check_telnet_port(request.device_ip, timeout=request.timeout)

    if not has_ssh and not has_telnet:
        return PortCheckResponse(
            success=False,
            message="Neither SSH nor Telnet accessible. Check USB stick setup.",
            has_ssh=False,
            has_telnet=False,
        )

    return PortCheckResponse(
        success=True,
        message=f"Remote access enabled (SSH: {has_ssh}, Telnet: {has_telnet})",
        has_ssh=has_ssh,
        has_telnet=has_telnet,
    )


@wizard_router.post("/wizard/backup", response_model=BackupResponse)
async def wizard_backup(request: BackupRequest):
    """Create complete backup to USB stick (Wizard Step 4)."""
    logger.info(f"Starting backup for {request.device_ip}")

    async with ssh_operation(request.device_ip, "backup") as ssh:
        backup_service = SoundTouchBackupService(ssh)
        results = await backup_service.backup_all()

        failed = [r for r in results if not r.success]
        if failed:
            return BackupResponse(
                success=False,
                message="; ".join(r.error or "Unknown" for r in failed),
            )

        total_size = sum(r.size_bytes for r in results) / 1024 / 1024
        total_duration = sum(r.duration_seconds for r in results)

        return BackupResponse(
            success=True,
            message=f"Backup complete: {total_size:.2f} MB",
            volumes=[
                {
                    "volume": r.volume.value,
                    "path": r.backup_path,
                    "size_mb": r.size_bytes / 1024 / 1024,
                    "duration_seconds": r.duration_seconds,
                }
                for r in results
            ],
            total_size_mb=total_size,
            total_duration_seconds=total_duration,
        )


@wizard_router.post("/wizard/modify-config", response_model=ConfigModifyResponse)
async def wizard_modify_config(request: ConfigModifyRequest):
    """Modify OverrideSdkPrivateCfg.xml (Wizard Step 5)."""
    from urllib.parse import urlparse

    logger.info(f"Modifying config on {request.device_ip} (OCT: {request.target_addr})")

    # Parse URL to extract host for config service
    parsed = urlparse(request.target_addr)
    target_host = parsed.hostname or parsed.netloc

    async with ssh_operation(request.device_ip, "modify-config") as ssh:
        config_service = SoundTouchConfigService(ssh)
        result = await config_service.modify_bmx_url(target_host)

        if not result.success:
            return ConfigModifyResponse(
                success=False, message=result.error or "Modification failed"
            )

        return ConfigModifyResponse(
            success=True,
            message="Config modified successfully",
            backup_path=result.backup_path,
            diff=result.diff,
            old_url="bmx.bose.com",
            new_url=target_host,
        )


@wizard_router.post("/wizard/modify-hosts", response_model=HostsModifyResponse)
async def wizard_modify_hosts(request: HostsModifyRequest):
    """Modify /etc/hosts (Wizard Step 6)."""
    from urllib.parse import urlparse

    logger.info(f"Modifying hosts on {request.device_ip} (OCT: {request.target_addr})")

    # Parse URL to extract host for hosts service
    parsed = urlparse(request.target_addr)
    target_host = parsed.hostname or parsed.netloc

    async with ssh_operation(request.device_ip, "modify-hosts") as ssh:
        hosts_service = SoundTouchHostsService(ssh)
        result = await hosts_service.modify_hosts(target_host, request.include_optional)

        if not result.success:
            return HostsModifyResponse(
                success=False, message=result.error or "Modification failed"
            )

        return HostsModifyResponse(
            success=True,
            message="Hosts modified successfully",
            backup_path=result.backup_path,
            diff=result.diff,
        )


@wizard_router.post("/wizard/restore-config", response_model=RestoreResponse)
async def wizard_restore_config(request: RestoreRequest):
    """Restore config from backup (Wizard Step 8)."""
    logger.info(f"Restoring config from {request.backup_path}")

    async with ssh_operation(request.device_ip, "restore-config") as ssh:
        config_service = SoundTouchConfigService(ssh)
        result = await config_service.restore_config(request.backup_path)

        if not result.success:
            return RestoreResponse(
                success=False, message=result.error or "Restore failed"
            )

        return RestoreResponse(success=True, message="Config restored")


@wizard_router.post("/wizard/restore-hosts", response_model=RestoreResponse)
async def wizard_restore_hosts(request: RestoreRequest):
    """Restore hosts from backup (Wizard Step 8)."""
    logger.info(f"Restoring hosts from {request.backup_path}")

    async with ssh_operation(request.device_ip, "restore-hosts") as ssh:
        hosts_service = SoundTouchHostsService(ssh)
        result = await hosts_service.restore_hosts(request.backup_path)

        if not result.success:
            return RestoreResponse(
                success=False, message=result.error or "Restore failed"
            )

        return RestoreResponse(success=True, message="Hosts restored")


@wizard_router.post("/wizard/list-backups", response_model=ListBackupsResponse)
async def wizard_list_backups(request: ListBackupsRequest):
    """List available backups (Wizard Step 8)."""
    logger.info(f"Listing backups on {request.device_ip}")

    async with ssh_operation(request.device_ip, "list-backups") as ssh:
        config_service = SoundTouchConfigService(ssh)
        hosts_service = SoundTouchHostsService(ssh)

        config_backups = await config_service.list_backups()
        hosts_backups = await hosts_service.list_backups()

        return ListBackupsResponse(
            success=True,
            config_backups=config_backups,
            hosts_backups=hosts_backups,
        )


@wizard_router.post("/wizard/reboot-device")
async def wizard_reboot_device(request: ConnectivityCheckRequest) -> Dict[str, Any]:
    """Reboot SoundTouch device via SSH (Wizard Step 7).

    Sends the `reboot` command via SSH. The device drops the SSH connection
    immediately after receiving the command — this is expected and not an error.
    Frontend should wait ~60s before attempting verify-redirect tests.
    """
    logger.info(f"Sending reboot command to {request.ip}")

    ssh_client = SoundTouchSSHClient(host=request.ip, port=22)
    try:
        conn_result = await ssh_client.connect(timeout=10.0)
        if not conn_result.success:
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"SSH connection failed: {conn_result.error}",
            )

        # The device drops the connection immediately on reboot — that is expected.
        # A short timeout avoids blocking the request for 30s.
        await ssh_client.execute("reboot", timeout=5.0)

        logger.info(f"Reboot command sent to {request.ip}")
        return {
            "success": True,
            "message": "Neustart-Befehl gesendet. Das Gerät startet in wenigen Sekunden neu.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during reboot: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
    finally:
        await ssh_client.close()


@wizard_router.post("/wizard/verify-redirect", response_model=VerifyRedirectResponse)
async def wizard_verify_redirect(request: VerifyRedirectRequest):
    """Verify a domain is redirected to OCT on the device (Wizard Step 7).

    SSH into the device, run ping against the domain, and check whether
    the resolved IP matches the OCT server's IP.
    """
    logger.info(
        f"Verifying redirect of {request.domain} on {request.device_ip} "
        f"(expected: {request.expected_ip})"
    )

    # Resolve expected_ip on the server side (handles hostname like 'myserver')
    try:
        expected_resolved = socket.gethostbyname(request.expected_ip)
    except socket.gaierror:
        expected_resolved = request.expected_ip  # already an IP or unresolvable

    async with ssh_operation(request.device_ip, "verify-redirect") as ssh:
        # Use ping -c1 -W2 — respects /etc/hosts on the device
        result = await ssh.execute(
            f"ping -c 1 -W 2 {shlex.quote(request.domain)} 2>&1 | head -2"
        )
        output = (result.output or "").strip()

        # BusyBox ping first line: 'PING domain (resolved_ip): ...'
        match = re.search(r"PING [^\(]*\(([^\)]+)\)", output)
        if not match:
            return VerifyRedirectResponse(
                success=False,
                domain=request.domain,
                resolved_ip="",
                matches_expected=False,
                message=f"Could not resolve {request.domain} on device. Output: {output[:200]}",
            )

        resolved_ip = match.group(1).strip()
        matches = resolved_ip == expected_resolved

        return VerifyRedirectResponse(
            success=matches,
            domain=request.domain,
            resolved_ip=resolved_ip,
            matches_expected=matches,
            message=(
                f"{request.domain} → {resolved_ip} ✓"
                if matches
                else f"{request.domain} → {resolved_ip} (expected {expected_resolved})"
            ),
        )
