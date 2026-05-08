"""
Unit tests for SoundTouchConfigService.

Regression tests for:
- BUG-03: Wrong config path /nv/ instead of /mnt/nv/

On the real SoundTouch device the config file is at:
  /mnt/nv/OverrideSdkPrivateCfg.xml

The old code had CONFIG_PATH = "/nv/OverrideSdkPrivateCfg.xml" which
caused step 5 (config modification) to fail with "file not found".
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.setup.config_service import (
    ConfigDiff,
    SoundTouchConfigService,
)
from opencloudtouch.setup.ssh_client import CommandResult

# Sample config XML as found on real SoundTouch 10 devices (unmodified state)
SAMPLE_CONFIG_XML = """\
<SoundTouchSdkPrivateCfg>
    <margeServerUrl>https://streaming.bose.com</margeServerUrl>
    <statsServerUrl>https://events.api.bosecm.com</statsServerUrl>
    <swUpdateUrl>https://worldwide.bose.com/updates/soundtouch</swUpdateUrl>
    <isZeroconfEnabled>true</isZeroconfEnabled>
    <usePandoraProductionServer>true</usePandoraProductionServer>
    <saveMargeCustomerReport>false</saveMargeCustomerReport>
    <bmxRegistryUrl>https://content.api.bose.io/bmx/registry/v1/services</bmxRegistryUrl>
</SoundTouchSdkPrivateCfg>
"""

# Real output from device after OCT modification (cat /mnt/nv/OverrideSdkPrivateCfg.xml)
SAMPLE_CONFIG_ALREADY_MODIFIED = """\
<SoundTouchSdkPrivateCfg>
    <margeServerUrl>http://content.api.bose.io:7777</margeServerUrl>
    <statsServerUrl>http://content.api.bose.io:7777</statsServerUrl>
    <swUpdateUrl>http://content.api.bose.io:7777/updates/soundtouch</swUpdateUrl>
    <isZeroconfEnabled>true</isZeroconfEnabled>
    <usePandoraProductionServer>true</usePandoraProductionServer>
    <saveMargeCustomerReport>false</saveMargeCustomerReport>
    <bmxRegistryUrl>http://content.api.bose.io:7777/bmx/registry/v1/services</bmxRegistryUrl>
</SoundTouchSdkPrivateCfg>
"""


def _ok(output: str = "") -> CommandResult:
    """Helper: successful CommandResult."""
    return CommandResult(success=True, output=output, exit_code=0)


def _fail(error: str = "error", exit_code: int = 1) -> CommandResult:
    """Helper: failed CommandResult."""
    return CommandResult(success=False, output="", exit_code=exit_code, error=error)


@pytest.fixture
def mock_ssh():
    """Mocked SoundTouchSSHClient."""
    ssh = MagicMock()
    ssh.execute = AsyncMock()
    return ssh


@pytest.fixture
def service(mock_ssh):
    svc = SoundTouchConfigService(mock_ssh)
    # Pre-set config path to avoid extra SSH probe in every test
    svc.config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
    return svc


# ---------------------------------------------------------------------------
# BUG-03: Wrong config path /nv/ vs /mnt/nv/
# ---------------------------------------------------------------------------


class TestConfigPath:
    """Config path auto-detection tests."""

    @pytest.fixture
    def fresh_service(self, mock_ssh):
        """Service without pre-set config_path for detection tests."""
        return SoundTouchConfigService(mock_ssh)

    def test_first_candidate_is_opt_bose(self):
        assert (
            SoundTouchConfigService.CONFIG_CANDIDATES[0]
            == "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        )

    def test_all_three_candidates(self):
        """All 3 known config paths must be probed."""
        candidates = SoundTouchConfigService.CONFIG_CANDIDATES
        assert len(candidates) == 3
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in candidates
        assert "/mnt/nv/OverrideSdkPrivateCfg.xml" in candidates
        assert "/mnt/nv/SoundTouchSdkPrivateCfg.xml" in candidates

    def test_backup_dir_is_on_persistent_volume(self):
        """Backups must be on persistent volume so they survive reboots."""
        assert SoundTouchConfigService.BACKUP_DIR == "/mnt/nv"

    @pytest.mark.asyncio
    async def test_detect_canonical_path(self, fresh_service, mock_ssh):
        """Detects /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml."""
        mock_ssh.execute.return_value = _ok("found")
        path = await fresh_service._detect_config_path()
        assert path == "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"

    @pytest.mark.asyncio
    async def test_detect_raises_when_none_found(self, fresh_service, mock_ssh):
        """Raises RuntimeError when no config file exists."""
        mock_ssh.execute.return_value = _ok("missing")
        with pytest.raises(RuntimeError, match="Config file not found"):
            await fresh_service._detect_config_path()

    @pytest.mark.asyncio
    async def test_detect_caches_result(self, fresh_service, mock_ssh):
        """Second call returns cached path without SSH call."""
        mock_ssh.execute.return_value = _ok("found")
        await fresh_service._detect_config_path()
        mock_ssh.execute.reset_mock()
        path = await fresh_service._detect_config_path()
        assert path == "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        mock_ssh.execute.assert_not_called()


# ---------------------------------------------------------------------------
# _replace_tag_value (pure function, no SSH)
# ---------------------------------------------------------------------------


class TestReplaceTagValue:
    """Unit tests for the XML tag replacement logic."""

    def test_replaces_bmx_registry_url(self):
        xml = "<bmxRegistryUrl>https://old.url</bmxRegistryUrl>"
        result, old = SoundTouchConfigService._replace_tag_value(
            xml, "bmxRegistryUrl", "http://new.url"
        )
        assert result == "<bmxRegistryUrl>http://new.url</bmxRegistryUrl>"
        assert old == "https://old.url"

    def test_replaces_only_first_occurrence(self):
        xml = "<bmxRegistryUrl>A</bmxRegistryUrl>" "<bmxRegistryUrl>B</bmxRegistryUrl>"
        result, old = SoundTouchConfigService._replace_tag_value(
            xml, "bmxRegistryUrl", "C"
        )
        assert result.count("<bmxRegistryUrl>C</bmxRegistryUrl>") == 1
        assert old == "A"

    def test_returns_none_when_tag_not_found(self):
        xml = "<other>value</other>"
        result, old = SoundTouchConfigService._replace_tag_value(
            xml, "bmxRegistryUrl", "http://new"
        )
        assert result == xml
        assert old is None

    def test_preserves_surrounding_xml(self):
        xml = (
            '<?xml version="1.0"?>\n'
            "<root>\n"
            "  <bmxRegistryUrl>https://old</bmxRegistryUrl>\n"
            "  <other>keep</other>\n"
            "</root>"
        )
        result, _ = SoundTouchConfigService._replace_tag_value(
            xml, "bmxRegistryUrl", "http://new"
        )
        assert "<other>keep</other>" in result
        assert '<?xml version="1.0"?>' in result

    def test_handles_empty_tag_value(self):
        xml = "<bmxRegistryUrl></bmxRegistryUrl>"
        result, old = SoundTouchConfigService._replace_tag_value(
            xml, "bmxRegistryUrl", "http://new"
        )
        assert result == "<bmxRegistryUrl>http://new</bmxRegistryUrl>"
        assert old == ""


# ---------------------------------------------------------------------------
# URL builders (pure functions)
# ---------------------------------------------------------------------------


class TestUrlBuilders:
    """Tests for static URL builder methods."""

    def test_bmx_url_uses_http(self):
        url = SoundTouchConfigService.build_bmx_url("192.168.1.50")
        assert url.startswith("http://")
        assert "https" not in url

    def test_bmx_url_uses_bose_domain(self):
        """URL must use content.api.bose.io domain (resolved via /etc/hosts)."""
        url = SoundTouchConfigService.build_bmx_url("192.168.1.50")
        assert "content.api.bose.io" in url

    def test_bmx_url_default_port(self):
        url = SoundTouchConfigService.build_bmx_url("192.168.1.50")
        assert ":7777/" in url

    def test_bmx_url_custom_port(self):
        url = SoundTouchConfigService.build_bmx_url("192.168.1.50", port=8080)
        assert ":8080/" in url

    def test_bmx_url_includes_registry_path(self):
        url = SoundTouchConfigService.build_bmx_url("x")
        assert url.endswith("/bmx/registry/v1/services")

    def test_marge_url_uses_http(self):
        url = SoundTouchConfigService.build_marge_url("x")
        assert url.startswith("http://")

    def test_swupdate_url_includes_path(self):
        url = SoundTouchConfigService.build_swupdate_url("x")
        assert "/updates/soundtouch" in url


# ---------------------------------------------------------------------------
# ConfigDiff
# ---------------------------------------------------------------------------


class TestConfigDiff:
    def test_empty_diff(self):
        d = ConfigDiff()
        assert str(d) == ""
        assert d.changes == []

    def test_single_change(self):
        d = ConfigDiff()
        d.add("bmxRegistryUrl", "old", "new")
        s = str(d)
        assert "<bmxRegistryUrl>" in s
        assert "- old" in s
        assert "+ new" in s

    def test_multiple_changes(self):
        d = ConfigDiff()
        d.add("tag1", "a", "b")
        d.add("tag2", "c", "d")
        assert len(d.changes) == 2


# ---------------------------------------------------------------------------
# modify_bmx_url (integration with mocked SSH)
# ---------------------------------------------------------------------------


class TestModifyBmxUrl:
    """Tests for the full modify_bmx_url flow."""

    @pytest.mark.asyncio
    async def test_happy_path_modifies_bmx_url(self, service, mock_ssh):
        """Full flow: remount rw → read → backup → write → verify → sync override → remount ro."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config (cat)
            _ok("missing"),  # backup check (test -f → missing)
            _ok(),  # cp backup
            _ok(),  # write config (base64 pipe)
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify read-back
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await service.modify_bmx_url("192.168.1.50")

        assert result.success is True
        assert result.backup_path != ""
        assert "bmxRegistryUrl" in result.diff

    @pytest.mark.asyncio
    async def test_creates_backup_before_modifying(self, service, mock_ssh):
        """Backup must be created before any modification."""
        calls_log = []

        async def track_calls(cmd, **kwargs):
            calls_log.append(cmd)
            if "cat" in cmd and "config" not in cmd.lower():
                return _ok("missing")
            if "cat" in cmd:
                return _ok(SAMPLE_CONFIG_XML)
            if "base64" in cmd:
                return _ok()
            return _ok(SAMPLE_CONFIG_ALREADY_MODIFIED if "cat" in cmd else "")

        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        # Verify backup cp was called (4th SSH command = index 3)
        cp_call = mock_ssh.execute.call_args_list[3][0][0]
        assert "cp" in cp_call

    @pytest.mark.asyncio
    async def test_skips_backup_if_already_exists(self, service, mock_ssh):
        """Don't overwrite existing backup."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup check → already exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        # No cp command should have been issued (backup exists)
        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        cp_cmds = [c for c in all_cmds if c.startswith("cp ")]
        assert len(cp_cmds) == 0

    @pytest.mark.asyncio
    async def test_writes_config_atomically(self, service, mock_ssh):
        """Config must be written via /tmp then mv (BusyBox atomic write)."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        await service.modify_bmx_url("192.168.1.50")

        # Find the write command (index 3: remount, read, backup_check, write)
        write_cmd = mock_ssh.execute.call_args_list[3][0][0]
        assert "base64 -d" in write_cmd
        assert "/tmp/config.new" in write_cmd
        assert "mv /tmp/config.new" in write_cmd

    @pytest.mark.asyncio
    async def test_verifies_config_after_write(self, service, mock_ssh):
        """Must read back and verify XML after writing."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok("corrupted garbage"),  # verify → missing closing tag!
            _ok(),  # remount ro
        ]

        result = await service.modify_bmx_url("192.168.1.50")

        assert result.success is False
        assert "verification failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_remounts_rw_before_and_ro_after(self, service, mock_ssh):
        """Filesystem must be remounted rw before write, ro after."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        await service.modify_bmx_url("192.168.1.50")

        cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        assert cmds[0] == "mount -o remount,rw /"
        assert cmds[-1] == "mount -o remount,ro /"

    @pytest.mark.asyncio
    async def test_remounts_ro_even_on_error(self, service, mock_ssh):
        """remount ro must happen even when modification fails (finally block)."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _fail("cannot read"),  # read config fails → RuntimeError
            _ok(),  # remount ro (finally)
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is False

        # Last call must still be remount ro
        last_cmd = mock_ssh.execute.call_args_list[-1][0][0]
        assert "remount,ro" in last_cmd

    @pytest.mark.asyncio
    async def test_connection_error_returns_failure(self, service, mock_ssh):
        """SSH connection error returns ModifyResult(success=False)."""
        mock_ssh.execute.side_effect = OSError("connection lost")

        result = await service.modify_bmx_url("192.168.1.50")

        assert result.success is False
        assert "connection lost" in result.error

    @pytest.mark.asyncio
    async def test_no_url_tags_returns_success_with_info(self, service, mock_ssh):
        """Config without any URL tags still succeeds but reports no changes."""
        minimal_xml = (
            '<?xml version="1.0"?>'
            "<SoundTouchSdkPrivateCfg>"
            "<isZeroconfEnabled>true</isZeroconfEnabled>"
            "</SoundTouchSdkPrivateCfg>"
        )
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(minimal_xml),  # read config
            _ok("exists"),  # backup check
            _ok(),  # remount ro (no write — no changes)
        ]

        result = await service.modify_bmx_url("192.168.1.50")

        assert result.success is True
        assert "no changes" in result.diff.lower()

    @pytest.mark.asyncio
    async def test_diff_contains_old_and_new_urls(self, service, mock_ssh):
        """Diff must show what was changed."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup check
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await service.modify_bmx_url("192.168.1.50")

        assert "https://content.api.bose.io/bmx" in result.diff  # old
        assert "http://content.api.bose.io:7777/bmx" in result.diff  # new
        assert "https://streaming.bose.com" in result.diff  # old marge
        assert "http://content.api.bose.io:7777" in result.diff  # new marge

    @pytest.mark.asyncio
    async def test_bmx_url_always_http_never_https(self, service, mock_ssh):
        """Critical: BMX URL must be HTTP. HTTPS breaks SoundTouch devices."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup check
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        await service.modify_bmx_url("192.168.1.50")

        # Find the write command and decode the base64 content
        write_cmd = mock_ssh.execute.call_args_list[3][0][0]
        # Extract base64 string from: echo 'BASE64' | base64 -d > ...
        import base64 as b64

        b64_str = write_cmd.split("'")[1]
        written_xml = b64.b64decode(b64_str).decode()

        # The written bmxRegistryUrl must be HTTP
        assert "http://content.api.bose.io:7777/bmx" in written_xml
        assert "<bmxRegistryUrl>https://" not in written_xml


# ---------------------------------------------------------------------------
# restore_config
# ---------------------------------------------------------------------------


class TestRestoreConfig:

    @pytest.mark.asyncio
    async def test_restore_success(self, service, mock_ssh):
        """Happy path: backup exists → cp → verify → success."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _ok(),  # remount rw
            _ok(),  # cp restore
            _ok(SAMPLE_CONFIG_XML),  # verify
            _ok(),  # remount ro
        ]

        result = await service.restore_config(
            "/mnt/nv/OverrideSdkPrivateCfg.xml.oct-backup"
        )

        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_restore_backup_not_found(self, service, mock_ssh):
        """Backup missing → fail without modifying anything."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # backup check
        ]

        result = await service.restore_config("/mnt/nv/nonexistent.xml")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_restore_copy_failure(self, service, mock_ssh):
        """cp fails → fail result."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _ok(),  # remount rw
            _fail("permission denied"),  # cp fails
            _ok(),  # remount ro
        ]

        result = await service.restore_config("/mnt/nv/backup.xml")

        assert result.success is False
        assert "permission denied" in result.error.lower()

    @pytest.mark.asyncio
    async def test_restore_verify_failure(self, service, mock_ssh):
        """Verification after copy fails → error result."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _ok(),  # remount rw
            _ok(),  # cp
            _ok("garbage"),  # verify → missing XML tag
            _ok(),  # remount ro
        ]

        result = await service.restore_config("/mnt/nv/backup.xml")

        assert result.success is False
        assert "verification" in result.error.lower()

    @pytest.mark.asyncio
    async def test_restore_remounts_ro_on_error(self, service, mock_ssh):
        """remount ro must happen even when restore fails."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _ok(),  # remount rw
            _fail("disk full"),  # cp fails
            _ok(),  # remount ro (finally)
        ]

        await service.restore_config("/mnt/nv/backup.xml")

        last_cmd = mock_ssh.execute.call_args_list[-1][0][0]
        assert "remount,ro" in last_cmd

    @pytest.mark.asyncio
    async def test_restore_ssh_exception(self, service, mock_ssh):
        """SSH exception → clean error result."""
        mock_ssh.execute.side_effect = OSError("network unreachable")

        result = await service.restore_config("/mnt/nv/backup.xml")

        assert result.success is False
        assert "network unreachable" in result.error


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------


class TestListBackups:

    @pytest.mark.asyncio
    async def test_list_backups_returns_paths(self, service, mock_ssh):
        """Happy path: ls returns backup files."""
        mock_ssh.execute.return_value = _ok(
            "/mnt/nv/OverrideSdkPrivateCfg.xml.oct-backup\n"
            "/mnt/nv/OverrideSdkPrivateCfg.xml.backup.20260310\n"
        )

        result = await service.list_backups()

        assert len(result) == 2
        assert result[0].endswith(".oct-backup")

    @pytest.mark.asyncio
    async def test_list_backups_empty(self, service, mock_ssh):
        """No backups → empty list."""
        mock_ssh.execute.return_value = _fail("No such file")

        result = await service.list_backups()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_backups_empty_output(self, service, mock_ssh):
        """ls succeeds but returns nothing."""
        mock_ssh.execute.return_value = _ok("")

        result = await service.list_backups()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_backups_strips_whitespace(self, service, mock_ssh):
        """Paths should be stripped of whitespace."""
        mock_ssh.execute.return_value = _ok(
            "  /mnt/nv/backup.xml  \n  /mnt/nv/backup2.xml  \n\n"
        )

        result = await service.list_backups()

        assert len(result) == 2
        assert result[0] == "/mnt/nv/backup.xml"

    @pytest.mark.asyncio
    async def test_list_backups_ssh_exception(self, service, mock_ssh):
        """SSH exception → empty list."""
        mock_ssh.execute.side_effect = OSError("timeout")

        result = await service.list_backups()

        assert result == []


# ---------------------------------------------------------------------------
# Remount helpers
# ---------------------------------------------------------------------------


class TestRemountHelpers:

    @pytest.mark.asyncio
    async def test_remount_rw_calls_ssh(self, service, mock_ssh):
        mock_ssh.execute.return_value = _ok()
        await service._remount_rw()
        mock_ssh.execute.assert_called_once_with("mount -o remount,rw /")

    @pytest.mark.asyncio
    async def test_remount_ro_calls_ssh(self, service, mock_ssh):
        mock_ssh.execute.return_value = _ok()
        await service._remount_ro()
        mock_ssh.execute.assert_called_once_with("mount -o remount,ro /")

    @pytest.mark.asyncio
    async def test_remount_rw_warns_on_failure(self, service, mock_ssh):
        """Non-zero exit code should log warning, not raise."""
        mock_ssh.execute.return_value = CommandResult(
            success=False, output="", exit_code=1, stderr="busy"
        )
        # Should not raise
        await service._remount_rw()

    @pytest.mark.asyncio
    async def test_remount_ro_warns_on_failure(self, service, mock_ssh):
        """Non-zero exit code should log warning, not raise."""
        mock_ssh.execute.return_value = CommandResult(
            success=False, output="", exit_code=1, stderr="busy"
        )
        await service._remount_ro()


# ---------------------------------------------------------------------------
# End-to-end flow with /opt/Bose/etc/ path (Issue #78)
# ---------------------------------------------------------------------------

# Real config XML from /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml (Issue #78)
SAMPLE_OPT_BOSE_CONFIG = """\
<?xml version="1.0" encoding="utf-8"?>
<SoundTouchSdkPrivateCfg>
    <margeServerUrl>https://streaming.bose.com</margeServerUrl>
    <statsServerUrl>https://events.api.bosecm.com</statsServerUrl>
    <swUpdateUrl>https://worldwide.bose.com/updates/soundtouch</swUpdateUrl>
    <usePandoraProductionServer>true</usePandoraProductionServer>
    <isZeroconfEnabled>true</isZeroconfEnabled>
    <saveMargeCustomerReport>false</saveMargeCustomerReport>
    <bmxRegistryUrl>https://content.api.bose.io/bmx/registry/v1/services</bmxRegistryUrl>
</SoundTouchSdkPrivateCfg>
"""


class TestModifyWithOptBosePath:
    """Full modify flow when config is at /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml."""

    @pytest.fixture
    def opt_service(self, mock_ssh):
        svc = SoundTouchConfigService(mock_ssh)
        svc.config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        return svc

    @pytest.mark.asyncio
    async def test_writes_directly_to_opt_bose(self, opt_service, mock_ssh):
        """Config must be written directly to /opt/Bose/etc/ (no /mnt/nv/ copy)."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config (cat)
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config (base64 pipe)
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify: cat
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await opt_service.modify_bmx_url("192.168.1.50")
        assert result.success is True
        # Path must NOT have been redirected to /mnt/nv/
        assert opt_service.config_path == "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"

    @pytest.mark.asyncio
    async def test_backup_uses_detected_filename(self, opt_service, mock_ssh):
        """Backup must use SoundTouchSdkPrivateCfg.xml, not Override variant."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # base64 write
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await opt_service.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert result.backup_path == "/mnt/nv/SoundTouchSdkPrivateCfg.xml.oct-backup"

    @pytest.mark.asyncio
    async def test_diff_contains_original_urls(self, opt_service, mock_ssh):
        """Diff must show original Bose server URLs."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await opt_service.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert "https://content.api.bose.io/bmx" in result.diff
        assert "https://streaming.bose.com" in result.diff


class TestModifyDirectWrite:
    """Verify modify writes directly to canonical path."""

    @pytest.mark.asyncio
    async def test_writes_directly_no_copy(self, service, mock_ssh):
        """Config is written directly to /opt/Bose/etc/ — no copy to /mnt/nv/."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config (direct)
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        # No cp to /mnt/nv/ should exist
        cp_to_mnt = [c for c in all_cmds if "cp" in c and "/mnt/nv/SoundTouch" in c]
        assert len(cp_to_mnt) == 0

    @pytest.mark.asyncio
    async def test_backup_uses_canonical_filename(self, service, mock_ssh):
        """Backup must be named SoundTouchSdkPrivateCfg.xml.oct-backup."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.backup_path == "/mnt/nv/SoundTouchSdkPrivateCfg.xml.oct-backup"


# ---------------------------------------------------------------------------
# Config file sync (never delete, always sync ALL existing paths)
#
# We don't know which config file firmware reads on a given device model.
# After modifying the primary config, we sync ALL other existing config
# paths with the same content. Never delete, never create.
# ---------------------------------------------------------------------------


class TestSyncAllConfigFiles:
    """Tests: ALL existing config files must be synced, never deleted."""

    @pytest.fixture
    def fresh_service(self, mock_ssh):
        return SoundTouchConfigService(mock_ssh)

    def test_no_rm_command_in_service(self):
        """The service must NEVER use 'rm' on any config file."""
        import inspect

        source = inspect.getsource(SoundTouchConfigService)
        assert "rm -f" not in source, (
            "rm -f found in SoundTouchConfigService — "
            "config files must NEVER be deleted"
        )

    @pytest.mark.asyncio
    async def test_sync_writes_to_all_found_paths(self, fresh_service, mock_ssh):
        """When secondary config files exist, sync writes modified content to them."""
        fresh_service.config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        mock_ssh.execute.side_effect = [
            _ok("found"),  # check Override
            _ok(),  # write to Override
            _ok("found"),  # check /mnt/nv/SoundTouch
            _ok(),  # write to /mnt/nv/SoundTouch
        ]

        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

        assert mock_ssh.execute.call_count == 4
        # First write goes to Override
        write1 = mock_ssh.execute.call_args_list[1][0][0]
        assert "base64" in write1
        assert "OverrideSdkPrivateCfg.xml" in write1
        assert "rm" not in write1
        # Second write goes to /mnt/nv/SoundTouch
        write2 = mock_ssh.execute.call_args_list[3][0][0]
        assert "base64" in write2
        assert "/mnt/nv/SoundTouchSdkPrivateCfg.xml" in write2

    @pytest.mark.asyncio
    async def test_sync_skips_missing_paths(self, fresh_service, mock_ssh):
        """Paths that don't exist are skipped (never created)."""
        fresh_service.config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # Override not present
            _ok("missing"),  # /mnt/nv/SoundTouch not present
        ]

        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

        # Only existence checks, no writes
        assert mock_ssh.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_skips_primary_path(self, fresh_service, mock_ssh):
        """The primary path (already written) must NOT be synced again."""
        fresh_service.config_path = "/mnt/nv/OverrideSdkPrivateCfg.xml"
        mock_ssh.execute.side_effect = [
            _ok("found"),  # check /opt/Bose/etc/ -> found
            _ok(),  # write to /opt/Bose/etc/
            _ok("missing"),  # /mnt/nv/SoundTouch missing
        ]

        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

        # Override is primary -> skipped; /opt/Bose found -> written; /mnt/nv missing -> skipped
        assert mock_ssh.execute.call_count == 3
        check1 = mock_ssh.execute.call_args_list[0][0][0]
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in check1

    @pytest.mark.asyncio
    async def test_sync_failure_does_not_raise(self, fresh_service, mock_ssh):
        """Sync is best-effort -- failure must not abort the main flow."""
        fresh_service.config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        mock_ssh.execute.side_effect = [
            _ok("found"),  # Override exists
            _fail("permission denied"),  # write fails
            _ok("missing"),  # /mnt/nv/SoundTouch missing
        ]

        # Must not raise
        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

    @pytest.mark.asyncio
    async def test_modify_syncs_all_after_write(self, fresh_service, mock_ssh):
        """Full modify flow must sync ALL paths AFTER writing primary config."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok("found"),  # probe: /opt/Bose/etc/ found
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config to primary
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("found"),  # sync: check Override -> found
            _ok(),  # sync: write Override
            _ok("found"),  # sync: check /mnt/nv/SoundTouch -> found
            _ok(),  # sync: write /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        rm_cmds = [c for c in all_cmds if "rm " in c]
        assert len(rm_cmds) == 0, f"Found rm commands: {rm_cmds}"
        # Must have written to all 3 paths (primary + 2 syncs)
        base64_cmds = [c for c in all_cmds if "base64" in c]
        assert len(base64_cmds) == 3

    @pytest.mark.asyncio
    async def test_modify_succeeds_when_no_secondary_files(
        self, fresh_service, mock_ssh
    ):
        """Full flow works fine when no secondary config files exist."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok("found"),  # probe: /opt/Bose/etc/ found
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: Override not present
            _ok("missing"),  # sync: /mnt/nv/SoundTouch not present
            _ok(),  # remount ro
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_write_targets_opt_bose_directly(self, service, mock_ssh):
        """Write command must target /opt/Bose/etc/ directly."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        await service.modify_bmx_url("192.168.1.50")

        write_cmd = mock_ssh.execute.call_args_list[3][0][0]
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in write_cmd


class TestRestoreWithCanonicalPath:
    """Restore flow with canonical /opt/Bose/etc/ path."""

    @pytest.mark.asyncio
    async def test_restore_targets_canonical_path(self, service, mock_ssh):
        """Restore must copy to /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _ok(),  # remount rw
            _ok(),  # cp backup → /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # verify
            _ok(),  # remount ro
        ]

        result = await service.restore_config(
            "/mnt/nv/SoundTouchSdkPrivateCfg.xml.oct-backup"
        )
        assert result.success is True

        cp_cmd = mock_ssh.execute.call_args_list[2][0][0]
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in cp_cmd
        assert "oct-backup" in cp_cmd


class TestDetectConfigPathFullFlow:
    """End-to-end tests: auto-detect path → modify → verify correct paths."""

    @pytest.fixture
    def fresh(self, mock_ssh):
        return SoundTouchConfigService(mock_ssh)

    @pytest.mark.asyncio
    async def test_canonical_path_found(self, fresh, mock_ssh):
        """Full flow when /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml is found."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok("found"),  # probe: /opt/Bose/etc/ → found
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # cat config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify: cat
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await fresh.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert fresh.config_path == "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        assert result.backup_path == "/mnt/nv/SoundTouchSdkPrivateCfg.xml.oct-backup"

    @pytest.mark.asyncio
    async def test_no_config_found(self, fresh, mock_ssh):
        """Probe fails → returns failure."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok("missing"),  # probe: /opt/Bose/etc/ → miss
            _ok("missing"),  # probe: Override → miss
            _ok("missing"),  # probe: /mnt/nv/SoundTouch → miss
            _ok(),  # remount ro (finally)
        ]

        result = await fresh.modify_bmx_url("192.168.1.50")
        assert result.success is False
        assert "Config file not found" in result.error


# ---------------------------------------------------------------------------
# Regression: ALL config paths probed and synced (Issue #139 / PR #220)
#
# We don't know which file firmware reads on a given device model.
# /opt/Bose/etc/ is the primary target (probed first), but ALL other
# existing config files are kept in sync after modification.
# See: github.com/gesellix/Bose-SoundTouch/pull/220
# ---------------------------------------------------------------------------


class TestAllConfigPathsHandled:
    """Regression tests: all known config paths are probed and synced."""

    def test_config_candidates_contains_all_known_paths(self):
        """All 3 known config locations must be in CONFIG_CANDIDATES."""
        candidates = SoundTouchConfigService.CONFIG_CANDIDATES
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in candidates
        assert "/mnt/nv/OverrideSdkPrivateCfg.xml" in candidates
        assert "/mnt/nv/SoundTouchSdkPrivateCfg.xml" in candidates

    def test_config_candidates_starts_with_opt_bose(self):
        """Primary config path must be /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml."""
        assert SoundTouchConfigService.CONFIG_CANDIDATES[0] == (
            "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        )

    @pytest.fixture
    def fresh_service(self, mock_ssh):
        return SoundTouchConfigService(mock_ssh)

    @pytest.mark.asyncio
    async def test_detect_prefers_opt_bose(self, fresh_service, mock_ssh):
        """Detection must resolve to /opt/Bose/etc/ when it exists."""
        mock_ssh.execute.return_value = _ok("found")
        path = await fresh_service._detect_config_path()
        assert path == "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"

    @pytest.mark.asyncio
    async def test_detect_falls_back_to_override(self, fresh_service, mock_ssh):
        """If /opt/Bose/etc/ missing, fall back to Override."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # /opt/Bose/etc/ not found
            _ok("found"),  # Override found
        ]
        path = await fresh_service._detect_config_path()
        assert path == "/mnt/nv/OverrideSdkPrivateCfg.xml"

    @pytest.mark.asyncio
    async def test_detect_falls_back_to_mnt_nv(self, fresh_service, mock_ssh):
        """If /opt/Bose/etc/ and Override missing, fall back to /mnt/nv/SoundTouch."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # /opt/Bose/etc/ not found
            _ok("missing"),  # Override not found
            _ok("found"),  # /mnt/nv/SoundTouch found
        ]
        path = await fresh_service._detect_config_path()
        assert path == "/mnt/nv/SoundTouchSdkPrivateCfg.xml"

    @pytest.mark.asyncio
    async def test_write_targets_primary_directly(self, fresh_service, mock_ssh):
        """Write must go to primary path directly."""
        fresh_service.config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        mock_ssh.execute.return_value = _ok()

        await fresh_service._write_config("<SoundTouchSdkPrivateCfg/>")

        write_cmd = mock_ssh.execute.call_args_list[0][0][0]
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in write_cmd

    @pytest.mark.asyncio
    async def test_modify_syncs_all_secondary_paths(self, fresh_service, mock_ssh):
        """After writing primary, ALL existing secondary paths must be synced."""
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok("found"),  # probe: /opt/Bose/etc/ found
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config to primary
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("found"),  # sync: check Override -> found
            _ok(),  # sync: write Override
            _ok("found"),  # sync: check /mnt/nv/SoundTouch -> found
            _ok(),  # sync: write /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        # Must NOT contain any rm command
        rm_cmds = [c for c in all_cmds if "rm" in c and "Override" in c]
        assert len(rm_cmds) == 0, "Override must be synced, not deleted"
        # Must have written via base64 to all 3 paths (primary + 2 syncs)
        base64_cmds = [c for c in all_cmds if "base64" in c]
        assert len(base64_cmds) == 3

    @pytest.mark.asyncio
    async def test_full_flow_primary_is_opt_bose(self, fresh_service, mock_ssh):
        """End-to-end: primary write always targets /opt/Bose/etc/."""
        fresh_service.config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
        mock_ssh.execute.side_effect = [
            _ok(),  # remount rw
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("missing"),  # sync: check Override
            _ok("missing"),  # sync: check /mnt/nv/SoundTouch
            _ok(),  # remount ro
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        # The primary write must target /opt/Bose/etc/
        write_cmds = [
            c[0][0] for c in mock_ssh.execute.call_args_list if "base64" in c[0][0]
        ]
        assert len(write_cmds) == 1
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" in write_cmds[0]
