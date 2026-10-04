import asyncio

from fastapi import APIRouter, HTTPException

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
    set_update_status,
)


router = APIRouter(prefix="/api/system", tags=["System"])

_ACTIVE_PHASES = {
    "pulling",
    "restarting",
    "rolling_back",
}

_update_lock = asyncio.Lock()


@router.get("/check-update")
async def check_update():
    try:
        return await check_for_update()
    except UpdateCheckError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/update-status")
async def update_status():
    return get_update_status()


@router.post("/update")
async def update():
    if _update_lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Update already in progress",
        )

    async with _update_lock:
        existing_status = get_update_status()

        if existing_status.get("phase") in _ACTIVE_PHASES:
            raise HTTPException(
                status_code=409,
                detail="Update already in progress",
            )

        try:
            update_info = await check_for_update()

            if not update_info["update_available"]:
                raise HTTPException(
                    status_code=409,
                    detail="No update available",
                )

            target_version = update_info["latest"]
            current_version = update_info["current"]
            target_image = target_image_for_version(
                target_version
            )

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
            set_update_status(
                "failed",
                progress_pct=0,
                message="Update failed",
                error=str(exc),
            )

            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc
