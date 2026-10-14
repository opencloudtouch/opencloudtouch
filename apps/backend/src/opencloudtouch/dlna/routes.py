"""DLNA API routes."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from opencloudtouch.dlna.client import DlnaBrowseError
from opencloudtouch.core.dependencies import DlnaServiceDep

router = APIRouter(prefix="/api/dlna", tags=["dlna"])


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
