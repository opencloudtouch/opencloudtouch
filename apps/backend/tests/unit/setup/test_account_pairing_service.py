"""Tests for account_pairing_service — margeAccountUUID check & SSH pairing."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from opencloudtouch.setup.account_pairing_service import (
    check_marge_account_uuid,
    ensure_account_uuid,
    ensure_account_uuid_unique,
    set_account_uuid_via_ssh,
    _generate_account_uuid,
    _update_uuid_in_xml,
)
from opencloudtouch.setup.ssh_client import CommandResult

# ── Fixtures ──────────────────────────────────────────────────────


_INFO_WITH_UUID = """<?xml version="1.0" encoding="UTF-8" ?>
<info deviceID="689E194F7D2F">
  <name>SoundTouch 20</name>
  <type>SoundTouch 20</type>
  <margeAccountUUID>5448503</margeAccountUUID>
  <components/>
  <margeURL>http://content.api.bose.io:7777</margeURL>
</info>"""

_INFO_WITHOUT_UUID = """<?xml version="1.0" encoding="UTF-8" ?>
<info deviceID="A0F6FD7D683D">
  <name>SoundTouch 20</name>
  <type>SoundTouch 20</type>
  <margeAccountUUID/>
  <components/>
  <margeURL>http://content.api.bose.io:7777</margeURL>
</info>"""

_INFO_NO_TAG = """<?xml version="1.0" encoding="UTF-8" ?>
<info deviceID="AABBCCDDEEFF">
  <name>SoundTouch 10</name>
  <type>SoundTouch 10</type>
  <components/>
</info>"""

_EXISTING_SYS_CONFIG = """<?xml version="1.0" encoding="UTF-8" ?>
<SystemConfiguration>
    <Password />
    <DeviceName>Kitchen</DeviceName>
    <AccountUUID>9999999</AccountUUID>
    <acctMode>local</acctMode>
    <isMultiDeviceAccount>false</isMultiDeviceAccount>
</SystemConfiguration>"""


# ── check_marge_account_uuid ─────────────────────────────────────


class TestCheckMargeAccountUUID:
    """Tests for reading margeAccountUUID from device /info."""

    @pytest.mark.asyncio
    async def test_returns_uuid_when_present(self):
        mock_resp = MagicMock()
        mock_resp.text = _INFO_WITH_UUID
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "opencloudtouch.setup.account_pairing_service.httpx.AsyncClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_marge_account_uuid("192.168.1.100")
            assert result == "5448503"

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(self):
        mock_resp = MagicMock()
        mock_resp.text = _INFO_WITHOUT_UUID
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "opencloudtouch.setup.account_pairing_service.httpx.AsyncClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_marge_account_uuid("192.168.1.100")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_tag_missing(self):
        mock_resp = MagicMock()
        mock_resp.text = _INFO_NO_TAG
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "opencloudtouch.setup.account_pairing_service.httpx.AsyncClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_marge_account_uuid("192.168.1.100")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        import httpx as _httpx

        with patch(
            "opencloudtouch.setup.account_pairing_service.httpx.AsyncClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_marge_account_uuid("192.168.1.100")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_xml(self):
        mock_resp = MagicMock()
        mock_resp.text = "NOT VALID XML {{{"
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "opencloudtouch.setup.account_pairing_service.httpx.AsyncClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_marge_account_uuid("192.168.1.100")
            assert result is None


# ── _update_uuid_in_xml ──────────────────────────────────────────


class TestUpdateUuidInXml:
    """Tests for in-place XML update of AccountUUID."""

    def test_updates_existing_uuid(self):
        result = _update_uuid_in_xml(_EXISTING_SYS_CONFIG, "1234567")
        assert "1234567" in result
        assert "9999999" not in result
        assert "global" in result
        assert ">true<" in result

    def test_adds_missing_elements(self):
        xml = "<SystemConfiguration><DeviceName>Test</DeviceName></SystemConfiguration>"
        result = _update_uuid_in_xml(xml, "7654321")
        assert "7654321" in result
        assert "global" in result
        assert ">true<" in result


# ── set_account_uuid_via_ssh ─────────────────────────────────────


class TestSetAccountUuidViaSSH:
    """Tests for setting UUID via SSH file write."""

    @pytest.mark.asyncio
    async def test_success_file_exists(self):
        ssh = AsyncMock()
        ssh.execute = AsyncMock(
            side_effect=[
                CommandResult(success=True, output="", exit_code=0),  # mkdir
                CommandResult(
                    success=True, output=_EXISTING_SYS_CONFIG, exit_code=0
                ),  # cat (read existing)
                CommandResult(
                    success=True,
                    output="<AccountUUID>1234567</AccountUUID>",
                    exit_code=0,
                ),  # verify cat
            ]
        )

        with patch(
            "opencloudtouch.setup.account_pairing_service._file_exists",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "opencloudtouch.setup.account_pairing_service._write_file_atomic",
            new_callable=AsyncMock,
        ):
            result = await set_account_uuid_via_ssh(ssh, "1234567")
            assert result.success is True
            assert result.uuid == "1234567"

    @pytest.mark.asyncio
    async def test_success_file_missing_creates_new(self):
        ssh = AsyncMock()
        ssh.execute = AsyncMock(
            side_effect=[
                CommandResult(success=True, output="", exit_code=0),  # mkdir
                CommandResult(
                    success=True,
                    output="<AccountUUID>1234567</AccountUUID>",
                    exit_code=0,
                ),  # verify cat
            ]
        )

        with patch(
            "opencloudtouch.setup.account_pairing_service._file_exists",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "opencloudtouch.setup.account_pairing_service._write_file_atomic",
            new_callable=AsyncMock,
        ):
            result = await set_account_uuid_via_ssh(ssh, "1234567")
            assert result.success is True
            assert result.uuid == "1234567"
            assert "SSH" in result.message

    @pytest.mark.asyncio
    async def test_verification_fails(self):
        ssh = AsyncMock()
        ssh.execute = AsyncMock(
            side_effect=[
                CommandResult(success=True, output="", exit_code=0),  # mkdir
                CommandResult(
                    success=True, output="<AccountUUID>WRONG</AccountUUID>", exit_code=0
                ),  # verify
            ]
        )

        with patch(
            "opencloudtouch.setup.account_pairing_service._file_exists",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "opencloudtouch.setup.account_pairing_service._write_file_atomic",
            new_callable=AsyncMock,
        ):
            result = await set_account_uuid_via_ssh(ssh, "1234567")
            assert result.success is False
            assert "Verification failed" in result.error

    @pytest.mark.asyncio
    async def test_ssh_exception(self):
        ssh = AsyncMock()
        ssh.execute = AsyncMock(side_effect=RuntimeError("SSH broken"))

        result = await set_account_uuid_via_ssh(ssh, "1234567")
        assert result.success is False
        assert "SSH write failed" in result.error


# ── ensure_account_uuid ──────────────────────────────────────────


class TestEnsureAccountUuid:
    """Tests for the orchestration function — only sets UUID when missing."""

    @pytest.mark.asyncio
    async def test_skips_when_uuid_already_present(self):
        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value="5448503",
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as mock_set:
            result = await ensure_account_uuid("192.168.1.100")

            assert result.success is True
            assert result.had_uuid is True
            assert result.uuid == "5448503"
            mock_set.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_uuid_when_missing_with_provided_ssh(self):
        ssh = AsyncMock()

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as mock_set:
            from opencloudtouch.setup.account_pairing_service import (
                AccountPairingResult,
            )

            mock_set.return_value = AccountPairingResult(
                success=True, had_uuid=False, uuid="9876543", message="Set via SSH"
            )

            result = await ensure_account_uuid("192.168.1.100", ssh=ssh)

            assert result.success is True
            assert result.uuid == "9876543"
            mock_set.assert_called_once()
            assert mock_set.call_args[0][0] is ssh

    @pytest.mark.asyncio
    async def test_sets_uuid_when_missing_creates_ssh(self):
        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as mock_set, patch(
            "opencloudtouch.setup.account_pairing_service.SoundTouchSSHClient",
        ) as mock_ssh_cls:
            from opencloudtouch.setup.account_pairing_service import (
                AccountPairingResult,
            )

            mock_ssh = AsyncMock()
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_set.return_value = AccountPairingResult(
                success=True, had_uuid=False, uuid="9876543", message="Set via SSH"
            )

            result = await ensure_account_uuid("192.168.1.100")

            assert result.success is True
            mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_error_when_ssh_fails(self):
        ssh = AsyncMock()

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as mock_set:
            from opencloudtouch.setup.account_pairing_service import (
                AccountPairingResult,
            )

            mock_set.return_value = AccountPairingResult(
                success=False, had_uuid=False, error="SSH write failed"
            )

            result = await ensure_account_uuid("192.168.1.100", ssh=ssh)

            assert result.success is False

    @pytest.mark.asyncio
    async def test_idempotent_multiple_calls(self):
        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value="5448503",
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_ssh",
            new_callable=AsyncMock,
        ) as mock_set:
            r1 = await ensure_account_uuid("192.168.1.100")
            r2 = await ensure_account_uuid("192.168.1.100")

            assert r1.success is True
            assert r2.success is True
            assert r1.had_uuid is True
            assert r2.had_uuid is True
            mock_set.assert_not_called()


# ── UUID generation ──────────────────────────────────────────────


class TestGenerateAccountUuid:
    def test_is_7_digits(self):
        for _ in range(20):
            uuid = _generate_account_uuid()
            assert len(uuid) == 7
            assert uuid.isdigit()

    def test_is_string(self):
        assert isinstance(_generate_account_uuid(), str)


# ── ensure_account_uuid_unique ───────────────────────────────────


class TestEnsureAccountUuidUnique:
    """Tests for ensure_account_uuid_unique — collision-safe UUID assignment."""

    @pytest.mark.asyncio
    async def test_keeps_existing_unique_uuid(self):
        device_repo = AsyncMock()
        device_repo.get_by_account_uuid = AsyncMock(return_value=None)

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            return_value="5448503",
        ):
            result = await ensure_account_uuid_unique(
                device_ip="192.168.1.100",
                device_id="AABBCCDDEEFF",
                device_repo=device_repo,
            )
            assert result.success is True
            assert result.had_uuid is True
            assert result.uuid == "5448503"

    @pytest.mark.asyncio
    async def test_keeps_uuid_owned_by_same_device(self):
        owner = MagicMock()
        owner.device_id = "AABBCCDDEEFF"
        device_repo = AsyncMock()
        device_repo.get_by_account_uuid = AsyncMock(return_value=owner)

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            return_value="5448503",
        ):
            result = await ensure_account_uuid_unique(
                device_ip="192.168.1.100",
                device_id="AABBCCDDEEFF",
                device_repo=device_repo,
            )
            assert result.success is True
            assert result.had_uuid is True

    @pytest.mark.asyncio
    async def test_generates_new_uuid_on_collision(self):
        """When existing UUID is owned by another device, generate a new one."""
        other_owner = MagicMock()
        other_owner.device_id = "OTHER_DEVICE"
        device_repo = AsyncMock()
        # First call returns the other owner (collision), second call returns None (no collision for new UUID)
        device_repo.get_by_account_uuid = AsyncMock(side_effect=[other_owner, None])

        mock_ssh = AsyncMock()
        mock_ssh.execute = AsyncMock(
            return_value=CommandResult(
                success=True, output="<AccountUUID>1234567</AccountUUID>", exit_code=0
            )
        )
        mock_ssh.__aenter__ = AsyncMock(return_value=mock_ssh)
        mock_ssh.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            return_value="5448503",
        ), patch(
            "opencloudtouch.setup.account_pairing_service.SoundTouchSSHClient",
            return_value=mock_ssh,
        ), patch(
            "opencloudtouch.setup.account_pairing_service._generate_account_uuid",
            return_value="1234567",
        ):
            result = await ensure_account_uuid_unique(
                device_ip="192.168.1.100",
                device_id="AABBCCDDEEFF",
                device_repo=device_repo,
            )
            assert result.success is True
            assert result.had_uuid is True

    @pytest.mark.asyncio
    async def test_generates_new_uuid_when_no_existing(self):
        """When device has no UUID, generate one."""
        device_repo = AsyncMock()
        device_repo.get_by_account_uuid = AsyncMock(return_value=None)

        mock_ssh = AsyncMock()
        mock_ssh.execute = AsyncMock(
            return_value=CommandResult(
                success=True, output="<AccountUUID>7654321</AccountUUID>", exit_code=0
            )
        )
        mock_ssh.__aenter__ = AsyncMock(return_value=mock_ssh)
        mock_ssh.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            return_value=None,
        ), patch(
            "opencloudtouch.setup.account_pairing_service.SoundTouchSSHClient",
            return_value=mock_ssh,
        ), patch(
            "opencloudtouch.setup.account_pairing_service._generate_account_uuid",
            return_value="7654321",
        ):
            result = await ensure_account_uuid_unique(
                device_ip="192.168.1.100",
                device_id="AABBCCDDEEFF",
                device_repo=device_repo,
            )
            assert result.success is True
            assert result.had_uuid is False

    @pytest.mark.asyncio
    async def test_fails_after_max_retries_on_persistent_collision(self):
        """When every generated UUID collides, return failure."""
        other_device = MagicMock()
        other_device.device_id = "OTHER_DEVICE"
        device_repo = AsyncMock()
        # Always return a collision
        device_repo.get_by_account_uuid = AsyncMock(
            side_effect=[other_device, other_device, other_device, other_device]
        )

        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            return_value="5448503",
        ), patch(
            "opencloudtouch.setup.account_pairing_service._generate_account_uuid",
            return_value="9999999",
        ):
            result = await ensure_account_uuid_unique(
                device_ip="192.168.1.100",
                device_id="AABBCCDDEEFF",
                device_repo=device_repo,
                max_retries=3,
            )
            assert result.success is False
            assert "collision" in result.error.lower()
