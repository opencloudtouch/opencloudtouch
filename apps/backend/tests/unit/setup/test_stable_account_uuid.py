"""Regression tests for stable per-device account UUIDs (issue #511)."""

from unittest.mock import AsyncMock, patch

import pytest

from opencloudtouch.setup.account_pairing_service import (
    AccountPairingResult,
    _generate_account_uuid,
    ensure_account_uuid_unique,
    is_valid_account_uuid,
)


def test_uuid_is_stable_between_servers_and_mac_formats():
    expected = _generate_account_uuid("AABBCCDDEEFF")
    assert expected == _generate_account_uuid("aa:bb:cc:dd:ee:ff")
    assert expected == _generate_account_uuid("aa-bb-cc-dd-ee-ff")
    assert is_valid_account_uuid(expected)
    assert len(expected) == 7


def test_collision_fallback_is_stable():
    device = "AABBCCDDEEFF"
    first = _generate_account_uuid(device)
    second = _generate_account_uuid(device, 1)
    assert second == _generate_account_uuid(device, 1)
    assert first != second


@pytest.mark.asyncio
async def test_two_independent_servers_choose_identical_uuid():
    values = []

    async def write_uuid(ssh, uuid, device_name):
        return AccountPairingResult(success=True, had_uuid=False, uuid=uuid)

    for _ in range(2):
        repo = AsyncMock()
        repo.get_by_account_uuid.return_value = None
        with (
            patch(
                "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
                new_callable=AsyncMock,
                side_effect=write_uuid,
            ),
        ):
            result = await ensure_account_uuid_unique(
                "192.168.1.100", "AABBCCDDEEFF", repo, ssh=AsyncMock()
            )
            assert result.success
            values.append(result.uuid)

    assert values == [_generate_account_uuid("AABBCCDDEEFF")] * 2


@pytest.mark.asyncio
async def test_collision_uses_counter_one():
    from unittest.mock import MagicMock

    other = MagicMock()
    other.device_id = "112233445566"
    repo = AsyncMock()
    repo.get_by_account_uuid.side_effect = [other, None]

    async def write_uuid(ssh, uuid, device_name):
        return AccountPairingResult(success=True, had_uuid=False, uuid=uuid)

    with (
        patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
            side_effect=write_uuid,
        ),
    ):
        result = await ensure_account_uuid_unique(
            "192.168.1.100", "AABBCCDDEEFF", repo, ssh=AsyncMock()
        )

    assert result.success
    assert result.uuid == _generate_account_uuid("AABBCCDDEEFF", 1)


@pytest.mark.asyncio
async def test_info_connection_failure_never_writes_uuid():
    import httpx

    from opencloudtouch.setup.account_pairing_service import ensure_account_uuid

    with (
        patch(
            "opencloudtouch.setup.account_pairing_service.httpx.AsyncClient"
        ) as client_cls,
        patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as setter,
    ):
        client = AsyncMock()
        client.get.side_effect = httpx.ConnectError("offline")
        client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await ensure_account_uuid(
            "192.168.1.100", device_id="AABBCCDDEEFF", ssh=AsyncMock()
        )
    assert result.success is False
    assert "Cannot verify" in result.error
    setter.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("incoming_id", "owner_id"),
    [("AABBCCDDEEFF", "BBBBCCDDEEFF"), ("BBBBCCDDEEFF", "AABBCCDDEEFF")],
)
async def test_existing_uuid_collision_changes_only_incoming_device(
    incoming_id, owner_id
):
    from unittest.mock import MagicMock

    owner = MagicMock()
    owner.device_id = owner_id
    repo = AsyncMock()
    repo.get_by_account_uuid.side_effect = [owner, None]
    repo.update_marge_account_uuid = AsyncMock()
    incoming_ssh = AsyncMock()

    async def write_uuid(ssh, uuid, device_name):
        return AccountPairingResult(success=True, had_uuid=False, uuid=uuid)

    with (
        patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value="1234567",
        ),
        patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
            side_effect=write_uuid,
        ) as writer,
    ):
        result = await ensure_account_uuid_unique(
            "192.168.1.100", incoming_id, repo, ssh=incoming_ssh
        )

    assert result.success
    assert result.uuid == _generate_account_uuid(incoming_id)
    assert result.uuid_source == "collision_fallback"
    writer.assert_awaited_once()
    repo.update_marge_account_uuid.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_mac", ["", "AABBCC", "AABBCCDDEEFG", "not-a-mac"])
async def test_invalid_mac_does_not_trigger_ssh_write(invalid_mac):
    """Reject invalid device IDs instead of assigning a made-up UUID."""
    repo = AsyncMock()
    repo.get_by_account_uuid.return_value = None

    with (
        patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as writer,
    ):
        result = await ensure_account_uuid_unique(
            "192.168.1.100", invalid_mac, repo, ssh=AsyncMock()
        )

    assert result.success is False
    assert "MAC address" in result.error
    writer.assert_not_awaited()
