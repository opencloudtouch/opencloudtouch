"""Log download routes for OpenCloudTouch."""

import datetime
import logging

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from opencloudtouch.core.logging import get_log_entries

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get(
    "/backend",
    response_class=PlainTextResponse,
    summary="Download backend log buffer",
    description="Returns the in-memory backend log ring-buffer (last 500 entries) as a plain-text file.",
)
async def download_backend_logs() -> PlainTextResponse:
    entries = get_log_entries()
    content = "\n".join(entries) if entries else "(no log entries captured yet)"
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"oct-backend-{timestamp}.log"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    logger.debug("Backend log download requested: %d entries", len(entries))
    return PlainTextResponse(content=content, headers=headers)
