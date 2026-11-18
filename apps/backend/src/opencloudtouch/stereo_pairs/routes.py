"""OCT API for stereo pairs (called by the frontend)."""

from typing import List, Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from opencloudtouch.core.dependencies import StereoLifecycleDep
from opencloudtouch.stereo_pairs.lifecycle import STEP_KEYS

router = APIRouter(prefix="/api/stereo-pairs", tags=["Stereo pairs"])


class StereoPairMemberOut(BaseModel):
    device_id: str
    name: str
    role: str = Field(description="LEFT or RIGHT")
    reachable: bool


class StereoPairOut(BaseModel):
    id: int
    name: str
    status: str = Field(description="creating, active or degraded")
    source: str = Field(description="oct, or device for pairs created outside OCT")
    members: List[StereoPairMemberOut]
    warnings: List[str] = []


class CreateStereoPairRequest(BaseModel):
    left_device_id: str = Field(min_length=1)
    right_device_id: str = Field(min_length=1)
    name: Optional[str] = Field(default=None, max_length=100)


class OperationAccepted(BaseModel):
    operation_id: str


class OperationStep(BaseModel):
    key: str
    state: str = Field(description="waiting, running, done or failed")


class OperationError(BaseModel):
    code: str
    message: str


class OperationOut(BaseModel):
    state: str = Field(description="running, succeeded or failed")
    steps: List[OperationStep]
    pair: Optional[StereoPairOut] = None
    warnings: List[str] = []
    error: Optional[OperationError] = None


class RenameStereoPairRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.get("", response_model=List[StereoPairOut])
async def list_stereo_pairs(lifecycle: StereoLifecycleDep):
    return await lifecycle.list_pairs()


@router.post("", status_code=202, response_model=OperationAccepted)
async def create_stereo_pair(
    request: CreateStereoPairRequest, lifecycle: StereoLifecycleDep
):
    """Start creating a pair. Poll the operation; it can take up to a minute."""
    operation = lifecycle.start_create(
        request.left_device_id, request.right_device_id, request.name
    )
    return OperationAccepted(operation_id=operation.id)


@router.get("/operations/{operation_id}", response_model=OperationOut)
async def get_stereo_pair_operation(operation_id: str, lifecycle: StereoLifecycleDep):
    operation = lifecycle.get_operation(operation_id)
    return OperationOut(
        state=operation.state,
        steps=[OperationStep(key=k, state=operation.steps[k]) for k in STEP_KEYS],
        pair=(
            StereoPairOut.model_validate(await lifecycle.describe(operation.pair))
            if operation.pair
            else None
        ),
        warnings=operation.warnings,
        error=(
            OperationError(
                code=operation.error_code, message=operation.error_message or ""
            )
            if operation.error_code
            else None
        ),
    )


@router.patch("/{pair_id}", response_model=StereoPairOut)
async def rename_stereo_pair(
    pair_id: int, request: RenameStereoPairRequest, lifecycle: StereoLifecycleDep
):
    return await lifecycle.describe(await lifecycle.rename(pair_id, request.name))


@router.delete("/{pair_id}", status_code=204)
async def dissolve_stereo_pair(pair_id: int, lifecycle: StereoLifecycleDep):
    await lifecycle.dissolve(pair_id)
    return Response(status_code=204)


@router.post("/{pair_id}/repair", status_code=204)
async def repair_stereo_pair(pair_id: int, lifecycle: StereoLifecycleDep):
    """Run the removal on both speakers again so the pair ends clean."""
    await lifecycle.repair(pair_id)
    return Response(status_code=204)
