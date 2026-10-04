"""Setup wizard subsystem: per-step route handlers + the composed WizardService facade."""

from opencloudtouch.setup.wizard.router import wizard_router
from opencloudtouch.setup.wizard.service import WizardService

__all__ = ["WizardService", "wizard_router"]
