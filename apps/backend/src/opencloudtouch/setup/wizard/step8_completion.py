"""Setup Wizard Step 8 (Completion) — mark device as configured."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.api_models import (
    WizardCompleteRequest,
    WizardCompleteResponse,
)
from opencloudtouch.setup.wizard.base import _ERR_DEVICE_REPO_UNAVAILABLE

logger = logging.getLogger(__name__)

step8_router = APIRouter()


class Step8CompletionMixin:
    """Mark device setup as complete (Wizard Step 8)."""

    if TYPE_CHECKING:
        _device_repo: Any

    async def mark_complete(self, device_id: str) -> dict:
        """Mark wizard setup as complete for a device."""
        if not self._device_repo:
            return {"success": False, "error": _ERR_DEVICE_REPO_UNAVAILABLE}

        try:
            await self._device_repo.update_setup_status(
                device_id=device_id,
                setup_status="configured",
                setup_completed_at=datetime.now(UTC),
            )
            return {"success": True}
        except Exception as e:
            logger.exception("Failed to update setup status for %s", device_id)
            return {"success": False, "error": f"Failed to update setup status: {e}"}


@step8_router.post("/wizard/complete", response_model=WizardCompleteResponse)
async def wizard_complete(
    request: WizardCompleteRequest,
    wizard: WizardServiceDep,
):
    """Mark wizard setup as complete for a device."""
    logger.info("Marking wizard setup complete for device %s", request.device_id)

    result = await wizard.mark_complete(request.device_id)

    if not result["success"]:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return WizardCompleteResponse(
        success=True,
        device_id=request.device_id,
        setup_status="configured",
        message="Setup abgeschlossen. Ger�t ist konfiguriert.",
    )
