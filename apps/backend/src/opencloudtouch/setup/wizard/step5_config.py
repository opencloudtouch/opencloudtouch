"""Setup Wizard Step 5 (Config Modification) — rewrite OverrideSdkPrivateCfg.xml URLs."""

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from fastapi import APIRouter

from opencloudtouch.core.config import get_config
from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.api_models import ConfigModifyRequest, ConfigModifyResponse
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.wizard_helpers import snapshot_config_files, ssh_operation

logger = logging.getLogger(__name__)

step5_router = APIRouter()


class Step5ConfigMixin:
    """Rewrite OverrideSdkPrivateCfg.xml BMX URLs (Wizard Step 5)."""

    if TYPE_CHECKING:
        _audit_repo: Any

    async def modify_config(self, device_ip: str, target_addr: str) -> dict:
        """Modify BMX URL in device config.

        Returns:
            Dict with success, message, backup_path, diff, old_url, new_url
        """
        parsed = urlparse(target_addr)
        target_host = parsed.hostname or parsed.netloc
        target_port = parsed.port or get_config().port

        async with ssh_operation(device_ip, "modify-config") as ssh:
            config_service = SoundTouchConfigService(ssh)

            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                config_service.CONFIG_CANDIDATES,
                "before_modify_config",
            )

            result = await config_service.modify_bmx_url(target_host, port=target_port)

            if result.success:
                await snapshot_config_files(
                    ssh,
                    self._audit_repo,
                    device_ip,
                    config_service.CONFIG_CANDIDATES,
                    "after_modify_config",
                )

            if not result.success:
                return {
                    "success": False,
                    "message": result.error or "Modification failed",
                }

            return {
                "success": True,
                "message": "Config modified successfully",
                "backup_path": result.backup_path,
                "diff": result.diff,
                "old_url": "https://*.bose.com (4 URLs)",
                "new_url": target_addr,
            }


@step5_router.post("/wizard/modify-config", response_model=ConfigModifyResponse)
async def wizard_modify_config(
    request: ConfigModifyRequest,
    wizard: WizardServiceDep,
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
