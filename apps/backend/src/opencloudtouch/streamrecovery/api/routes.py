"""Stream recovery API: configuration and activity log of the watchdog."""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, StrictBool

from opencloudtouch.core.dependencies import StreamRecoveryServiceDep

router = APIRouter(prefix="/api/stream-recovery", tags=["Stream recovery"])


class StreamRecoveryConfigRequest(BaseModel):
    """Full replacement. Ranges are validated by the service (coded errors)."""

    enabled: StrictBool
    min_play_seconds: Any
    max_attempts_per_hour: Any


class StreamRecoveryConfigResponse(BaseModel):
    enabled: bool
    min_play_seconds: int
    max_attempts_per_hour: int
    updated_at: str | None = None


class StreamRecoveryEventItem(BaseModel):
    id: int
    occurred_at: str
    device_id: str
    preset_number: int | None = None
    station_name: str | None = None
    play_seconds: int | None = None
    outcome: str
    attempts: int
    error_code: str | None = None


class StreamRecoveryEventsResponse(BaseModel):
    events: list[StreamRecoveryEventItem]


@router.get("", response_model=StreamRecoveryConfigResponse)
async def get_stream_recovery(service: StreamRecoveryServiceDep):
    """Current configuration (defaults while nothing was stored)."""
    config = await service.get_config()
    return StreamRecoveryConfigResponse(**vars(config))


@router.put("", response_model=StreamRecoveryConfigResponse)
async def put_stream_recovery(
    body: StreamRecoveryConfigRequest, service: StreamRecoveryServiceDep
):
    """Store the configuration and apply it immediately."""
    config = await service.set_config(
        body.enabled, body.min_play_seconds, body.max_attempts_per_hour
    )
    return StreamRecoveryConfigResponse(**vars(config))


@router.get("/events", response_model=StreamRecoveryEventsResponse)
async def list_stream_recovery_events(
    service: StreamRecoveryServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Recent activity, newest first."""
    events = await service.list_events(limit=limit)
    return StreamRecoveryEventsResponse(
        events=[StreamRecoveryEventItem(**vars(e)) for e in events]
    )
