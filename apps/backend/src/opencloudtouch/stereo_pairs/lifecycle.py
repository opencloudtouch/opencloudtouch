"""Stereo pair lifecycle: create with verification and rollback, dissolve, rename.

Order of the create flow: the LEFT speaker (master) is asked first and persists
the group through Marge; its group id is then handed to the RIGHT speaker. Every
result is verified with a fresh ``getGroup`` read, never trusted from a mutation
response.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from opencloudtouch.core import error_codes as codes
from opencloudtouch.core.exceptions import CodedApiError
from opencloudtouch.devices.repository import Device, DeviceRepository
from opencloudtouch.stereo_pairs.group_client import (
    GROUP_ALREADY_EXISTS,
    GroupClient,
    GroupClientError,
    GroupState,
    SpeakerInfo,
)
from opencloudtouch.stereo_pairs.repository import StereoPair, StereoPairRepository
from opencloudtouch.stereo_pairs.service import StereoPairService

logger = logging.getLogger(__name__)

SUPPORTED_TYPE = "SoundTouch 10"
STEP_KEYS = ("preflight", "create_left", "create_right", "verify")
# The speaker retries its Marge call about every 15 s.
UNCERTAIN_RETRY_DELAYS: Sequence[float] = (15.0, 15.0, 15.0)
# A pair list must stay responsive when a speaker is switched off.
REACHABILITY_TIMEOUT = 2.0


def stereo_error(status: int, code: str, detail: str, **params) -> CodedApiError:
    return CodedApiError(status, code, detail, params=params or None)


@dataclass
class Operation:
    id: str
    state: str = "running"  # running | succeeded | failed
    steps: Dict[str, str] = field(
        default_factory=lambda: dict.fromkeys(STEP_KEYS, "waiting")
    )
    pair: Optional[StereoPair] = None
    warnings: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class _Member:
    device: Device
    info: SpeakerInfo
    client: GroupClient


class StereoPairLifecycle:
    def __init__(
        self,
        service: StereoPairService,
        repo: StereoPairRepository,
        device_repo: DeviceRepository,
        client_factory: Callable[[str], GroupClient],
        retry_delays: Sequence[float] = UNCERTAIN_RETRY_DELAYS,
    ):
        self._service = service
        self._repo = repo
        self._device_repo = device_repo
        self._factory = client_factory
        self._retry_delays = retry_delays
        self._lock = asyncio.Lock()
        self._operations: Dict[str, Operation] = {}
        self._tasks: set[asyncio.Task] = set()

    # ---- operations (asynchronous create) ----

    def start_create(
        self, left_id: str, right_id: str, name: Optional[str]
    ) -> Operation:
        if left_id == right_id:
            raise stereo_error(
                400, codes.STEREO_PAIR_INVALID_REQUEST, "LEFT and RIGHT must differ"
            )
        operation = Operation(uuid.uuid4().hex)
        self._operations[operation.id] = operation
        task = asyncio.create_task(self._run_create(operation, left_id, right_id, name))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return operation

    def get_operation(self, operation_id: str) -> Operation:
        operation = self._operations.get(operation_id)
        if operation is None:
            raise stereo_error(
                404, codes.STEREO_PAIR_OPERATION_NOT_FOUND, "Unknown operation"
            )
        return operation

    async def _run_create(
        self, op: Operation, left_id: str, right_id: str, name: Optional[str]
    ):
        try:
            async with self._lock:
                op.pair = await self.create(left_id, right_id, name, op)
            op.state = "succeeded"
        except CodedApiError as exc:
            op.state = "failed"
            op.error_code, op.error_message = exc.code, exc.detail
        except Exception:  # noqa: BLE001 - an operation must always end
            logger.exception("[STEREO] Unexpected error during create")
            op.state = "failed"
            op.error_code = codes.INTERNAL_ERROR
            op.error_message = "Unexpected error while creating the stereo pair"
        for key, state in op.steps.items():
            if state == "running":
                op.steps[key] = "failed"

    # ---- create ----

    async def _preflight_member(self, device_id: str, other_id: str) -> _Member:
        device = await self._device_repo.get_by_device_id(device_id)
        if device is None:
            raise stereo_error(
                404, codes.DEVICE_NOT_FOUND, f"Device {device_id} is unknown"
            )
        client = self._factory(device.ip)
        try:
            info = await client.get_info()
            group = await client.get_group()
            zone_ids = await client.get_zone_member_ids()
        except GroupClientError as exc:
            raise stereo_error(
                502, codes.STEREO_PAIR_DEVICE_UNREACHABLE, str(exc), device_id=device_id
            ) from exc
        if info.device_id != device.device_id:
            raise stereo_error(
                409,
                codes.STEREO_PAIR_DEVICE_UNREACHABLE,
                "Speaker identity does not match the OCT record",
                device_id=device_id,
            )
        if info.type != SUPPORTED_TYPE or not info.lr_stereo_capable:
            raise stereo_error(
                409,
                codes.STEREO_PAIR_DEVICE_NOT_CAPABLE,
                f"{device.name} cannot form a stereo pair",
                device_id=device_id,
            )
        if not info.marge_account_uuid:
            raise stereo_error(
                409,
                codes.STEREO_PAIR_DEVICE_NOT_PROVISIONED,
                f"{device.name} is not set up with OCT",
                device_id=device_id,
            )
        if group is not None or await self._repo.get_by_device(device_id) is not None:
            raise stereo_error(
                409,
                codes.STEREO_PAIR_DEVICE_IN_PAIR,
                f"{device.name} is already in a stereo pair",
                device_id=device_id,
            )
        if zone_ids and set(zone_ids) != {device_id, other_id}:
            raise stereo_error(
                409,
                codes.STEREO_PAIR_DEVICE_IN_ZONE,
                f"{device.name} is part of a zone",
                device_id=device_id,
            )
        return _Member(device, info, client)

    async def create(
        self,
        left_id: str,
        right_id: str,
        name: Optional[str],
        op: Optional[Operation] = None,
    ) -> StereoPair:
        op = op or Operation(uuid.uuid4().hex)

        def step(key: str, state: str) -> None:
            op.steps[key] = state

        step("preflight", "running")
        left = await self._preflight_member(left_id, right_id)
        right = await self._preflight_member(right_id, left_id)
        if left.info.firmware != right.info.firmware:
            op.warnings.append("firmware_mismatch")
        pair_name = name or f"{left.device.name} + {right.device.name}"
        step("preflight", "done")

        roles = {
            left_id: ("LEFT", left.device.ip),
            right_id: ("RIGHT", right.device.ip),
        }
        self._service.expect_create(left_id)
        try:
            step("create_left", "running")
            await self._add_group(
                left, pair_name, left_id, roles, expected_master=left_id
            )
            row = await self._repo.get_by_device(left_id)
            if row is None:
                raise stereo_error(
                    502,
                    codes.STEREO_PAIR_MARGE_FAILED,
                    "The speaker did not register the group with OCT",
                )
            step("create_left", "done")

            step("create_right", "running")
            await self._add_group(
                right,
                pair_name,
                left_id,
                roles,
                expected_master=left_id,
                group_id=str(row.id),
                sender_ip=left.device.ip,
            )
            step("create_right", "done")

            step("verify", "running")
            await self._verify(left, right, row.id)
            await self._repo.set_status(row.id, "active")
            step("verify", "done")
        except CodedApiError as exc:
            await self._compensate(left, right, exc)
            raise
        finally:
            self._service.clear_intent(left_id)
        created = await self._repo.get(row.id)
        assert created is not None
        return created

    async def _add_group(
        self,
        member: _Member,
        name: str,
        master_id: str,
        roles,
        *,
        expected_master: str,
        group_id: Optional[str] = None,
        sender_ip: Optional[str] = None,
    ) -> None:
        try:
            await member.client.add_group(
                name, master_id, roles, group_id=group_id, sender_ip=sender_ip
            )
            return
        except GroupClientError as exc:
            already_there = exc.code == GROUP_ALREADY_EXISTS
            # the master may already have handed the group to the slave (5510):
            # then re-reading the group below confirms it
            if not exc.uncertain and exc.code != GROUP_ALREADY_EXISTS:
                raise stereo_error(
                    502,
                    codes.STEREO_PAIR_MARGE_FAILED,
                    "The speakers did not accept the pairing; check that both are set up with OCT",
                    device_error=exc.code,
                ) from exc
            logger.warning(
                "[STEREO] addGroup outcome uncertain on %s: %s", member.device.ip, exc
            )
        # uncertain outcome: the speaker may still have applied it, look again
        # 5510 means the group is already there: look right away, then wait between tries
        delays = (0, *self._retry_delays) if already_there else self._retry_delays
        for delay in delays:
            await asyncio.sleep(delay)
            try:
                group = await member.client.get_group()
            except GroupClientError:
                continue
            if group is not None and group.master_id == expected_master:
                return
        raise stereo_error(
            502,
            codes.STEREO_PAIR_MARGE_FAILED,
            "The speaker did not confirm the pairing in time",
        )

    async def _verify(self, left: _Member, right: _Member, group_id: int) -> None:
        expected_roles = {
            left.device.device_id: "LEFT",
            right.device.device_id: "RIGHT",
        }
        for member in (left, right):
            try:
                group = await member.client.get_group()
            except GroupClientError as exc:
                raise stereo_error(
                    502, codes.STEREO_PAIR_VERIFICATION_FAILED, str(exc)
                ) from exc
            if (
                group is None
                or group.id != str(group_id)
                or group.master_id != left.device.device_id
                or group.roles != expected_roles
            ):
                raise stereo_error(
                    502,
                    codes.STEREO_PAIR_VERIFICATION_FAILED,
                    f"{member.device.name} does not report the expected group",
                )

    async def _compensate(
        self, left: _Member, right: _Member, cause: CodedApiError
    ) -> None:
        """Undo a failed create. Nothing may remain half-paired."""
        clean = True
        for member in (left, right):
            try:
                await member.client.remove_group()
                if await member.client.get_group() is not None:
                    clean = False
            except GroupClientError:
                clean = False
        row = await self._repo.get_by_device(left.device.device_id)
        if row is not None:
            if clean:
                await self._repo.delete(row.id)
            else:
                await self._repo.set_status(row.id, "degraded")
        if not clean:
            cause.code = codes.STEREO_PAIR_DEGRADED
            cause.detail = (
                "The pairing failed and could not be fully undone; repair the pair"
            )
            cause.title = None

    # ---- dissolve / repair / rename ----

    async def _members_of(
        self, pair: StereoPair
    ) -> List[tuple[str, Optional[GroupClient]]]:
        members: List[tuple[str, Optional[GroupClient]]] = []
        for device_id in (pair.left_device_id, pair.right_device_id):
            device = await self._device_repo.get_by_device_id(device_id)
            members.append((device_id, self._factory(device.ip) if device else None))
        return members

    async def dissolve(self, pair_id: int) -> None:
        """Remove the group on both speakers and verify; idempotent and retry-safe."""
        pair = await self._repo.get(pair_id)
        if pair is None:
            raise stereo_error(
                404, codes.STEREO_PAIR_NOT_FOUND, "Stereo pair not found"
            )
        async with self._lock:
            problems: List[str] = []
            for device_id, client in await self._members_of(pair):
                if client is None:
                    problems.append(device_id)
                    continue
                try:
                    await client.remove_group()
                    if await client.get_group() is not None:
                        problems.append(device_id)
                except GroupClientError:
                    problems.append(device_id)
            if problems:
                await self._repo.set_status(pair_id, "degraded")
                raise stereo_error(
                    502,
                    codes.STEREO_PAIR_DEGRADED,
                    "Not every speaker confirmed the removal; try again when both are online",
                    device_ids=problems,
                )
            await self._repo.dissolve(pair_id)

    repair = dissolve  # repair means: end in a clean standalone state

    async def rename(self, pair_id: int, name: str) -> StereoPair:
        name = name.strip()
        if not name:
            raise stereo_error(
                400, codes.STEREO_PAIR_INVALID_REQUEST, "Name must not be empty"
            )
        pair = await self._repo.get(pair_id)
        if pair is None:
            raise stereo_error(
                404, codes.STEREO_PAIR_NOT_FOUND, "Stereo pair not found"
            )
        async with self._lock:
            master = next(
                (
                    c
                    for d, c in await self._members_of(pair)
                    if d == pair.master_device_id
                ),
                None,
            )
            if master is None:
                raise stereo_error(
                    502, codes.STEREO_PAIR_DEVICE_UNREACHABLE, "Master is unknown"
                )
            roles: Dict[str, tuple[str, str]] = {}
            for device_id, role in (
                (pair.left_device_id, "LEFT"),
                (pair.right_device_id, "RIGHT"),
            ):
                device = await self._device_repo.get_by_device_id(device_id)
                if device is None:
                    raise stereo_error(
                        502, codes.STEREO_PAIR_DEVICE_UNREACHABLE, "Member is unknown"
                    )
                roles[device_id] = (role, device.ip)
            try:
                await master.update_group(
                    name, pair.master_device_id, roles, str(pair.id)
                )
                group: Optional[GroupState] = await master.get_group()
            except GroupClientError as exc:
                raise stereo_error(
                    502, codes.STEREO_PAIR_DEVICE_UNREACHABLE, str(exc)
                ) from exc
            if group is None or group.name != name:
                raise stereo_error(
                    502,
                    codes.STEREO_PAIR_VERIFICATION_FAILED,
                    "The speaker did not apply the new name",
                )
            await self._repo.rename(pair_id, name)
        renamed = await self._repo.get(pair_id)
        assert renamed is not None
        return renamed

    # ---- read model ----

    async def describe(self, pair: StereoPair) -> dict:
        """Pair as the API shows it: members with name, role and reachability."""

        async def member(device_id: str, role: str) -> dict:
            device = await self._device_repo.get_by_device_id(device_id)
            reachable = False
            if device is not None:
                try:
                    await asyncio.wait_for(
                        self._factory(device.ip).get_info(), REACHABILITY_TIMEOUT
                    )
                    reachable = True
                except (GroupClientError, asyncio.TimeoutError):
                    reachable = False
            return {
                "device_id": device_id,
                "name": device.name if device else device_id,
                "role": role,
                "reachable": reachable,
            }

        members = await asyncio.gather(
            member(pair.left_device_id, "LEFT"), member(pair.right_device_id, "RIGHT")
        )
        return {
            "id": pair.id,
            "name": pair.name,
            "status": "creating" if pair.status == "pending" else pair.status,
            "source": pair.source,
            "members": list(members),
            "warnings": [],
        }

    async def list_pairs(self) -> List[dict]:
        return [await self.describe(p) for p in await self._repo.list_active()]
