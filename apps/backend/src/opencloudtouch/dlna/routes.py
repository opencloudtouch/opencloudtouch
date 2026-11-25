"""DLNA API routes."""

from dataclasses import asdict

from fastapi import APIRouter, Query
from pydantic import BaseModel

from opencloudtouch.core.dependencies import DlnaServiceDep
from opencloudtouch.core.exceptions import raise_coded
from opencloudtouch.dlna.client import DlnaBrowseError
from opencloudtouch.dlna.errors import classify

router = APIRouter(prefix="/api/dlna", tags=["dlna"])


class DlnaBrowseResponse(BaseModel):
    server_id: str
    object_id: str
    items: list[dict]
    starting_index: int
    number_returned: int
    total_matches: int | None
    next_index: int
    has_more: bool


class FirstChildAudio(BaseModel):
    first_child_is_audio: bool


@router.get("/servers")
async def get_dlna_servers(service: DlnaServiceDep) -> list[dict]:
    """Discover DLNA media servers."""
    servers = await service.get_servers()
    return [asdict(server) for server in servers]


@router.get("/servers/{server_id}/browse")
async def browse_dlna_server(
    server_id: str,
    service: DlnaServiceDep,
    object_id: str = Query(default="0", max_length=512),
    starting_index: int = Query(default=0, ge=0),
    requested_count: int = Query(default=50, ge=1, le=200),
) -> DlnaBrowseResponse:
    """Browse one page of a media server folder."""
    try:
        page = await service.browse_page(
            server_id, object_id, starting_index, requested_count
        )
    except (LookupError, DlnaBrowseError) as exc:
        raise_coded(*classify(exc))
    next_index = starting_index + page.number_returned
    # number_returned also counts filtered-out items, so clients must use has_more.
    has_more = (
        next_index < page.total_matches
        if page.total_matches is not None
        else page.number_returned >= requested_count
    )
    return DlnaBrowseResponse(
        server_id=server_id,
        object_id=object_id,
        items=[asdict(item) for item in page.items],
        starting_index=starting_index,
        number_returned=page.number_returned,
        total_matches=page.total_matches,
        next_index=next_index,
        has_more=has_more,
    )


@router.get("/servers/{server_id}/first-child-audio")
async def first_child_audio(
    server_id: str,
    service: DlnaServiceDep,
    object_id: str = Query(max_length=512),
) -> FirstChildAudio:
    """Tell whether a folder starts with an audio item (playable as preset)."""
    try:
        return FirstChildAudio(
            first_child_is_audio=await service.first_child_is_audio(
                server_id, object_id
            )
        )
    except (LookupError, DlnaBrowseError) as exc:
        raise_coded(*classify(exc))
