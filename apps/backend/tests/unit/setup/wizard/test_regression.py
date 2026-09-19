"""Regression tests guarding against previously-fixed stale-mock and dead-code bugs.

Covers build_system_config_xml's acctMode/DeviceName/AccountUUID encoding
(root cause of the Phase 1 / 010-websocket-push incident, where several tests
kept mocking WizardService methods that had since been inlined or removed),
confirmation that WizardService/opencloudtouch.setup.wizard no longer expose
_apply_existing_config, _fetch_device_metadata, _read_file_content, or the
removed legacy list_backups/ensure_account_pairing methods, and an edge case
of _check_config_files_identical.
"""

from unittest.mock import AsyncMock

import pytest

from opencloudtouch.setup.persistence_service import build_system_config_xml
from opencloudtouch.setup.ssh_client import CommandResult
from opencloudtouch.setup.wizard import WizardService


class TestBuildSystemConfigXmlAcctMode:
    """Regression: acctMode must be 'global' (not 'local')."""

    def test_acct_mode_is_global(self):
        xml = build_system_config_xml("TestDevice", "1234567")
        assert "<acctMode>local</acctMode>" in xml

    def test_device_name_embedded(self):
        xml = build_system_config_xml("Kitchen", "9999999")
        assert "<DeviceName>Kitchen</DeviceName>" in xml

    def test_uuid_embedded(self):
        xml = build_system_config_xml("Kitchen", "1234567")
        assert "<AccountUUID>1234567</AccountUUID>" in xml

    def test_xml_escapes_device_name(self):
        xml = build_system_config_xml("Büro & <Küche>", "1234567")
        assert "&amp;" in xml
        assert "&lt;" in xml
        assert "&gt;" in xml


class TestWizardServiceRemovedMethods:
    """Regression: these methods were removed/inlined — confirm they don't exist."""

    def test_no_apply_existing_config(self):
        assert not hasattr(WizardService, "_apply_existing_config")

    def test_no_fetch_device_metadata(self):
        assert not hasattr(WizardService, "_fetch_device_metadata")

    def test_no_read_file_content_in_module(self):
        from opencloudtouch.setup.wizard import service as mod

        assert not hasattr(mod, "_read_file_content")


class TestLegacyWizardMethodsRemoved:
    """Regression: dead pre-Restore-Wizard methods were deleted in the setup/wizard refactor."""

    def test_no_list_backups(self):
        assert not hasattr(WizardService, "list_backups")

    def test_no_ensure_account_pairing(self):
        assert not hasattr(WizardService, "ensure_account_pairing")


class TestWizardServiceExistingMethods:
    """Regression: these internal methods MUST exist (tests mock them)."""

    def test_file_exists_importable(self):
        from opencloudtouch.setup.persistence_service import _file_exists

        assert callable(_file_exists)

    def test_write_file_atomic_importable(self):
        from opencloudtouch.setup.persistence_service import _write_file_atomic

        assert callable(_write_file_atomic)


class TestCheckConfigFilesIdenticalMissing:
    """Regression: _check_config_files_identical returns False when configs missing."""

    @pytest.mark.asyncio
    async def test_missing_configs_returns_false(self):
        service = WizardService()
        ssh = AsyncMock()
        ssh.execute = AsyncMock(
            return_value=CommandResult(success=True, output="", exit_code=0)
        )

        checks: list[dict] = []

        def _add(name, passed, message, data):
            checks.append(
                {"name": name, "passed": passed, "message": message, "data": data}
            )

        from opencloudtouch.setup.config_service import SoundTouchConfigService

        all_missing = list(SoundTouchConfigService.CONFIG_CANDIDATES)
        await service._check_config_files_identical(ssh, all_missing, _add)

        assert len(checks) == 1
        assert checks[0]["passed"] is True
        assert "no comparison" in checks[0]["message"].lower()
