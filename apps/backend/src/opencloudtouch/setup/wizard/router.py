"""Aggregates every wizard step's sub-router into the single public wizard_router."""

from fastapi import APIRouter

from opencloudtouch.setup.wizard.ntp_patch import ntp_patch_router
from opencloudtouch.setup.wizard.restore_wizard_routes import restore_wizard_router
from opencloudtouch.setup.wizard.step3_connectivity import step3_router
from opencloudtouch.setup.wizard.step4_backup import step4_router
from opencloudtouch.setup.wizard.step5_config import step5_router
from opencloudtouch.setup.wizard.step6_hosts import step6_router
from opencloudtouch.setup.wizard.step8_finalize_verify import step8_router
from opencloudtouch.setup.wizard.step9_completion import step9_router
from opencloudtouch.setup.wizard.strategy import strategy_router

wizard_router = APIRouter(prefix="/api/setup", tags=["Setup Wizard"])

wizard_router.include_router(strategy_router)
wizard_router.include_router(step3_router)
wizard_router.include_router(step4_router)
wizard_router.include_router(step5_router)
wizard_router.include_router(step6_router)
wizard_router.include_router(ntp_patch_router)
wizard_router.include_router(step8_router)
wizard_router.include_router(step9_router)
wizard_router.include_router(restore_wizard_router)
