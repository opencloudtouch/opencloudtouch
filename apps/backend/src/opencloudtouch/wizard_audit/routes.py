"""Wizard audit log API routes.

Provides endpoints for:
- POST /api/wizard/audit-log          – receive audit entries from frontend
- POST /api/wizard/audit-log/batch    – receive multiple entries at once
- GET  /api/wizard/audit-log          – retrieve entries (for download)
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from opencloudtouch.wizard_audit.repository import WizardAuditRepository

logger = logging.getLogger(__name__)

audit_router = APIRouter(prefix="/api/wizard", tags=["Wizard Audit"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AuditEntryRequest(BaseModel):
    """Single wizard audit log entry from the frontend."""

    device_id: str = Field(..., description="Device MAC/ID")
    category: str = Field(
        ...,
        description="Event category: user_action, device_info, api_call, config_change, step_transition, checkbox, dropdown, error",
    )
    event: str = Field(..., description="Short event name, e.g. 'button_click:next'")
    step: Optional[int] = Field(
        None, ge=0, le=7, description="Wizard step number (0=init)"
    )
    detail: Optional[str] = Field(
        None,
        max_length=10_000,
        description="JSON-encoded extra data (free-form)",
    )
    timestamp: Optional[str] = Field(
        None, description="ISO-8601 timestamp from frontend"
    )


class AuditBatchRequest(BaseModel):
    """Batch of audit entries (reduces HTTP roundtrips)."""

    entries: list[AuditEntryRequest] = Field(..., min_length=1, max_length=200)


class AuditEntryResponse(BaseModel):
    """Response for single entry creation."""

    success: bool
    id: int


class AuditBatchResponse(BaseModel):
    """Response for batch creation."""

    success: bool
    count: int


class ConfigSnapshotRequest(BaseModel):
    """Request to store a config XML snapshot."""

    device_id: str
    file_path: str = Field(..., description="Config file path on device")
    content: str = Field(..., max_length=50_000, description="Full XML content")
    trigger: Optional[str] = Field(
        None, description="What caused the snapshot, e.g. 'before_modify'"
    )
    timestamp: Optional[str] = None


class ConfigSnapshotResponse(BaseModel):
    """Response for snapshot creation."""

    success: bool
    id: int


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def _get_audit_repo(request: Request):
    """Get wizard audit repository from app.state."""
    repo = getattr(request.app.state, "wizard_audit_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=503, detail="Wizard audit repository not initialized"
        )
    return repo


AuditRepo = Annotated[WizardAuditRepository, Depends(_get_audit_repo)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@audit_router.post("/audit-log", response_model=AuditEntryResponse)
async def post_audit_entry(entry: AuditEntryRequest, repo: AuditRepo):
    """Record a single wizard audit log entry."""
    row_id = await repo.add_entry(
        device_id=entry.device_id,
        category=entry.category,
        event=entry.event,
        step=entry.step,
        detail=entry.detail,
        timestamp=entry.timestamp,
    )
    logger.debug(
        "[WIZARD AUDIT] %s | step=%s | %s: %s",
        entry.device_id,
        entry.step,
        entry.category,
        entry.event,
    )
    return AuditEntryResponse(success=True, id=row_id)


@audit_router.post("/audit-log/batch", response_model=AuditBatchResponse)
async def post_audit_batch(batch: AuditBatchRequest, repo: AuditRepo):
    """Record multiple wizard audit log entries in one request."""
    entries_dicts = [e.model_dump() for e in batch.entries]
    count = await repo.add_batch(entries_dicts)
    logger.debug("[WIZARD AUDIT] Batch: %d entries received", count)
    return AuditBatchResponse(success=True, count=count)


@audit_router.post("/config-snapshot", response_model=ConfigSnapshotResponse)
async def post_config_snapshot(snapshot: ConfigSnapshotRequest, repo: AuditRepo):
    """Store a config XML snapshot."""
    row_id = await repo.add_config_snapshot(
        device_id=snapshot.device_id,
        file_path=snapshot.file_path,
        content=snapshot.content,
        trigger=snapshot.trigger,
        timestamp=snapshot.timestamp,
    )
    logger.debug(
        "[WIZARD AUDIT] Config snapshot: %s %s (%d bytes)",
        snapshot.device_id,
        snapshot.file_path,
        len(snapshot.content),
    )
    return ConfigSnapshotResponse(success=True, id=row_id)
