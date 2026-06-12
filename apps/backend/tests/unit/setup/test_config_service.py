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
    BASE_CONFIG_PATH,
    OVERRIDE_PATH,
    ConfigDiff,
    SoundTouchConfigService,
    _validate_oct_ip,
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
    svc.config_path = OVERRIDE_PATH
    return svc


# ---------------------------------------------------------------------------
# BUG-03: Wrong config path /nv/ vs /mnt/nv/
# ---------------------------------------------------------------------------


class TestConfigPath:
    """Config path resolution tests (_ensure_override_config)."""

    @pytest.fixture
    def fresh_service(self, mock_ssh):
        """Service without pre-set config_path for detection tests."""
        return SoundTouchConfigService(mock_ssh)

    def test_first_candidate_is_override(self):
        assert SoundTouchConfigService.CONFIG_CANDIDATES[0] == OVERRIDE_PATH

    def test_two_candidates(self):
        """Both /mnt/nv/ config paths must be in CONFIG_CANDIDATES."""
        candidates = SoundTouchConfigService.CONFIG_CANDIDATES
        assert len(candidates) == 2
        assert OVERRIDE_PATH in candidates
        assert "/mnt/nv/SoundTouchSdkPrivateCfg.xml" in candidates

    def test_backup_dir_is_on_persistent_volume(self):
        """Backups must be on persistent volume so they survive reboots."""
        assert SoundTouchConfigService.BACKUP_DIR == "/mnt/nv"

    @pytest.mark.asyncio
    async def test_ensure_override_exists(self, fresh_service, mock_ssh):
        """Returns OVERRIDE_PATH when override file exists."""
        mock_ssh.execute.return_value = _ok("found")
        path = await fresh_service._ensure_override_config()
        assert path == OVERRIDE_PATH

    @pytest.mark.asyncio
    async def test_ensure_override_copies_from_base(self, fresh_service, mock_ssh):
        """Copies from base config when override is missing."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # override missing
            _ok("found"),  # base config exists
            _ok(),  # cp base → override
        ]
        path = await fresh_service._ensure_override_config()
        assert path == OVERRIDE_PATH
        # Verify cp command
        cp_cmd = mock_ssh.execute.call_args_list[2][0][0]
        assert BASE_CONFIG_PATH in cp_cmd
        assert OVERRIDE_PATH in cp_cmd

    @pytest.mark.asyncio
    async def test_ensure_override_raises_when_none_found(
        self, fresh_service, mock_ssh
    ):
        """Raises RuntimeError when no config file exists."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # override missing
            _ok("missing"),  # base missing
        ]
        with pytest.raises(RuntimeError, match="No config source found"):
            await fresh_service._ensure_override_config()

    @pytest.mark.asyncio
    async def test_ensure_override_caches_result(self, fresh_service, mock_ssh):
        """Second call returns cached path without SSH call."""
        mock_ssh.execute.return_value = _ok("found")
        await fresh_service._ensure_override_config()
        mock_ssh.execute.reset_mock()
        path = await fresh_service._ensure_override_config()
        assert path == OVERRIDE_PATH
        mock_ssh.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_override_cp_failure_raises(self, fresh_service, mock_ssh):
        """RuntimeError when cp from base to override fails."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # override missing
            _ok("found"),  # base exists
            _fail("permission denied"),  # cp fails
        ]
        with pytest.raises(RuntimeError, match="Failed to copy base config"):
            await fresh_service._ensure_override_config()


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

    def test_bmx_url_uses_provided_host(self):
        """URL must use the user-specified hostname or IP."""
        url = SoundTouchConfigService.build_bmx_url("192.168.1.50")
        assert "192.168.1.50" in url

    def test_bmx_url_uses_hostname(self):
        """URL must use the hostname when provided."""
        url = SoundTouchConfigService.build_bmx_url("hera.fritz.box")
        assert "hera.fritz.box" in url

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
        """Full flow: read → backup → write → verify → sync."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config (cat)
            _ok("missing"),  # backup check (test -f → missing)
            _ok(),  # cp backup
            _ok(),  # write config (base64 pipe)
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify read-back
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync: batch check
            _ok(),  # sync: write /mnt/nv/SoundTouch
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
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync: batch check
            _ok(),  # sync: write /mnt/nv/SoundTouch
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        # Verify backup cp was called (3rd SSH command = index 2)
        cp_call = mock_ssh.execute.call_args_list[2][0][0]
        assert "cp" in cp_call

    @pytest.mark.asyncio
    async def test_skips_backup_if_already_exists(self, service, mock_ssh):
        """Don't overwrite existing backup."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup check → already exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync: batch check
            _ok(),  # sync: write /mnt/nv/SoundTouch
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
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync: batch check
            _ok(),  # sync: write /mnt/nv/SoundTouch
        ]

        await service.modify_bmx_url("192.168.1.50")

        # Find the write command (index 2: read, backup_check, write)
        write_cmd = mock_ssh.execute.call_args_list[2][0][0]
        assert "base64 -d" in write_cmd
        assert "/tmp/config.new" in write_cmd
        assert "mv /tmp/config.new" in write_cmd

    @pytest.mark.asyncio
    async def test_verifies_config_after_write(self, service, mock_ssh):
        """Must read back and verify XML after writing."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok("corrupted garbage"),  # verify → missing closing tag!
        ]

        result = await service.modify_bmx_url("192.168.1.50")

        assert result.success is False
        assert "verification failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_no_remount_needed(self, service, mock_ssh):
        """/mnt/nv/ is always writable — no remount rw/ro calls."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        await service.modify_bmx_url("192.168.1.50")

        cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        assert not any("remount" in c for c in cmds)

    @pytest.mark.asyncio
    async def test_returns_failure_on_error(self, service, mock_ssh):
        """Read failure returns ModifyResult(success=False)."""
        mock_ssh.execute.side_effect = [
            _fail("cannot read"),  # read config fails → RuntimeError
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is False

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
            _ok(minimal_xml),  # read config
            _ok("exists"),  # backup check
        ]

        result = await service.modify_bmx_url("192.168.1.50")

        assert result.success is True
        assert "no changes" in result.diff.lower()

    @pytest.mark.asyncio
    async def test_diff_contains_old_and_new_urls(self, service, mock_ssh):
        """Diff must show what was changed."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup check
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await service.modify_bmx_url("192.168.1.50")

        assert "https://content.api.bose.io/bmx" in result.diff  # old
        assert "http://192.168.1.50:7777/bmx" in result.diff  # new (uses provided host)
        assert "https://streaming.bose.com" in result.diff  # old marge
        assert "http://192.168.1.50:7777" in result.diff  # new marge

    @pytest.mark.asyncio
    async def test_bmx_url_always_http_never_https(self, service, mock_ssh):
        """Critical: BMX URL must be HTTP. HTTPS breaks SoundTouch devices."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup check
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        await service.modify_bmx_url("192.168.1.50")

        # Find the write command and decode the base64 content
        write_cmd = mock_ssh.execute.call_args_list[2][0][0]
        # Extract base64 string from: echo 'BASE64' | base64 -d > ...
        import base64 as b64

        b64_str = write_cmd.split("'")[1]
        written_xml = b64.b64decode(b64_str).decode()

        # The written bmxRegistryUrl must be HTTP, using provided host
        assert "http://192.168.1.50:7777/bmx" in written_xml
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
            _ok(),  # cp restore
            _ok(SAMPLE_CONFIG_XML),  # verify
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
            _fail("permission denied"),  # cp fails
        ]

        result = await service.restore_config("/mnt/nv/backup.xml")

        assert result.success is False
        assert "permission denied" in result.error.lower()

    @pytest.mark.asyncio
    async def test_restore_verify_failure(self, service, mock_ssh):
        """Verification after copy fails → error result."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _ok(),  # cp
            _ok("garbage"),  # verify → missing XML tag
        ]

        result = await service.restore_config("/mnt/nv/backup.xml")

        assert result.success is False
        assert "verification" in result.error.lower()

    @pytest.mark.asyncio
    async def test_restore_no_remount_needed(self, service, mock_ssh):
        """/mnt/nv/ is always writable — no remount calls."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _fail("disk full"),  # cp fails
        ]

        await service.restore_config("/mnt/nv/backup.xml")

        cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        assert not any("remount" in c for c in cmds)

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


class TestModifyAlwaysUsesOverride:
    """Modify flow always uses OVERRIDE_PATH as write target."""

    @pytest.mark.asyncio
    async def test_writes_to_override_path(self, service, mock_ssh):
        """Config must always be written to OVERRIDE_PATH."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config (base64 pipe)
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert service.config_path == OVERRIDE_PATH

    @pytest.mark.asyncio
    async def test_backup_uses_override_filename(self, service, mock_ssh):
        """Backup must use OverrideSdkPrivateCfg.xml filename."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # base64 write
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert result.backup_path == "/mnt/nv/OverrideSdkPrivateCfg.xml.oct-backup"

    @pytest.mark.asyncio
    async def test_diff_contains_original_urls(self, service, mock_ssh):
        """Diff must show original Bose server URLs."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await service.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert "https://content.api.bose.io/bmx" in result.diff
        assert "https://streaming.bose.com" in result.diff

    @pytest.mark.asyncio
    async def test_never_writes_to_opt_bose(self, service, mock_ssh):
        """Write commands must NEVER target /opt/Bose/etc/."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        await service.modify_bmx_url("192.168.1.50")

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        write_cmds = [c for c in all_cmds if "base64" in c]
        for cmd in write_cmds:
            assert (
                "/opt/Bose/etc/" not in cmd
            ), f"Write to /opt/Bose/etc/ detected: {cmd}"

    @pytest.mark.asyncio
    async def test_write_targets_override_directly(self, service, mock_ssh):
        """Write command must target OVERRIDE_PATH."""
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        await service.modify_bmx_url("192.168.1.50")

        write_cmd = mock_ssh.execute.call_args_list[2][0][0]
        assert OVERRIDE_PATH in write_cmd


# ---------------------------------------------------------------------------
# Config file sync (never delete, always sync ALL existing paths)
#
# We don't know which config file firmware reads on a given device model.
# After modifying the primary config, we sync ALL other config candidate
# paths with the same content. Override files are created if missing to
# ensure persistence across reboots. Never delete.
# ---------------------------------------------------------------------------


class TestSyncAllConfigFiles:
    """Tests: /mnt/nv/ config files synced, never deleted."""

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
    async def test_sync_writes_to_existing_mnt_nv_paths(self, fresh_service, mock_ssh):
        """Sync writes modified content to existing /mnt/nv/ candidate."""
        fresh_service.config_path = OVERRIDE_PATH
        check_output = "/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"
        mock_ssh.execute.side_effect = [
            _ok(check_output),  # batch existence check
            _ok(),  # write to /mnt/nv/SoundTouch
        ]

        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

        assert mock_ssh.execute.call_count == 2
        write1 = mock_ssh.execute.call_args_list[1][0][0]
        assert "base64" in write1
        assert "/mnt/nv/SoundTouchSdkPrivateCfg.xml" in write1
        assert "rm" not in write1

    @pytest.mark.asyncio
    async def test_sync_skips_missing_files(self, fresh_service, mock_ssh):
        """Missing /mnt/nv/ files are NOT created by sync."""
        fresh_service.config_path = OVERRIDE_PATH
        check_output = "/mnt/nv/SoundTouchSdkPrivateCfg.xml:missing"
        mock_ssh.execute.side_effect = [
            _ok(check_output),  # batch check — missing
        ]

        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

        # Only the batch check, no writes
        assert mock_ssh.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_sync_skips_primary_path(self, fresh_service, mock_ssh):
        """The primary path (already written) must NOT be synced again."""
        fresh_service.config_path = OVERRIDE_PATH
        check_output = "/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"
        mock_ssh.execute.side_effect = [
            _ok(check_output),  # batch check
            _ok(),  # write to /mnt/nv/SoundTouch
        ]

        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

        # batch check + 1 write (Override is primary → skipped)
        assert mock_ssh.execute.call_count == 2
        write1 = mock_ssh.execute.call_args_list[1][0][0]
        assert "/mnt/nv/SoundTouchSdkPrivateCfg.xml" in write1

    @pytest.mark.asyncio
    async def test_sync_failure_does_not_raise(self, fresh_service, mock_ssh):
        """Sync is best-effort -- failure must not abort the main flow."""
        fresh_service.config_path = OVERRIDE_PATH
        check_output = "/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"
        mock_ssh.execute.side_effect = [
            _ok(check_output),  # batch check
            _fail("permission denied"),  # write fails
        ]

        # Must not raise
        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

    @pytest.mark.asyncio
    async def test_modify_syncs_after_write(self, fresh_service, mock_ssh):
        """Full modify flow syncs /mnt/nv/ variants after writing primary."""
        mock_ssh.execute.side_effect = [
            _ok("found"),  # ensure override: exists
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config to primary
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync: batch check
            _ok(),  # sync: write /mnt/nv/SoundTouch
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        rm_cmds = [c for c in all_cmds if "rm " in c]
        assert len(rm_cmds) == 0, f"Found rm commands: {rm_cmds}"
        base64_cmds = [c for c in all_cmds if "base64" in c]
        assert len(base64_cmds) == 2  # primary + 1 sync

    @pytest.mark.asyncio
    async def test_modify_succeeds_even_when_sync_fails(self, fresh_service, mock_ssh):
        """Full flow works fine even when sync writes fail (best-effort)."""
        mock_ssh.execute.side_effect = [
            _ok("found"),  # ensure override: exists
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _fail("permission denied"),  # sync write fails
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_sync_never_writes_opt_bose(self, fresh_service, mock_ssh):
        """Sync must NEVER write to /opt/Bose/etc/."""
        fresh_service.config_path = OVERRIDE_PATH
        check_output = "/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"
        mock_ssh.execute.side_effect = [
            _ok(check_output),
            _ok(),  # write
        ]

        await fresh_service._sync_all_config_files(SAMPLE_CONFIG_ALREADY_MODIFIED)

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        for cmd in all_cmds:
            assert "/opt/Bose/etc/" not in cmd, f"Sync wrote to /opt/Bose/etc/: {cmd}"


class TestRestoreWithOverridePath:
    """Restore flow targets OVERRIDE_PATH."""

    @pytest.mark.asyncio
    async def test_restore_targets_override_path(self, service, mock_ssh):
        """Restore must copy to OVERRIDE_PATH."""
        mock_ssh.execute.side_effect = [
            _ok("exists"),  # backup check
            _ok(),  # cp backup → OVERRIDE_PATH
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # verify
        ]

        result = await service.restore_config(
            "/mnt/nv/OverrideSdkPrivateCfg.xml.oct-backup"
        )
        assert result.success is True

        cp_cmd = mock_ssh.execute.call_args_list[1][0][0]
        assert OVERRIDE_PATH in cp_cmd
        assert "oct-backup" in cp_cmd


class TestEnsureOverrideFullFlow:
    """End-to-end tests: ensure override → modify → verify correct paths."""

    @pytest.fixture
    def fresh(self, mock_ssh):
        return SoundTouchConfigService(mock_ssh)

    @pytest.mark.asyncio
    async def test_override_exists(self, fresh, mock_ssh):
        """Full flow when override config already exists."""
        mock_ssh.execute.side_effect = [
            _ok("found"),  # ensure override: exists
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await fresh.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert fresh.config_path == OVERRIDE_PATH
        assert result.backup_path == "/mnt/nv/OverrideSdkPrivateCfg.xml.oct-backup"

    @pytest.mark.asyncio
    async def test_override_created_from_base(self, fresh, mock_ssh):
        """Full flow when override missing but base exists → copies and uses override."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # ensure override: override missing
            _ok("found"),  # ensure override: base exists
            _ok(),  # ensure override: cp base → override
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await fresh.modify_bmx_url("192.168.1.50")
        assert result.success is True
        assert fresh.config_path == OVERRIDE_PATH

    @pytest.mark.asyncio
    async def test_no_config_found(self, fresh, mock_ssh):
        """No config source → returns failure."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # ensure override: override missing
            _ok("missing"),  # ensure override: base missing
        ]

        result = await fresh.modify_bmx_url("192.168.1.50")
        assert result.success is False
        assert "No config source found" in result.error


# ---------------------------------------------------------------------------
# Regression: ALL config paths probed and synced (Issue #139 / PR #220)
#
# We don't know which file firmware reads on a given device model.
# /opt/Bose/etc/ is the primary target (probed first), but ALL other
# existing config files are kept in sync after modification.
# See: github.com/gesellix/Bose-SoundTouch/pull/220
# ---------------------------------------------------------------------------


class TestAllConfigPathsHandled:
    """Tests: override path is primary, /mnt/nv/ variants synced."""

    def test_config_candidates_contains_mnt_nv_paths(self):
        """Both /mnt/nv/ paths must be in CONFIG_CANDIDATES."""
        candidates = SoundTouchConfigService.CONFIG_CANDIDATES
        assert OVERRIDE_PATH in candidates
        assert "/mnt/nv/SoundTouchSdkPrivateCfg.xml" in candidates

    def test_config_candidates_starts_with_override(self):
        """Primary config path must be OVERRIDE_PATH."""
        assert SoundTouchConfigService.CONFIG_CANDIDATES[0] == OVERRIDE_PATH

    def test_opt_bose_not_in_candidates(self):
        """/opt/Bose/etc/ is NOT a write target — only used as copy source."""
        candidates = SoundTouchConfigService.CONFIG_CANDIDATES
        assert "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml" not in candidates

    @pytest.fixture
    def fresh_service(self, mock_ssh):
        return SoundTouchConfigService(mock_ssh)

    @pytest.mark.asyncio
    async def test_ensure_override_returns_override(self, fresh_service, mock_ssh):
        """_ensure_override_config returns OVERRIDE_PATH when override exists."""
        mock_ssh.execute.return_value = _ok("found")
        path = await fresh_service._ensure_override_config()
        assert path == OVERRIDE_PATH

    @pytest.mark.asyncio
    async def test_ensure_override_copies_from_base_if_missing(
        self, fresh_service, mock_ssh
    ):
        """If override missing, copy from base and return OVERRIDE_PATH."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # override not found
            _ok("found"),  # base found
            _ok(),  # cp succeeds
        ]
        path = await fresh_service._ensure_override_config()
        assert path == OVERRIDE_PATH

    @pytest.mark.asyncio
    async def test_ensure_override_fails_no_sources(self, fresh_service, mock_ssh):
        """If neither override nor base exists, raise RuntimeError."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # override not found
            _ok("missing"),  # base not found
        ]
        with pytest.raises(RuntimeError, match="No config source found"):
            await fresh_service._ensure_override_config()

    @pytest.mark.asyncio
    async def test_write_targets_override_directly(self, fresh_service, mock_ssh):
        """Write must go to OVERRIDE_PATH directly."""
        fresh_service.config_path = OVERRIDE_PATH
        mock_ssh.execute.return_value = _ok()

        await fresh_service._write_config("<SoundTouchSdkPrivateCfg/>")

        write_cmd = mock_ssh.execute.call_args_list[0][0][0]
        assert OVERRIDE_PATH in write_cmd

    @pytest.mark.asyncio
    async def test_modify_syncs_mnt_nv_variant(self, fresh_service, mock_ssh):
        """After writing primary, /mnt/nv/SoundTouch variant is synced."""
        mock_ssh.execute.side_effect = [
            _ok("found"),  # ensure override: exists
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write config to primary
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync: batch check
            _ok(),  # sync: write /mnt/nv/SoundTouch
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        rm_cmds = [c for c in all_cmds if "rm" in c and "Override" in c]
        assert len(rm_cmds) == 0, "Override must be synced, not deleted"
        base64_cmds = [c for c in all_cmds if "base64" in c]
        assert len(base64_cmds) == 2  # primary + 1 sync

    @pytest.mark.asyncio
    async def test_full_flow_primary_is_override(self, fresh_service, mock_ssh):
        """End-to-end: primary write always targets OVERRIDE_PATH."""
        fresh_service.config_path = OVERRIDE_PATH
        mock_ssh.execute.side_effect = [
            _ok(SAMPLE_OPT_BOSE_CONFIG),  # read config
            _ok("exists"),  # backup exists
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync: batch check
            _ok(),  # sync: write /mnt/nv/SoundTouch
        ]

        result = await fresh_service.modify_bmx_url("192.168.1.50")
        assert result.success is True

        write_cmds = [
            c[0][0] for c in mock_ssh.execute.call_args_list if "base64" in c[0][0]
        ]
        assert len(write_cmds) == 2
        assert OVERRIDE_PATH in write_cmds[0]


# ---------------------------------------------------------------------------
# Issue #351: Config Safety Override — new tests
# ---------------------------------------------------------------------------


class TestConfigSafetyOverride:
    """Tests for Issue #351: override for ALL devices, no exceptions.

    Core invariants:
    - _ensure_override_config creates from base if missing
    - _ensure_override_config uses existing override
    - _ensure_override_config fails when no source
    - modify_bmx_url NEVER writes to /opt/Bose/etc/
    - Full flow: copy from base + modify works end-to-end
    """

    @pytest.fixture
    def fresh(self, mock_ssh):
        return SoundTouchConfigService(mock_ssh)

    @pytest.mark.asyncio
    async def test_ensure_override_creates_from_base(self, fresh, mock_ssh):
        """Override missing → copies from base → returns override path."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # override doesn't exist
            _ok("found"),  # base config exists
            _ok(),  # cp base → override succeeds
        ]

        path = await fresh._ensure_override_config()

        assert path == OVERRIDE_PATH
        # Verify cp was called with correct args
        cp_cmd = mock_ssh.execute.call_args_list[2][0][0]
        assert f"cp {BASE_CONFIG_PATH} {OVERRIDE_PATH}" == cp_cmd

    @pytest.mark.asyncio
    async def test_ensure_override_uses_existing(self, fresh, mock_ssh):
        """Override exists → returns directly without touching base."""
        mock_ssh.execute.side_effect = [
            _ok("found"),  # override exists
        ]

        path = await fresh._ensure_override_config()

        assert path == OVERRIDE_PATH
        # Only 1 SSH call — no check of base, no cp
        assert mock_ssh.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_ensure_override_fails_no_source(self, fresh, mock_ssh):
        """Neither override nor base exists → RuntimeError."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # override doesn't exist
            _ok("missing"),  # base doesn't exist either
        ]

        with pytest.raises(RuntimeError, match="No config source found"):
            await fresh._ensure_override_config()

    @pytest.mark.asyncio
    async def test_modify_never_writes_opt_bose(self, fresh, mock_ssh):
        """Verify no SSH write command targets /opt/Bose/etc/."""
        mock_ssh.execute.side_effect = [
            _ok("found"),  # ensure override: exists
            _ok(SAMPLE_CONFIG_XML),  # read config
            _ok("exists"),  # backup check
            _ok(),  # write config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await fresh.modify_bmx_url("192.168.1.50")
        assert result.success is True

        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        write_cmds = [c for c in all_cmds if "base64" in c or "mv " in c]
        for cmd in write_cmds:
            assert (
                "/opt/Bose/etc/" not in cmd
            ), f"Write to /opt/Bose/etc/ detected in: {cmd}"

    @pytest.mark.asyncio
    async def test_modify_creates_override_then_modifies(self, fresh, mock_ssh):
        """Full flow: override missing → copy from base → modify → write to override."""
        mock_ssh.execute.side_effect = [
            _ok("missing"),  # ensure override: override missing
            _ok("found"),  # ensure override: base exists
            _ok(),  # ensure override: cp base → override
            _ok(SAMPLE_CONFIG_XML),  # read config (from OVERRIDE_PATH)
            _ok("missing"),  # backup check
            _ok(),  # cp backup
            _ok(),  # write modified config
            _ok(SAMPLE_CONFIG_ALREADY_MODIFIED),  # verify
            _ok("/mnt/nv/SoundTouchSdkPrivateCfg.xml:found"),  # sync
            _ok(),  # sync write
        ]

        result = await fresh.modify_bmx_url("192.168.1.50")

        assert result.success is True
        assert fresh.config_path == OVERRIDE_PATH
        assert "bmxRegistryUrl" in result.diff
        assert result.backup_path == "/mnt/nv/OverrideSdkPrivateCfg.xml.oct-backup"

        # Verify cp from base was first meaningful operation
        cp_cmd = mock_ssh.execute.call_args_list[2][0][0]
        assert f"cp {BASE_CONFIG_PATH} {OVERRIDE_PATH}" == cp_cmd

        # Verify write targets override, not base
        all_cmds = [c[0][0] for c in mock_ssh.execute.call_args_list]
        write_cmds = [c for c in all_cmds if "base64" in c]
        for cmd in write_cmds:
            assert "/opt/Bose/etc/" not in cmd


# ---------------------------------------------------------------------------
# _validate_oct_ip
# ---------------------------------------------------------------------------


class TestValidateOctIp:
    """Tests for oct_ip input validation (HIGH-1 fix)."""

    def test_valid_ipv4(self):
        assert _validate_oct_ip("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv4_loopback(self):
        assert _validate_oct_ip("127.0.0.1") == "127.0.0.1"

    def test_valid_ipv6_loopback(self):
        assert _validate_oct_ip("::1") == "::1"

    def test_valid_ipv6_link_local(self):
        assert _validate_oct_ip("fe80::1") == "fe80::1"

    def test_valid_hostname_simple(self):
        assert _validate_oct_ip("oct.local") == "oct.local"

    def test_valid_hostname_with_hyphens(self):
        assert _validate_oct_ip("my-server.home") == "my-server.home"

    def test_valid_hostname_single_label(self):
        assert _validate_oct_ip("localhost") == "localhost"

    def test_strips_whitespace(self):
        assert _validate_oct_ip("  192.168.1.1  ") == "192.168.1.1"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_oct_ip("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_oct_ip("   ")

    def test_xml_injection_angle_brackets(self):
        with pytest.raises(ValueError, match="Invalid characters"):
            _validate_oct_ip("<script>")

    def test_xml_injection_ampersand(self):
        with pytest.raises(ValueError, match="Invalid characters"):
            _validate_oct_ip("host&name")

    def test_xml_injection_double_quote(self):
        with pytest.raises(ValueError, match="Invalid characters"):
            _validate_oct_ip('host"name')

    def test_xml_injection_single_quote(self):
        with pytest.raises(ValueError, match="Invalid characters"):
            _validate_oct_ip("host'name")

    def test_control_chars_null(self):
        with pytest.raises(ValueError, match="Invalid characters"):
            _validate_oct_ip("host\x00name")

    def test_control_chars_newline(self):
        with pytest.raises(ValueError, match="Invalid characters"):
            _validate_oct_ip("host\nname")

    def test_hostname_too_long(self):
        long_name = "a" * 254
        with pytest.raises(ValueError, match="too long"):
            _validate_oct_ip(long_name)

    def test_hostname_max_length_ok(self):
        name_253 = "a" * 253
        assert _validate_oct_ip(name_253) == name_253

    def test_hostname_invalid_start_hyphen(self):
        with pytest.raises(ValueError, match="Invalid hostname format"):
            _validate_oct_ip("-invalid.host")

    def test_hostname_invalid_end_hyphen(self):
        with pytest.raises(ValueError, match="Invalid hostname format"):
            _validate_oct_ip("invalid.host-")

    def test_hostname_with_spaces_in_middle(self):
        with pytest.raises(ValueError, match="Invalid hostname format"):
            _validate_oct_ip("host name")
