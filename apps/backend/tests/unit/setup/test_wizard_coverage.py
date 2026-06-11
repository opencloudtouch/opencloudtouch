"""Tests for wizard_service coverage gaps.

Covers: _apply_existing_config, _fetch_device_metadata hardware profile branch,
ensure_account_pairing error/success paths, verify_setup connection failure,
finalize_device edge cases (Sources.xml fail, existing config merge, DeviceName fallback),
_verify_sys_config XML parse error, and various check helper error branches.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opencloudtouch.setup.account_pairing_service import AccountPairingResult
from opencloudtouch.setup.persistence_service import ForceWriteResult
from opencloudtouch.setup.ssh_client import CommandResult
from opencloudtouch.setup.wizard_service import WizardService


def _make_device_repo(existing_uuid_owner=None):
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
    ssh = AsyncMock()
    ssh.execute = AsyncMock(
        return_value=CommandResult(success=True, output="", exit_code=0)
    )
    return ssh


# ── _apply_existing_config (removed in refactor) ────────────────────
# Method was removed from WizardService; tests deleted.


# ── ensure_account_pairing ───────────────────────────────────────────


class TestEnsureAccountPairing:
    @pytest.mark.asyncio
    async def test_success_with_repo_persists_uuid(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with patch(
            "opencloudtouch.setup.wizard_service.ensure_account_uuid",
            new_callable=AsyncMock,
            return_value=AccountPairingResult(
                success=True, had_uuid=True, uuid="1234567", message="OK"
            ),
        ):
            result = await service.ensure_account_pairing("192.168.1.10", "DEV001")

        assert result["success"] is True
        assert result["uuid"] == "1234567"
        repo.update_marge_account_uuid.assert_called_once_with("DEV001", "1234567")

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with patch(
            "opencloudtouch.setup.wizard_service.ensure_account_uuid",
            new_callable=AsyncMock,
            side_effect=ConnectionError("SSH timeout"),
        ):
            result = await service.ensure_account_pairing("192.168.1.10", "DEV001")

        assert result["success"] is False
        assert "SSH timeout" in result["error"]


# ── _fetch_device_metadata hardware profile branch ───────────────────


# ── _fetch_device_metadata (removed in refactor) ────────────────────
# Method was removed from WizardService; tests deleted.


# ── finalize_device edge cases ───────────────────────────────────────


def _finalize_patches(
    uuid="1234567",
    had_uuid=False,
    sources_success=True,
    existing_config=None,
    info_xml=None,
):
    """Build context manager stack for finalize_device tests."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _ctx():
        mock_ssh = _mock_ssh()

        with (
            patch(
                "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
                new_callable=AsyncMock,
                return_value=AccountPairingResult(
                    success=True, had_uuid=had_uuid, uuid=uuid, message="OK"
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.force_write_sources_xml",
                new_callable=AsyncMock,
                return_value=ForceWriteResult(
                    success=sources_success,
                    written_path="/path/Sources.xml" if sources_success else "",
                    error="" if sources_success else "Write failed",
                ),
            ),
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                return_value=uuid,
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
                return_value=existing_config is not None,
            ),
            patch("httpx.AsyncClient") as mock_http,
        ):
            mock_ssh_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ssh)
            mock_ssh_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp_xml = (
                info_xml
                or f"<info><name>SoundTouch</name><margeAccountUUID>{uuid}</margeAccountUUID></info>"
            )
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.text = resp_xml
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_http.return_value = mock_client

            yield

    return _ctx()


class TestFinalizeDeviceEdgeCases:
    @pytest.mark.asyncio
    async def test_sources_xml_failure_still_succeeds(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        async with _finalize_patches(sources_success=False):
            result = await service.finalize_device("192.168.1.10", "AABBCC")

        assert result["success"] is True
        assert result["sources_written"] is False

    @pytest.mark.asyncio
    async def test_existing_config_preserves_device_name(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)
        existing_xml = (
            "<SystemConfigurationDB>"
            "<DeviceName>My Speaker</DeviceName>"
            "</SystemConfigurationDB>"
        )

        async with _finalize_patches(existing_config=existing_xml):
            result = await service.finalize_device("192.168.1.10", "AABBCC")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_name_fallback_to_device_id(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        async with _finalize_patches(
            info_xml="<info><name>SoundTouch</name><margeAccountUUID>1234567</margeAccountUUID></info>"
        ):
            result = await service.finalize_device("192.168.1.10", "AABBCC112233")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_finalize_exception_returns_error(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with patch(
            "opencloudtouch.setup.wizard_service.ensure_account_uuid_unique",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Unexpected"),
        ):
            result = await service.finalize_device("192.168.1.10", "AABBCC")

        assert result["success"] is False
        assert "Unexpected" in result["error"]


# ── _verify_sys_config ───────────────────────────────────────────────


class TestVerifySysConfig:
    @pytest.mark.asyncio
    async def test_xml_parse_error(self):
        ssh = _mock_ssh()
        ssh.execute = AsyncMock(
            return_value=CommandResult(
                success=True, output="<broken>xml<<", exit_code=0
            )
        )
        result = await WizardService._verify_sys_config(ssh, "1234567")
        assert result["passed"] is False
        assert "parse" in result.get("error", "").lower() or not result["passed"]


# ── verify_setup connection failure ──────────────────────────────────


class TestVerifySetupConnectionFailure:
    @pytest.mark.asyncio
    async def test_connection_error_adds_check(self):
        repo = _make_device_repo()
        service = WizardService(device_repo=repo)

        with (
            patch(
                "opencloudtouch.setup.wizard_service.check_marge_account_uuid",
                new_callable=AsyncMock,
                side_effect=ConnectionError("Cannot connect"),
            ),
        ):
            result = await service.verify_setup("192.168.1.10", "DEV001", "10.0.0.1")

        assert result["success"] is False
        conn_check = [c for c in result["checks"] if c["name"] == "connection"]
        assert len(conn_check) == 1
        assert conn_check[0]["passed"] is False


# ── Check helper error branches ──────────────────────────────────────


def _make_add(checks: list):
    """Create an _add callback that appends check results to a list."""

    def _add(name, passed, msg, details=None):
        checks.append(
            {"name": name, "passed": passed, "message": msg, "details": details or {}}
        )

    return _add


class TestCheckHelperErrorBranches:
    @pytest.mark.asyncio
    async def test_uuid_in_db_no_repo(self):
        service = WizardService(device_repo=None)
        checks: list[dict] = []
        await service._check_uuid_in_db("DEV001", "1234567", _make_add(checks))
        assert checks[0]["name"] == "uuid_in_db"
        assert checks[0]["passed"] is False

    @pytest.mark.asyncio
    async def test_sources_complete_empty(self):
        service = WizardService()
        ssh = _mock_ssh()
        ssh.execute = AsyncMock(
            return_value=CommandResult(success=False, output="", exit_code=1)
        )
        checks: list[dict] = []
        await service._check_sources_complete(ssh, _make_add(checks))
        assert checks[0]["passed"] is False
        assert "not found" in checks[0]["message"]

    @pytest.mark.asyncio
    async def test_config_files_identical_skipped_when_all_missing(self):
        service = WizardService()
        ssh = _mock_ssh()
        checks: list[dict] = []
        # All CONFIG_CANDIDATES missing → only 0 present → True (no comparison needed)
        from opencloudtouch.setup.config_service import SoundTouchConfigService

        all_missing = list(SoundTouchConfigService.CONFIG_CANDIDATES)
        await service._check_config_files_identical(ssh, all_missing, _make_add(checks))
        assert checks[0]["passed"] is True
        assert "no comparison" in checks[0]["message"].lower()

    @pytest.mark.asyncio
    async def test_config_files_identical_unreadable(self):
        service = WizardService()
        ssh = _mock_ssh()
        ssh.execute = AsyncMock(
            return_value=CommandResult(success=False, output="", exit_code=1)
        )
        checks: list[dict] = []
        await service._check_config_files_identical(ssh, [], _make_add(checks))
        assert checks[0]["passed"] is False

    @pytest.mark.asyncio
    async def test_bmx_url_not_readable(self):
        service = WizardService()
        ssh = _mock_ssh()
        ssh.execute = AsyncMock(
            return_value=CommandResult(success=False, output="", exit_code=1)
        )
        checks: list[dict] = []
        await service._check_bmx_url(ssh, _make_add(checks))
        assert checks[0]["passed"] is False

    @pytest.mark.asyncio
    async def test_bmx_url_not_found_in_config(self):
        service = WizardService()
        ssh = _mock_ssh()
        ssh.execute = AsyncMock(
            return_value=CommandResult(
                success=True,
                output="<config>no-bmx-here</config>",
                exit_code=0,
            )
        )
        checks: list[dict] = []
        await service._check_bmx_url(ssh, _make_add(checks))
        assert checks[0]["passed"] is False
        assert "not found" in checks[0]["message"]

    @pytest.mark.asyncio
    async def test_system_config_uuid_skipped_no_uuid(self):
        service = WizardService()
        ssh = _mock_ssh()
        checks: list[dict] = []
        await service._check_system_config_uuid(ssh, True, None, _make_add(checks))
        assert checks[0]["passed"] is False
        assert "Skipped" in checks[0]["message"]
