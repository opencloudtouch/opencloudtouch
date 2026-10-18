"""DLNA API routes."""

import socket
from dataclasses import asdict
from xml.etree.ElementTree import ParseError

from fastapi import APIRouter, HTTPException, Query, Request, Response

from opencloudtouch.dlna.client import DlnaBrowseError
from opencloudtouch.dlna.events import parse_avtransport_event
from opencloudtouch.dlna.playback import DlnaPlaybackError
from opencloudtouch.dlna.renderer import DlnaRendererError
from opencloudtouch.core.dependencies import DlnaServiceDep

router = APIRouter(prefix="/api/dlna", tags=["dlna"])


async def _get_device_ip(request: Request, device_id: str) -> str:
    """Resolve a SoundTouch device IP through the OCT DeviceService."""
    device_service = request.app.state.device_service
    device = await device_service.get_device_by_id(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail=f"Device not found: {device_id}",
        )

    return device.ip


def _get_callback_base_url(request: Request, device_ip: str) -> str:
    """Build an AVTransport callback URL reachable by the renderer.

    The LAN interface is selected using the renderer address and the callback
    uses the actual OCT backend port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((device_ip, 8091))
        callback_host = sock.getsockname()[0]

    server = request.scope.get("server")
    callback_port = server[1] if server else request.url.port

    if callback_port is None:
        callback_port = 80

    return f"http://{callback_host}:{callback_port}"


@router.get("/servers")
async def get_dlna_servers(service: DlnaServiceDep) -> list[dict]:
    """Discover DLNA media servers."""
    servers = await service.get_servers()
    return [asdict(server) for server in servers]


@router.get("/servers/{server_id}/browse")
async def browse_dlna_server(
    server_id: str,
    service: DlnaServiceDep,
    object_id: str = Query(default="0"),
) -> dict:
    """Browse a DLNA MediaServer ContentDirectory."""
    try:
        items = await service.browse(server_id, object_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DlnaBrowseError as exc:
        if exc.error_code == "701":
            raise HTTPException(
                status_code=404,
                detail=f"DLNA object not found: {object_id}",
            ) from exc

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return {
        "server_id": server_id,
        "object_id": object_id,
        "items": [asdict(item) for item in items],
    }


@router.post("/servers/{server_id}/items/{object_id}/play/{device_id}")
async def play_dlna_item(
    request: Request,
    server_id: str,
    object_id: str,
    device_id: str,
    service: DlnaServiceDep,
    parent_id: str = Query(...),
) -> dict:
    """Play a media server item directly on a SoundTouch device."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        item = await service.play(
            device_id=device_id,
            device_ip=device_ip,
            server_id=server_id,
            parent_id=parent_id,
            object_id=object_id,
            callback_base_url=_get_callback_base_url(request, device_ip),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DlnaBrowseError, DlnaRendererError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "device_id": device_id,
        "item": asdict(item),
    }


@router.api_route(
    "/events/{device_id}",
    methods=["NOTIFY"],
    status_code=200,
    include_in_schema=False,
)
async def dlna_avtransport_event(
    request: Request,
    device_id: str,
    service: DlnaServiceDep,
) -> Response:
    """Receive AVTransport events from a SoundTouch renderer."""
    body = (await request.body()).decode("utf-8", errors="replace")

    try:
        event = parse_avtransport_event(body)
    except ParseError:
        # UPnP event callbacks must remain tolerant of malformed
        # notifications from the renderer.
        return Response(status_code=200)

    if event.transport_state:
        await service.playback.handle_transport_state(
            device_id,
            event.transport_state,
        )

    return Response(status_code=200)


@router.get("/devices/{device_id}/current")
async def get_current_dlna_item(
    device_id: str,
    service: DlnaServiceDep,
) -> dict:
    """Return the current media server item managed by the OCT playback queue."""
    item = service.playback.current(device_id)

    return {
        "device_id": device_id,
        "item": asdict(item) if item else None,
    }


@router.post("/devices/{device_id}/pause")
async def pause_dlna(
    request: Request,
    device_id: str,
    service: DlnaServiceDep,
) -> dict:
    """Pause current DLNA playback."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        await service.pause(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"device_id": device_id, "status": "paused"}


@router.post("/devices/{device_id}/resume")
async def resume_dlna(
    request: Request,
    device_id: str,
    service: DlnaServiceDep,
) -> dict:
    """Resume current DLNA playback."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        await service.resume(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"device_id": device_id, "status": "playing"}


@router.post("/devices/{device_id}/next")
async def next_dlna(
    request: Request,
    device_id: str,
    service: DlnaServiceDep,
) -> dict:
    """Play the next DLNA track."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        item = await service.next(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "device_id": device_id,
        "item": asdict(item),
    }


@router.post("/devices/{device_id}/previous")
async def previous_dlna(
    request: Request,
    device_id: str,
    service: DlnaServiceDep,
) -> dict:
    """Play the previous DLNA track."""
    device_ip = await _get_device_ip(request, device_id)

    try:
        item = await service.previous(device_id, device_ip)
    except DlnaPlaybackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DlnaRendererError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "device_id": device_id,
        "item": asdict(item),
    }
