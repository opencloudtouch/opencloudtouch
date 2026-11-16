"""API routes for enabling media servers as native speaker sources."""

from typing import Any

from fastapi import APIRouter, Query
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
    """Every discovered media server and every enabled server, with its state on this speaker."""
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
    response_model=NativeEnableResponse,
    responses={
        **_ERRORS,
        502: {
            "model": ErrorDetail,
            "description": "The speaker did not accept the pairing",
        },
    },
)
async def enable_native_server(
    device_id: str, server_id: str, service: DlnaNativeServiceDep
) -> NativeEnableResponse:
    """Enable the media server for the speaker and report the resulting state.

    Takes a few seconds when the speaker has to be re-paired; ``unavailable`` means the
    speaker did not list the server within 15 s (usually it cannot see the server).
    """
    return NativeEnableResponse(
        server_id=server_id, state=await service.enable(device_id, server_id)
    )


@router.delete(
    "/{device_id}/servers/{server_id}",
    response_model=NativeDisableResponse,
    responses={
        **_ERRORS,
        409: {
            "model": ErrorDetail,
            "description": "Native presets use the media server",
        },
        502: {
            "model": ErrorDetail,
            "description": "A preset slot could not be switched back",
        },
    },
)
async def disable_native_server(
    device_id: str,
    server_id: str,
    service: DlnaNativeServiceDep,
    force: bool = False,
) -> NativeDisableResponse:
    """Stop listing the server; ``force`` first switches native presets back to first-track."""
    return NativeDisableResponse(
        affected_slots=await service.disable(device_id, server_id, force)
    )
