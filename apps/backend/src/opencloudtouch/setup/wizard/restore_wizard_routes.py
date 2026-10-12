"""Restore Wizard endpoints — scan USB for backups, execute the restore sequence.

Thin passthrough to RestoreService (setup/restore_service.py), which is
already a fully separate, well-sized service — this file only relocates
the two HTTP handlers out of the old wizard_routes.py monolith.
"""

import logging

from fastapi import APIRouter, HTTPException

from opencloudtouch.core.dependencies import RestoreServiceDep
from opencloudtouch.setup.api_models import (
    BackupFileInfoResponse,
    BackupSetResponse,
    RestoreStepResponse,
    RestoreWizardRequest,
    RestoreWizardResponse,
    ScanBackupsRequest,
    ScanBackupsResponse,
)

logger = logging.getLogger(__name__)

restore_wizard_router = APIRouter()


def _backup_set_to_response(bs):
    """Convert domain BackupSet to API response model."""
    if bs is None:
        return None

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


@restore_wizard_router.post(
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


@restore_wizard_router.post(
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
