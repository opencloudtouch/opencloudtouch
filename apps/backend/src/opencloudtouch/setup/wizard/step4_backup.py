"""Setup Wizard Step 4 (Backup) — full-device backup to USB before config changes."""

import logging

from fastapi import APIRouter

from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.api_models import BackupRequest, BackupResponse
from opencloudtouch.setup.backup_service import SoundTouchBackupService
from opencloudtouch.setup.wizard_helpers import ssh_operation

logger = logging.getLogger(__name__)

step4_router = APIRouter()


class Step4BackupMixin:
    """Full-device backup to USB before config changes (Wizard Step 4)."""

    async def backup_all(self, device_ip: str, device_id: str) -> dict:
        """Create complete backup to USB stick.

        Returns:
            Dict with success, message, volumes, total_size_mb, total_duration_seconds
        """
        async with ssh_operation(device_ip, "backup") as ssh:
            backup_service = SoundTouchBackupService(ssh)
            results = await backup_service.backup_all(device_id=device_id)

            failed = [r for r in results if not r.success]
            if failed:
                return {
                    "success": False,
                    "message": "; ".join(r.error or "Unknown" for r in failed),
                }

            total_size = sum(r.size_bytes for r in results) / 1024 / 1024
            total_duration = sum(r.duration_seconds for r in results)

            return {
                "success": True,
                "message": f"Backup complete: {total_size:.2f} MB",
                "volumes": [
                    {
                        "volume": r.volume.value,
                        "path": r.backup_path,
                        "size_mb": r.size_bytes / 1024 / 1024,
                        "duration_seconds": r.duration_seconds,
                    }
                    for r in results
                ],
                "total_size_mb": total_size,
                "total_duration_seconds": total_duration,
            }


@step4_router.post("/wizard/backup", response_model=BackupResponse)
async def wizard_backup(
    request: BackupRequest,
    wizard: WizardServiceDep,
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
