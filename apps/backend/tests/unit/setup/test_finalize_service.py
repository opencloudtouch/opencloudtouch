"""Tests for wizard_service.finalize_device() -- Issue #184."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from opencloudtouch.setup.account_pairing_service import AccountPairingResult
from opencloudtouch.setup.persistence_service import ForceWriteResult
from opencloudtouch.setup.ssh_client import CommandResult
from opencloudtouch.setup.wizard_service import WizardService


def _make_device_repo(existing_uuid_owner=None):
    """Create mock device repo."""
    repo = AsyncMock()
    if existing_uuid_owner:
        device = MagicMock()
        device.device_id = existing_uuid_owner
        repo.get_by_account_uuid = AsyncMock(return_value=device)
    else:
        repo.get_by_account_uuid = AsyncMock(return_value=None)
    repo.update_marge_account_uuid = AsyncMock()
    return repo


def _mock_ssh():
    """Create a mock SSH client."""
    ssh = AsyncMock()
    ssh.execute = AsyncMock(
        return_value=CommandResult(success=True, output="", exit_code=0)
    )
    return ssh


class TestFinalizeDeviceNoUUID:
    """Device has no UUID -- should generate and set."""

    @pytest.mark.asyncio
    async def test_generates_uuid_when_missing(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with (
            patch(
                "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
                new_callable=AsyncMock,
                return_value=AccountPairingResult(
                    success=True,
                    had_uuid=False,
                    uuid="1234567",
                    message="UUID set via SSH",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.force_write_sources_xml",
                new_callable=AsyncMock,
                return_value=ForceWriteResult(
                    success=True,
                    written_path="/mnt/nv/BoseApp-Persistence/1/Sources.xml",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="1234567",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
            patch(
                "opencloudtouch.setup.wizard_service._write_file_atomic",
                new_callable=AsyncMock,
            ),
            patch(
                "opencloudtouch.setup.wizard_service._file_exists",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_ssh = _mock_ssh()
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.text = "<info><name>Kitchen</name><margeAccountUUID>1234567</margeAccountUUID></info>"
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value = mock_client

            result = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

            assert result["success"] is True
            assert result["uuid"] == "1234567"
            assert result["had_uuid"] is False
            repo.update_marge_account_uuid.assert_called_once_with(
                "AABBCCDDEEFF", "1234567"
            )


class TestFinalizeDeviceExistingUUID:
    """Device has unique UUID -- should keep it."""

    @pytest.mark.asyncio
    async def test_keeps_existing_unique_uuid(self):
        repo = _make_device_repo(existing_uuid_owner="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        with (
            patch(
                "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
                new_callable=AsyncMock,
                return_value=AccountPairingResult(
                    success=True,
                    had_uuid=True,
                    uuid="5448503",
                    message="Device has unique UUID",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.force_write_sources_xml",
                new_callable=AsyncMock,
                return_value=ForceWriteResult(
                    success=True,
                    written_path="/mnt/nv/BoseApp-Persistence/1/Sources.xml",
                    had_existing=True,
                    backup_path="/mnt/nv/BoseApp-Persistence/1/Sources.xml.bak",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
            patch(
                "opencloudtouch.setup.wizard_service._write_file_atomic",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "opencloudtouch.setup.wizard_service._file_exists",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_ssh = _mock_ssh()
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.text = "<info><name>Kitchen</name><margeAccountUUID>5448503</margeAccountUUID></info>"
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value = mock_client

            result = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

            assert result["success"] is True
            assert result["uuid"] == "5448503"
            assert result["had_uuid"] is True


class TestFinalizeDeviceSSHFails:
    """SSH connection fails -- should return error, no partial state."""

    @pytest.mark.asyncio
    async def test_ssh_failure_returns_error(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with (
            patch(
                "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
                new_callable=AsyncMock,
                return_value=AccountPairingResult(
                    success=True,
                    had_uuid=False,
                    uuid="1234567",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(
                side_effect=ConnectionError("SSH down")
            )
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

            assert result["success"] is False
            assert result["error"] is not None


class TestFinalizeDeviceUUIDFails:
    """UUID setup fails -- should return error."""

    @pytest.mark.asyncio
    async def test_uuid_failure_returns_error(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with patch(
            "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
            new_callable=AsyncMock,
            return_value=AccountPairingResult(
                success=False,
                had_uuid=False,
                error="SSH failed",
            ),
        ):
            result = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

            assert result["success"] is False
            assert "SSH failed" in result["error"]


class TestFinalizeDeviceNoRepo:
    """No device repo available -- should return error."""

    @pytest.mark.asyncio
    async def test_no_repo_returns_error(self):
        service = WizardService(device_repo=None)

        result = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

        assert result["success"] is False
        assert "repository" in result["error"].lower()


class TestFinalizeSystemConfig:
    """SystemConfigurationDB.xml handling."""

    @pytest.mark.asyncio
    async def test_creates_sysconfig_when_missing(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with (
            patch(
                "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
                new_callable=AsyncMock,
                return_value=AccountPairingResult(
                    success=True,
                    had_uuid=False,
                    uuid="1234567",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.force_write_sources_xml",
                new_callable=AsyncMock,
                return_value=ForceWriteResult(success=True),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="1234567",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
            patch(
                "opencloudtouch.setup.wizard_service._write_file_atomic",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_write,
            patch(
                "opencloudtouch.setup.wizard_service._file_exists",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_ssh = _mock_ssh()
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.text = "<info><name>Test</name><margeAccountUUID>1234567</margeAccountUUID></info>"
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value = mock_client

            result = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

            assert result["success"] is True
            assert result["system_config_written"] is True
            mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_overwrites_sysconfig_when_existing(self):
        """Existing SystemConfigurationDB.xml with wrong content must be overwritten."""
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with (
            patch(
                "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
                new_callable=AsyncMock,
                return_value=AccountPairingResult(
                    success=True,
                    had_uuid=False,
                    uuid="1234567",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.force_write_sources_xml",
                new_callable=AsyncMock,
                return_value=ForceWriteResult(success=True),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="1234567",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
            patch(
                "opencloudtouch.setup.wizard_service._write_file_atomic",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_write,
            patch(
                "opencloudtouch.setup.wizard_service._file_exists",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_ssh = _mock_ssh()
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.text = "<info><name>BÃ¼ro</name><margeAccountUUID>1234567</margeAccountUUID></info>"
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value = mock_client

            result = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

            assert result["success"] is True
            assert result["system_config_written"] is True
            mock_write.assert_called_once()
            # Verify correct content was written
            written_content = mock_write.call_args.args[2]
            assert "<AccountUUID>1234567</AccountUUID>" in written_content
            assert "<acctMode>local</acctMode>" in written_content


class TestFinalizeIdempotent:
    """Calling twice produces same result."""

    @pytest.mark.asyncio
    async def test_second_call_is_noop(self):
        repo = _make_device_repo(existing_uuid_owner="AABBCCDDEEFF")
        service = WizardService(device_repo=repo)

        with (
            patch(
                "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
                new_callable=AsyncMock,
                return_value=AccountPairingResult(
                    success=True,
                    had_uuid=True,
                    uuid="5448503",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.force_write_sources_xml",
                new_callable=AsyncMock,
                return_value=ForceWriteResult(success=True, had_existing=True),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value="5448503",
            ),
            patch(
                "opencloudtouch.setup.wizard_helpers.SoundTouchSSHClient",
            ) as mock_ssh_cls,
            patch(
                "opencloudtouch.setup.wizard_service._write_file_atomic",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "opencloudtouch.setup.wizard_service._file_exists",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_ssh = _mock_ssh()
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.text = "<info><name>Test</name><margeAccountUUID>5448503</margeAccountUUID></info>"
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value = mock_client

            r1 = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")
            r2 = await service.finalize_device("192.168.1.100", "AABBCCDDEEFF")

            assert r1["success"] is True
            assert r2["success"] is True
            assert r1["uuid"] == r2["uuid"]
            assert r1["system_config_written"] is True
            assert r2["system_config_written"] is True
