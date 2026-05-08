"""
Device Setup API Routes

General device setup endpoints: connectivity check, full setup flow, SSH management.
SSH-driven wizard step endpoints live in wizard_routes.py (STORY-304).
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi import status as http_status

from opencloudtouch.setup.api_models import (
    ConnectivityCheckRequest,
    EnablePermanentSSHRequest,
    SetupRequest,
)
from opencloudtouch.setup.models import SetupStatus
from opencloudtouch.core.dependencies import get_setup_service
from opencloudtouch.setup.service import SetupService
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["Device Setup"])


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
    Check if device is ready for setup (SSH available).

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

    ssh_client = SoundTouchSSHClient(host=request.ip, port=22)

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
