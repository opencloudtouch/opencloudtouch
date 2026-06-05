"""
Device Setup API Routes

General device setup endpoints: connectivity check, verification, SSH management.
SSH-driven wizard step endpoints live in wizard_routes.py (STORY-304).
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from opencloudtouch.core.dependencies import get_setup_service
from opencloudtouch.setup.api_models import (
    ConnectivityCheckRequest,
    EnablePermanentSSHRequest,
)
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
            "message": "No active setup for this device",
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
            "message": "SSH remains temporary (USB stick required)",
        }

    ssh_client = SoundTouchSSHClient(host=request.ip, port=22)

    try:
        # Connect to device
        logger.info("Connecting to %s to enable permanent SSH...", request.ip)
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
            logger.error("Failed to create /mnt/nv/remote_services: %s", result.error)
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Command failed: {result.error or result.output}",
            )

        logger.info("Permanent SSH enabled for %s at %s", request.device_id, request.ip)

        return {
            "success": True,
            "permanent_enabled": True,
            "device_id": request.device_id,
            "message": (
                "SSH permanently enabled. "
                "After reboot, SSH starts automatically without USB stick. "
                "⚠️ Security risk in untrusted networks!"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error enabling permanent SSH: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while enabling permanent SSH",
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
