"""
Setup Wizard API Routes � Thin Handlers

SSH-driven step-by-step wizard endpoints for device configuration.
All business logic lives in WizardService; routes only handle HTTP concerns.
"""

import asyncio
import logging
import socket
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status

from opencloudtouch.core.dependencies import get_wizard_service
from opencloudtouch.core.dependencies import RestoreServiceDep
from opencloudtouch.setup.api_models import (
    BackupRequest,
    BackupResponse,
    ConfigModifyRequest,
    ConfigModifyResponse,
    ConnectivityCheckRequest,
    DetectStrategyResponse,
    EnsureAccountRequest,
    EnsureAccountResponse,
    FinalizeRequest,
    FinalizeResponse,
    InitPersistenceRequest,
    InitPersistenceResponse,
    HostsModifyRequest,
    HostsModifyResponse,
    ListBackupsRequest,
    ListBackupsResponse,
    PortCheckRequest,
    PortCheckResponse,
    RestoreRequest,
    RestoreResponse,
    ScanBackupsRequest,
    ScanBackupsResponse,
    RestoreWizardRequest,
    RestoreWizardResponse,
    RestoreStepResponse,
    VerifyRedirectRequest,
    VerifyRedirectResponse,
    VerifySetupRequest,
    VerifySetupResponse,
    WizardCompleteRequest,
    WizardCompleteResponse,
    AccountPairingRequest,
    AccountPairingResponse,
)
from opencloudtouch.setup.wizard_helpers import check_port_443, ssh_operation
from opencloudtouch.setup.wizard_service import WizardService

logger = logging.getLogger(__name__)

wizard_router = APIRouter(prefix="/api/setup", tags=["Setup Wizard"])


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
    port = url.port or 7777

    # Resolve actual LAN IP for /etc/hosts (requires numeric IP).
    # Do NOT use the request hostname — behind Docker/port-forwarding it's
    # "localhost" which resolves to 127.0.0.1 and breaks device hosts entries.
    try:
        server_ip = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        # Fallback: try resolving request hostname (better than nothing)
        try:
            server_ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            server_ip = hostname

    # Guard against loopback IPs (common in Docker where /etc/hosts maps
    # the container ID to 127.0.0.1).  Use a UDP connect trick to find
    # the real outgoing interface IP without sending any traffic.
    #
    # How: Opening a UDP socket and connect()ing to an external address
    # (here 8.8.8.8) causes the OS to select the outgoing network interface
    # without actually sending a packet.  getsockname() then returns the
    # local IP of that interface — i.e. the LAN IP the device can reach.
    if server_ip.startswith("127."):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                server_ip = s.getsockname()[0]
            finally:
                s.close()
        except OSError:
            # UDP trick failed — fall back to request hostname
            if not hostname.startswith("127."):
                server_ip = hostname

    # Build server_url using the resolved IP so the frontend gets a
    # reachable address, not the browser hostname (e.g. "hera").
    server_url = f"{url.scheme}://{server_ip}:{port}"

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

    proxy_available = check_port_443(hostname)

    if proxy_available:
        return DetectStrategyResponse(
            proxy_available=True,
            strategy="hosts_only",
            message=(
                "HTTPS Reverse-Proxy auf Port 443 erkannt. "
                "Es reicht, die /etc/hosts-Datei zu �ndern."
            ),
        )
    return DetectStrategyResponse(
        proxy_available=False,
        strategy="bmx_and_hosts",
        message=(
            "Kein Reverse-Proxy auf Port 443 erkannt. "
            "Die BMX-URL muss zus�tzlich ge�ndert werden."
        ),
    )


@wizard_router.post("/wizard/check-ports", response_model=PortCheckResponse)
async def wizard_check_ports(
    request: PortCheckRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Check if SSH port is accessible (Wizard Step 3)."""
    logger.info("Checking SSH port on %s", request.device_ip)

    async with asyncio.timeout(request.timeout):
        has_ssh = await wizard.check_ssh_port(request.device_ip)

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
async def wizard_backup(
    request: BackupRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Create complete backup to USB stick (Wizard Step 4)."""
    logger.info("Starting backup for %s", request.device_ip)

    result = await wizard.backup_all(request.device_ip, request.device_id or "")

    if not result["success"]:
        return BackupResponse(success=False, message=result["message"])

    return BackupResponse(
        success=True,
        message=result["message"],
        volumes=result.get("volumes") or [],
        total_size_mb=result.get("total_size_mb") or 0.0,
        total_duration_seconds=result.get("total_duration_seconds") or 0.0,
    )


@wizard_router.post("/wizard/modify-config", response_model=ConfigModifyResponse)
async def wizard_modify_config(
    request: ConfigModifyRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Modify OverrideSdkPrivateCfg.xml (Wizard Step 5)."""
    logger.info(
        "Modifying config on %s (OCT: %s)", request.device_ip, request.target_addr
    )

    result = await wizard.modify_config(request.device_ip, request.target_addr)

    if not result["success"]:
        return ConfigModifyResponse(success=False, message=result["message"])

    return ConfigModifyResponse(
        success=True,
        message=result["message"],
        backup_path=result.get("backup_path", ""),
        diff=result.get("diff", ""),
        old_url=result.get("old_url", ""),
        new_url=result.get("new_url", ""),
    )


@wizard_router.post("/wizard/modify-hosts", response_model=HostsModifyResponse)
async def wizard_modify_hosts(
    request: HostsModifyRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Modify /etc/hosts (Wizard Step 6)."""
    logger.info(
        "Modifying hosts on %s (OCT: %s)", request.device_ip, request.target_addr
    )

    try:
        result = await wizard.modify_hosts(
            request.device_ip, request.target_addr, request.include_optional
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not result["success"]:
        return HostsModifyResponse(success=False, message=result["message"])

    return HostsModifyResponse(
        success=True,
        message=result["message"],
        backup_path=result.get("backup_path", ""),
        diff=result.get("diff", ""),
    )


@wizard_router.post("/wizard/restore-config", response_model=RestoreResponse)
async def wizard_restore_config(
    request: RestoreRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Restore config from backup (Wizard Step 8)."""
    logger.info("Restoring config from %s", request.backup_path)

    result = await wizard.restore_config(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])


@wizard_router.post("/wizard/restore-hosts", response_model=RestoreResponse)
async def wizard_restore_hosts(
    request: RestoreRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Restore hosts from backup (Wizard Step 8)."""
    logger.info("Restoring hosts from %s", request.backup_path)

    result = await wizard.restore_hosts(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])


@wizard_router.post("/wizard/list-backups", response_model=ListBackupsResponse)
async def wizard_list_backups(
    request: ListBackupsRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """List available backups (Wizard Step 8)."""
    logger.info("Listing backups on %s", request.device_ip)

    result = await wizard.list_backups(request.device_ip)

    return ListBackupsResponse(
        success=True,
        config_backups=result["config_backups"],
        hosts_backups=result["hosts_backups"],
    )


@wizard_router.post("/wizard/reboot-device")
async def wizard_reboot_device(
    request: ConnectivityCheckRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
) -> Dict[str, Any]:
    """Reboot SoundTouch device via SSH (Wizard Step 7)."""
    logger.info("Sending reboot command to %s", request.ip)

    result = await wizard.reboot_device(request.ip)

    if not result["success"]:
        error_msg = result["error"]
        # Connection failures ? 503; unexpected errors ? 500
        if "SSH connection failed" in error_msg:
            status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            status_code = http_status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(status_code=status_code, detail=error_msg)

    logger.info("Reboot command sent to %s", request.ip)
    return {
        "success": True,
        "message": "Neustart-Befehl gesendet. Das Ger�t startet in wenigen Sekunden neu.",
    }


@wizard_router.post("/wizard/account-pairing", response_model=AccountPairingResponse)
async def wizard_account_pairing(
    request: AccountPairingRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Ensure device has a margeAccountUUID (Wizard Step - Account Pairing).

    Checks if the device already has a UUID. If not, generates one and
    sets it via Telnet. Persists the UUID in the device repository for
    streaming endpoint resolution.
    """
    logger.info(
        "Account pairing for %s (device %s)", request.device_ip, request.device_id
    )

    result = await wizard.ensure_account_pairing(request.device_ip, request.device_id)

    return AccountPairingResponse(
        success=result["success"],
        had_uuid=result.get("had_uuid", False),
        uuid=result.get("uuid", ""),
        message=result.get("message", ""),
    )


@wizard_router.post("/wizard/ensure-account", response_model=EnsureAccountResponse)
async def wizard_ensure_account(request: EnsureAccountRequest):
    """Ensure device has a margeAccountUUID (Wizard Step � after config/hosts).

    Devices without a margeAccountUUID cannot play presets (INVALID_SOURCE).
    This endpoint checks GET :8090/info and sets a UUID via Telnet if missing.

    Safe to call multiple times � no-op if UUID already present.
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


@wizard_router.post("/wizard/init-persistence", response_model=InitPersistenceResponse)
async def wizard_init_persistence(request: InitPersistenceRequest):
    """Initialize persistence files on factory-reset devices (Wizard Step — after account pairing).

    Factory-reset devices lack SystemConfigurationDB.xml and Sources.xml.
    Without them, the firmware never fully initialises playback state,
    causing INVALID_SOURCE on preset recall (GitHub Issue #167).

    Only creates files that are missing — never overwrites existing ones.
    Safe to call multiple times.
    """
    from opencloudtouch.setup.persistence_service import ensure_persistence_files

    logger.info(
        "Initializing persistence files on %s (name=%s, uuid=%s)",
        request.device_ip,
        request.device_name,
        request.account_uuid,
    )

    async with ssh_operation(request.device_ip, "init-persistence") as ssh:
        # Remount rw for file creation
        await ssh.execute("mount -o remount,rw /")
        try:
            result = await ensure_persistence_files(
                ssh=ssh,
                device_name=request.device_name,
                account_uuid=request.account_uuid,
            )
        finally:
            await ssh.execute("sync")
            await ssh.execute("mount -o remount,ro /")

    if not result.success:
        return InitPersistenceResponse(
            success=False,
            message=result.error or "Persistence initialization failed",
        )

    return InitPersistenceResponse(
        success=True,
        created_files=result.created_files,
        skipped_files=result.skipped_files,
        message=result.message,
    )


@wizard_router.post("/wizard/complete", response_model=WizardCompleteResponse)
async def wizard_complete(
    request: WizardCompleteRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Mark wizard setup as complete for a device."""
    logger.info("Marking wizard setup complete for device %s", request.device_id)

    result = await wizard.mark_complete(request.device_id)

    if not result["success"]:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return WizardCompleteResponse(
        success=True,
        device_id=request.device_id,
        setup_status="configured",
        message="Setup abgeschlossen. Ger�t ist konfiguriert.",
    )


@wizard_router.post("/wizard/verify-redirect", response_model=VerifyRedirectResponse)
async def wizard_verify_redirect(
    request: VerifyRedirectRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Verify a domain is redirected to OCT on the device (Wizard Step 7)."""
    logger.info(
        "Verifying redirect of %s on %s (expected: %s)",
        request.domain,
        request.device_ip,
        request.expected_ip,
    )

    result = await wizard.verify_redirect(
        request.device_ip, request.domain, request.expected_ip
    )

    return VerifyRedirectResponse(
        success=result["matches_expected"],
        domain=result["domain"],
        resolved_ip=result["resolved_ip"],
        expected_ip=result["expected_ip"],
        matches_expected=result["matches_expected"],
        message=result["message"],
    )


@wizard_router.post(
    "/wizard/finalize",
    response_model=FinalizeResponse,
    responses={500: {"description": "Finalization failed"}},
)
async def wizard_finalize(
    request: FinalizeRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Finalize device setup: set UUID + write Sources.xml (Issue #184).

    Atomic operation that ensures the device has a unique margeAccountUUID
    and a complete Sources.xml. Safe to call multiple times (idempotent).
    """
    logger.info("Finalizing device %s (%s)", request.device_id, request.device_ip)

    result = await wizard.finalize_device(request.device_ip, request.device_id)

    if not result["success"]:
        return FinalizeResponse(
            success=False,
            error=result.get("error", "Finalization failed"),
        )

    return FinalizeResponse(
        success=True,
        uuid=result.get("uuid", ""),
        had_uuid=result.get("had_uuid", False),
        uuid_was_collision=result.get("uuid_was_collision", False),
        sources_written=result.get("sources_written", False),
        sources_backup_path=result.get("sources_backup_path", ""),
        system_config_written=result.get("system_config_written", False),
        message=result.get("message", ""),
    )


@wizard_router.post(
    "/wizard/verify-setup",
    response_model=VerifySetupResponse,
    responses={500: {"description": "Verification failed"}},
)
async def wizard_verify_setup(
    request: VerifySetupRequest,
    wizard: Annotated[WizardService, Depends(get_wizard_service)],
):
    """Comprehensive post-setup health check (Issue #184).

    Read-only validation: checks UUID, Sources.xml, config files,
    hosts entries, and SystemConfigurationDB.xml. Never modifies device.
    """
    logger.info(
        "Verifying setup for %s (%s, expected OCT IP: %s)",
        request.device_id,
        request.device_ip,
        request.expected_oct_ip,
    )

    result = await wizard.verify_setup(
        request.device_ip, request.device_id, request.expected_oct_ip
    )

    return VerifySetupResponse(
        success=result["success"],
        checks=result.get("checks", []),
        passed_count=result.get("passed_count", 0),
        failed_count=result.get("failed_count", 0),
        message=result.get("message", ""),
    )


# ============================================================================
# Restore Wizard Endpoints
# ============================================================================


@wizard_router.post(
    "/wizard/scan-backups",
    response_model=ScanBackupsResponse,
    responses={500: {"description": "Backup scan failed"}},
)
async def wizard_scan_backups(
    request: ScanBackupsRequest,
    restore: RestoreServiceDep,
):
    """Scan USB stick for backup files and auto-select matching set."""
    logger.info(
        "Scanning backups on %s for device %s", request.device_ip, request.device_id
    )
    try:
        result = await restore.scan_backups(request.device_ip, request.device_id)
        return ScanBackupsResponse(
            usb_mounted=result.usb_mounted,
            backup_dir=result.backup_dir,
            selected_set=_backup_set_to_response(result.selected_set),
            all_sets=[_backup_set_to_response(s) for s in result.all_sets],
            error=result.error,
        )
    except Exception as e:
        logger.exception("Backup scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@wizard_router.post(
    "/wizard/restore-wizard",
    response_model=RestoreWizardResponse,
    responses={500: {"description": "Restore wizard execution failed"}},
)
async def wizard_restore_wizard(
    request: RestoreWizardRequest,
    restore: RestoreServiceDep,
):
    """Execute full restore wizard sequence."""
    logger.info(
        "Executing %s restore on %s (device %s)",
        request.restore_type,
        request.device_ip,
        request.device_id,
    )
    try:
        backup_set_dict = None
        if request.backup_set:
            backup_set_dict = {
                "device_id": request.backup_set.device_id,
                "backup_date": request.backup_set.backup_date,
                "files": [
                    {"file_path": f.file_path, "volume_type": f.volume_type}
                    for f in request.backup_set.files
                ],
            }
        result = await restore.execute_restore(
            device_ip=request.device_ip,
            device_id=request.device_id,
            restore_type=request.restore_type,
            backup_set=backup_set_dict,
            skip_snapshot=request.skip_snapshot,
        )
        return RestoreWizardResponse(
            success=result.success,
            restore_type=result.restore_type,
            steps=[
                RestoreStepResponse(
                    name=s.name.value if hasattr(s.name, "value") else s.name,
                    status=s.status.value if hasattr(s.status, "value") else s.status,
                    message=s.message,
                    error=s.error,
                    duration_seconds=s.duration_seconds,
                )
                for s in result.steps
            ],
            pre_restore_snapshot=result.pre_restore_snapshot,
            snapshot_skipped=result.snapshot_skipped,
            device_rebooted=result.device_rebooted,
            total_duration_seconds=result.total_duration_seconds,
        )
    except Exception as e:
        logger.exception("Restore wizard failed")
        raise HTTPException(status_code=500, detail=str(e))


def _backup_set_to_response(bs):
    """Convert domain BackupSet to API response model."""
    if bs is None:
        return None
    from opencloudtouch.setup.api_models import (
        BackupFileInfoResponse,
        BackupSetResponse,
    )

    return BackupSetResponse(
        device_id=bs.device_id,
        backup_date=bs.backup_date,
        files=[
            BackupFileInfoResponse(
                filename=f.filename,
                volume_type=f.volume_type,
                file_path=f.file_path,
                size_bytes=f.size_bytes,
                device_id=f.device_id,
                backup_date=f.backup_date,
                is_pre_restore=f.is_pre_restore,
                validation_status=(
                    f.validation_status.value
                    if hasattr(f.validation_status, "value")
                    else f.validation_status
                ),
                validation_message=f.validation_message,
            )
            for f in bs.files
        ],
        is_legacy=bs.is_legacy,
        is_match=bs.is_match,
    )
