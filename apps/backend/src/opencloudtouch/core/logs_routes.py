"""Log download and runtime log-level routes for OpenCloudTouch."""

import datetime
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from opencloudtouch.core.logging import (
    get_current_log_level,
    get_log_entries,
    set_log_level,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


# ---------------------------------------------------------------------------
# Log level management
# ---------------------------------------------------------------------------


class LogLevelResponse(BaseModel):
    """Current log level."""

    level: str


class LogLevelRequest(BaseModel):
    """Request to change the log level at runtime."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@router.get("/level", summary="Get current log level")
async def get_log_level() -> LogLevelResponse:
    return LogLevelResponse(level=get_current_log_level())


@router.put(
    "/level",
    summary="Set log level at runtime",
    responses={400: {"description": "Invalid log level"}},
)
async def put_log_level(request: LogLevelRequest) -> LogLevelResponse:
    try:
        set_log_level(request.level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LogLevelResponse(level=get_current_log_level())


# ---------------------------------------------------------------------------
# Log download
# ---------------------------------------------------------------------------


class FrontendLogEntry(BaseModel):
    """A single frontend console log entry."""

    timestamp: str = ""
    level: str = ""
    message: str = ""


class LogDownloadRequest(BaseModel):
    """Optional body for POST /api/logs/backend with frontend logs."""

    frontend_logs: list[FrontendLogEntry] = []


@router.get(
    "/backend",
    response_class=PlainTextResponse,
    summary="Download backend log buffer (without frontend logs)",
    description="Returns backend logs only. Use POST to include frontend console logs.",
)
async def download_backend_logs_get(request: Request) -> PlainTextResponse:
    """GET handler for backward compatibility (no frontend logs)."""
    return await _build_log_response(request, frontend_logs=[])


@router.post(
    "/backend",
    response_class=PlainTextResponse,
    summary="Download backend + frontend logs",
    description="Returns backend logs with frontend console logs included.",
)
async def download_backend_logs_post(
    request: Request, body: LogDownloadRequest
) -> PlainTextResponse:
    """POST handler that accepts frontend logs in the request body."""
    return await _build_log_response(request, frontend_logs=body.frontend_logs)


async def _build_log_response(
    request: Request, frontend_logs: list[FrontendLogEntry]
) -> PlainTextResponse:
    entries = get_log_entries()

    # --- Section 1: Backend Ring Buffer ---
    content = "=" * 80
    content += f"\n BACKEND LOG BUFFER ({len(entries)} entries, max 1000)"
    content += "\n" + "=" * 80 + "\n\n"
    content += (
        "\n".join(entries) if entries else "(no backend log entries captured yet)"
    )

    # --- Section 2: Frontend Console Logs ---
    content += "\n\n" + "=" * 80
    content += f"\n FRONTEND CONSOLE LOGS ({len(frontend_logs)} entries, max 500)"
    content += "\n" + "=" * 80 + "\n\n"
    if frontend_logs:
        content += "".join(
            f"[{entry.timestamp}] {entry.level}: {entry.message}\n"
            for entry in frontend_logs
        )
    else:
        content += "(no frontend logs received — use the Download button in Settings\n"
        content += " or the Bug Report button to include browser console logs)\n"

    # --- Section 3: Wizard Audit Trail ---
    content += await _build_audit_trail_section(request)

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"oct-backend-{timestamp}.log"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    logger.debug("Backend log download requested: %d entries", len(entries))
    return PlainTextResponse(content=content, headers=headers)


async def _build_audit_trail_section(request: Request) -> str:
    """Build the wizard audit trail section."""
    header = "\n" + "=" * 80
    header += "\n WIZARD AUDIT TRAIL"
    header += "\n" + "=" * 80 + "\n"

    audit_repo = getattr(request.app.state, "wizard_audit_repo", None)
    if not audit_repo:
        return header + "\n(wizard audit repository not initialized)\n"

    try:
        audit_entries = await audit_repo.get_entries(limit=5000)
        snapshots = await audit_repo.get_config_snapshots(limit=200)
        return (
            header + _format_audit_entries(audit_entries) + _format_snapshots(snapshots)
        )
    except Exception as e:
        logger.warning("Failed to append audit trail to log download: %s", e)
        return header + f"\n(error reading audit trail: {e})\n"


def _format_audit_entries(entries: list[dict]) -> str:
    """Format audit log entries as text."""
    result = f"\n--- Audit Log ({len(entries)} entries) ---\n"
    if not entries:
        return result + "(no wizard audit entries recorded yet)\n"
    for e in entries:
        line = (
            f"[{e['timestamp']}] "
            f"device={e['device_id']} "
            f"step={e.get('step', '-')} "
            f"{e['category']}: {e['event']}"
        )
        if e.get("detail"):
            line += f" | {e['detail']}"
        result += line + "\n"
    return result


def _format_snapshots(snapshots: list[dict]) -> str:
    """Format config snapshots as text."""
    result = f"\n--- Config Snapshots ({len(snapshots)} entries) ---\n"
    if not snapshots:
        return result + "(no config snapshots recorded yet)\n"
    for s in snapshots:
        result += (
            f"\n[{s['timestamp']}] "
            f"device={s['device_id']} "
            f"trigger={s.get('trigger', '?')} "
            f"file={s['file_path']}\n"
        )
        result += s["content"] + "\n"
        result += "-" * 40 + "\n"
    return result
