"""Unit tests for StereoPairService (Marge side) and the group XML helpers."""

from unittest.mock import AsyncMock

import pytest

from opencloudtouch.stereo_pairs.repository import (
    DeviceAlreadyPairedError,
    StereoPairRepository,
)
from opencloudtouch.stereo_pairs.service import (
    INTENT_TTL_SECONDS,
    StereoPairService,
    UnknownDeviceError,
)
from opencloudtouch.stereo_pairs.xml import (
    GroupRequest,
    InvalidGroupError,
    build_group_xml,
    parse_group_request,
)

GROUP_BODY = b"""<?xml version="1.0" encoding="UTF-8"?>
<group>
  <masterDeviceId>L1</masterDeviceId>
  <name>Office</name>
  <roles>
    <groupRole><deviceId>L1</deviceId><role>LEFT</role><ipAddress>10.0.0.1</ipAddress></groupRole>
    <groupRole><deviceId>R1</deviceId><role>RIGHT</role></groupRole>
  </roles>
</group>"""


def _request(**overrides):
    values = dict(
        master_device_id="L1", name="Office", left_device_id="L1", right_device_id="R1"
    )
    values.update(overrides)
    return GroupRequest(**values)


class TestGroupXml:
    def test_parse_ignores_extra_fields(self):
        request = parse_group_request(GROUP_BODY)

        assert request == _request()

    def test_parse_rejects_garbage_and_wrong_root(self):
        with pytest.raises(InvalidGroupError):
            parse_group_request(b"not xml")
        with pytest.raises(InvalidGroupError):
            parse_group_request(b"<other/>")

    def test_parse_rejects_entity_expansion(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE g [<!ENTITY a "x">]><group>&a;</group>'
        with pytest.raises(InvalidGroupError):
            parse_group_request(bomb)


@pytest.mark.asyncio
class TestStereoPairService:
    @pytest.fixture
    async def repo(self, tmp_path):
        repository = StereoPairRepository(str(tmp_path / "pairs.db"))
        await repository.initialize()
        yield repository
        await repository.close()

    @pytest.fixture
    def now(self):
        return [1000.0]

    @pytest.fixture
    def service(self, repo, now):
        device_repo = AsyncMock()
        device_repo.get_by_device_id.side_effect = lambda device_id: (
            object() if device_id in ("L1", "R1") else None
        )
        return StereoPairService(repo, device_repo, clock=lambda: now[0])

    async def test_create_without_intent_is_imported_and_active(self, service):
        pair = await service.marge_create(_request())

        assert (pair.status, pair.source) == ("active", "device")
        assert pair.name == "Office"

    async def test_create_with_intent_is_pending_oct(self, service):
        service.expect_create("L1")

        pair = await service.marge_create(_request())

        assert (pair.status, pair.source) == ("pending", "oct")

    async def test_expired_intent_is_ignored(self, service, now):
        service.expect_create("L1")
        now[0] += INTENT_TTL_SECONDS + 1

        pair = await service.marge_create(_request())

        assert pair.source == "device"

    async def test_intent_is_consumed_once(self, service):
        service.expect_create("L1")
        first = await service.marge_create(_request())
        await service.marge_dissolve(first.id)

        second = await service.marge_create(_request())

        assert (first.source, second.source) == ("oct", "device")

    async def test_repeated_identical_create_is_idempotent(self, service):
        first = await service.marge_create(_request())

        again = await service.marge_create(_request())

        assert again.id == first.id

    async def test_different_composition_with_paired_device_is_rejected(self, service):
        await service.marge_create(_request())

        other_right = _request(master_device_id="L1", right_device_id="R2")
        other_left = _request(
            master_device_id="X", left_device_id="X", right_device_id="R1"
        )
        with pytest.raises(DeviceAlreadyPairedError):
            await service.marge_create(other_right)
        with pytest.raises(DeviceAlreadyPairedError):
            await service.marge_create(other_left)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"left_device_id": ""},
            {"right_device_id": ""},
            {"right_device_id": "L1"},
            {"master_device_id": "OTHER"},
        ],
    )
    async def test_invalid_requests_are_rejected(self, service, overrides):
        request = _request(**overrides)
        with pytest.raises(InvalidGroupError):
            await service.marge_create(request)

    async def test_default_name(self, service):
        pair = await service.marge_create(_request(name=""))

        assert pair.name == "L1 + R1"

    async def test_get_for_device(self, service):
        assert await service.get_for_device("L1") is None
        created = await service.marge_create(_request())

        found = await service.get_for_device("R1")

        assert found is not None
        assert found.id == created.id
        assert b'id="%d"' % created.id in build_group_xml(found)
        with pytest.raises(UnknownDeviceError):
            await service.get_for_device("NOPE")

    async def test_rename_and_dissolve(self, service):
        created = await service.marge_create(_request())

        renamed = await service.marge_rename(created.id, "Renamed")
        assert renamed.name == "Renamed"
        assert await service.marge_rename(99999, "x") is None
        with pytest.raises(InvalidGroupError):
            await service.marge_rename(created.id, "")

        await service.marge_dissolve(created.id)
        await service.marge_dissolve(created.id)
        assert await service.get_for_device("L1") is None
