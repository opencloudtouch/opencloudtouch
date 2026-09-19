"""Setup Wizard — legacy/superseded endpoints, kept for API-compat only.

4 of the original 6 endpoints here (list-backups, account-pairing,
ensure-account, init-persistence) were confirmed dead (no frontend caller,
no test coverage outside this router) and removed 2026-08-17. Superseded by
/wizard/scan-backups + /wizard/restore-wizard (backup listing) and
/wizard/finalize (UUID + persistence, folding in what account-pairing/
ensure-account/init-persistence used to do separately).

restore-config/restore-hosts are kept: they still have a live (if currently
uncalled) frontend wrapper (apps/frontend/src/api/wizard.ts:
restoreConfig()/restoreHosts()) and an active backend contract test
(test_api_contract.py::test_restore_requires_backup_path). This file is no
longer a deletion candidate pending a future, separately-scoped frontend and
test cleanup for these two endpoints.

Do not add new callers here.
"""

import logging

from fastapi import APIRouter

from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.api_models import (
    RestoreRequest,
    RestoreResponse,
)
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.wizard_helpers import ssh_operation

logger = logging.getLogger(__name__)

legacy_router = APIRouter()


class LegacyWizardMixin:
    """Superseded WizardService methods kept for API-compat.

    Only restore_config/restore_hosts remain (backing /wizard/restore-config
    and /wizard/restore-hosts). list_backups and ensure_account_pairing were
    removed 2026-08-17 along with their dead endpoints — see the module
    docstring above for details and the 2026-08-17 scope narrowing rationale.
    """

    async def restore_config(self, device_ip: str, backup_path: str) -> dict:
        """Restore config from backup."""
        async with ssh_operation(device_ip, "restore-config") as ssh:
            config_service = SoundTouchConfigService(ssh)
            result = await config_service.restore_config(backup_path)

            if not result.success:
                return {"success": False, "message": result.error or "Restore failed"}
            return {"success": True, "message": "Config restored"}

    async def restore_hosts(self, device_ip: str, backup_path: str) -> dict:
        """Restore hosts from backup."""
        async with ssh_operation(device_ip, "restore-hosts") as ssh:
            hosts_service = SoundTouchHostsService(ssh)
            result = await hosts_service.restore_hosts(backup_path)

            if not result.success:
                return {"success": False, "message": result.error or "Restore failed"}
            return {"success": True, "message": "Hosts restored"}


@legacy_router.post("/wizard/restore-config", response_model=RestoreResponse)
async def wizard_restore_config(
    request: RestoreRequest,
    wizard: WizardServiceDep,
):
    """Restore config from backup (Wizard Step 8)."""
    logger.info("Restoring config from %s", request.backup_path)

    result = await wizard.restore_config(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])


@legacy_router.post("/wizard/restore-hosts", response_model=RestoreResponse)
async def wizard_restore_hosts(
    request: RestoreRequest,
    wizard: WizardServiceDep,
):
    """Restore hosts from backup (Wizard Step 8)."""
    logger.info("Restoring hosts from %s", request.backup_path)

    result = await wizard.restore_hosts(request.device_ip, request.backup_path)

    if not result["success"]:
        return RestoreResponse(success=False, message=result["message"])
    return RestoreResponse(success=True, message=result["message"])
