"""
Device Setup Module

Provides functionality for configuring SoundTouch devices:
- SSH/Telnet client for device access
- Setup wizard orchestration
- Model-specific instructions
"""

from opencloudtouch.setup.models import (
    SetupStatus,
    SetupStep,
    SetupProgress,
    ModelInstructions,
    get_model_instructions,
)
from opencloudtouch.setup.service import (
    SetupService,
    get_setup_service,
)
from opencloudtouch.setup.routes import router as setup_router

__all__ = [
    "SetupStatus",
    "SetupStep",
    "SetupProgress",
    "ModelInstructions",
    "get_model_instructions",
    "SetupService",
    "get_setup_service",
    "setup_router",
]
