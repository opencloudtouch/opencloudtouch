"""
Unit tests for SoundTouchHostsService.

Regression tests for:
- BUG-01: modify_hosts was a TODO-stub (no SSH commands executed)
- BUG-02: bose.vtuner.com missing from REQUIRED_HOSTS

These bugs caused /etc/hosts to remain unmodified despite wizard reporting success.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.ssh_client import CommandResult


def _ok(output: str = "") -> CommandResult:
    """Helper: successful CommandResult."""
    return CommandResult(success=True, output=output, exit_code=0)


def _fail(error: str = "error") -> CommandResult:
    """Helper: failed CommandResult."""
    return CommandResult(success=False, output="", exit_code=1, error=error)


@pytest.fixture
def mock_ssh():
    """Mocked SoundTouchSSHClient."""
    ssh = MagicMock()
    ssh.execute = AsyncMock()
    return ssh


@pytest.fixture
def service(mock_ssh):
    return SoundTouchHostsService(mock_ssh)


# ---------------------------------------------------------------------------
# BUG-01: modify_hosts was a TODO-stub
# ---------------------------------------------------------------------------


class TestModifyHostsSSHCommands:
    """
    BUG-01 Regression: modify_hosts() must execute real SSH commands,
    not just return ModifyResult(success=True) without any action.

    Discovered: cat /etc/hosts on real device (192.168.1.79) showed
    old entries after wizard reported success.
    """

    @pytest.mark.asyncio
    async def test_modify_hosts_executes_ssh_commands(self, service, mock_ssh):
        """modify_hosts must send at least one SSH execute() call."""
        # Arrange: ssh returns success for all calls
        mock_ssh.execute.return_value = _ok("")

        # Act
        await service.modify_hosts(oct_ip="192.168.1.50")

        # Assert: SSH commands were actually sent (not stubbed)
        mock_ssh.execute.assert_awaited()
        call_count = mock_ssh.execute.await_count
        assert call_count > 0, (
            "BUG-01: modify_hosts performed 0 SSH calls. "
            "It was a TODO-stub that never wrote to /etc/hosts."
        )

    @pytest.mark.asyncio
    async def test_modify_hosts_reads_current_hosts_file(self, service, mock_ssh):
        """modify_hosts must read the current hosts file before modifying."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        await service.modify_hosts(oct_ip="192.168.1.50")

        # Verify at least one call reads /etc/hosts (cat command)
        calls = [call[0][0] for call in mock_ssh.execute.call_args_list]
        cat_calls = [cmd for cmd in calls if "cat" in cmd and "/etc/hosts" in cmd]
        assert len(cat_calls) >= 1, (
            "modify_hosts must read /etc/hosts before writing. "
            "No 'cat /etc/hosts' command found in SSH calls."
        )

    @pytest.mark.asyncio
    async def test_modify_hosts_writes_new_hosts_file(self, service, mock_ssh):
        """modify_hosts must write the new hosts file content to device."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        await service.modify_hosts(oct_ip="192.168.1.50")

        # Verify at least one write command (echo/base64/mv to /etc/hosts)
        calls = [call[0][0] for call in mock_ssh.execute.call_args_list]
        write_calls = [
            cmd
            for cmd in calls
            if "/etc/hosts" in cmd
            and any(x in cmd for x in ["echo", "base64", ">", "mv", "tee"])
        ]
        assert len(write_calls) >= 1, (
            f"modify_hosts must write to /etc/hosts. "
            f"No write command found. SSH calls were: {calls}"
        )

    @pytest.mark.asyncio
    async def test_modify_hosts_includes_oct_ip_in_hosts(self, service, mock_ssh):
        """New hosts content must redirect Bose domains to the specified OCT IP."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")
        oct_ip = "192.168.1.42"

        result = await service.modify_hosts(oct_ip=oct_ip)

        assert result.success is True
        # The diff should contain the OCT IP
        assert (
            oct_ip in result.diff
        ), f"diff '{result.diff}' must contain OCT IP '{oct_ip}'"

    @pytest.mark.asyncio
    async def test_modify_hosts_returns_backup_path(self, service, mock_ssh):
        """modify_hosts must report where the backup was created."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        result = await service.modify_hosts(oct_ip="192.168.1.50")

        assert result.success is True
        assert (
            result.backup_path != ""
        ), "modify_hosts should report the backup path so restore_hosts can use it."

    @pytest.mark.asyncio
    async def test_modify_hosts_remounts_rw_before_write(self, service, mock_ssh):
        """Filesystem must be remounted read-write before writing /etc/hosts."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        await service.modify_hosts(oct_ip="192.168.1.50")

        calls = [call[0][0] for call in mock_ssh.execute.call_args_list]
        remount_rw_calls = [
            cmd for cmd in calls if "remount,rw" in cmd or "mount -o remount,rw" in cmd
        ]
        assert len(remount_rw_calls) >= 1, (
            "BusyBox root filesystem is read-only by default. "
            "modify_hosts must run 'mount -o remount,rw /' before writing."
        )

    @pytest.mark.asyncio
    async def test_modify_hosts_remounts_ro_after_write(self, service, mock_ssh):
        """Filesystem must be remounted read-only after writing /etc/hosts."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        await service.modify_hosts(oct_ip="192.168.1.50")

        calls = [call[0][0] for call in mock_ssh.execute.call_args_list]
        remount_ro_calls = [
            cmd for cmd in calls if "remount,ro" in cmd or "mount -o remount,ro" in cmd
        ]
        assert (
            len(remount_ro_calls) >= 1
        ), "Root filesystem must be remounted read-only after modification for safety."

    @pytest.mark.asyncio
    async def test_modify_hosts_handles_write_failure(self, service, mock_ssh):
        """If the write command fails, modify_hosts must return success=False."""

        # First calls (remount, cat, check backup) succeed; write fails
        def side_effect(cmd, **kwargs):
            if "cat" in cmd and "/etc/hosts" in cmd:
                return _ok("127.0.0.1 localhost")
            if "remount" in cmd:
                return _ok()
            if "test -f" in cmd:
                return _ok("missing")
            if "cp" in cmd:
                return _ok()
            # Write commands fail
            if "base64" in cmd or (">" in cmd and "/etc/hosts" in cmd):
                return _fail("Permission denied")
            return _ok()

        mock_ssh.execute.side_effect = AsyncMock(side_effect=side_effect)

        result = await service.modify_hosts(oct_ip="192.168.1.50")

        assert (
            result.success is False
        ), "modify_hosts must return success=False if the write fails."


# ---------------------------------------------------------------------------
# BUG-02: bose.vtuner.com missing from REQUIRED_HOSTS
# ---------------------------------------------------------------------------


class TestVTunerDomainsPresent:
    """
    BUG-02 Regression: After hosts modification, bose.vtuner.com was still
    resolving to external IP 66.135.37.14 because the domain was not in
    REQUIRED_HOSTS / VTUNER_HOSTS.

    Critical for Internet Radio functionality.
    """

    def test_vtuner_hosts_contains_primary_vtuner_domain(self):
        """bose.vtuner.com must be in VTUNER_HOSTS."""
        assert "bose.vtuner.com" in SoundTouchHostsService.VTUNER_HOSTS, (
            "BUG-02: 'bose.vtuner.com' missing from VTUNER_HOSTS. "
            "Internet Radio will fail after cloud shutdown."
        )

    def test_vtuner_hosts_contains_bose2_vtuner_domain(self):
        """bose2.vtuner.com must be in VTUNER_HOSTS."""
        assert (
            "bose2.vtuner.com" in SoundTouchHostsService.VTUNER_HOSTS
        ), "BUG-02: 'bose2.vtuner.com' missing from VTUNER_HOSTS."

    def test_vtuner_hosts_contains_primary5_domain(self):
        """primary5.vtuner.com must be in VTUNER_HOSTS."""
        assert (
            "primary5.vtuner.com" in SoundTouchHostsService.VTUNER_HOSTS
        ), "BUG-02: 'primary5.vtuner.com' missing from VTUNER_HOSTS."

    def test_vtuner_hosts_contains_primary6_domain(self):
        """primary6.vtuner.com must be in VTUNER_HOSTS."""
        assert (
            "primary6.vtuner.com" in SoundTouchHostsService.VTUNER_HOSTS
        ), "BUG-02: 'primary6.vtuner.com' missing from VTUNER_HOSTS."

    def test_vtuner_hosts_contains_all_four_domains(self):
        """All 4 vTuner domains must be present."""
        required = {
            "bose.vtuner.com",
            "bose2.vtuner.com",
            "primary5.vtuner.com",
            "primary6.vtuner.com",
        }
        actual = set(SoundTouchHostsService.VTUNER_HOSTS)
        missing = required - actual
        assert len(missing) == 0, (
            f"BUG-02: Missing vTuner domains: {missing}. "
            "All 4 are needed for SoundTouch Internet Radio."
        )

    @pytest.mark.asyncio
    async def test_modify_hosts_includes_vtuner_domains(self, service, mock_ssh):
        """Modified hosts file must redirect all vTuner domains to OCT."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")
        oct_ip = "192.168.1.50"

        result = await service.modify_hosts(oct_ip=oct_ip)

        assert result.success is True
        # All 4 vTuner domains must appear in the diff
        for domain in SoundTouchHostsService.VTUNER_HOSTS:
            assert domain in result.diff, (
                f"BUG-02: vTuner domain '{domain}' not in diff. "
                "It won't be redirected to OCT."
            )


# ---------------------------------------------------------------------------
# BUG-03: hostname instead of numeric IP in /etc/hosts
# ---------------------------------------------------------------------------


class TestHostsRequiresNumericIP:
    """
    BUG-03 Regression: /etc/hosts was written with a hostname (e.g. 'hera')
    instead of a numeric IP (e.g. '192.168.178.11').

    The /etc/hosts format requires a numeric IP in the first field.
    Entries like 'hera  bose.vtuner.com' are silently ignored by the
    system resolver, causing domains to resolve to their real Bose IPs.

    Discovered: ping bose.vtuner.com on device → 66.135.37.14 despite
    /etc/hosts containing 'hera bose.vtuner.com'.
    """

    @pytest.mark.asyncio
    async def test_hostname_rejected(self, service, mock_ssh):
        """modify_hosts must reject a hostname (non-IP) as oct_ip."""
        result = await service.modify_hosts(oct_ip="hera")

        assert result.success is False
        assert "not a valid IP" in (result.error or "")
        mock_ssh.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fqdn_rejected(self, service, mock_ssh):
        """modify_hosts must reject a FQDN as oct_ip."""
        result = await service.modify_hosts(oct_ip="myserver.local")

        assert result.success is False
        assert "not a valid IP" in (result.error or "")

    @pytest.mark.asyncio
    async def test_ipv4_accepted(self, service, mock_ssh):
        """modify_hosts must accept a valid IPv4 address."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        result = await service.modify_hosts(oct_ip="192.168.178.11")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_ipv6_accepted(self, service, mock_ssh):
        """modify_hosts must accept a valid IPv6 address."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        result = await service.modify_hosts(oct_ip="::1")

        assert result.success is True


# ---------------------------------------------------------------------------
# BUG-04: content.api.bose.io missing from REQUIRED_HOSTS
# ---------------------------------------------------------------------------


class TestContentApiBoseIoPresent:
    """
    BUG-04 Regression: content.api.bose.io was not in REQUIRED_HOSTS,
    causing preset playback to fail for ALL users.

    The Bose device calls content.api.bose.io:7777 when a preset button
    is pressed (Orion adapter callback). Without the /etc/hosts redirect,
    the request goes to the dead Bose cloud and playback never starts.

    Discovered: GitHub issue #139 — multiple users report "music does not
    start" after successful setup wizard. Root cause: hosts file missing
    content.api.bose.io entry.
    """

    def test_content_api_bose_io_in_required_hosts(self):
        """content.api.bose.io must be in REQUIRED_HOSTS."""
        assert "content.api.bose.io" in SoundTouchHostsService.REQUIRED_HOSTS, (
            "BUG-04: 'content.api.bose.io' missing from REQUIRED_HOSTS. "
            "Preset playback will fail — device cannot reach Orion adapter."
        )

    @pytest.mark.asyncio
    async def test_modify_hosts_includes_content_api_domain(self, service, mock_ssh):
        """Modified hosts file must redirect content.api.bose.io to OCT."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")
        oct_ip = "192.168.1.50"

        result = await service.modify_hosts(oct_ip=oct_ip)

        assert result.success is True
        assert "content.api.bose.io" in result.diff, (
            "BUG-04: content.api.bose.io not in hosts diff. "
            "Preset playback will fail after setup wizard completes."
        )


# ---------------------------------------------------------------------------
# restore_hosts
# ---------------------------------------------------------------------------


class TestRestoreHosts:
    """Tests for hosts file restoration from backup."""

    @pytest.mark.asyncio
    async def test_restore_success(self, service, mock_ssh):
        """Successful restore copies backup to /etc/hosts."""
        mock_ssh.execute.return_value = _ok("exists")

        result = await service.restore_hosts("/mnt/nv/hosts_backup")

        assert result.success is True
        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        cp_calls = [c for c in calls if "cp" in c and "/etc/hosts" in c]
        assert len(cp_calls) >= 1

    @pytest.mark.asyncio
    async def test_restore_backup_not_found(self, service, mock_ssh):
        """Restore fails gracefully when backup file doesn't exist."""
        mock_ssh.execute.return_value = _ok("missing")

        result = await service.restore_hosts("/mnt/nv/hosts_backup")

        assert result.success is False
        assert "Backup not found" in (result.error or "")

    @pytest.mark.asyncio
    async def test_restore_copy_failure(self, service, mock_ssh):
        """Restore reports error when cp command fails."""

        async def side_effect(cmd, **kwargs):
            if "test -f" in cmd:
                return _ok("exists")
            if "remount,rw" in cmd or "remount,ro" in cmd:
                return _ok()
            if "cp" in cmd:
                return _fail("Permission denied")
            return _ok()

        mock_ssh.execute = AsyncMock(side_effect=side_effect)
        result = await service.restore_hosts("/mnt/nv/hosts_backup")

        assert result.success is False
        assert "Copy failed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_restore_remounts_rw_then_ro(self, service, mock_ssh):
        """Restore remounts rw before copy, ro after."""
        mock_ssh.execute.return_value = _ok("exists")

        await service.restore_hosts("/mnt/nv/hosts_backup")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        rw = [c for c in calls if "remount,rw" in c]
        ro = [c for c in calls if "remount,ro" in c]
        assert len(rw) >= 1
        assert len(ro) >= 1

    @pytest.mark.asyncio
    async def test_restore_handles_ssh_exception(self, service, mock_ssh):
        """Restore catches unexpected SSH exceptions."""
        mock_ssh.execute = AsyncMock(side_effect=ConnectionError("lost"))

        result = await service.restore_hosts("/mnt/nv/hosts_backup")

        assert result.success is False
        assert "lost" in (result.error or "")


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------


class TestListBackups:
    """Tests for listing available hosts backups."""

    @pytest.mark.asyncio
    async def test_returns_backup_paths(self, service, mock_ssh):
        """Returns sorted list of backup file paths."""
        mock_ssh.execute.return_value = _ok(
            "/mnt/nv/hosts_backup\n/mnt/nv/hosts_backup.1\n"
        )

        result = await service.list_backups()

        assert result == ["/mnt/nv/hosts_backup", "/mnt/nv/hosts_backup.1"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_backups(self, service, mock_ssh):
        """Returns empty list when no backup files exist."""
        mock_ssh.execute.return_value = _ok("")

        result = await service.list_backups()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_ssh_failure(self, service, mock_ssh):
        """Returns empty list if SSH command fails."""
        mock_ssh.execute.return_value = _fail("No such file")

        result = await service.list_backups()

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_exception(self, service, mock_ssh):
        """Returns empty list on unexpected exception."""
        mock_ssh.execute = AsyncMock(side_effect=RuntimeError("boom"))

        result = await service.list_backups()

        assert result == []


# ---------------------------------------------------------------------------
# _build_clean_lines — OCT block removal
# ---------------------------------------------------------------------------


class TestBuildCleanLines:
    """Tests for stripping existing OCT blocks and Bose domain entries."""

    def test_removes_existing_oct_block(self, service):
        """Existing OCT block is stripped from hosts content."""
        content = (
            "127.0.0.1 localhost\n"
            "# OCT-START\n"
            "192.168.1.50\tbose.vtuner.com\n"
            "# OCT-END\n"
            "::1 localhost\n"
        )
        all_domains = (
            service.VTUNER_HOSTS + service.REQUIRED_HOSTS + service.OPTIONAL_HOSTS
        )
        result = service._build_clean_lines(content, all_domains)

        assert "127.0.0.1 localhost" in result
        assert "::1 localhost" in result
        assert not any("OCT-START" in line for line in result)
        assert not any("bose.vtuner.com" in line for line in result)

    def test_removes_bare_bose_domain_entries(self, service):
        """Bare Bose domain entries outside OCT block are also removed."""
        content = (
            "127.0.0.1 localhost\n"
            "1.2.3.4 bose.vtuner.com\n"
            "5.6.7.8 streaming.bose.com\n"
        )
        all_domains = (
            service.VTUNER_HOSTS + service.REQUIRED_HOSTS + service.OPTIONAL_HOSTS
        )
        result = service._build_clean_lines(content, all_domains)

        assert len(result) == 1
        assert result[0] == "127.0.0.1 localhost"

    def test_preserves_unrelated_entries(self, service):
        """Non-Bose entries are preserved."""
        content = "127.0.0.1 localhost\n192.168.1.1 router.local\n"
        all_domains = (
            service.VTUNER_HOSTS + service.REQUIRED_HOSTS + service.OPTIONAL_HOSTS
        )
        result = service._build_clean_lines(content, all_domains)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# modify_hosts — optional domains
# ---------------------------------------------------------------------------


class TestModifyHostsOptionalDomains:
    """Tests for include_optional parameter."""

    @pytest.mark.asyncio
    async def test_includes_optional_domains_by_default(self, service, mock_ssh):
        """Optional domains (analytics, telemetry) included by default."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        result = await service.modify_hosts(oct_ip="10.0.0.1", include_optional=True)

        assert result.success is True
        for domain in SoundTouchHostsService.OPTIONAL_HOSTS:
            assert domain in result.diff

    @pytest.mark.asyncio
    async def test_excludes_optional_domains_when_disabled(self, service, mock_ssh):
        """Optional domains excluded when include_optional=False."""
        mock_ssh.execute.return_value = _ok("127.0.0.1 localhost")

        result = await service.modify_hosts(oct_ip="10.0.0.1", include_optional=False)

        assert result.success is True
        for domain in SoundTouchHostsService.OPTIONAL_HOSTS:
            assert domain not in result.diff


# ---------------------------------------------------------------------------
# _build_oct_block
# ---------------------------------------------------------------------------


class TestBuildOctBlock:
    """Tests for OCT marker block generation."""

    def test_block_has_markers(self, service):
        """Block starts with OCT-START and ends with OCT-END."""
        block = service._build_oct_block("10.0.0.1", ["bose.vtuner.com"])

        assert block[0] == "# OCT-START"
        assert block[-1] == "# OCT-END"

    def test_block_entries_have_correct_format(self, service):
        """Each entry has IP, tab, domain, tab, comment."""
        block = service._build_oct_block("10.0.0.1", ["bose.vtuner.com"])

        assert "10.0.0.1\tbose.vtuner.com\t# OpenCloudTouch redirect" in block[1]


# ---------------------------------------------------------------------------
# _ensure_backup — backup already exists
# ---------------------------------------------------------------------------


class TestEnsureBackup:
    """Tests for backup creation logic."""

    @pytest.mark.asyncio
    async def test_skips_backup_if_already_exists(self, service, mock_ssh):
        """No copy if backup file already exists."""
        mock_ssh.execute.return_value = _ok("exists")

        await service._ensure_backup("/mnt/nv/hosts_backup")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        cp_calls = [c for c in calls if c.startswith("cp")]
        assert len(cp_calls) == 0

    @pytest.mark.asyncio
    async def test_creates_backup_if_missing(self, service, mock_ssh):
        """Creates backup copy when no backup exists yet."""

        async def side_effect(cmd, **kwargs):
            if "test -f" in cmd:
                return _ok("missing")
            return _ok()

        mock_ssh.execute = AsyncMock(side_effect=side_effect)
        await service._ensure_backup("/mnt/nv/hosts_backup")

        calls = [c[0][0] for c in mock_ssh.execute.call_args_list]
        cp_calls = [c for c in calls if c.startswith("cp")]
        assert len(cp_calls) == 1
