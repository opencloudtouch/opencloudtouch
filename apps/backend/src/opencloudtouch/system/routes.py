import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from opencloudtouch.system.update_service import (
    UpdateCheckError,
    check_for_update,
    get_oct_container,
    launch_update_helper,
    pull_oct_image,
    target_image_for_version,
)
from opencloudtouch.system.update_state import (
    get_update_status,
    is_active_status_fresh,
    set_update_status,
)

router = APIRouter(prefix="/api/system", tags=["System"])
logger = logging.getLogger(__name__)

_update_lock = asyncio.Lock()


class UpdateRequest(BaseModel):
    target_version: str


class UpdateCheckResponse(BaseModel):
    current: str
    latest: str
    update_available: bool
    release_url: str
    self_update_enabled: bool
    self_update_reason: str | None


class UpdateAcceptedResponse(BaseModel):
    accepted: bool
    target_version: str


class UpdateStatusResponse(BaseModel):
    phase: str
    progress_pct: int
    message: str
    target_version: str | None = None
    current_version: str
    updated_at: str | None = None
    error: str | None = None
    rollback_error: str | None = None
    container_id: str | None = None
    image: str | None = None


@router.get(
    "/check-update",
    response_model=UpdateCheckResponse,
    responses={503: {"description": "Release check unavailable"}},
)
async def check_update():
    try:
        return await check_for_update()
    except UpdateCheckError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/update-status", response_model=UpdateStatusResponse)
async def update_status():
    return get_update_status()


@router.post(
    "/update",
    response_model=UpdateAcceptedResponse,
    status_code=202,
    responses={
        404: {"description": "OpenCloudTouch container not found"},
        409: {"description": "Update conflict or confirmation mismatch"},
        503: {"description": "Update service unavailable"},
    },
)
async def update(request: UpdateRequest):
    if _update_lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Update already in progress",
        )

    async with _update_lock:
        existing_status = get_update_status()

        if is_active_status_fresh(existing_status):
            raise HTTPException(
                status_code=409,
                detail="Update already in progress",
            )

        if existing_status.get("phase") in {"pulling", "restarting", "rolling_back"}:
            logger.warning(
                "Ignoring stale self-update state",
                extra={"update_phase": existing_status.get("phase")},
            )

        try:
            update_info = await check_for_update()

            if not update_info.get("self_update_enabled", True):
                raise HTTPException(
                    status_code=503,
                    detail=update_info.get("self_update_reason")
                    or "Self-update is disabled",
                )

            if not update_info["update_available"]:
                raise HTTPException(
                    status_code=409,
                    detail="No update available",
                )

            if request.target_version != update_info["latest"]:
                raise HTTPException(
                    status_code=409,
                    detail="Requested target version is not the latest available release",
                )

            target_version = update_info["latest"]
            current_version = update_info["current"]
            target_image = target_image_for_version(target_version)

            container = await get_oct_container()

            if container is None:
                raise HTTPException(
                    status_code=404,
                    detail="OpenCloudTouch container not found",
                )

            set_update_status(
                "pulling",
                progress_pct=5,
                message="Preparing image download",
                target_version=target_version,
                current_version=current_version,
            )

            def report_progress(
                progress_pct: int,
                message: str,
            ) -> None:
                set_update_status(
                    "pulling",
                    progress_pct=progress_pct,
                    message=message,
                    target_version=target_version,
                    current_version=current_version,
                )

            await pull_oct_image(
                target_image,
                report_progress,
            )

            set_update_status(
                "restarting",
                progress_pct=95,
                message="Restarting OpenCloudTouch",
                target_version=target_version,
                current_version=current_version,
            )

            await launch_update_helper(
                container["Id"],
                target_image,
            )

            return {
                "accepted": True,
                "target_version": target_version,
            }

        except HTTPException:
            raise

        except Exception as exc:
            logger.exception("Self-update failed before helper handoff")
            try:
                set_update_status(
                    "failed",
                    progress_pct=0,
                    message="Update failed",
                    error=str(exc),
                )
            except Exception:
                logger.exception("Failed to persist self-update failure status")

            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc
