"""Tests for persistence_service — factory-reset device initialization."""

import base64

import pytest
from unittest.mock import AsyncMock

from opencloudtouch.setup.persistence_service import (
    build_sources_xml,
    build_system_config_xml,
    ensure_persistence_files,
    force_write_sources_xml,
    parse_system_config_xml,
    _PERSISTENCE_DIR,
)
from opencloudtouch.setup.ssh_client import CommandResult

# —— XML Generation ————————————————————————————————————


class TestBuildSystemConfigXml:
    """Tests for SystemConfigurationDB.xml generation."""

    def test_contains_device_name(self):
        xml = build_system_config_xml("Kitchen Speaker", "1234567")
        assert "<DeviceName>Kitchen Speaker</DeviceName>" in xml

    def test_contains_account_uuid(self):
        xml = build_system_config_xml("Test", "8866380")
        assert "<AccountUUID>8866380</AccountUUID>" in xml

    def test_has_xml_declaration(self):
        xml = build_system_config_xml("Test", "1234567")
        assert xml.startswith('<?xml version="1.0"')

    def test_has_closing_tag(self):
        xml = build_system_config_xml("Test", "1234567")
        assert "</SystemConfiguration>" in xml

    def test_local_acct_mode(self):
        xml = build_system_config_xml("Test", "1234567")
        assert "<acctMode>local</acctMode>" in xml

    def test_multi_device_account_true(self):
        xml = build_system_config_xml("Test", "1234567")
        assert "<isMultiDeviceAccount>true</isMultiDeviceAccount>" in xml


class TestSourcesXml:
    """Tests for the Sources.xml builder."""

    def test_contains_local_internet_radio(self):
        xml = build_sources_xml()
        assert 'type="LOCAL_INTERNET_RADIO"' in xml

    def test_contains_tunein(self):
        xml = build_sources_xml()
        assert 'type="TUNEIN"' in xml

    def test_contains_radio_browser(self):
        xml = build_sources_xml()
        assert 'type="RADIO_BROWSER"' in xml

    def test_contains_aux(self):
        xml = build_sources_xml()
        assert 'type="AUX"' in xml

    def test_contains_airplay(self):
        xml = build_sources_xml()
        assert 'type="AIRPLAY"' in xml

    def test_has_xml_declaration(self):
        xml = build_sources_xml()
        assert xml.startswith('<?xml version="1.0"')

    def test_includes_bluetooth_by_default(self):
        xml = build_sources_xml()
        assert 'type="BLUETOOTH"' in xml

    def test_excludes_bluetooth_when_disabled(self):
        xml = build_sources_xml(has_bluetooth=False)
        assert 'type="BLUETOOTH"' not in xml
        # Other sources still present
        assert 'type="TUNEIN"' in xml
        assert 'type="AUX"' in xml

    def test_includes_bluetooth_explicitly(self):
        xml = build_sources_xml(has_bluetooth=True)
        assert 'type="BLUETOOTH"' in xml


# —— Helpers ———————————————————————————————————————————


def _mock_ssh(file_exists_map: dict[str, bool] | None = None) -> AsyncMock:
    """Create a mock SSH client with configurable file existence."""
    ssh = AsyncMock()
    exists = file_exists_map or {}

    async def fake_execute(cmd: str) -> CommandResult:
        # mkdir -p
        if cmd.startswith("mkdir"):
            return CommandResult(success=True, output="", exit_code=0)
        # file existence check
        if "test -f" in cmd:
            path = cmd.split("test -f ")[1].split(" &&")[0]
            found = exists.get(path, False)
            return CommandResult(
                success=True,
                output="exists" if found else "missing",
                exit_code=0,
            )
        # write (base64 pipe)
        if "base64 -d" in cmd:
            return CommandResult(success=True, output="", exit_code=0)
        # fallback
        return CommandResult(success=True, output="", exit_code=0)

    ssh.execute = AsyncMock(side_effect=fake_execute)
    return ssh


# —— ensure_persistence_files ——————————————————————————


class TestEnsurePersistenceFiles:
    """Tests for the main persistence initialization function."""

    @pytest.mark.asyncio
    async def test_creates_both_files_when_missing(self):
        ssh = _mock_ssh({})  # no files exist
        result = await ensure_persistence_files(ssh, "SoundTouch 20", "8866380")

        assert result.success is True
        assert len(result.created_files) == 2
        assert f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml" in result.created_files
        assert f"{_PERSISTENCE_DIR}/Sources.xml" in result.created_files
        assert result.skipped_files == []

    @pytest.mark.asyncio
    async def test_skips_existing_files(self):
        ssh = _mock_ssh(
            {
                f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml": True,
                f"{_PERSISTENCE_DIR}/Sources.xml": True,
            }
        )
        result = await ensure_persistence_files(ssh, "SoundTouch 20", "8866380")

        assert result.success is True
        assert result.created_files == []
        assert len(result.skipped_files) == 2

    @pytest.mark.asyncio
    async def test_creates_only_missing_sysconfig(self):
        ssh = _mock_ssh(
            {
                f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml": False,
                f"{_PERSISTENCE_DIR}/Sources.xml": True,
            }
        )
        result = await ensure_persistence_files(ssh, "Test", "1234567")

        assert result.success is True
        assert len(result.created_files) == 1
        assert f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml" in result.created_files
        assert f"{_PERSISTENCE_DIR}/Sources.xml" in result.skipped_files

    @pytest.mark.asyncio
    async def test_creates_only_missing_sources(self):
        ssh = _mock_ssh(
            {
                f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml": True,
                f"{_PERSISTENCE_DIR}/Sources.xml": False,
            }
        )
        result = await ensure_persistence_files(ssh, "Test", "1234567")

        assert result.success is True
        assert len(result.created_files) == 1
        assert f"{_PERSISTENCE_DIR}/Sources.xml" in result.created_files
        assert f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml" in result.skipped_files

    @pytest.mark.asyncio
    async def test_ensures_directory_created(self):
        ssh = _mock_ssh({})
        await ensure_persistence_files(ssh, "Test", "1234567")

        # First call should be mkdir -p
        first_call = ssh.execute.call_args_list[0]
        assert f"mkdir -p {_PERSISTENCE_DIR}" in first_call.args[0]

    @pytest.mark.asyncio
    async def test_returns_error_on_write_failure(self):
        ssh = AsyncMock()
        call_count = 0

        async def failing_execute(cmd: str) -> CommandResult:
            nonlocal call_count
            call_count += 1
            if cmd.startswith("mkdir"):
                return CommandResult(success=True, output="", exit_code=0)
            if "test -f" in cmd:
                return CommandResult(success=True, output="missing", exit_code=0)
            if "base64 -d" in cmd:
                return CommandResult(
                    success=False, output="", exit_code=1, error="disk full"
                )
            return CommandResult(success=True, output="", exit_code=0)

        ssh.execute = AsyncMock(side_effect=failing_execute)
        result = await ensure_persistence_files(ssh, "Test", "1234567")

        assert result.success is False
        assert result.error is not None
        assert "disk full" in result.error or "Failed to write" in result.error

    @pytest.mark.asyncio
    async def test_written_sysconfig_contains_uuid(self):
        """Verify the actual XML content written contains the UUID."""
        ssh = _mock_ssh({})
        written_content = []

        original_execute = ssh.execute.side_effect

        async def capture_execute(cmd: str) -> CommandResult:
            result = await original_execute(cmd)
            if "base64 -d" in cmd:
                written_content.append(cmd)
            return result

        ssh.execute = AsyncMock(side_effect=capture_execute)
        await ensure_persistence_files(ssh, "Kitchen", "5551234")

        assert len(written_content) >= 1
        # Decode base64 payload from the first write command and verify UUID
        first_write = written_content[0]
        b64_payload = first_write.split("echo '")[1].split("'")[0]
        decoded = base64.b64decode(b64_payload).decode()
        assert "5551234" in decoded
        assert "Kitchen" in decoded


# —— force_write_sources_xml ———————————————————————————


class TestForceWriteSourcesXml:
    """Tests for force-write Sources.xml (always overwrite, backup existing)."""

    @pytest.mark.asyncio
    async def test_writes_sources_no_existing(self):
        ssh = _mock_ssh({})
        result = await force_write_sources_xml(ssh)

        assert result.success is True
        assert result.had_existing is False
        assert result.backup_path == ""
        assert result.written_path == f"{_PERSISTENCE_DIR}/Sources.xml"

    @pytest.mark.asyncio
    async def test_writes_sources_with_backup(self):
        ssh = _mock_ssh({f"{_PERSISTENCE_DIR}/Sources.xml": True})
        result = await force_write_sources_xml(ssh, backup=True)

        assert result.success is True
        assert result.had_existing is True
        assert result.backup_path == f"{_PERSISTENCE_DIR}/Sources.xml.bak"

    @pytest.mark.asyncio
    async def test_writes_sources_skip_backup(self):
        ssh = _mock_ssh({f"{_PERSISTENCE_DIR}/Sources.xml": True})
        result = await force_write_sources_xml(ssh, backup=False)

        assert result.success is True
        assert result.had_existing is True
        assert result.backup_path == ""

    @pytest.mark.asyncio
    async def test_returns_error_on_write_failure(self):
        ssh = _mock_ssh({})

        async def failing_execute(cmd: str) -> CommandResult:
            if "base64 -d" in cmd:
                return CommandResult(
                    success=False, output="", exit_code=1, error="disk full"
                )
            if cmd.startswith("mkdir"):
                return CommandResult(success=True, output="", exit_code=0)
            if "test -f" in cmd:
                return CommandResult(success=True, output="missing", exit_code=0)
            return CommandResult(success=True, output="", exit_code=0)

        ssh.execute = AsyncMock(side_effect=failing_execute)
        result = await force_write_sources_xml(ssh)

        assert result.success is False
        assert result.error is not None


class TestXmlEscaping:
    """Tests for XML special character handling in device names."""

    def test_escapes_angle_brackets(self):
        xml = build_system_config_xml("Bose <Living Room>", "1234567")
        assert "&lt;Living Room&gt;" in xml
        assert "<Living Room>" not in xml

    def test_escapes_ampersand(self):
        xml = build_system_config_xml("Kitchen & Bath", "1234567")
        assert "Kitchen &amp; Bath" in xml

    def test_escapes_quotes_in_name(self):
        xml = build_system_config_xml('My "Speaker"', "1234567")
        assert "</DeviceName>" in xml
        assert "</SystemConfiguration>" in xml

    def test_result_is_parseable_xml(self):
        from defusedxml import ElementTree as ET

        xml = build_system_config_xml("Böse <Lautsprecher> & Mehr", "9876543")
        root = ET.fromstring(xml)
        assert root.find("DeviceName").text == "Böse <Lautsprecher> & Mehr"
        assert root.find("AccountUUID").text == "9876543"


class TestParseSystemConfigXml:
    """Tests for extracting values from existing SystemConfigurationDB.xml."""

    def test_extracts_device_name_and_uuid(self):
        xml = build_system_config_xml("Büro", "1234567")
        result = parse_system_config_xml(xml)
        assert result["device_name"] == "Büro"
        assert result["account_uuid"] == "1234567"

    def test_handles_empty_uuid(self):
        xml = build_system_config_xml("Büro", "")
        result = parse_system_config_xml(xml)
        assert result["device_name"] == "Büro"
        assert result["account_uuid"] == ""

    def test_handles_empty_device_name(self):
        xml = build_system_config_xml("", "1234567")
        result = parse_system_config_xml(xml)
        assert result["device_name"] == ""
        assert result["account_uuid"] == "1234567"

    def test_handles_malformed_xml(self):
        result = parse_system_config_xml("<broken>xml")
        assert result["device_name"] == ""
        assert result["account_uuid"] == ""

    def test_handles_real_device_xml(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8" ?>\n'
            "<SystemConfiguration>\n"
            "    <Password />\n"
            "    <DeviceName>Büro</DeviceName>\n"
            "    <AccountAssociatedEMail />\n"
            "    <AccountUUID></AccountUUID>\n"
            "    <Locale />\n"
            "    <acctMode>local</acctMode>\n"
            "    <isMultiDeviceAccount>true</isMultiDeviceAccount>\n"
            "    <margeAuthServerToken />\n"
            '    <powerSavingSettings powersaving_en="true" />\n'
            "</SystemConfiguration>\n"
        )
        result = parse_system_config_xml(xml)
        assert result["device_name"] == "Büro"
        assert result["account_uuid"] == ""
