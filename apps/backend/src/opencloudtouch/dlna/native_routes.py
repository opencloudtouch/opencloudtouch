"""API routes for native (speaker-side) media server registrations."""

from typing import Any

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from opencloudtouch.core.dependencies import DlnaNativeServiceDep
from opencloudtouch.core.exceptions import ErrorDetail
from opencloudtouch.dlna.native_service import NativeState

router = APIRouter(prefix="/api/dlna/native", tags=["dlna"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorDetail, "description": "Device or media server not found"},
    503: {"model": ErrorDetail, "description": "Speaker unreachable"},
}


class NativeServer(BaseModel):
    server_id: str
    name: str
    state: NativeState
    server_known: bool
    source_id: int | None


class NativeServerList(BaseModel):
    device_id: str
    servers: list[NativeServer]


class NativeSlot(BaseModel):
    preset_number: int
    name: str


class NativeSlotList(BaseModel):
    slots: list[NativeSlot]


class NativeEnableResponse(BaseModel):
    server_id: str
    state: NativeState


class NativeDisableResponse(BaseModel):
    affected_slots: list[int]


@router.get("", response_model=NativeServerList, responses=_ERRORS)
async def list_native_servers(
    service: DlnaNativeServiceDep, device_id: str = Query(min_length=1)
) -> NativeServerList:
    """Every discovered media server and every registration, with its state on this speaker."""
    entries = await service.state(device_id)
    return NativeServerList(
        device_id=device_id,
        servers=[NativeServer(**vars(e)) for e in entries],
    )


@router.get("/{device_id}/servers/{server_id}/presets", response_model=NativeSlotList)
async def list_native_slots(
    device_id: str, server_id: str, service: DlnaNativeServiceDep
) -> NativeSlotList:
    """Native presets of the speaker that use this media server."""
    slots = await service.affected_slots(device_id, server_id)
    return NativeSlotList(
        slots=[
            NativeSlot(preset_number=p.preset_number, name=p.station_name)
            for p in slots
        ]
    )


@router.put(
    "/{device_id}/servers/{server_id}",
    status_code=202,
    response_model=NativeEnableResponse,
    responses={
        200: {"model": NativeEnableResponse, "description": "Already registered"},
        **_ERRORS,
        409: {
            "model": ErrorDetail,
            "description": "Registered but not usable, or removal pending",
        },
        502: {
            "model": ErrorDetail,
            "description": "The speaker did not register the server",
        },
    },
)
async def enable_native_server(
    device_id: str, server_id: str, response: Response, service: DlnaNativeServiceDep
) -> NativeEnableResponse:
    """Register the media server on the speaker (202), or report the current state (200)."""
    result = await service.enable(device_id, server_id)
    if not result.created:
        response.status_code = 200
    return NativeEnableResponse(server_id=server_id, state=result.state)


@router.delete(
    "/{device_id}/servers/{server_id}",
    response_model=NativeDisableResponse,
    responses={
        **_ERRORS,
        409: {
            "model": ErrorDetail,
            "description": "Native presets use the registration",
        },
        502: {
            "model": ErrorDetail,
            "description": "The speaker did not remove the server",
        },
    },
)
async def disable_native_server(
    device_id: str,
    server_id: str,
    service: DlnaNativeServiceDep,
    force: bool = False,
) -> NativeDisableResponse:
    """Remove the registration; ``force`` first switches native presets back to first-track."""
    return NativeDisableResponse(
        affected_slots=await service.disable(device_id, server_id, force)
    )
