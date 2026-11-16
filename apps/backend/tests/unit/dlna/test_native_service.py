"""DlnaNativeService: state table, enable, disable (AC-B1..B10)."""

import asyncio
from types import SimpleNamespace

import pytest

from opencloudtouch.core import error_codes
from opencloudtouch.core.exceptions import (
    CodedApiError,
    DeviceConnectionError,
    DeviceNotFoundError,
)
from opencloudtouch.devices.client import SpeakerCommandError, SpeakerSource
from opencloudtouch.dlna.models import DlnaServer
from opencloudtouch.dlna.native_service import DlnaNativeService, NativeState
from opencloudtouch.marge.source_repository import MargeSourceRepository
from opencloudtouch.presets.models import Preset

DEV = "DEV1"
SID = "5f9ec1b3-ed59-4f22-9c2e-1d3a7b8c4e01"
SID2 = "6a0fd2c4-fe6a-4033-8d3f-2e4b8c9d5f02"
ACCOUNT = f"{SID}/0"
STALE = "7b1ae3d5-0f7b-4144-9e40-3f5c9dae6a03"


class FakeSpeaker:
    """Shared in-memory speaker; ``client()`` hands out per-call clients."""

    def __init__(self, store):
        self.store = store
        self.sources: dict[str, str] = {}
        self.calls: list[tuple] = []
        self.provider_id = 7
        self.set_error: int | None = None
        self.remove_error: int | None = None
        self.unreachable = False
        self.callback = True  # speaker calls Marge during setMusicServiceAccount
        self.callback_after: float | None = None  # ... or this long after it returned
        self.list_after_set = (
            "READY"  # status the account shows afterwards (None: absent)
        )
        self.remove_keeps_listed = False
        self.stored: list[dict] = []
        self.store_error = False

    def client(self):
        return FakeClient(self)


class FakeClient:
    def __init__(self, speaker: FakeSpeaker):
        self.s = speaker

    async def get_source_list(self):
        if self.s.unreachable:
            raise DeviceConnectionError("dev", "down")
        return [
            SpeakerSource("STORED_MUSIC", a, st) for a, st in self.s.sources.items()
        ]

    async def set_music_service_account(self, source, display_name, user):
        self.s.calls.append(("set", user))
        if self.s.set_error:
            raise SpeakerCommandError(self.s.set_error)
        server_id = user.split("/")[0]
        if self.s.callback:
            await self.s.store.upsert(DEV, server_id, display_name, self.s.provider_id)
        if self.s.callback_after is not None:

            async def late():
                await asyncio.sleep(self.s.callback_after)
                await self.s.store.upsert(
                    DEV, server_id, display_name, self.s.provider_id
                )

            self.s.late_task = asyncio.create_task(late())
        if self.s.list_after_set:
            self.s.sources[user] = self.s.list_after_set

    async def remove_music_service_account(self, source, display_name, user):
        self.s.calls.append(("remove", user))
        if self.s.remove_error:
            raise SpeakerCommandError(self.s.remove_error)
        if not self.s.remove_keeps_listed:
            self.s.sources.pop(user, None)

    async def store_preset(self, **kwargs):
        if self.s.store_error:
            raise DeviceConnectionError("dev", "down")
        self.s.stored.append(kwargs)

    async def close(self):
        pass


class FakeDevices:
    def __init__(self, known=True):
        self.known = known

    async def get_by_device_id(self, device_id):
        return (
            SimpleNamespace(device_id=device_id, ip="10.0.0.9") if self.known else None
        )


class FakeDlna:
    def __init__(self, servers):
        self.servers = servers

    async def list_servers(self):
        return self.servers


class FakePresets:
    def __init__(self, presets=()):
        self.presets = list(presets)

    async def get_all_presets(self, device_id):
        return [p for p in self.presets if p.device_id == device_id]

    async def set_preset(self, preset):
        return preset


def native_preset(number, server_id=SID, object_id="folder1"):
    return Preset(
        device_id=DEV,
        preset_number=number,
        station_uuid=f"dlna-{number}",
        station_name=f"Folder {number}",
        station_url=f"dlna://{server_id}/{object_id}",
        source="DLNA",
        native_type="dir",
    )


@pytest.fixture
async def store(tmp_path):
    repo = MargeSourceRepository(tmp_path / "t.db")
    await repo.initialize()
    yield repo
    await repo.close()


@pytest.fixture
def speaker(store):
    return FakeSpeaker(store)


def make(store, speaker, *, presets=(), servers=None, known=True):
    servers = servers if servers is not None else [DlnaServer(SID, "Music", "l", "c")]
    return DlnaNativeService(
        store,
        FakeDevices(known),
        FakeDlna(servers),
        FakePresets(presets),
        client_factory=lambda device: speaker.client(),
        row_polls=3,
        poll_interval=0.01,
        ready_timeout=0.1,
    )


def states(report):
    return {s.server_id: s for s in report}


# ---- AC-B1: state table -------------------------------------------------------------


@pytest.mark.parametrize(
    "row, listed, expected",
    [
        (None, None, NativeState.NOT_REGISTERED),
        (None, "READY", NativeState.UNMANAGED),
        (None, "UNAVAILABLE", NativeState.UNMANAGED),
        ("active7", None, NativeState.UNAVAILABLE),
        ("active50", None, NativeState.RESTART_REQUIRED),
        ("active7", "READY", NativeState.READY),
        ("active50", "ready", NativeState.READY),
        ("active7", "UNAVAILABLE", NativeState.UNAVAILABLE),
        ("pending", "READY", NativeState.REMOVAL_PENDING),
        ("pending", None, NativeState.NOT_REGISTERED),
    ],
)
async def test_state_table(store, speaker, row, listed, expected):
    if row:
        created = await store.upsert(DEV, SID, "Music", 50 if row == "active50" else 7)
        if row == "pending":
            await store.mark_removal_pending(DEV, created.source_id)
    if listed:
        speaker.sources[ACCOUNT.upper()] = listed  # speakers may report upper case
    report = await make(store, speaker).state(DEV)
    entry = states(report)[SID]
    assert entry.state is expected
    assert entry.server_known is True
    assert (entry.source_id is not None) == bool(
        row and not (row == "pending" and not listed)
    )
    if row == "pending" and not listed:
        assert await store.get_by_server(DEV, SID) is None  # deleted by the read


async def test_state_lists_stale_rows_and_new_uuid_separately(store, speaker):
    await store.upsert(DEV, STALE, "Gone", 7)
    speaker.sources[f"{STALE}/0"] = "READY"
    service = make(store, speaker)
    entries = states(await service.state(DEV))
    assert entries[STALE].server_known is False
    assert entries[STALE].name == "Gone"
    assert entries[STALE].state is NativeState.READY
    assert entries[SID].state is NativeState.NOT_REGISTERED
    assert speaker.calls == []  # never re-registered or removed automatically


async def test_state_speaker_unreadable(store, speaker):
    speaker.unreachable = True
    with pytest.raises(DeviceConnectionError):
        await make(store, speaker).state(DEV)


async def test_state_unknown_device(store, speaker):
    with pytest.raises(DeviceNotFoundError):
        await make(store, speaker, known=False).state(DEV)


# ---- AC-B2..B6: enable --------------------------------------------------------------


async def test_enable_registers_and_reports_ready(store, speaker):
    result = await make(store, speaker).enable(DEV, SID)
    assert (result.state, result.created) == (NativeState.READY, True)
    assert speaker.calls == [("set", ACCOUNT)]
    assert (await store.get_by_server(DEV, SID)).display_name == "Music"


async def test_enable_with_stale_provider_asks_for_one_restart(store, speaker):
    speaker.provider_id = 50
    speaker.list_after_set = None
    result = await make(store, speaker).enable(DEV, SID)
    assert (result.state, result.created) == (NativeState.RESTART_REQUIRED, True)


async def test_enable_never_listed_ends_unavailable(store, speaker):
    speaker.list_after_set = None
    result = await make(store, speaker).enable(DEV, SID)
    assert result.state is NativeState.UNAVAILABLE


async def test_enable_check_order_without_speaker_write(store, speaker):
    with pytest.raises(DeviceNotFoundError):
        await make(store, speaker, known=False).enable(DEV, SID)
    with pytest.raises(CodedApiError) as err:
        await make(store, speaker, servers=[]).enable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        404,
        error_codes.DLNA_SERVER_NOT_FOUND,
    )
    speaker.unreachable = True
    with pytest.raises(DeviceConnectionError):
        await make(store, speaker).enable(DEV, SID)
    assert speaker.calls == []


async def test_enable_rejects_a_server_id_that_is_not_a_uuid(store, speaker):
    service = make(
        store, speaker, servers=[DlnaServer("mock-media-server", "M", "l", "c")]
    )
    with pytest.raises(CodedApiError) as err:
        await service.enable(DEV, "mock-media-server")
    assert err.value.code == error_codes.VALIDATION_ERROR
    assert speaker.calls == []


async def test_enable_speaker_error_deletes_the_row_of_this_request(store, speaker):
    speaker.set_error = 1022
    with pytest.raises(CodedApiError) as err:
        await make(store, speaker).enable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        502,
        error_codes.DLNA_NATIVE_REGISTRATION_FAILED,
    )
    assert await store.get_by_server(DEV, SID) is None


async def test_enable_error_after_callback_removes_the_created_row(store, speaker):
    class Failing(FakeClient):
        async def set_music_service_account(self, source, display_name, user):
            await self.s.store.upsert(DEV, SID, display_name, 7)
            raise SpeakerCommandError(1022)

    service = make(store, speaker)
    service._client_factory = lambda device: Failing(speaker)
    with pytest.raises(CodedApiError):
        await service.enable(DEV, SID)
    assert await store.get_by_server(DEV, SID) is None


async def test_enable_without_callback_fails(store, speaker):
    speaker.callback = False
    with pytest.raises(CodedApiError) as err:
        await make(store, speaker).enable(DEV, SID)
    assert err.value.code == error_codes.DLNA_NATIVE_REGISTRATION_FAILED


async def test_callback_after_the_speaker_call_returned(store, speaker):
    speaker.callback = False
    speaker.callback_after = 0.015
    result = await make(store, speaker).enable(DEV, SID)
    assert result.state is NativeState.READY
    assert await store.count_for_device(DEV) == 1


async def test_enable_unmanaged_adopts_without_speaker_write(store, speaker):
    speaker.sources[ACCOUNT] = "READY"
    result = await make(store, speaker).enable(DEV, SID)
    assert (result.state, result.created) == (NativeState.READY, False)
    assert speaker.calls == []
    assert (await store.get_by_server(DEV, SID)) is not None


@pytest.mark.parametrize("status", ["READY"])
async def test_enable_ready_is_idempotent(store, speaker, status):
    await store.upsert(DEV, SID, "Music", 7)
    speaker.sources[ACCOUNT] = status
    result = await make(store, speaker).enable(DEV, SID)
    assert (result.state, result.created) == (NativeState.READY, False)
    assert speaker.calls == []


async def test_enable_restart_required_is_idempotent(store, speaker):
    await store.upsert(DEV, SID, "Music", 50)
    result = await make(store, speaker).enable(DEV, SID)
    assert (result.state, result.created) == (NativeState.RESTART_REQUIRED, False)
    assert speaker.calls == []


async def test_enable_unavailable_conflicts(store, speaker):
    await store.upsert(DEV, SID, "Music", 7)
    speaker.sources[ACCOUNT] = "UNAVAILABLE"
    with pytest.raises(CodedApiError) as err:
        await make(store, speaker).enable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        409,
        error_codes.DLNA_NATIVE_ALREADY_REGISTERED,
    )


async def test_enable_removal_pending_conflicts(store, speaker):
    row = await store.upsert(DEV, SID, "Music", 7)
    await store.mark_removal_pending(DEV, row.source_id)
    speaker.sources[ACCOUNT] = "READY"
    with pytest.raises(CodedApiError) as err:
        await make(store, speaker).enable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        409,
        error_codes.DLNA_NATIVE_REMOVAL_PENDING,
    )


async def test_parallel_puts_make_one_speaker_call(store, speaker):
    service = make(store, speaker)
    results = await asyncio.gather(*(service.enable(DEV, SID) for _ in range(4)))
    assert [r.created for r in results].count(True) == 1
    assert speaker.calls == [("set", ACCOUNT)]
    assert await store.count_for_device(DEV) == 1


async def test_different_servers_register_independently(store, speaker):
    servers = [DlnaServer(SID, "A", "l", "c"), DlnaServer(SID2, "B", "l", "c")]
    service = make(store, speaker, servers=servers)
    await asyncio.gather(service.enable(DEV, SID), service.enable(DEV, SID2))
    assert sorted(c[1] for c in speaker.calls) == sorted([ACCOUNT, f"{SID2}/0"])


# ---- AC-B7..B8: disable -------------------------------------------------------------


async def _registered(store, speaker, provider=7):
    row = await store.upsert(DEV, SID, "Music", provider)
    speaker.sources[ACCOUNT] = "READY"
    return row


async def test_disable_removes_and_deletes_the_row(store, speaker):
    await _registered(store, speaker)
    assert await make(store, speaker).disable(DEV, SID) == []
    assert speaker.calls == [("remove", ACCOUNT)]
    assert await store.get_by_server(DEV, SID) is None


async def test_disable_1047_counts_as_success(store, speaker):
    await _registered(store, speaker)
    speaker.remove_error = 1047
    speaker.sources.clear()  # 1047: the speaker does not know the account
    await make(store, speaker).disable(DEV, SID)
    assert await store.get_by_server(DEV, SID) is None


async def test_disable_other_error_keeps_the_row(store, speaker):
    await _registered(store, speaker)
    speaker.remove_error = 1000
    with pytest.raises(CodedApiError) as err:
        await make(store, speaker).disable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        502,
        error_codes.DLNA_NATIVE_REMOVE_FAILED,
    )
    assert await store.get_by_server(DEV, SID) is not None


async def test_disable_still_listed_becomes_removal_pending(store, speaker):
    await _registered(store, speaker)
    speaker.remove_keeps_listed = True
    await make(store, speaker).disable(DEV, SID)
    assert (await store.get_by_server(DEV, SID)).removal_pending is True


async def test_disable_with_native_presets_needs_force(store, speaker):
    await _registered(store, speaker)
    service = make(store, speaker, presets=[native_preset(2), native_preset(5, SID2)])
    with pytest.raises(CodedApiError) as err:
        await service.disable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        409,
        error_codes.DLNA_NATIVE_IN_USE,
    )
    assert speaker.calls == [] and speaker.stored == []
    assert [
        (p.preset_number, p.station_name)
        for p in await service.affected_slots(DEV, SID)
    ] == [(2, "Folder 2")]


async def test_disable_force_rewrites_slots_to_v1_first(store, speaker):
    await _registered(store, speaker)
    preset = native_preset(2)
    service = make(store, speaker, presets=[preset])
    assert await service.disable(DEV, SID, force=True) == [2]
    assert speaker.stored[0]["preset_number"] == 2
    assert speaker.stored[0]["dlna_reference"].server_id == SID
    assert preset.native_type is None
    assert speaker.calls == [("remove", ACCOUNT)]


async def test_disable_force_failing_rewrite_keeps_registration(store, speaker):
    await _registered(store, speaker)
    speaker.store_error = True
    service = make(store, speaker, presets=[native_preset(2)])
    with pytest.raises(CodedApiError) as err:
        await service.disable(DEV, SID, force=True)
    assert err.value.code == error_codes.DLNA_NATIVE_REMOVE_FAILED
    assert speaker.calls == []
    assert await store.get_by_server(DEV, SID) is not None


async def test_disable_stale_row_is_possible(store, speaker):
    await store.upsert(DEV, STALE, "Gone", 7)
    speaker.sources[f"{STALE}/0"] = "READY"
    await make(store, speaker).disable(DEV, STALE)
    assert await store.get_by_server(DEV, STALE) is None


async def test_disable_unknown_registration_is_a_noop(store, speaker):
    assert await make(store, speaker).disable(DEV, SID) == []
    assert speaker.calls == []
