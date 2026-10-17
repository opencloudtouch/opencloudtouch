"""Setup Wizard Step — NTP server patching.

Named ``ntp_patch`` rather than ``stepN_...`` to sidestep the backend's
step-number sequence entirely — see issue #469. (This PR does renumber the
other backend step modules to track the shifted frontend steps; this one
is named by function instead so it never needs a second rename if the
frontend step order changes again.)
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter

from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.api_models import NtpPatchRequest, NtpPatchResponse
from opencloudtouch.setup.ntp_service import SoundTouchNtpService
from opencloudtouch.setup.wizard_helpers import snapshot_config_files, ssh_operation

logger = logging.getLogger(__name__)

ntp_patch_router = APIRouter()


class NtpPatchMixin:
    """Patch the device's NTP server (Wizard Step — after hosts modification)."""

    if TYPE_CHECKING:
        _audit_repo: Any

    async def patch_ntp(self, device_ip: str, ntp_server: str) -> dict:
        """Patch NTP server on device.

        Returns:
            Dict with success, message, synced, backup_path, diff
        """
        async with ssh_operation(device_ip, "patch-ntp") as ssh:
            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                [SoundTouchNtpService.NTP_PATH],
                "before_patch_ntp",
            )

            ntp_service = SoundTouchNtpService(ssh)
            result = await ntp_service.patch_ntp(ntp_server)

            if not result.success:
                return {
                    "success": False,
                    "message": result.error or "NTP patch failed",
                }

            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                [SoundTouchNtpService.NTP_PATH],
                "after_patch_ntp",
            )

            message = f"NTP server set to {ntp_server}"
            if not result.synced:
                message += " (time sync pending — server did not respond yet)"

            return {
                "success": True,
                "message": message,
                "synced": result.synced,
                "backup_path": result.backup_path,
                "diff": result.diff,
            }


@ntp_patch_router.post("/wizard/patch-ntp", response_model=NtpPatchResponse)
async def wizard_patch_ntp(
    request: NtpPatchRequest,
    wizard: WizardServiceDep,
):
    """Patch NTP server on device (Wizard Step — NTP)."""
    logger.info(
        "Patching NTP on %s (server: %s)", request.device_ip, request.ntp_server
    )

    result = await wizard.patch_ntp(request.device_ip, request.ntp_server)

    if not result["success"]:
        return NtpPatchResponse(success=False, message=result["message"])

    return NtpPatchResponse(
        success=True,
        message=result["message"],
        synced=result.get("synced", True),
        backup_path=result.get("backup_path", ""),
        diff=result.get("diff", ""),
    )
