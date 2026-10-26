"""Sleep timer API: ``/api/devices/{device_id}/sleep-timer``."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from opencloudtouch.core.dependencies import SleepTimerServiceDep
from opencloudtouch.sleep_timer.models import (
    DEFAULT_FADE_SECONDS,
    MAX_DURATION_MINUTES,
    MAX_FADE_SECONDS,
    MIN_DURATION_MINUTES,
    SleepTimer,
)
from opencloudtouch.sleep_timer.repository import to_iso

router = APIRouter(prefix="/api/devices/{device_id}/sleep-timer", tags=["Sleep timer"])


class SleepTimerRequest(BaseModel):
    duration_minutes: int = Field(..., ge=MIN_DURATION_MINUTES, le=MAX_DURATION_MINUTES)
    fade_seconds: int = Field(DEFAULT_FADE_SECONDS, ge=0, le=MAX_FADE_SECONDS)
    end_action: Literal["stop", "standby"] = "stop"


class SleepTimerStatus(BaseModel):
    active: bool
    server_time: str
    device_id: str | None = None
    ends_at: str | None = None
    duration_minutes: int | None = None
    fade_seconds: int | None = None
    end_action: Literal["stop", "standby"] | None = None
    state: Literal["running", "fading", "ending"] | None = None


def _status(timer: SleepTimer | None, now: float) -> SleepTimerStatus:
    if timer is None:
        return SleepTimerStatus(active=False, server_time=to_iso(now))
    if now >= timer.ends_at:
        state = "ending"
    elif timer.fade_seconds > 0 and now >= timer.fade_start:
        state = "fading"
    else:
        state = "running"
    return SleepTimerStatus(
        active=True,
        server_time=to_iso(now),
        device_id=timer.device_id,
        ends_at=to_iso(timer.ends_at),
        duration_minutes=timer.duration_minutes,
        fade_seconds=timer.fade_seconds,
        end_action=timer.end_action,  # type: ignore[arg-type]
        state=state,  # type: ignore[arg-type]
    )


@router.get("", response_model=SleepTimerStatus)
async def get_sleep_timer(device_id: str, service: SleepTimerServiceDep):
    """Current timer of the device (no device call)."""
    timer = await service.get(device_id)
    return _status(timer, service.now())


@router.put("", response_model=SleepTimerStatus)
async def put_sleep_timer(
    device_id: str, body: SleepTimerRequest, service: SleepTimerServiceDep
):
    """Start the timer; replaces a running one."""
    timer = await service.start(
        device_id, body.duration_minutes, body.fade_seconds, body.end_action
    )
    return _status(timer, service.now())


@router.delete("", status_code=204)
async def delete_sleep_timer(device_id: str, service: SleepTimerServiceDep):
    """Cancel the timer (idempotent) and give a faded volume back."""
    await service.cancel(device_id)
    return Response(status_code=204)
