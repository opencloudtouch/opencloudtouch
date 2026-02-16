"""
Device Setup API Routes

Endpoints for device setup wizard and configuration.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from opencloudtouch.setup.service import SetupService, get_setup_service
from opencloudtouch.setup.models import SetupStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["Device Setup"])


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
