"""DLNA API routes."""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Query
from pydantic import BaseModel

from opencloudtouch.core.dependencies import DlnaServiceDep
from opencloudtouch.core.exceptions import ErrorDetail, raise_coded
from opencloudtouch.dlna.client import DlnaBrowseError
from opencloudtouch.dlna.errors import classify
from opencloudtouch.dlna.models import DlnaItem, page_cursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dlna", tags=["dlna"])


class DlnaBrowseResponse(BaseModel):
    """One page of a DLNA folder; consumers must use ``has_more``, not the page length."""

    server_id: str
    object_id: str
    items: list[DlnaItem]
    starting_index: int
    number_returned: int
    total_matches: int | None
    next_index: int
    has_more: bool


@router.get("/servers")
async def get_dlna_servers(
    service: DlnaServiceDep, refresh: bool = False
) -> list[dict]:
    """List DLNA media servers: known ones at once, a new scan runs in the background.

    ``refresh=true`` waits for a fresh scan instead.
    """
    servers = await (service.get_servers() if refresh else service.list_servers())
    return [asdict(server) for server in servers]


@router.get(
    "/servers/{server_id}/browse",
    response_model=DlnaBrowseResponse,
    responses={
        404: {"model": ErrorDetail, "description": "Server or object not found"},
        502: {"model": ErrorDetail, "description": "DLNA server failed"},
        504: {"model": ErrorDetail, "description": "DLNA server timed out"},
    },
)
async def browse_dlna_server(
    server_id: str,
    service: DlnaServiceDep,
    object_id: str = Query(default="0"),
    starting_index: int = Query(default=0, ge=0),
    requested_count: int = Query(default=50, ge=1, le=200),
) -> DlnaBrowseResponse:
    """Browse one page of a DLNA MediaServer ContentDirectory."""
    object_id = object_id or "0"
    failure: tuple[int, str, str] | None = None
    try:
        page = await service.browse(
            server_id, object_id, starting_index, requested_count
        )
    except (LookupError, DlnaBrowseError) as exc:
        failure = classify(exc)
    if failure:
        # Raised outside the except block: the cause chain (with server URLs in its
        # message) must not reach the error logger.
        logger.warning("DLNA browse on %s failed: %s", server_id, failure[1])
        raise_coded(*failure)

    next_index, has_more = page_cursor(page, starting_index, requested_count)
    return DlnaBrowseResponse(
        server_id=server_id,
        object_id=object_id,
        items=page.items,
        starting_index=starting_index,
        number_returned=page.number_returned,
        total_matches=page.total_matches,
        next_index=next_index,
        has_more=has_more,
    )
