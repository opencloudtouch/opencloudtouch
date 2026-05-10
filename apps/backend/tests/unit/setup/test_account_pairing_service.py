"""Tests for account_pairing_service — margeAccountUUID check & Telnet pairing."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from opencloudtouch.setup.account_pairing_service import (
    check_marge_account_uuid,
    ensure_account_uuid,
    set_account_uuid_via_telnet,
    _generate_account_uuid,
)
from opencloudtouch.setup.ssh_client import CommandResult, SSHConnectionResult

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


# ── set_account_uuid_via_telnet ──────────────────────────────────


class TestSetAccountUuidViaTelnet:
    """Tests for setting UUID via Telnet envswitch."""

    @pytest.mark.asyncio
    async def test_success(self):
        with patch(
            "opencloudtouch.setup.account_pairing_service.SoundTouchTelnetClient"
        ) as mock_cls:
            mock_telnet = AsyncMock()
            mock_telnet.connect = AsyncMock(
                return_value=SSHConnectionResult(success=True)
            )
            mock_telnet.execute = AsyncMock(
                return_value=CommandResult(success=True, output="OK")
            )
            mock_telnet.close = AsyncMock()
            mock_cls.return_value = mock_telnet

            result = await set_account_uuid_via_telnet("192.168.1.100", "1234567")
            assert result.success is True
            assert result.uuid == "1234567"
            assert result.had_uuid is False

            # Verify correct command was sent
            mock_telnet.execute.assert_called_once_with(
                "envswitch accountid set 1234567", timeout=5.0
            )

    @pytest.mark.asyncio
    async def test_telnet_connection_fails(self):
        with patch(
            "opencloudtouch.setup.account_pairing_service.SoundTouchTelnetClient"
        ) as mock_cls:
            mock_telnet = AsyncMock()
            mock_telnet.connect = AsyncMock(
                return_value=SSHConnectionResult(
                    success=False, error="Connection refused"
                )
            )
            mock_telnet.close = AsyncMock()
            mock_cls.return_value = mock_telnet

            result = await set_account_uuid_via_telnet("192.168.1.100", "1234567")
            assert result.success is False
            assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_envswitch_command_fails(self):
        with patch(
            "opencloudtouch.setup.account_pairing_service.SoundTouchTelnetClient"
        ) as mock_cls:
            mock_telnet = AsyncMock()
            mock_telnet.connect = AsyncMock(
                return_value=SSHConnectionResult(success=True)
            )
            mock_telnet.execute = AsyncMock(
                return_value=CommandResult(success=False, error="Command not found")
            )
            mock_telnet.close = AsyncMock()
            mock_cls.return_value = mock_telnet

            result = await set_account_uuid_via_telnet("192.168.1.100", "1234567")
            assert result.success is False


# ── ensure_account_uuid (integration logic) ──────────────────────


class TestEnsureAccountUuid:
    """Tests for the orchestration function — only sets UUID when missing."""

    @pytest.mark.asyncio
    async def test_skips_when_uuid_already_present(self):
        """CRITICAL: Must NOT modify device if UUID already exists."""
        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value="5448503",
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_telnet",
            new_callable=AsyncMock,
        ) as mock_set:
            result = await ensure_account_uuid("192.168.1.100")

            assert result.success is True
            assert result.had_uuid is True
            assert result.uuid == "5448503"

            # Must NOT call Telnet — device already has UUID
            mock_set.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_uuid_when_missing(self):
        """Sets UUID via Telnet when device has empty margeAccountUUID."""
        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_telnet",
            new_callable=AsyncMock,
        ) as mock_set:
            from opencloudtouch.setup.account_pairing_service import (
                AccountPairingResult,
            )

            mock_set.return_value = AccountPairingResult(
                success=True, had_uuid=False, uuid="9876543", message="Set via Telnet"
            )

            result = await ensure_account_uuid("192.168.1.100")

            assert result.success is True
            assert result.had_uuid is False
            assert result.uuid == "9876543"

            # Telnet MUST be called exactly once
            mock_set.assert_called_once()
            call_args = mock_set.call_args
            assert call_args[0][0] == "192.168.1.100"  # device_ip
            assert len(call_args[0][1]) == 7  # 7-digit UUID

    @pytest.mark.asyncio
    async def test_returns_error_when_telnet_fails(self):
        """Returns failure when UUID is missing AND Telnet fails."""
        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_telnet",
            new_callable=AsyncMock,
        ) as mock_set:
            from opencloudtouch.setup.account_pairing_service import (
                AccountPairingResult,
            )

            mock_set.return_value = AccountPairingResult(
                success=False, had_uuid=False, error="Port 17000 closed"
            )

            result = await ensure_account_uuid("192.168.1.100")

            assert result.success is False

    @pytest.mark.asyncio
    async def test_idempotent_multiple_calls(self):
        """Calling ensure twice with existing UUID never triggers Telnet."""
        with patch(
            "opencloudtouch.setup.account_pairing_service.check_marge_account_uuid",
            new_callable=AsyncMock,
            return_value="5448503",
        ), patch(
            "opencloudtouch.setup.account_pairing_service.set_account_uuid_via_telnet",
            new_callable=AsyncMock,
        ) as mock_set:
            # Call twice
            r1 = await ensure_account_uuid("192.168.1.100")
            r2 = await ensure_account_uuid("192.168.1.100")

            assert r1.success is True
            assert r2.success is True
            assert r1.had_uuid is True
            assert r2.had_uuid is True

            # Telnet must NEVER be called
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
