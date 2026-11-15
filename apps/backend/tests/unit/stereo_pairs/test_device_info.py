"""Tests for the stereo fields of the device list."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from opencloudtouch.stereo_pairs.device_info import (
    load_stereo_context,
    stereo_fields,
)
from opencloudtouch.stereo_pairs.repository import StereoPair, StereoPairRepository
from opencloudtouch.zones.repository import ZoneRepository


def _device(device_id="L1", model="SoundTouch 10", lr=True, account="123"):
    return SimpleNamespace(
        device_id=device_id,
        model=model,
        marge_account_uuid=account,
        capabilities={"features": {"lr_stereo": lr}},
    )


def _pair():
    return StereoPair(7, "Office", "L1", "L1", "R1", datetime.now(UTC))


class TestStereoFields:
    def test_pair_name_is_set_for_both_members_and_none_for_single_speakers(self):
        pair = _pair()
        pairs = {"L1": pair, "R1": pair}

        left = stereo_fields(_device("L1"), pairs, set())
        right = stereo_fields(_device("R1"), pairs, set())
        single = stereo_fields(_device("X1"), pairs, set())

        assert left["stereo_pair_name"] == right["stereo_pair_name"] == "Office"
        assert single["stereo_pair_name"] is None

    def test_eligible_device(self):
        fields = stereo_fields(_device(), {}, set())

        assert fields["stereo_capable"]
        assert fields["oct_provisioned"]
        assert fields["stereo_ineligible_reason"] is None
        assert (fields["stereo_pair_id"], fields["stereo_role"]) == (None, None)

    @pytest.mark.parametrize(
        "device, reason",
        [
            (_device(model="SoundTouch 20"), "not_capable"),
            (_device(lr=False), "not_capable"),
            (_device(account=""), "not_provisioned"),
            (_device(account=None), "not_provisioned"),
        ],
    )
    def test_reasons_from_stored_data(self, device, reason):
        assert stereo_fields(device, {}, set())["stereo_ineligible_reason"] == reason

    def test_legacy_device_without_stored_capability_is_judged_by_model(self):
        """Devices synced before lr_stereo was detected must not all look incapable."""
        legacy = _device()
        legacy.capabilities = None
        no_flag = _device()
        no_flag.capabilities = {"features": {"bass_control": True}}
        other_model = _device(model="SoundTouch 20")
        other_model.capabilities = None

        assert stereo_fields(legacy, {}, set())["stereo_capable"] is True
        assert stereo_fields(no_flag, {}, set())["stereo_capable"] is True
        assert (
            stereo_fields(other_model, {}, set())["stereo_ineligible_reason"]
            == "not_capable"
        )

    def test_explicit_false_still_excludes_a_device(self):
        assert stereo_fields(_device(lr=False), {}, set())["stereo_capable"] is False

    def test_in_zone(self):
        fields = stereo_fields(_device(), {}, {"L1"})

        assert fields["stereo_ineligible_reason"] == "in_zone"

    def test_pair_members_get_role_and_master_flag(self):
        pairs = {"L1": _pair(), "R1": _pair()}

        left = stereo_fields(_device("L1"), pairs, set())
        right = stereo_fields(_device("R1"), pairs, set())

        assert (left["stereo_role"], left["stereo_master"], left["stereo_pair_id"]) == (
            "LEFT",
            True,
            7,
        )
        assert (right["stereo_role"], right["stereo_master"]) == ("RIGHT", False)
        assert left["stereo_ineligible_reason"] == "in_pair"


@pytest.mark.asyncio
async def test_load_stereo_context(tmp_path):
    stereo = StereoPairRepository(str(tmp_path / "db.sqlite"))
    zones = ZoneRepository(str(tmp_path / "db.sqlite"))
    await stereo.initialize()
    await zones.initialize()
    try:
        pair = await stereo.create_pair("A", "L1", "L1", "R1")
        zone = await zones.create_zone("Z1")
        await zones.add_member(zone.id, "Z2")

        pairs, zone_ids = await load_stereo_context(stereo, zones)

        assert pairs["R1"].id == pair.id
        assert zone_ids == {"Z1", "Z2"}
        assert await load_stereo_context(None, None) == ({}, set())
    finally:
        await stereo.close()
        await zones.close()


def test_device_list_survives_broken_stereo_repository(monkeypatch):
    """The device list must still answer when the optional stereo data fails."""
    from unittest.mock import AsyncMock, MagicMock

    from fastapi.testclient import TestClient

    from opencloudtouch.core.dependencies import (
        get_device_service,
        get_stereo_pair_repo,
        get_zone_repo,
    )
    from opencloudtouch.main import app

    service = MagicMock()
    service.get_all_devices = AsyncMock(return_value=[])
    broken = MagicMock()
    broken.list_active = AsyncMock(side_effect=RuntimeError("Database not initialized"))
    app.dependency_overrides[get_device_service] = lambda: service
    app.dependency_overrides[get_stereo_pair_repo] = lambda: broken
    app.dependency_overrides[get_zone_repo] = lambda: None
    try:
        response = TestClient(app).get("/api/devices")
    finally:
        for dep in (get_device_service, get_stereo_pair_repo, get_zone_repo):
            app.dependency_overrides.pop(dep, None)

    assert response.status_code == 200
    assert response.json() == {"count": 0, "devices": []}


def test_partner_and_master_names_come_with_the_device():
    pairs = {"L1": _pair(), "R1": _pair()}
    names = {"L1": "Office left", "R1": "Office right"}

    left = stereo_fields(_device("L1"), pairs, set(), names)
    right = stereo_fields(_device("R1"), pairs, set(), names)

    assert left["stereo_partner_name"] == "Office right"
    assert left["stereo_master_name"] == "Office left"
    assert right["stereo_partner_name"] == "Office left"
    assert right["stereo_master_name"] == "Office left"
    assert (
        stereo_fields(_device("X"), pairs, set(), names)["stereo_partner_name"] is None
    )
