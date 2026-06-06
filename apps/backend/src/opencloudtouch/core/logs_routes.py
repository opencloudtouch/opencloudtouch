"""Log download and runtime log-level routes for OpenCloudTouch."""

import datetime
import io
import logging
import zipfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from opencloudtouch.core.logging import (
    CLUSTER_NAMES,
    get_clustered_log_entries,
    get_current_log_level,
    get_persistent_log_dir,
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
    frontend_log_buffers: dict[str, list[FrontendLogEntry]] | None = None


@router.get(
    "/backend",
    summary="Download backend log buffer (without frontend logs)",
    description="Returns backend logs as plain text, or ZIP if persistent log files exist.",
)
async def download_backend_logs_get(request: Request) -> Response:
    """GET handler for backward compatibility (no frontend logs)."""
    return await _build_log_response(request, frontend_logs=[])


@router.post(
    "/backend",
    summary="Download backend + frontend logs",
    description="Returns backend + frontend logs as plain text, or ZIP if persistent log files exist.",
)
async def download_backend_logs_post(
    request: Request, body: LogDownloadRequest
) -> Response:
    """POST handler that accepts frontend logs in the request body."""
    return await _build_log_response(
        request,
        frontend_logs=body.frontend_logs,
        frontend_log_buffers=body.frontend_log_buffers,
    )


async def _build_log_response(
    request: Request,
    frontend_logs: list[FrontendLogEntry],
    frontend_log_buffers: dict[str, list[FrontendLogEntry]] | None = None,
) -> Response:
    log_dir = get_persistent_log_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    if log_dir and log_dir.exists():
        return await _build_zip_response(
            request, frontend_logs, log_dir, timestamp, frontend_log_buffers
        )
    return await _build_plaintext_response(
        request, frontend_logs, timestamp, frontend_log_buffers
    )


async def _build_plaintext_response(
    request: Request,
    frontend_logs: list[FrontendLogEntry],
    timestamp: str,
    frontend_log_buffers: dict[str, list[FrontendLogEntry]] | None = None,
) -> PlainTextResponse:
    content = _build_ram_buffer_text()
    content += _build_frontend_section(frontend_logs, frontend_log_buffers)
    content += await _build_audit_trail_section(request)

    filename = f"oct-backend-{timestamp}.log"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    logger.debug("Backend log download (plain text)")
    return PlainTextResponse(content=content, headers=headers)


async def _build_zip_response(
    request: Request,
    frontend_logs: list[FrontendLogEntry],
    log_dir: Path,
    timestamp: str,
    frontend_log_buffers: dict[str, list[FrontendLogEntry]] | None = None,
) -> Response:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add persistent cluster log files (including rotated backups)
        for log_file in sorted(log_dir.glob("*.log*")):
            if log_file.is_file():
                zf.write(str(log_file), f"logs/{log_file.name}")

        # Add in-memory ring buffer as ram-buffer.log
        ram_text = _build_ram_buffer_text()
        zf.writestr("ram-buffer.log", ram_text)

        # Add frontend logs — structured per domain if available
        if frontend_log_buffers:
            for domain, entries in frontend_log_buffers.items():
                if entries:
                    text = "".join(
                        f"[{e.timestamp}] {e.level}: {e.message}\n" for e in entries
                    )
                    zf.writestr(f"frontend-{domain}.log", text)
        elif frontend_logs:
            frontend_text = "".join(
                f"[{e.timestamp}] {e.level}: {e.message}\n" for e in frontend_logs
            )
            zf.writestr("frontend-console.log", frontend_text)

        # Add audit trail
        audit_text = await _build_audit_trail_section(request)
        zf.writestr("wizard-audit.log", audit_text)

    buf.seek(0)
    filename = f"oct-logs-{timestamp}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    logger.debug("Backend log download (ZIP with persistent logs)")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers=headers,
    )


def _build_ram_buffer_text() -> str:
    clusters = get_clustered_log_entries()
    total = sum(len(v) for v in clusters.values())

    content = "=" * 80
    content += f"\n BACKEND LOG BUFFER — CLUSTERED ({total} entries total)"
    content += "\n" + "=" * 80 + "\n"

    for cluster_name in CLUSTER_NAMES:
        entries = clusters.get(cluster_name, [])
        content += "\n" + "-" * 60
        content += f"\n [{cluster_name.upper()}] ({len(entries)} entries, max 1000)"
        content += "\n" + "-" * 60 + "\n"
        content += "\n".join(entries) if entries else "(empty)"
        content += "\n"

    return content


def _build_frontend_section(
    frontend_logs: list[FrontendLogEntry],
    frontend_log_buffers: dict[str, list[FrontendLogEntry]] | None = None,
) -> str:
    # If structured buffers are available, render per-domain sections
    if frontend_log_buffers:
        content = ""
        for domain, entries in frontend_log_buffers.items():
            content += "\n\n" + "=" * 80
            content += f"\n FRONTEND [{domain.upper()}] LOGS ({len(entries)} entries)"
            content += "\n" + "=" * 80 + "\n\n"
            if entries:
                content += "".join(
                    f"[{entry.timestamp}] {entry.level}: {entry.message}\n"
                    for entry in entries
                )
            else:
                content += "(empty)\n"
        return content

    # Fallback: flat list (legacy / bug report modal)
    content = "\n\n" + "=" * 80
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
    return content


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
