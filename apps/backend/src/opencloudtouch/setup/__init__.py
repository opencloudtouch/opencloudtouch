"""
Device Setup Module

Provides functionality for configuring SoundTouch devices:
- SSH client for device access
- Setup wizard orchestration
- Model-specific instructions
"""

from opencloudtouch.setup.models import (
    ModelInstructions,
    SetupProgress,
    SetupStatus,
    SetupStep,
    get_model_instructions,
)
from opencloudtouch.setup.routes import router as setup_router
from opencloudtouch.setup.service import SetupService

__all__ = [
    "SetupStatus",
    "SetupStep",
    "SetupProgress",
    "ModelInstructions",
    "get_model_instructions",
    "SetupService",
    "setup_router",
]
