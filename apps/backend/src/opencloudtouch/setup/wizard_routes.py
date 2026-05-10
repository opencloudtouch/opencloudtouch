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
import ssl
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
    DetectStrategyResponse,
    EnsureAccountRequest,
    EnsureAccountResponse,
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
    WizardCompleteRequest,
    WizardCompleteResponse,
)
from opencloudtouch.setup.backup_service import SoundTouchBackupService
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.ssh_client import (
    SoundTouchSSHClient,
    check_ssh_port,
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
            "[Wizard/%s] failed on %s: %s", operation_name, device_ip, e, exc_info=True
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
    Also resolves the hostname to an IP for /etc/hosts usage.
    """
    # Extract from actual HTTP request
    url = request.url
    hostname = url.hostname or "127.0.0.1"
    server_url = f"{url.scheme}://{hostname}:{url.port or 7777}"

    # Resolve hostname → IP for /etc/hosts (requires numeric IP)
    try:
        server_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        server_ip = hostname

    return {
        "server_url": server_url,
        "server_ip": server_ip,
        "default_port": 7777,
        "supported_protocols": ["http", "https"],
    }


@wizard_router.get("/wizard/detect-strategy", response_model=DetectStrategyResponse)
async def wizard_detect_strategy(request: Request) -> DetectStrategyResponse:
    """Detect whether an HTTPS reverse proxy is available on port 443.

    If a reverse proxy (e.g. Nginx) terminates SSL on 443 and forwards
    to OCT, then the device only needs ``/etc/hosts`` changes (Strategy B).
    Otherwise, the BMX URL in the device config must also be changed
    (Strategy A + hosts).
    """
    hostname = request.url.hostname or "127.0.0.1"

    proxy_available = _check_port_443(hostname)

    if proxy_available:
        return DetectStrategyResponse(
            proxy_available=True,
            strategy="hosts_only",
            message=(
                "HTTPS Reverse-Proxy auf Port 443 erkannt. "
                "Es reicht, die /etc/hosts-Datei zu ändern."
            ),
        )
    return DetectStrategyResponse(
        proxy_available=False,
        strategy="bmx_and_hosts",
        message=(
            "Kein Reverse-Proxy auf Port 443 erkannt. "
            "Die BMX-URL muss zusätzlich geändert werden."
        ),
    )


def _check_port_443(hostname: str) -> bool:
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


@wizard_router.post("/wizard/check-ports", response_model=PortCheckResponse)
async def wizard_check_ports(request: PortCheckRequest):
    """Check if SSH port is accessible (Wizard Step 3)."""
    logger.info("Checking SSH port on %s", request.device_ip)

    has_ssh = await check_ssh_port(request.device_ip, timeout=request.timeout)

    if not has_ssh:
        return PortCheckResponse(
            success=False,
            message="SSH not accessible. Check USB stick setup.",
            has_ssh=False,
        )

    return PortCheckResponse(
        success=True,
        message="SSH access enabled",
        has_ssh=True,
    )


@wizard_router.post("/wizard/backup", response_model=BackupResponse)
async def wizard_backup(request: BackupRequest):
    """Create complete backup to USB stick (Wizard Step 4)."""
    logger.info("Starting backup for %s", request.device_ip)

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
async def wizard_modify_config(request: ConfigModifyRequest, http_request: Request):
    """Modify OverrideSdkPrivateCfg.xml (Wizard Step 5)."""
    from urllib.parse import urlparse

    logger.info(
        "Modifying config on %s (OCT: %s)", request.device_ip, request.target_addr
    )

    parsed = urlparse(request.target_addr)
    target_host = parsed.hostname or parsed.netloc

    async with ssh_operation(request.device_ip, "modify-config") as ssh:
        config_service = SoundTouchConfigService(ssh)
        audit_repo = getattr(http_request.app.state, "wizard_audit_repo", None)

        await _snapshot_config_files(
            ssh,
            audit_repo,
            request.device_ip,
            config_service.CONFIG_CANDIDATES,
            "before_modify_config",
        )

        result = await config_service.modify_bmx_url(target_host)

        if result.success:
            await _snapshot_config_files(
                ssh,
                audit_repo,
                request.device_ip,
                config_service.CONFIG_CANDIDATES,
                "after_modify_config",
            )

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
async def wizard_modify_hosts(request: HostsModifyRequest, http_request: Request):
    """Modify /etc/hosts (Wizard Step 6)."""
    from urllib.parse import urlparse

    logger.info(
        "Modifying hosts on %s (OCT: %s)", request.device_ip, request.target_addr
    )

    parsed = urlparse(request.target_addr)
    target_host = parsed.hostname or parsed.netloc

    try:
        target_ip = socket.gethostbyname(target_host)
    except socket.gaierror:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve hostname '{target_host}' to an IP address.",
        )

    async with ssh_operation(request.device_ip, "modify-hosts") as ssh:
        audit_repo = getattr(http_request.app.state, "wizard_audit_repo", None)

        await _snapshot_config_files(
            ssh,
            audit_repo,
            request.device_ip,
            ["/etc/hosts"],
            "before_modify_hosts",
        )

        hosts_service = SoundTouchHostsService(ssh)
        result = await hosts_service.modify_hosts(target_ip, request.include_optional)

        if result.success:
            await _snapshot_config_files(
                ssh,
                audit_repo,
                request.device_ip,
                ["/etc/hosts"],
                "after_modify_hosts",
            )

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
    logger.info("Restoring config from %s", request.backup_path)

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
    logger.info("Restoring hosts from %s", request.backup_path)

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
    logger.info("Listing backups on %s", request.device_ip)

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
    logger.info("Sending reboot command to %s", request.ip)

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

        logger.info("Reboot command sent to %s", request.ip)
        return {
            "success": True,
            "message": "Neustart-Befehl gesendet. Das Gerät startet in wenigen Sekunden neu.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during reboot: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
    finally:
        await ssh_client.close()


@wizard_router.post("/wizard/ensure-account", response_model=EnsureAccountResponse)
async def wizard_ensure_account(request: EnsureAccountRequest):
    """Ensure device has a margeAccountUUID (Wizard Step — after config/hosts).

    Devices without a margeAccountUUID cannot play presets (INVALID_SOURCE).
    This endpoint checks GET :8090/info and sets a UUID via Telnet if missing.

    Safe to call multiple times — no-op if UUID already present.
    """
    from opencloudtouch.setup.account_pairing_service import ensure_account_uuid

    logger.info("Ensuring account UUID on device %s", request.device_ip)

    result = await ensure_account_uuid(request.device_ip)

    if not result.success:
        return EnsureAccountResponse(
            success=False,
            had_uuid=result.had_uuid,
            message=result.error or "Account pairing failed",
        )

    return EnsureAccountResponse(
        success=True,
        had_uuid=result.had_uuid,
        uuid=result.uuid,
        message=result.message,
    )


@wizard_router.post("/wizard/complete", response_model=WizardCompleteResponse)
async def wizard_complete(request: WizardCompleteRequest, http_request: Request):
    """Mark wizard setup as complete for a device.

    Updates the device's setup_status to 'configured' in the database.
    Called by the frontend when the user finishes the wizard.
    """
    from datetime import UTC, datetime

    logger.info("Marking wizard setup complete for device %s", request.device_id)

    device_repo = http_request.app.state.device_repo
    try:
        await device_repo.update_setup_status(
            device_id=request.device_id,
            setup_status="configured",
            setup_completed_at=datetime.now(UTC),
        )
    except Exception as e:
        logger.exception("Failed to update setup status for %s", request.device_id)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update setup status: {e}",
        )

    return WizardCompleteResponse(
        success=True,
        device_id=request.device_id,
        setup_status="configured",
        message="Setup abgeschlossen. Gerät ist konfiguriert.",
    )


@wizard_router.post("/wizard/verify-redirect", response_model=VerifyRedirectResponse)
async def wizard_verify_redirect(request: VerifyRedirectRequest):
    """Verify a domain is redirected to OCT on the device (Wizard Step 7).

    SSH into the device, run ping against the domain, and check whether
    the resolved IP matches the OCT server's IP.
    """
    logger.info(
        "Verifying redirect of %s on %s (expected: %s)",
        request.domain,
        request.device_ip,
        request.expected_ip,
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
                expected_ip=expected_resolved,
                matches_expected=False,
                message=f"Could not resolve {request.domain} on device. Output: {output[:200]}",
            )

        resolved_ip = match.group(1).strip()
        matches = resolved_ip == expected_resolved

        return VerifyRedirectResponse(
            success=matches,
            domain=request.domain,
            resolved_ip=resolved_ip,
            expected_ip=expected_resolved,
            matches_expected=matches,
            message=(
                f"{request.domain} → {resolved_ip} ✓"
                if matches
                else f"{request.domain} → {resolved_ip} (expected {expected_resolved})"
            ),
        )


async def _snapshot_config_files(
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
        logger.warning("Config snapshot (%s) failed: %s", trigger, e)
