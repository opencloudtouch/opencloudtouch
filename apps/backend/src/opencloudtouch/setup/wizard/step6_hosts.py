"""Setup Wizard Step 6 (Hosts Modification) — redirect Bose cloud domains via /etc/hosts."""

import logging
import socket
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.api_models import HostsModifyRequest, HostsModifyResponse
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.wizard_helpers import snapshot_config_files, ssh_operation

logger = logging.getLogger(__name__)

step6_router = APIRouter()


class Step6HostsMixin:
    """Redirect Bose cloud domains via /etc/hosts (Wizard Step 6)."""

    if TYPE_CHECKING:
        _audit_repo: Any

    async def modify_hosts(
        self, device_ip: str, target_addr: str, include_optional: bool = False
    ) -> dict:
        """Modify /etc/hosts on device.

        Returns:
            Dict with success, message, backup_path, diff

        Raises:
            ValueError: If target hostname cannot be resolved
        """
        parsed = urlparse(target_addr)
        target_host = parsed.hostname or parsed.netloc

        try:
            target_ip = socket.gethostbyname(target_host)
        except socket.gaierror:
            raise ValueError(
                f"Cannot resolve hostname '{target_host}' to an IP address."
            )

        async with ssh_operation(device_ip, "modify-hosts") as ssh:
            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                ["/etc/hosts"],
                "before_modify_hosts",
            )

            hosts_service = SoundTouchHostsService(ssh)
            result = await hosts_service.modify_hosts(target_ip, include_optional)

            if result.success:
                await snapshot_config_files(
                    ssh,
                    self._audit_repo,
                    device_ip,
                    ["/etc/hosts"],
                    "after_modify_hosts",
                )

            if not result.success:
                return {
                    "success": False,
                    "message": result.error or "Modification failed",
                }

            return {
                "success": True,
                "message": "Hosts modified successfully",
                "backup_path": result.backup_path,
                "diff": result.diff,
            }


@step6_router.post("/wizard/modify-hosts", response_model=HostsModifyResponse)
async def wizard_modify_hosts(
    request: HostsModifyRequest,
    wizard: WizardServiceDep,
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
