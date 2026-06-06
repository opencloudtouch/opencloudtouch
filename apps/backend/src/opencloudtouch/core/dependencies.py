"""Dependency injection for FastAPI routes.

Centralizes dependency management using FastAPI app.state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.devices.state import DeviceStateManager
from opencloudtouch.marge.service import MargeService
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.recents.repository import RecentsRepository
from opencloudtouch.recents.service import RecentsService
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.service import SettingsService
from opencloudtouch.zones.service import ZoneService

if TYPE_CHECKING:
    from opencloudtouch.setup.restore_service import RestoreService
    from opencloudtouch.setup.service import SetupService
    from opencloudtouch.setup.wizard_service import WizardService


def get_device_repo(request: Request) -> DeviceRepository:
    """Get device repository instance from app.state (FastAPI dependency)."""
    return request.app.state.device_repo


def get_device_service(request: Request) -> DeviceService:
    """Get device service instance from app.state (FastAPI dependency)."""
    return request.app.state.device_service


def get_preset_repository(request: Request) -> PresetRepository:
    """Get preset repository instance from app.state (FastAPI dependency)."""
    return request.app.state.preset_repo


def get_recents_repository(request: Request) -> RecentsRepository:
    """Get recents repository instance from app.state (FastAPI dependency)."""
    return request.app.state.recents_repo


def get_preset_service(request: Request) -> PresetService:
    """Get preset service instance from app.state (FastAPI dependency)."""
    return request.app.state.preset_service


def get_settings_repo(request: Request) -> SettingsRepository:
    """Get settings repository instance from app.state (FastAPI dependency)."""
    return request.app.state.settings_repo


def get_settings_service(request: Request) -> SettingsService:
    """Get settings service instance from app.state (FastAPI dependency)."""
    return request.app.state.settings_service


def get_device_state_manager(request: Request) -> DeviceStateManager:
    """Get device state manager instance from app.state (FastAPI dependency).

    Returns a fresh (empty) instance if not yet initialised — this avoids
    ``AttributeError`` in tests that exercise routes but don't wire up
    the full lifespan.
    """
    return (
        getattr(request.app.state, "device_state_manager", None) or DeviceStateManager()
    )


def get_zone_service(request: Request) -> ZoneService:
    """Get zone service instance from app.state (FastAPI dependency)."""
    return request.app.state.zone_service


def get_setup_service(request: Request) -> SetupService:
    """Get setup service instance from app.state (FastAPI dependency)."""
    return request.app.state.setup_service


def get_recents_service(request: Request) -> RecentsService:
    """Get recents service instance from app.state (FastAPI dependency)."""
    return request.app.state.recents_service


def get_marge_service(request: Request) -> MargeService:
    """Get marge service instance from app.state (FastAPI dependency)."""
    return request.app.state.marge_service


def get_wizard_service(request: Request) -> WizardService:
    """Get wizard service instance from app.state (FastAPI dependency)."""
    return request.app.state.wizard_service


# ---- Annotated type aliases for route signatures ----
DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]
PresetServiceDep = Annotated[PresetService, Depends(get_preset_service)]
MargeServiceDep = Annotated[MargeService, Depends(get_marge_service)]
ZoneServiceDep = Annotated[ZoneService, Depends(get_zone_service)]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
DeviceStateManagerDep = Annotated[DeviceStateManager, Depends(get_device_state_manager)]
WizardServiceDep = Annotated["WizardService", Depends(get_wizard_service)]


def get_restore_service(request: Request) -> "RestoreService":
    """Get restore service instance from app.state (FastAPI dependency)."""
    return request.app.state.restore_service


RestoreServiceDep = Annotated["RestoreService", Depends(get_restore_service)]
SetupServiceDep = Annotated["SetupService", Depends(get_setup_service)]
RecentsServiceDep = Annotated[RecentsService, Depends(get_recents_service)]
DeviceRepoDep = Annotated[DeviceRepository, Depends(get_device_repo)]
PresetRepoDep = Annotated[PresetRepository, Depends(get_preset_repository)]
RecentsRepoDep = Annotated[RecentsRepository, Depends(get_recents_repository)]
SettingsRepoDep = Annotated[SettingsRepository, Depends(get_settings_repo)]
