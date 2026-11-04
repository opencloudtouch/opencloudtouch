"""Request and response models of the device settings endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class LanguageItem(BaseModel):
    id: int
    name: str | None = None


class ClockItem(BaseModel):
    enabled: bool | None = None
    time_format: str | None = None
    timezone: str | None = None


class PowerSavingItem(BaseModel):
    enabled: bool | None = None


class SettingsAvailability(BaseModel):
    language: bool
    clock: bool
    power_saving: bool


class DeviceSettingsResponse(BaseModel):
    """All device settings; a missing setting is null with available=false."""

    language: LanguageItem | None = None
    clock: ClockItem | None = None
    power_saving: PowerSavingItem | None = None
    available: SettingsAvailability
    languages: list[LanguageItem]


class LanguageWriteResponse(BaseModel):
    applied: bool
    value: LanguageItem | None = None


class ClockWriteResponse(BaseModel):
    applied: bool
    value: ClockItem | None = None


class PowerSavingWriteResponse(BaseModel):
    applied: bool
    value: PowerSavingItem | None = None


class _LooseRequest(BaseModel):
    """Loose field types on purpose: wrong types must become coded 422 errors from the
    service (``settings_*_invalid``), not a generic ``validation_error``."""

    model_config = ConfigDict(extra="ignore")


class SetLanguageRequest(_LooseRequest):
    language_id: Any = None


class SetClockRequest(_LooseRequest):
    enabled: Any = None
    time_format: Any = None
    timezone: Any = None


class SetPowerSavingRequest(_LooseRequest):
    enabled: Any = None
