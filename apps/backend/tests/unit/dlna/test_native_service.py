"""DlnaNativeService: state table, enable (re-pairing), disable (AC-B1..B10)."""

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
    """Shared in-memory speaker; ``client()`` hands out per-call clients.

    It lists the media servers OpenCloudTouch has rows for (the speaker reads them from
    ``/full``): at once, or only after a re-pairing when ``stale`` is set.
    """

    def __init__(self, store):
        self.store = store
        self.static: dict[str, str] = {}  # accounts listed regardless of OCT rows
        self.calls: list[tuple] = []
        self.stale = False
        self.paired = False
        self.sees_servers = True  # False: the speaker cannot reach the media server
        self.pair_error: int | None = None
        self.pair_unreachable = False
        self.unreachable = False
        self.stored: list[dict] = []
        self.store_error = False
        self.unbrowsable: set[str] = set()  # server ids the speaker cannot browse
        self.browse_calls: list[str] = []

    def client(self):
        return FakeClient(self)


class FakeClient:
    def __init__(self, speaker: FakeSpeaker):
        self.s = speaker

    async def get_source_list(self):
        if self.s.unreachable:
            raise DeviceConnectionError("dev", "down")
        listed = dict(self.s.static)
        if self.s.sees_servers and (self.s.paired or not self.s.stale):
            for row in await self.s.store.list_active(DEV):
                listed[f"{row.server_id}/0"] = "READY"
        return [SpeakerSource("STORED_MUSIC", a, st) for a, st in listed.items()]

    async def can_browse_stored_music(self, server_id):
        self.s.browse_calls.append(server_id)
        return server_id not in self.s.unbrowsable

    async def pair_with_account(self, account_id):
        self.s.calls.append(("pair", account_id))
        if self.s.pair_unreachable:
            raise DeviceConnectionError("dev", "down")
        if self.s.pair_error:
            raise SpeakerCommandError(self.s.pair_error)
        self.s.paired = True

    async def store_preset(self, **kwargs):
        if self.s.store_error:
            raise DeviceConnectionError("dev", "down")
        self.s.stored.append(kwargs)

    async def close(self):
        pass


class FakeDevices:
    def __init__(self, known=True, account="acct-1"):
        self.known = known
        self.account = account

    async def get_by_device_id(self, device_id):
        return (
            SimpleNamespace(
                device_id=device_id, ip="10.0.0.9", marge_account_uuid=self.account
            )
            if self.known
            else None
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


def make(store, speaker, *, presets=(), servers=None, known=True, account="acct-1"):
    servers = servers if servers is not None else [DlnaServer(SID, "Music", "l", "c")]
    return DlnaNativeService(
        store,
        FakeDevices(known, account),
        FakeDlna(servers),
        FakePresets(presets),
        client_factory=lambda device: speaker.client(),
        poll_interval=0.01,
        ready_timeout=0.1,
    )


def states(report):
    return {s.server_id: s for s in report}


# ---- AC-B1: state table -------------------------------------------------------------


@pytest.mark.parametrize(
    "row, listed, expected",
    [
        (False, None, NativeState.NOT_ENABLED),
        (False, "READY", NativeState.NOT_ENABLED),  # the speaker drops it on its sync
        (True, None, NativeState.UNAVAILABLE),
        (True, "READY", NativeState.READY),
        (True, "ready", NativeState.READY),
        (True, "UNAVAILABLE", NativeState.UNAVAILABLE),
    ],
)
async def test_state_table(store, speaker, row, listed, expected):
    speaker.sees_servers = False
    if row:
        await store.upsert(DEV, SID, "Music")
    if listed:
        speaker.static[ACCOUNT.upper()] = listed  # speakers may report upper case
    entry = states(await make(store, speaker).state(DEV))[SID]
    assert entry.state is expected
    assert entry.server_known is True
    assert (entry.source_id is not None) == row


async def test_state_lists_stale_rows_and_new_uuid_separately(store, speaker):
    await store.upsert(DEV, STALE, "Gone")
    service = make(store, speaker)
    entries = states(await service.state(DEV))
    assert entries[STALE].server_known is False
    assert entries[STALE].name == "Gone"
    assert entries[STALE].state is NativeState.READY
    assert entries[SID].state is NativeState.NOT_ENABLED
    assert speaker.calls == []  # never paired or changed automatically


async def test_state_speaker_unreadable(store, speaker):
    speaker.unreachable = True
    with pytest.raises(DeviceConnectionError):
        await make(store, speaker).state(DEV)


async def test_state_unknown_device(store, speaker):
    with pytest.raises(DeviceNotFoundError):
        await make(store, speaker, known=False).state(DEV)


# ---- AC-B2..B6: enable --------------------------------------------------------------


async def test_enable_on_an_up_to_date_speaker_does_not_re_pair(store, speaker):
    assert await make(store, speaker).enable(DEV, SID) is NativeState.READY
    assert speaker.calls == []
    row = await store.get_by_server(DEV, SID)
    assert row.display_name == "Music" and row.source_id >= 20000000


async def test_enable_on_a_stale_speaker_re_pairs_once(store, speaker):
    speaker.stale = True
    assert await make(store, speaker).enable(DEV, SID) is NativeState.READY
    assert speaker.calls == [("pair", "acct-1")]


async def test_re_pairing_falls_back_to_the_device_id_without_an_account(
    store, speaker
):
    speaker.stale = True
    await make(store, speaker, account=None).enable(DEV, SID)
    assert speaker.calls == [("pair", DEV)]


async def test_enable_when_the_speaker_never_lists_it_ends_unavailable(store, speaker):
    speaker.sees_servers = False
    assert await make(store, speaker).enable(DEV, SID) is NativeState.UNAVAILABLE
    assert speaker.calls == [("pair", "acct-1")]  # once, not repeated while polling
    assert await store.get_by_server(DEV, SID) is not None


async def test_enable_when_ready_changes_nothing(store, speaker):
    row = await store.upsert(DEV, SID, "Music")
    assert await make(store, speaker).enable(DEV, SID) is NativeState.READY
    assert speaker.calls == []
    assert (await store.get_by_server(DEV, SID)).source_id == row.source_id


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
    assert await store.count_for_device(DEV) == 0


async def test_enable_rejects_a_server_id_that_is_not_a_uuid(store, speaker):
    service = make(
        store, speaker, servers=[DlnaServer("mock-media-server", "M", "l", "c")]
    )
    with pytest.raises(CodedApiError) as err:
        await service.enable(DEV, "mock-media-server")
    assert err.value.code == error_codes.VALIDATION_ERROR
    assert speaker.calls == []


async def test_pairing_refused_deletes_the_row_of_this_request(store, speaker):
    speaker.stale = True
    speaker.pair_error = 1038
    with pytest.raises(CodedApiError) as err:
        await make(store, speaker).enable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        502,
        error_codes.DLNA_NATIVE_SETUP_FAILED,
    )
    assert await store.get_by_server(DEV, SID) is None


async def test_pairing_refused_keeps_a_row_that_existed(store, speaker):
    speaker.stale = True
    speaker.sees_servers = False
    speaker.pair_error = 1038
    await store.upsert(DEV, SID, "Music")
    with pytest.raises(CodedApiError):
        await make(store, speaker).enable(DEV, SID)
    assert await store.get_by_server(DEV, SID) is not None


async def test_speaker_lost_while_pairing_deletes_the_new_row(store, speaker):
    speaker.stale = True
    speaker.pair_unreachable = True
    with pytest.raises(DeviceConnectionError):
        await make(store, speaker).enable(DEV, SID)
    assert await store.get_by_server(DEV, SID) is None


async def test_parallel_enables_re_pair_once_and_make_one_row(store, speaker):
    speaker.stale = True
    service = make(store, speaker)
    results = await asyncio.gather(*(service.enable(DEV, SID) for _ in range(4)))
    assert set(results) == {NativeState.READY}
    assert speaker.calls == [("pair", "acct-1")]
    assert await store.count_for_device(DEV) == 1


async def test_different_servers_enable_independently(store, speaker):
    servers = [DlnaServer(SID, "A", "l", "c"), DlnaServer(SID2, "B", "l", "c")]
    service = make(store, speaker, servers=servers)
    await asyncio.gather(service.enable(DEV, SID), service.enable(DEV, SID2))
    assert await store.count_for_device(DEV) == 2


# ---- AC-B7..B8: disable -------------------------------------------------------------


async def test_disable_deletes_the_row_without_a_speaker_call(store, speaker):
    await store.upsert(DEV, SID, "Music")
    assert await make(store, speaker).disable(DEV, SID) == []
    assert speaker.calls == [] and speaker.stored == []
    assert await store.get_by_server(DEV, SID) is None


async def test_disable_with_native_presets_needs_force(store, speaker):
    await store.upsert(DEV, SID, "Music")
    service = make(store, speaker, presets=[native_preset(2), native_preset(5, SID2)])
    with pytest.raises(CodedApiError) as err:
        await service.disable(DEV, SID)
    assert (err.value.status_code, err.value.code) == (
        409,
        error_codes.DLNA_NATIVE_IN_USE,
    )
    assert speaker.stored == []
    assert await store.get_by_server(DEV, SID) is not None
    assert [
        (p.preset_number, p.station_name)
        for p in await service.affected_slots(DEV, SID)
    ] == [(2, "Folder 2")]


async def test_disable_force_rewrites_slots_to_v1_first(store, speaker):
    await store.upsert(DEV, SID, "Music")
    preset = native_preset(2)
    service = make(store, speaker, presets=[preset])
    assert await service.disable(DEV, SID, force=True) == [2]
    assert speaker.stored[0]["preset_number"] == 2
    assert speaker.stored[0]["dlna_reference"].server_id == SID
    assert preset.native_type is None
    assert await store.get_by_server(DEV, SID) is None


async def test_disable_force_failing_rewrite_keeps_the_row(store, speaker):
    await store.upsert(DEV, SID, "Music")
    speaker.store_error = True
    service = make(store, speaker, presets=[native_preset(2)])
    with pytest.raises(CodedApiError) as err:
        await service.disable(DEV, SID, force=True)
    assert err.value.code == error_codes.DLNA_NATIVE_REMOVE_FAILED
    assert await store.get_by_server(DEV, SID) is not None


async def test_disable_stale_row_is_possible(store, speaker):
    await store.upsert(DEV, STALE, "Gone")
    await make(store, speaker).disable(DEV, STALE)
    assert await store.get_by_server(DEV, STALE) is None


async def test_disable_unknown_server_is_a_noop(store, speaker):
    assert await make(store, speaker).disable(DEV, SID) == []
    assert speaker.calls == []


# ---- native_ready (used by the preset write) -----------------------------------------


async def test_native_ready_needs_a_row_and_a_ready_listing(store, speaker):
    service = make(store, speaker)
    assert await service.native_ready(DEV, SID) is False  # no row
    await store.upsert(DEV, SID, "Music")
    assert await service.native_ready(DEV, SID.upper()) is True
    speaker.sees_servers = False
    assert await service.native_ready(DEV, SID) is False  # row, not listed
    speaker.unreachable = True
    with pytest.raises(DeviceConnectionError):
        await service.native_ready(DEV, SID)


# ---- combined state: READY listing AND the speaker can browse the server -----------


async def test_listed_ready_but_browse_fails_is_unavailable(store, speaker):
    await store.upsert(DEV, SID, "Music")
    speaker.unbrowsable.add(SID)
    service = make(store, speaker)
    assert states(await service.state(DEV))[SID].state is NativeState.UNAVAILABLE
    assert await service.native_ready(DEV, SID) is False


async def test_listed_ready_and_browse_ok_is_ready(store, speaker):
    await store.upsert(DEV, SID, "Music")
    assert states(await make(store, speaker).state(DEV))[SID].state is NativeState.READY


async def test_not_listed_is_not_probed(store, speaker):
    speaker.sees_servers = False
    await store.upsert(DEV, SID, "Music")
    entry = states(await make(store, speaker).state(DEV))[SID]
    assert entry.state is NativeState.UNAVAILABLE
    assert speaker.browse_calls == []


async def test_enable_with_failing_browse_is_unavailable(store, speaker):
    speaker.unbrowsable.add(SID)
    assert await make(store, speaker).enable(DEV, SID) is NativeState.UNAVAILABLE


async def test_probe_is_cached_and_failure_expires_sooner(store, speaker):
    from opencloudtouch.dlna import native_service as ns

    await store.upsert(DEV, SID, "Music")
    service = make(store, speaker)
    await service.state(DEV)
    await service.state(DEV)
    assert speaker.browse_calls == [SID]  # second poll served from the cache
    assert ns.PROBE_FAIL_TTL < ns.PROBE_OK_TTL

    key = (DEV, SID)
    ok, expiry = service._probes[key]
    service._probes[key] = (ok, 0.0)  # expired
    await service.state(DEV)
    assert speaker.browse_calls == [SID, SID]
