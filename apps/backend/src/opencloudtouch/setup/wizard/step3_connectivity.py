"""Setup Wizard Step 3 (Power Cycle) — SSH port connectivity check."""

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter

from opencloudtouch.core.dependencies import WizardServiceDep
from opencloudtouch.setup.api_models import PortCheckRequest, PortCheckResponse
from opencloudtouch.setup.ssh_client import check_ssh_port

logger = logging.getLogger(__name__)

step3_router = APIRouter()


class Step3ConnectivityMixin:
    """SSH port connectivity check (Wizard Step 3)."""

    if TYPE_CHECKING:
        SSH_TIMEOUT: float

    async def check_ssh_port(self, device_ip: str) -> bool:
        """Check if SSH port is accessible on device."""
        return await check_ssh_port(device_ip, timeout=self.SSH_TIMEOUT)


@step3_router.post("/wizard/check-ports", response_model=PortCheckResponse)
async def wizard_check_ports(
    request: PortCheckRequest,
    wizard: WizardServiceDep,
):
    """Check if SSH port is accessible (Wizard Step 3)."""
    logger.info("Checking SSH port on %s", request.device_ip)

    async with asyncio.timeout(request.timeout):
        has_ssh = await wizard.check_ssh_port(request.device_ip)

    if not has_ssh:
        return PortCheckResponse(
            success=False,
            message="SSH not accessible. Check USB stick setup.",
            has_ssh=False,
        )

    return PortCheckResponse(
        success=True,
        message="SSH access enabled",
        has_ssh=True,
    )
