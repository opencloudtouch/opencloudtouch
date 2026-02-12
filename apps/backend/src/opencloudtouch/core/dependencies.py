"""Dependency injection for FastAPI routes.

Centralizes dependency management using FastAPI app.state.
"""

from fastapi import Request

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.devices.service import DeviceService
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.settings.repository import SettingsRepository
from opencloudtouch.settings.service import SettingsService


async def get_device_repo(request: Request) -> DeviceRepository:
    """Get device repository instance from app.state (FastAPI dependency)."""
    return request.app.state.device_repo


async def get_device_service(request: Request) -> DeviceService:
    """Get device service instance from app.state (FastAPI dependency)."""
    return request.app.state.device_service


async def get_preset_repository(request: Request) -> PresetRepository:
    """Get preset repository instance from app.state (FastAPI dependency)."""
    return request.app.state.preset_repo


async def get_preset_service(request: Request) -> PresetService:
    """Get preset service instance from app.state (FastAPI dependency)."""
    return request.app.state.preset_service


async def get_settings_repo(request: Request) -> SettingsRepository:
    """Get settings repository instance from app.state (FastAPI dependency)."""
    return request.app.state.settings_repo


async def get_settings_service(request: Request) -> SettingsService:
    """Get settings service instance from app.state (FastAPI dependency)."""
    return request.app.state.settings_service
