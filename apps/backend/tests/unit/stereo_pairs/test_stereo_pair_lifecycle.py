"""Unit tests for StereoPairLifecycle using in-memory speakers."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from opencloudtouch.core import error_codes as codes
from opencloudtouch.core.exceptions import CodedApiError
from opencloudtouch.stereo_pairs.group_client import GroupClientError
from opencloudtouch.stereo_pairs.lifecycle import StereoPairLifecycle
from opencloudtouch.stereo_pairs.mock_group_client import InMemorySpeakerNetwork
from opencloudtouch.stereo_pairs.repository import StereoPairRepository
from opencloudtouch.stereo_pairs.service import StereoPairService

L_IP, R_IP = "10.0.0.1", "10.0.0.2"
MARGE_ERROR = GroupClientError(
    "addGroup failed", code="GROUP_CREATE_GROUP_ON_MARGE_ERROR"
)


@pytest.fixture
async def repo(tmp_path):
    repository = StereoPairRepository(str(tmp_path / "pairs.db"))
    await repository.initialize()
    yield repository
    await repository.close()


@pytest.fixture
def network():
    net = InMemorySpeakerNetwork()
    net.add(L_IP, "L1", name="Office left")
    net.add(R_IP, "R1", name="Office right")
    return net


@pytest.fixture
def lifecycle(repo, network):
    devices = {
        "L1": SimpleNamespace(device_id="L1", ip=L_IP, name="Office left"),
        "R1": SimpleNamespace(device_id="R1", ip=R_IP, name="Office right"),
    }
    device_repo = AsyncMock()
    device_repo.get_by_device_id.side_effect = devices.get
    service = StereoPairService(repo, device_repo)
    network.service = service
    return StereoPairLifecycle(
        service, repo, device_repo, network.client, retry_delays=(0, 0)
    )


async def _create(lifecycle):
    return await lifecycle.create("L1", "R1", None)


@pytest.mark.asyncio
class TestCreate:
    async def test_happy_path(self, lifecycle, network, repo):
        pair = await _create(lifecycle)

        assert (pair.status, pair.source) == ("active", "oct")
        assert pair.name == "Office left + Office right"
        left, right = network.speakers[L_IP].group, network.speakers[R_IP].group
        assert left.id == right.id == str(pair.id)
        assert left.master_id == "L1"
        assert left.roles == {"L1": "LEFT", "R1": "RIGHT"}
        assert (await repo.get_by_device("R1")).id == pair.id

    async def test_left_is_asked_first_and_right_gets_the_group_id(
        self, lifecycle, network
    ):
        await _create(lifecycle)

        assert network.speakers[L_IP].calls.index("add_group") >= 0
        assert "add_group" in network.speakers[R_IP].calls

    async def test_operation_reports_steps(self, lifecycle):
        operation = lifecycle.start_create("L1", "R1", "Office")
        await next(iter(lifecycle._tasks))

        assert operation.state == "succeeded"
        assert set(operation.steps.values()) == {"done"}
        assert operation.pair.name == "Office"

    async def test_firmware_mismatch_is_only_a_warning(self, lifecycle, network):
        network.speakers[R_IP].info.firmware = "27.0.9"
        operation = lifecycle.start_create("L1", "R1", None)
        await next(iter(lifecycle._tasks))

        assert operation.state == "succeeded"
        assert operation.warnings == ["firmware_mismatch"]

    async def test_zone_of_exactly_the_two_candidates_is_allowed(
        self, lifecycle, network
    ):
        network.speakers[L_IP].zone_ids = ["L1", "R1"]
        network.speakers[R_IP].zone_ids = ["L1", "R1"]

        assert (await _create(lifecycle)).status == "active"

    @pytest.mark.parametrize(
        "setup, code",
        [
            (
                lambda n: setattr(n.speakers[R_IP].info, "type", "SoundTouch 20"),
                codes.STEREO_PAIR_DEVICE_NOT_CAPABLE,
            ),
            (
                lambda n: setattr(n.speakers[R_IP].info, "lr_stereo_capable", False),
                codes.STEREO_PAIR_DEVICE_NOT_CAPABLE,
            ),
            (
                lambda n: setattr(n.speakers[L_IP].info, "marge_account_uuid", ""),
                codes.STEREO_PAIR_DEVICE_NOT_PROVISIONED,
            ),
            (
                lambda n: setattr(n.speakers[R_IP], "zone_ids", ["R1", "OTHER"]),
                codes.STEREO_PAIR_DEVICE_IN_ZONE,
            ),
            (
                lambda n: setattr(n.speakers[R_IP], "reachable", False),
                codes.STEREO_PAIR_DEVICE_UNREACHABLE,
            ),
        ],
    )
    async def test_preflight_failures_change_nothing(
        self, lifecycle, network, repo, setup, code
    ):
        setup(network)

        with pytest.raises(CodedApiError) as raised:
            await _create(lifecycle)

        assert raised.value.code == code
        assert network.speakers[L_IP].group is None
        assert "add_group" not in network.speakers[L_IP].calls
        assert await repo.list_active() == []

    async def test_device_already_in_a_group_is_rejected(self, lifecycle, network):
        await _create(lifecycle)

        with pytest.raises(CodedApiError) as raised:
            await _create(lifecycle)

        assert raised.value.code == codes.STEREO_PAIR_DEVICE_IN_PAIR

    async def test_unknown_device(self, lifecycle):
        with pytest.raises(CodedApiError) as raised:
            await lifecycle.create("L1", "NOPE", None)

        assert raised.value.code == codes.DEVICE_NOT_FOUND

    async def test_marge_failure_on_master_leaves_nothing_behind(
        self, lifecycle, network, repo
    ):
        network.speakers[L_IP].add_group_errors = [MARGE_ERROR]

        with pytest.raises(CodedApiError) as raised:
            await _create(lifecycle)

        assert raised.value.code == codes.STEREO_PAIR_MARGE_FAILED
        assert network.speakers[L_IP].group is None
        assert network.speakers[R_IP].group is None
        assert await repo.list_active() == []

    async def test_failure_on_slave_rolls_back_the_master(
        self, lifecycle, network, repo
    ):
        network.speakers[R_IP].add_group_errors = [MARGE_ERROR]

        with pytest.raises(CodedApiError) as raised:
            await _create(lifecycle)

        assert raised.value.code == codes.STEREO_PAIR_MARGE_FAILED
        assert network.speakers[L_IP].group is None
        assert network.speakers[R_IP].group is None
        assert await repo.list_active() == []
        assert await repo.get_by_device("L1") is None

    async def test_slave_already_in_the_group_counts_as_created(
        self, lifecycle, network
    ):
        # seen on hardware: the master hands the group to the slave itself, so
        # the explicit slave call is answered with 5510 GROUP_ALREADY_EXISTS_ERROR
        speaker = network.speakers[R_IP]
        speaker.add_group_errors = [
            GroupClientError("exists", code="GROUP_ALREADY_EXISTS_ERROR")
        ]
        speaker.apply_before_error = True

        assert (await _create(lifecycle)).status == "active"

    async def test_slave_already_in_the_group_is_confirmed_without_waiting(
        self, lifecycle, network
    ):
        lifecycle._retry_delays = (60,)  # a wait here would blow the timeout
        speaker = network.speakers[R_IP]
        speaker.add_group_errors = [
            GroupClientError("exists", code="GROUP_ALREADY_EXISTS_ERROR")
        ]
        speaker.apply_before_error = True

        pair = await asyncio.wait_for(_create(lifecycle), timeout=5)

        assert pair.status == "active"

    async def test_already_exists_without_the_group_still_fails(
        self, lifecycle, network
    ):
        network.speakers[R_IP].add_group_errors = [
            GroupClientError("exists", code="GROUP_ALREADY_EXISTS_ERROR")
        ]

        with pytest.raises(CodedApiError):
            await _create(lifecycle)

    async def test_uncertain_timeout_is_resolved_by_rereading_the_group(
        self, lifecycle, network
    ):
        speaker = network.speakers[L_IP]
        speaker.add_group_errors = [GroupClientError("timeout", uncertain=True)]
        speaker.apply_before_error = True

        assert (await _create(lifecycle)).status == "active"

    async def test_uncertain_without_effect_fails_and_is_clean(
        self, lifecycle, network, repo
    ):
        network.speakers[L_IP].add_group_errors = [
            GroupClientError("timeout", uncertain=True)
        ]

        with pytest.raises(CodedApiError) as raised:
            await _create(lifecycle)

        assert raised.value.code == codes.STEREO_PAIR_MARGE_FAILED
        assert await repo.list_active() == []

    async def test_failed_rollback_is_reported_as_degraded(
        self, lifecycle, network, repo
    ):
        network.speakers[R_IP].add_group_errors = [MARGE_ERROR]
        network.speakers[L_IP].remove_group_errors = [
            GroupClientError("gone", uncertain=True)
        ]

        with pytest.raises(CodedApiError) as raised:
            await _create(lifecycle)

        assert raised.value.code == codes.STEREO_PAIR_DEGRADED
        row = await repo.get_by_device("L1")
        assert row is not None
        assert row.status == "degraded"

    async def test_same_device_twice_is_invalid(self, lifecycle):
        with pytest.raises(CodedApiError) as raised:
            lifecycle.start_create("L1", "L1", None)

        assert raised.value.code == codes.STEREO_PAIR_INVALID_REQUEST


@pytest.mark.asyncio
class TestDissolveAndRename:
    async def test_dissolve(self, lifecycle, network, repo):
        pair = await _create(lifecycle)

        await lifecycle.dissolve(pair.id)

        assert network.speakers[L_IP].group is None
        assert network.speakers[R_IP].group is None
        assert await repo.get(pair.id) is None

    async def test_dissolve_with_offline_member_is_degraded_then_retry_succeeds(
        self, lifecycle, network, repo
    ):
        pair = await _create(lifecycle)
        network.speakers[R_IP].reachable = False

        with pytest.raises(CodedApiError) as raised:
            await lifecycle.dissolve(pair.id)

        assert raised.value.code == codes.STEREO_PAIR_DEGRADED
        assert (await repo.get(pair.id)).status == "degraded"
        assert network.speakers[L_IP].group is None

        network.speakers[R_IP].reachable = True
        await lifecycle.repair(pair.id)
        assert network.speakers[R_IP].group is None
        assert await repo.get(pair.id) is None

    async def test_dissolve_unknown_pair(self, lifecycle):
        with pytest.raises(CodedApiError) as raised:
            await lifecycle.dissolve(999)

        assert raised.value.code == codes.STEREO_PAIR_NOT_FOUND

    async def test_rename(self, lifecycle, network):
        pair = await _create(lifecycle)

        renamed = await lifecycle.rename(pair.id, " Living room ")

        assert renamed.name == "Living room"
        assert network.speakers[L_IP].group.name == "Living room"

    async def test_rename_sends_the_group_id_and_both_roles_with_ips(
        self, lifecycle, network
    ):
        pair = await _create(lifecycle)

        await lifecycle.rename(pair.id, "Living room")

        name, master_id, roles, group_id = network.speakers[L_IP].updates[-1]
        assert (name, master_id, group_id) == ("Living room", "L1", str(pair.id))
        assert roles == {"L1": ("LEFT", L_IP), "R1": ("RIGHT", R_IP)}

    async def test_rename_rejects_empty_name_and_unknown_pair(self, lifecycle):
        pair = await _create(lifecycle)
        with pytest.raises(CodedApiError):
            await lifecycle.rename(pair.id, "  ")
        with pytest.raises(CodedApiError) as raised:
            await lifecycle.rename(999, "x")
        assert raised.value.code == codes.STEREO_PAIR_NOT_FOUND


@pytest.mark.asyncio
async def test_pair_list_stays_responsive_when_a_speaker_hangs(
    lifecycle, network, monkeypatch
):
    """A switched-off speaker must not block the list for the full HTTP timeout."""
    import asyncio

    from opencloudtouch.stereo_pairs import lifecycle as lifecycle_module

    pair = await _create(lifecycle)
    monkeypatch.setattr(lifecycle_module, "REACHABILITY_TIMEOUT", 0.05)

    async def hang():
        await asyncio.sleep(5)

    network.speakers[R_IP].reachable = True
    client = network.client(R_IP)
    monkeypatch.setattr(type(client), "get_info", lambda self: hang())

    described = await asyncio.wait_for(lifecycle.describe(pair), 1.0)

    assert all(member["reachable"] is False for member in described["members"])
