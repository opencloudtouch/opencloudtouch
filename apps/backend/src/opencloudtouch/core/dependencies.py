"""Dependency injection for FastAPI routes.

Centralizes dependency management using FastAPI app.state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.marge.service import MargeService
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.recents.repository import RecentsRepository
from opencloudtouch.recents.service import RecentsService
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.service import SettingsService
from opencloudtouch.zones.service import ZoneService

if TYPE_CHECKING:
    from opencloudtouch.setup.service import SetupService
    from opencloudtouch.setup.wizard_service import WizardService


async def get_device_repo(request: Request) -> DeviceRepository:
    """Get device repository instance from app.state (FastAPI dependency)."""
    return request.app.state.device_repo


async def get_device_service(request: Request) -> DeviceService:
    """Get device service instance from app.state (FastAPI dependency)."""
    return request.app.state.device_service


async def get_preset_repository(request: Request) -> PresetRepository:
    """Get preset repository instance from app.state (FastAPI dependency)."""
    return request.app.state.preset_repo


async def get_recents_repository(request: Request) -> RecentsRepository:
    """Get recents repository instance from app.state (FastAPI dependency)."""
    return request.app.state.recents_repo


async def get_preset_service(request: Request) -> PresetService:
    """Get preset service instance from app.state (FastAPI dependency)."""
    return request.app.state.preset_service


async def get_settings_repo(request: Request) -> SettingsRepository:
    """Get settings repository instance from app.state (FastAPI dependency)."""
    return request.app.state.settings_repo


async def get_settings_service(request: Request) -> SettingsService:
    """Get settings service instance from app.state (FastAPI dependency)."""
    return request.app.state.settings_service


async def get_zone_service(request: Request) -> ZoneService:
    """Get zone service instance from app.state (FastAPI dependency)."""
    return request.app.state.zone_service


async def get_setup_service(request: Request) -> SetupService:
    """Get setup service instance from app.state (FastAPI dependency)."""
    return request.app.state.setup_service


async def get_recents_service(request: Request) -> RecentsService:
    """Get recents service instance from app.state (FastAPI dependency)."""
    return request.app.state.recents_service


async def get_marge_service(request: Request) -> MargeService:
    """Get marge service instance from app.state (FastAPI dependency)."""
    return request.app.state.marge_service


async def get_wizard_service(request: Request) -> WizardService:
    """Get wizard service instance from app.state (FastAPI dependency)."""
    return request.app.state.wizard_service
