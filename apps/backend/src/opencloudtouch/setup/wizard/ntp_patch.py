"""Setup Wizard Step — NTP server patching.

Named ``ntp_patch`` (not ``stepN_...``) because the frontend step numbering
shifts independently of these backend module numbers — see issue #469.
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
            Dict with success, message, backup_path, diff
        """
        async with ssh_operation(device_ip, "patch-ntp") as ssh:
            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                ["/etc/ntpservers.txt"],
                "before_patch_ntp",
            )

            ntp_service = SoundTouchNtpService(ssh)
            result = await ntp_service.patch_ntp(ntp_server)

            if result.success:
                await snapshot_config_files(
                    ssh,
                    self._audit_repo,
                    device_ip,
                    ["/etc/ntpservers.txt"],
                    "after_patch_ntp",
                )

            if not result.success:
                return {
                    "success": False,
                    "message": result.error or "NTP patch failed",
                }

            return {
                "success": True,
                "message": f"NTP server set to {ntp_server}",
                "backup_path": result.backup_path,
                "diff": result.diff,
            }


@ntp_patch_router.post("/wizard/patch-ntp", response_model=NtpPatchResponse)
async def wizard_patch_ntp(
    request: NtpPatchRequest,
    wizard: WizardServiceDep,
):
    """Patch NTP server on device (Wizard Step — NTP)."""
    logger.info("Patching NTP on %s (server: %s)", request.device_ip, request.ntp_server)

    result = await wizard.patch_ntp(request.device_ip, request.ntp_server)

    if not result["success"]:
        return NtpPatchResponse(success=False, message=result["message"])

    return NtpPatchResponse(
        success=True,
        message=result["message"],
        backup_path=result.get("backup_path", ""),
        diff=result.get("diff", ""),
    )
