"""Dependency injection for FastAPI routes.

Centralizes dependency management and eliminates global state.
"""

from typing import Optional

from opencloudtouch.devices.repository import DeviceRepository
from opencloudtouch.presets.repository import PresetRepository
from opencloudtouch.presets.service import PresetService
from opencloudtouch.settings.repository import SettingsRepository

# Private singleton instances (module-level)
_device_repo_instance: Optional[DeviceRepository] = None
_preset_repo_instance: Optional[PresetRepository] = None
_preset_service_instance: Optional[PresetService] = None
_settings_repo_instance: Optional[SettingsRepository] = None


def set_device_repo(repo: DeviceRepository) -> None:
    """Register device repository instance (called from lifespan)."""
    global _device_repo_instance
    _device_repo_instance = repo


def set_preset_repo(repo: PresetRepository) -> None:
    """Register preset repository instance (called from lifespan)."""
    global _preset_repo_instance
    _preset_repo_instance = repo


def set_preset_service(service: PresetService) -> None:
    """Register preset service instance (called from lifespan)."""
    global _preset_service_instance
    _preset_service_instance = service


def set_settings_repo(repo: SettingsRepository) -> None:
    """Register settings repository instance (called from lifespan)."""
    global _settings_repo_instance
    _settings_repo_instance = repo


async def get_device_repo() -> DeviceRepository:
    """Get device repository instance (FastAPI dependency)."""
    if _device_repo_instance is None:
        raise RuntimeError("DeviceRepository not initialized")
    return _device_repo_instance


async def get_preset_repository() -> PresetRepository:
    """Get preset repository instance (FastAPI dependency)."""
    if _preset_repo_instance is None:
        raise RuntimeError("PresetRepository not initialized")
    return _preset_repo_instance


async def get_preset_service() -> PresetService:
    """Get preset service instance (FastAPI dependency)."""
    if _preset_service_instance is None:
        raise RuntimeError("PresetService not initialized")
    return _preset_service_instance


async def get_settings_repo() -> SettingsRepository:
    """Get settings repository instance (FastAPI dependency)."""
    if _settings_repo_instance is None:
        raise RuntimeError("SettingsRepository not initialized")
    return _settings_repo_instance


def clear_dependencies() -> None:
    """Clear all dependency instances (for testing)."""
    global _device_repo_instance, _preset_repo_instance, _preset_service_instance, _settings_repo_instance
    _device_repo_instance = None
    _preset_repo_instance = None
    _preset_service_instance = None
    _settings_repo_instance = None
