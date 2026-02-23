"""
Device Setup API Routes

Endpoints for device setup wizard and configuration.
Includes manual modification endpoints for advanced users.
"""

import logging
from typing import Any, Dict

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    status as http_status,
)
from pydantic import BaseModel, Field

from opencloudtouch.setup.service import SetupService, get_setup_service
from opencloudtouch.setup.models import SetupStatus
from opencloudtouch.setup.ssh_client import (
    SoundTouchSSHClient,
    check_ssh_port,
    check_telnet_port,
)
from opencloudtouch.setup.backup_service import SoundTouchBackupService
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["Device Setup"])


class EnablePermanentSSHRequest(BaseModel):
    """Request to enable permanent SSH access on device."""

    device_id: str = Field(..., description="Device ID")
    ip: str = Field(..., description="Device IP address")
    make_permanent: bool = Field(
        default=True, description="Copy remote_services to /mnt/nv/ for persistence"
    )


class SetupRequest(BaseModel):
    """Request to start device setup."""

    device_id: str
    ip: str
    model: str


class ConnectivityCheckRequest(BaseModel):
    """Request to check device connectivity."""

    ip: str


@router.get("/instructions/{model}")
async def get_instructions(
    model: str,
    setup_service: SetupService = Depends(get_setup_service),
) -> Dict[str, Any]:
    """
    Get model-specific setup instructions.

    Returns:
        Instructions including USB port location, adapter recommendations, etc.
    """
    instructions = setup_service.get_model_instructions(model)
    return instructions.to_dict()


@router.post("/check-connectivity")
async def check_connectivity(
    request: ConnectivityCheckRequest,
    setup_service: SetupService = Depends(get_setup_service),
) -> Dict[str, Any]:
    """
    Check if device is ready for setup (SSH/Telnet available).

    This should be called after user inserts USB stick and reboots device.
    """
    return await setup_service.check_device_connectivity(request.ip)


@router.post("/start")
async def start_setup(
    request: SetupRequest,
    background_tasks: BackgroundTasks,
    setup_service: SetupService = Depends(get_setup_service),
) -> Dict[str, Any]:
    """
    Start the device setup process.

    This runs the full setup flow:
    1. Connect via SSH
    2. Make SSH persistent
    3. Backup config
    4. Modify BMX URL
    5. Verify configuration

    The setup runs in background. Use GET /status/{device_id} to check progress.
    """
    # Check if setup already in progress
    existing = setup_service.get_setup_status(request.device_id)
    if existing and existing.status == SetupStatus.PENDING:
        raise HTTPException(
            status_code=409, detail="Setup already in progress for this device"
        )

    # Start setup in background
    async def run_setup():
        await setup_service.run_setup(
            device_id=request.device_id,
            ip=request.ip,
            model=request.model,
        )

    background_tasks.add_task(run_setup)

    return {
        "device_id": request.device_id,
        "status": "started",
        "message": "Setup gestartet. Prüfe Status unter /api/setup/status/{device_id}",
    }


@router.get("/status/{device_id}")
async def get_status(
    device_id: str,
    setup_service: SetupService = Depends(get_setup_service),
) -> Dict[str, Any]:
    """
    Get setup status for a device.

    Returns current step, progress, and any errors.
    """
    progress = setup_service.get_setup_status(device_id)

    if not progress:
        return {
            "device_id": device_id,
            "status": "not_found",
            "message": "Kein aktives Setup für dieses Gerät",
        }

    return progress.to_dict()


@router.post("/ssh/enable-permanent")
async def enable_permanent_ssh(
    request: EnablePermanentSSHRequest,
) -> Dict[str, Any]:
    """
    Enable permanent SSH access on SoundTouch device.

    Copies /remote_services to /mnt/nv/ persistent volume.
    After reboot, SSH remains active without USB stick.

    Security Warning:
    - SSH becomes permanently accessible on network
    - Root login without password
    - Only recommended in trusted home networks
    """
    if not request.make_permanent:
        return {
            "success": True,
            "permanent_enabled": False,
            "message": "SSH bleibt temporär (USB-Stick erforderlich)",
        }

    ssh_client = SoundTouchSSHClient(host=request.ip, port=17317)

    try:
        # Connect to device
        logger.info(f"Connecting to {request.ip} to enable permanent SSH...")
        conn_result = await ssh_client.connect(timeout=10.0)

        if not conn_result.success:
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"SSH connection failed: {conn_result.error}",
            )

        # Copy remote_services to persistent volume
        # SoundTouch init script (shelby_usb) checks both USB root AND /mnt/nv/
        cmd = "touch /mnt/nv/remote_services"
        result = await ssh_client.execute(cmd, timeout=5.0)

        if not result.success:
            logger.error(f"Failed to create /mnt/nv/remote_services: {result.error}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Command failed: {result.error or result.output}",
            )

        logger.info(f"Permanent SSH enabled for {request.device_id} at {request.ip}")

        return {
            "success": True,
            "permanent_enabled": True,
            "device_id": request.device_id,
            "message": (
                "SSH dauerhaft aktiviert. "
                "Nach Neustart startet SSH automatisch ohne USB-Stick. "
                "⚠️ Sicherheitsrisiko in unsicheren Netzen!"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error enabling permanent SSH: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
    finally:
        await ssh_client.close()


@router.post("/verify/{device_id}")
async def verify_setup(
    device_id: str,
    ip: str,
    setup_service: SetupService = Depends(get_setup_service),
) -> Dict[str, Any]:
    """
    Verify that device setup is complete and working.

    Checks:
    - SSH accessible
    - SSH persistent
    - BMX URL configured correctly
    """
    return await setup_service.verify_setup(ip)


@router.get("/models")
async def list_supported_models() -> Dict[str, Any]:
    """
    Get list of all supported models with their instructions.
    """
    from opencloudtouch.setup.models import MODEL_INSTRUCTIONS

    return {
        "models": [
            instructions.to_dict() for instructions in MODEL_INSTRUCTIONS.values()
        ]
    }


# === Manual Modification Endpoints (Advanced Users) ===


class PortCheckRequest(BaseModel):
    """Request to check SSH/Telnet ports."""

    device_ip: str = Field(..., description="Device IP address")
    timeout: float = Field(default=10.0, ge=1.0, le=60.0)


class PortCheckResponse(BaseModel):
    """Response with port check results."""

    success: bool
    message: str
    has_ssh: bool = False
    has_telnet: bool = False


class BackupRequest(BaseModel):
    """Request to create device backup."""

    device_ip: str


class BackupResponse(BaseModel):
    """Response with backup results."""

    success: bool
    message: str
    volumes: list[dict] = Field(default_factory=list)
    total_size_mb: float = 0.0
    total_duration_seconds: float = 0.0


class ConfigModifyRequest(BaseModel):
    """Request to modify config file."""

    device_ip: str
    oct_ip: str


class ConfigModifyResponse(BaseModel):
    """Response with config modification result."""

    success: bool
    message: str
    backup_path: str = ""
    diff: str = ""


class HostsModifyRequest(BaseModel):
    """Request to modify hosts file."""

    device_ip: str
    oct_ip: str
    include_optional: bool = True


class HostsModifyResponse(BaseModel):
    """Response with hosts modification result."""

    success: bool
    message: str
    backup_path: str = ""
    diff: str = ""


class RestoreRequest(BaseModel):
    """Request to restore from backup."""

    device_ip: str
    backup_path: str


class RestoreResponse(BaseModel):
    """Response with restore result."""

    success: bool
    message: str


class ListBackupsRequest(BaseModel):
    """Request to list backups."""

    device_ip: str


class ListBackupsResponse(BaseModel):
    """Response with backup list."""

    success: bool
    config_backups: list[str] = Field(default_factory=list)
    hosts_backups: list[str] = Field(default_factory=list)


@router.post("/wizard/check-ports", response_model=PortCheckResponse)
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


@router.post("/wizard/backup", response_model=BackupResponse)
async def wizard_backup(request: BackupRequest):
    """Create complete backup to USB stick (Wizard Step 4)."""
    logger.info(f"Starting backup for {request.device_ip}")

    try:
        async with SoundTouchSSHClient(request.device_ip) as ssh:
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

    except Exception as e:
        logger.error(f"Backup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/wizard/modify-config", response_model=ConfigModifyResponse)
async def wizard_modify_config(request: ConfigModifyRequest):
    """Modify OverrideSdkPrivateCfg.xml (Wizard Step 5)."""
    logger.info(f"Modifying config on {request.device_ip} (OCT: {request.oct_ip})")

    try:
        async with SoundTouchSSHClient(request.device_ip) as ssh:
            config_service = SoundTouchConfigService(ssh)
            result = await config_service.modify_bmx_url(request.oct_ip)

            if not result.success:
                return ConfigModifyResponse(
                    success=False, message=result.error or "Modification failed"
                )

            return ConfigModifyResponse(
                success=True,
                message="Config modified successfully",
                backup_path=result.backup_path,
                diff=result.diff,
            )

    except Exception as e:
        logger.error(f"Config modification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/wizard/modify-hosts", response_model=HostsModifyResponse)
async def wizard_modify_hosts(request: HostsModifyRequest):
    """Modify /etc/hosts (Wizard Step 6)."""
    logger.info(f"Modifying hosts on {request.device_ip} (OCT: {request.oct_ip})")

    try:
        async with SoundTouchSSHClient(request.device_ip) as ssh:
            hosts_service = SoundTouchHostsService(ssh)
            result = await hosts_service.modify_hosts(
                request.oct_ip, request.include_optional
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

    except Exception as e:
        logger.error(f"Hosts modification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/wizard/restore-config", response_model=RestoreResponse)
async def wizard_restore_config(request: RestoreRequest):
    """Restore config from backup (Wizard Step 8)."""
    logger.info(f"Restoring config from {request.backup_path}")

    try:
        async with SoundTouchSSHClient(request.device_ip) as ssh:
            config_service = SoundTouchConfigService(ssh)
            result = await config_service.restore_config(request.backup_path)

            if not result.success:
                return RestoreResponse(
                    success=False, message=result.error or "Restore failed"
                )

            return RestoreResponse(success=True, message="Config restored")

    except Exception as e:
        logger.error(f"Config restore failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/wizard/restore-hosts", response_model=RestoreResponse)
async def wizard_restore_hosts(request: RestoreRequest):
    """Restore hosts from backup (Wizard Step 8)."""
    logger.info(f"Restoring hosts from {request.backup_path}")

    try:
        async with SoundTouchSSHClient(request.device_ip) as ssh:
            hosts_service = SoundTouchHostsService(ssh)
            result = await hosts_service.restore_hosts(request.backup_path)

            if not result.success:
                return RestoreResponse(
                    success=False, message=result.error or "Restore failed"
                )

            return RestoreResponse(success=True, message="Hosts restored")

    except Exception as e:
        logger.error(f"Hosts restore failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/wizard/list-backups", response_model=ListBackupsResponse)
async def wizard_list_backups(request: ListBackupsRequest):
    """List available backups (Wizard Step 8)."""
    logger.info(f"Listing backups on {request.device_ip}")

    try:
        async with SoundTouchSSHClient(request.device_ip) as ssh:
            config_service = SoundTouchConfigService(ssh)
            hosts_service = SoundTouchHostsService(ssh)

            config_backups = await config_service.list_backups()
            hosts_backups = await hosts_service.list_backups()

            return ListBackupsResponse(
                success=True,
                config_backups=config_backups,
                hosts_backups=hosts_backups,
            )

    except Exception as e:
        logger.error(f"List backups failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
