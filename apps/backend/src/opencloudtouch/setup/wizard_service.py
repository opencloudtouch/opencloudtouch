"""Wizard orchestration service.

Encapsulates the multi-step wizard business logic. Route handlers delegate
here instead of directly instantiating SSH services and orchestrating steps.
"""

import logging
import re
import shlex
import socket
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from defusedxml import ElementTree as ET

from opencloudtouch.core.config import get_config
from opencloudtouch.setup.account_pairing_service import (
    check_marge_account_uuid,
    ensure_account_uuid,
    ensure_account_uuid_unique,
)
from opencloudtouch.setup.backup_service import SoundTouchBackupService
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.persistence_service import (
    _PERSISTENCE_DIR,
    REQUIRED_SOURCE_TYPES,
    _file_exists,
    _write_file_atomic,
    build_system_config_xml,
    force_write_sources_xml,
)
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient, check_ssh_port
from opencloudtouch.setup.wizard_helpers import snapshot_config_files, ssh_operation

logger = logging.getLogger(__name__)

_ERR_DEVICE_REPO_UNAVAILABLE = "Device repository not available"


class WizardService:
    """Orchestrates the device setup wizard steps.

    Each method corresponds to one wizard step and handles:
    - SSH connection lifecycle
    - Service instantiation
    - Audit trail snapshots
    - Result assembly
    """

    SSH_TIMEOUT: float = 5.0

    def __init__(self, audit_repo=None, device_repo=None) -> None:
        self._audit_repo = audit_repo
        self._device_repo = device_repo

    async def check_ssh_port(self, device_ip: str) -> bool:
        """Check if SSH port is accessible on device."""
        return await check_ssh_port(device_ip, timeout=self.SSH_TIMEOUT)

    async def backup_all(self, device_ip: str, device_id: str) -> dict:
        """Create complete backup to USB stick.

        Returns:
            Dict with success, message, volumes, total_size_mb, total_duration_seconds
        """
        async with ssh_operation(device_ip, "backup") as ssh:
            backup_service = SoundTouchBackupService(ssh)
            results = await backup_service.backup_all(device_id=device_id)

            failed = [r for r in results if not r.success]
            if failed:
                return {
                    "success": False,
                    "message": "; ".join(r.error or "Unknown" for r in failed),
                }

            total_size = sum(r.size_bytes for r in results) / 1024 / 1024
            total_duration = sum(r.duration_seconds for r in results)

            return {
                "success": True,
                "message": f"Backup complete: {total_size:.2f} MB",
                "volumes": [
                    {
                        "volume": r.volume.value,
                        "path": r.backup_path,
                        "size_mb": r.size_bytes / 1024 / 1024,
                        "duration_seconds": r.duration_seconds,
                    }
                    for r in results
                ],
                "total_size_mb": total_size,
                "total_duration_seconds": total_duration,
            }

    async def modify_config(self, device_ip: str, target_addr: str) -> dict:
        """Modify BMX URL in device config.

        Returns:
            Dict with success, message, backup_path, diff, old_url, new_url
        """
        parsed = urlparse(target_addr)
        target_host = parsed.hostname or parsed.netloc
        target_port = parsed.port or get_config().port

        async with ssh_operation(device_ip, "modify-config") as ssh:
            config_service = SoundTouchConfigService(ssh)

            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                config_service.CONFIG_CANDIDATES,
                "before_modify_config",
            )

            result = await config_service.modify_bmx_url(target_host, port=target_port)

            if result.success:
                await snapshot_config_files(
                    ssh,
                    self._audit_repo,
                    device_ip,
                    config_service.CONFIG_CANDIDATES,
                    "after_modify_config",
                )

            if not result.success:
                return {
                    "success": False,
                    "message": result.error or "Modification failed",
                }

            return {
                "success": True,
                "message": "Config modified successfully",
                "backup_path": result.backup_path,
                "diff": result.diff,
                "old_url": "https://*.bose.com (4 URLs)",
                "new_url": target_addr,
            }

    async def modify_hosts(
        self, device_ip: str, target_addr: str, include_optional: bool = False
    ) -> dict:
        """Modify /etc/hosts on device.

        Returns:
            Dict with success, message, backup_path, diff

        Raises:
            ValueError: If target hostname cannot be resolved
        """
        parsed = urlparse(target_addr)
        target_host = parsed.hostname or parsed.netloc

        try:
            target_ip = socket.gethostbyname(target_host)
        except socket.gaierror:
            raise ValueError(
                f"Cannot resolve hostname '{target_host}' to an IP address."
            )

        async with ssh_operation(device_ip, "modify-hosts") as ssh:
            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                ["/etc/hosts"],
                "before_modify_hosts",
            )

            hosts_service = SoundTouchHostsService(ssh)
            result = await hosts_service.modify_hosts(target_ip, include_optional)

            if result.success:
                await snapshot_config_files(
                    ssh,
                    self._audit_repo,
                    device_ip,
                    ["/etc/hosts"],
                    "after_modify_hosts",
                )

            if not result.success:
                return {
                    "success": False,
                    "message": result.error or "Modification failed",
                }

            return {
                "success": True,
                "message": "Hosts modified successfully",
                "backup_path": result.backup_path,
                "diff": result.diff,
            }

    async def restore_config(self, device_ip: str, backup_path: str) -> dict:
        """Restore config from backup."""
        async with ssh_operation(device_ip, "restore-config") as ssh:
            config_service = SoundTouchConfigService(ssh)
            result = await config_service.restore_config(backup_path)

            if not result.success:
                return {"success": False, "message": result.error or "Restore failed"}
            return {"success": True, "message": "Config restored"}

    async def restore_hosts(self, device_ip: str, backup_path: str) -> dict:
        """Restore hosts from backup."""
        async with ssh_operation(device_ip, "restore-hosts") as ssh:
            hosts_service = SoundTouchHostsService(ssh)
            result = await hosts_service.restore_hosts(backup_path)

            if not result.success:
                return {"success": False, "message": result.error or "Restore failed"}
            return {"success": True, "message": "Hosts restored"}

    async def list_backups(self, device_ip: str) -> dict:
        """List available backups on device."""
        async with ssh_operation(device_ip, "list-backups") as ssh:
            config_service = SoundTouchConfigService(ssh)
            hosts_service = SoundTouchHostsService(ssh)

            config_backups = await config_service.list_backups()
            hosts_backups = await hosts_service.list_backups()

            return {
                "success": True,
                "config_backups": config_backups,
                "hosts_backups": hosts_backups,
            }

    async def reboot_device(self, device_ip: str) -> dict:
        """Reboot device via SSH.

        The device drops SSH immediately — this is expected.
        """
        ssh_client = SoundTouchSSHClient(host=device_ip, port=22)
        try:
            conn_result = await ssh_client.connect(timeout=10.0)
            if not conn_result.success:
                return {
                    "success": False,
                    "error": f"SSH connection failed: {conn_result.error}",
                }

            await ssh_client.execute("reboot", timeout=5.0)
            return {"success": True}
        except Exception as e:
            logger.exception("Unexpected error during reboot: %s", e)
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
        finally:
            await ssh_client.close()

    async def ensure_account_pairing(self, device_ip: str, device_id: str) -> dict:
        """Ensure device has a margeAccountUUID — set one via SSH if missing.

        After pairing, persists the UUID to the device repository so the
        streaming endpoint can resolve account_id -> device_id.

        Returns:
            Dict with success, had_uuid, uuid, message
        """
        try:
            result = await ensure_account_uuid(device_ip)

            if result.success and result.uuid and self._device_repo:
                await self._device_repo.update_marge_account_uuid(
                    device_id, result.uuid
                )
                logger.info(
                    "Persisted marge_account_uuid=%s for device %s",
                    result.uuid,
                    device_id,
                )

            return {
                "success": result.success,
                "had_uuid": result.had_uuid,
                "uuid": result.uuid,
                "message": result.message,
                "error": result.error,
            }
        except Exception as e:
            logger.exception("Account pairing failed for %s: %s", device_ip, e)
            return {
                "success": False,
                "had_uuid": False,
                "uuid": "",
                "message": "",
                "error": f"Account pairing failed: {e}",
            }

    async def mark_complete(self, device_id: str) -> dict:
        """Mark wizard setup as complete for a device."""
        if not self._device_repo:
            return {"success": False, "error": _ERR_DEVICE_REPO_UNAVAILABLE}

        try:
            await self._device_repo.update_setup_status(
                device_id=device_id,
                setup_status="configured",
                setup_completed_at=datetime.now(UTC),
            )
            return {"success": True}
        except Exception as e:
            logger.exception("Failed to update setup status for %s", device_id)
            return {"success": False, "error": f"Failed to update setup status: {e}"}

    async def verify_redirect(
        self, device_ip: str, domain: str, expected_ip: str
    ) -> dict:
        """Verify a domain resolves to expected IP on the device via SSH ping.

        Returns:
            Dict with domain, resolved_ip, expected_ip, matches_expected, message
        """
        # Resolve expected_ip on the server side (handles hostname like 'myserver')
        try:
            expected_resolved = socket.gethostbyname(expected_ip)
        except socket.gaierror:
            expected_resolved = expected_ip

        async with ssh_operation(device_ip, "verify-redirect") as ssh:
            result = await ssh.execute(
                f"ping -c 1 -W 2 {shlex.quote(domain)} 2>&1 | head -2"
            )
            output = (result.output or "").strip()

            match = re.search(r"PING [^\(]*\(([^\)]+)\)", output)
            if not match:
                return {
                    "domain": domain,
                    "resolved_ip": "",
                    "expected_ip": expected_resolved,
                    "matches_expected": False,
                    "message": f"Could not resolve {domain} on device. Output: {output[:200]}",
                }

            resolved_ip = match.group(1).strip()
            matches = resolved_ip == expected_resolved

            return {
                "domain": domain,
                "resolved_ip": resolved_ip,
                "expected_ip": expected_resolved,
                "matches_expected": matches,
                "message": (
                    f"{domain} → {resolved_ip} ✓"
                    if matches
                    else f"{domain} → {resolved_ip} (expected {expected_resolved})"
                ),
            }

    # ========================================================================
    # Finalize & Verify (Issue #184)
    # ========================================================================

    async def finalize_device(self, device_ip: str, device_id: str) -> dict:
        """Finalize device setup: set UUID + force-write Sources.xml.

        Atomic operation that ensures the device has:
        1. A unique margeAccountUUID (with collision detection)
        2. A complete Sources.xml (force-overwrite, backup existing)
        3. SystemConfigurationDB.xml (create if missing)

        Returns:
            Dict with success, uuid, had_uuid, uuid_was_collision,
            sources_written, sources_backup_path, system_config_written,
            message, error
        """
        if not self._device_repo:
            return {"success": False, "error": _ERR_DEVICE_REPO_UNAVAILABLE}

        try:
            # 1. UUID handling with collision detection
            uuid_result = await ensure_account_uuid_unique(
                device_ip=device_ip,
                device_id=device_id,
                device_repo=self._device_repo,
            )

            if not uuid_result.success:
                return {
                    "success": False,
                    "uuid": "",
                    "had_uuid": uuid_result.had_uuid,
                    "uuid_was_collision": False,
                    "sources_written": False,
                    "sources_backup_path": "",
                    "system_config_written": False,
                    "message": "",
                    "error": uuid_result.error or "UUID setup failed",
                }

            # Persist UUID to DB
            await self._device_repo.update_marge_account_uuid(
                device_id, uuid_result.uuid
            )

            uuid_was_collision = not uuid_result.had_uuid and uuid_result.uuid != ""

            # 2. Fetch /info for device metadata (name, variant, module_type)
            device_name, _has_bluetooth = await self._fetch_device_info(device_ip)

            # 3. SSH operations: Sources.xml + SystemConfigurationDB.xml
            async with ssh_operation(device_ip, "finalize") as ssh:
                await ssh.execute("mount -o remount,rw /")
                try:
                    # Force-write Sources.xml (backup existing, hardware-tailored)
                    sources_result = await force_write_sources_xml(
                        ssh,
                        backup=True,
                    )

                    # Create SystemConfigurationDB.xml if missing
                    sys_config_path = f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml"
                    sys_config_written = False
                    await ssh.execute(f"mkdir -p {_PERSISTENCE_DIR}")
                    if not await _file_exists(ssh, sys_config_path):
                        xml_content = build_system_config_xml(
                            device_name, uuid_result.uuid
                        )
                        await _write_file_atomic(ssh, sys_config_path, xml_content)
                        sys_config_written = True
                        logger.info("Created SystemConfigurationDB.xml")

                    # Verify SystemConfigurationDB.xml content
                    verification = await self._verify_sys_config(ssh, uuid_result.uuid)
                finally:
                    await ssh.execute("sync")
                    await ssh.execute("mount -o remount,ro /")

            return {
                "success": True,
                "uuid": uuid_result.uuid,
                "had_uuid": uuid_result.had_uuid,
                "uuid_was_collision": uuid_was_collision,
                "sources_written": sources_result.success,
                "sources_backup_path": sources_result.backup_path,
                "system_config_written": sys_config_written,
                "verification": verification,
                "message": (
                    f"Device finalized: UUID={uuid_result.uuid}, "
                    f"Sources={'written' if sources_result.success else 'FAILED'}, "
                    f"SystemConfig={'created' if sys_config_written else 'exists'}"
                ),
                "error": None,
            }

        except Exception as e:
            logger.exception("Finalize failed for %s: %s", device_ip, e)
            return {
                "success": False,
                "uuid": "",
                "had_uuid": False,
                "uuid_was_collision": False,
                "sources_written": False,
                "sources_backup_path": "",
                "system_config_written": False,
                "message": "",
                "error": f"Finalize failed: {e}",
            }

    @staticmethod
    async def _fetch_device_info(device_ip: str) -> tuple[str, bool]:
        """Fetch device name and Bluetooth capability from /info endpoint.

        Returns:
            Tuple of (device_name, has_bluetooth) with safe defaults on failure.
        """
        device_name = "SoundTouch"
        has_bluetooth = True  # safe default: include BLUETOOTH source
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"http://{device_ip}:8090/info")
                root = ET.fromstring(resp.text)
                name_elem = root.find("name")
                if name_elem is not None and name_elem.text:
                    device_name = name_elem.text.strip()
                # Determine Bluetooth capability from hardware profile
                variant = root.findtext("variant", "").strip()
                module_type = root.findtext("moduleType", "").strip()
                device_type = root.findtext("type", "").strip()
                if module_type:
                    from opencloudtouch.devices.hardware import get_hardware_profile

                    profile = get_hardware_profile(
                        variant or None, module_type, device_type or None
                    )
                    if profile is not None:
                        has_bluetooth = profile.has_bluetooth
                        logger.info(
                            "Hardware profile: %s (bluetooth=%s)",
                            profile.product_name,
                            has_bluetooth,
                        )
        except Exception:
            logger.debug("Could not fetch /info for hardware profile, using defaults")
        return device_name, has_bluetooth

    @staticmethod
    async def _verify_sys_config(ssh: SoundTouchSSHClient, expected_uuid: str) -> dict:
        """Read back SystemConfigurationDB.xml and verify UUID, acctMode, isMultiDeviceAccount."""
        sys_config_path = f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml"
        result = await ssh.execute(f"cat {sys_config_path} 2>/dev/null")
        if not result.success or not result.output:
            logger.warning("Verification: SystemConfigurationDB.xml not readable")
            return {"passed": False, "error": "File not readable"}

        content = result.output.strip()
        checks = {}

        try:
            root = ET.fromstring(content)

            uuid_elem = root.find("AccountUUID")
            uuid_val = (
                uuid_elem.text.strip()
                if uuid_elem is not None and uuid_elem.text
                else ""
            )
            checks["uuid_match"] = uuid_val == expected_uuid
            if not checks["uuid_match"]:
                logger.warning(
                    "Verification: UUID mismatch — expected=%s, got=%s",
                    expected_uuid,
                    uuid_val,
                )

            acct_elem = root.find("acctMode")
            acct_val = (
                acct_elem.text.strip()
                if acct_elem is not None and acct_elem.text
                else ""
            )
            checks["acct_mode_global"] = acct_val == "global"

            multi_elem = root.find("isMultiDeviceAccount")
            multi_val = (
                multi_elem.text.strip()
                if multi_elem is not None and multi_elem.text
                else ""
            )
            checks["multi_device"] = multi_val == "true"

            checks["passed"] = all(checks.values())
        except Exception as e:
            logger.warning("Verification: XML parse failed: %s", e)
            return {"passed": False, "error": f"XML parse failed: {e}"}

        return checks

    async def verify_setup(
        self, device_ip: str, device_id: str, expected_oct_ip: str
    ) -> dict:
        """Comprehensive post-setup health check. Read-only, never modifies device.

        Returns:
            Dict with success, checks (list of check results),
            passed_count, failed_count, message
        """
        checks: list[dict] = []

        def _add(name: str, passed: bool, message: str, details: dict | None = None):
            checks.append(
                {
                    "name": name,
                    "passed": passed,
                    "message": message,
                    "details": details or {},
                }
            )

        try:
            device_uuid = await self._check_uuid_present(device_ip, _add)
            await self._check_uuid_in_db(device_id, device_uuid, _add)

            async with ssh_operation(device_ip, "verify-setup") as ssh:
                await self._check_sources_complete(ssh, _add)
                missing_configs = await self._check_config_files_present(ssh, _add)
                await self._check_config_files_identical(ssh, missing_configs, _add)
                await self._check_bmx_url(ssh, _add)
                hosts_content = await self._read_hosts(ssh)
                has_oct_block = self._check_hosts_oct_block(hosts_content, _add)
                self._check_hosts_domains(hosts_content, has_oct_block, _add)
                self._check_hosts_ip(
                    hosts_content, has_oct_block, expected_oct_ip, _add
                )
                sys_exists = await self._check_system_config_present(ssh, _add)
                await self._check_system_config_uuid(ssh, sys_exists, device_uuid, _add)

        except Exception as e:
            logger.exception("Verify setup failed for %s: %s", device_ip, e)
            _add("connection", False, f"Connection failed: {e}", {})

        passed = sum(1 for c in checks if c["passed"])
        failed = len(checks) - passed

        return {
            "success": failed == 0,
            "checks": checks,
            "passed_count": passed,
            "failed_count": failed,
            "message": f"{passed}/{len(checks)} checks passed"
            + ("" if failed == 0 else f" ({failed} failed)"),
        }

    # ── verify_setup helpers ──────────────────────────────────────────────

    async def _check_uuid_present(self, device_ip, _add):
        """Check 1: UUID present on device."""
        device_uuid = await check_marge_account_uuid(device_ip)
        _add(
            "uuid_present",
            device_uuid is not None and len(device_uuid) > 0,
            (
                f"Device UUID: {device_uuid}"
                if device_uuid
                else "Device has no account UUID. Boot sync will not work."
            ),
            {"uuid": device_uuid or ""},
        )
        return device_uuid

    async def _check_uuid_in_db(self, device_id, device_uuid, _add):
        """Check 2: UUID registered in OCT database."""
        if self._device_repo and device_uuid:
            db_device = await self._device_repo.get_by_account_uuid(device_uuid)
            db_match = db_device is not None and db_device.device_id == device_id
            _add(
                "uuid_in_db",
                db_match,
                (
                    f"UUID registered for {device_id}"
                    if db_match
                    else "UUID not registered in OCT database. Streaming endpoint cannot resolve this device."
                ),
                {"db_device_id": db_device.device_id if db_device else ""},
            )
        elif not device_uuid:
            _add("uuid_in_db", False, "Skipped: no UUID to check", {})
        else:
            _add("uuid_in_db", False, _ERR_DEVICE_REPO_UNAVAILABLE, {})

    async def _check_sources_complete(self, ssh, _add):
        """Check 3: Sources.xml has all required source types."""
        sources_path = f"{_PERSISTENCE_DIR}/Sources.xml"
        r = await ssh.execute(f"cat {sources_path} 2>/dev/null")
        if not (r.success and r.output):
            _add("sources_complete", False, "Sources.xml not found or empty", {})
            return
        found_types = set()
        for line in r.output.splitlines():
            if 'type="' in line:
                m = re.search(r'type="([^"]+)"', line)
                if m:
                    found_types.add(m.group(1))
        missing = REQUIRED_SOURCE_TYPES - found_types
        _add(
            "sources_complete",
            len(missing) == 0,
            (
                f"All {len(REQUIRED_SOURCE_TYPES)} required sources present"
                if not missing
                else f"Missing sources: {', '.join(sorted(missing))}. Preset playback may fail for these source types."
            ),
            {"found": sorted(found_types), "missing": sorted(missing)},
        )

    async def _check_config_files_present(self, ssh, _add):
        """Check 4: Override config file exists on device. Returns list of missing paths."""
        from opencloudtouch.setup.config_service import OVERRIDE_PATH

        # Only the override file is required after setup
        r = await ssh.execute(f"test -f {OVERRIDE_PATH} && echo exists || echo missing")
        missing_configs = []
        if "missing" in (r.output or ""):
            missing_configs.append(OVERRIDE_PATH)

        # Check other /mnt/nv/ variants (informational)
        config_paths = SoundTouchConfigService.CONFIG_CANDIDATES
        for path in config_paths:
            if path == OVERRIDE_PATH:
                continue
            r2 = await ssh.execute(f"test -f {path} && echo exists || echo missing")
            if "missing" in (r2.output or ""):
                missing_configs.append(path)

        _add(
            "config_files_present",
            OVERRIDE_PATH not in missing_configs,
            (
                f"Override config present at {OVERRIDE_PATH}"
                if OVERRIDE_PATH not in missing_configs
                else f"Missing override config: {OVERRIDE_PATH}. Device may not find OCT redirect on reboot."
            ),
            {"missing": missing_configs},
        )
        return missing_configs

    async def _check_config_files_identical(self, ssh, missing_configs, _add):
        """Check 5: All /mnt/nv/ config files have identical content (md5sum)."""
        config_paths = SoundTouchConfigService.CONFIG_CANDIDATES
        # Only compare files that exist
        present = [p for p in config_paths if p not in missing_configs]
        if len(present) < 2:
            _add(
                "config_files_identical",
                True,
                "Only one config file present, no comparison needed",
                {},
            )
            return
        r = await ssh.execute(f"md5sum {' '.join(present)} 2>/dev/null")
        if not (r.success and r.output):
            _add(
                "config_files_identical",
                False,
                "Could not read config files for comparison",
                {},
            )
            return
        hashes = []
        for line in r.output.strip().splitlines():
            parts = line.split()
            if parts:
                hashes.append(parts[0])
        all_same = len(set(hashes)) <= 1
        _add(
            "config_files_identical",
            all_same,
            (
                "All config files have identical content"
                if all_same
                else "Config files differ. Device may use wrong BMX URL after reboot."
            ),
            {"hashes": hashes},
        )

    async def _check_bmx_url(self, ssh, _add):
        """Check 6: BMX URL in config points to OCT, not Bose cloud."""
        from opencloudtouch.setup.config_service import BASE_CONFIG_PATH, OVERRIDE_PATH

        # Try override first, fall back to base config
        r = await ssh.execute(f"cat {OVERRIDE_PATH} 2>/dev/null")
        if not (r.success and r.output):
            r = await ssh.execute(f"cat {BASE_CONFIG_PATH} 2>/dev/null")
        if not (r.success and r.output):
            _add("config_bmx_url", False, "Could not read config file", {})
            return
        bmx_match = re.search(r'bmxRegistryUrl["\s>]*([^<"]+)', r.output)
        if not bmx_match:
            _add("config_bmx_url", False, "bmxRegistryUrl not found in config", {})
            return
        bmx_url = bmx_match.group(1).strip()
        points_to_oct = "bmx.bose.com" not in bmx_url
        _add(
            "config_bmx_url",
            points_to_oct,
            (
                f"BMX URL: {bmx_url}"
                if points_to_oct
                else f"BMX URL still points to Bose cloud ({bmx_url}). Device will not contact OCT."
            ),
            {"bmx_url": bmx_url},
        )

    async def _read_hosts(self, ssh):
        """Read /etc/hosts content from device."""
        r = await ssh.execute("cat /etc/hosts 2>/dev/null")
        return r.output or "" if r.success else ""

    def _check_hosts_oct_block(self, hosts_content, _add):
        """Check 7: OCT block present in /etc/hosts."""
        has_oct_block = (
            SoundTouchHostsService.OCT_MARKER_START in hosts_content
            and SoundTouchHostsService.OCT_MARKER_END in hosts_content
        )
        _add(
            "hosts_oct_block",
            has_oct_block,
            (
                "OCT block present in /etc/hosts"
                if has_oct_block
                else "No OCT block in /etc/hosts. Domain redirects are missing."
            ),
            {},
        )
        return has_oct_block

    def _check_hosts_domains(self, hosts_content, has_oct_block, _add):
        """Check 8: All required domains present in hosts."""
        if not has_oct_block:
            _add("hosts_domains_complete", False, "Skipped: no OCT block", {})
            return
        all_required = (
            SoundTouchHostsService.VTUNER_HOSTS + SoundTouchHostsService.REQUIRED_HOSTS
        )
        missing_domains = [d for d in all_required if d not in hosts_content]
        _add(
            "hosts_domains_complete",
            len(missing_domains) == 0,
            (
                f"All {len(all_required)} required domains present"
                if not missing_domains
                else f"Missing host entries: {', '.join(missing_domains)}. Some Bose services will not be redirected."
            ),
            {"missing": missing_domains},
        )

    def _check_hosts_ip(self, hosts_content, has_oct_block, expected_oct_ip, _add):
        """Check 9: Host entries point to the correct OCT IP."""
        if not has_oct_block:
            _add("hosts_ip_correct", False, "Skipped: no OCT block", {})
            return
        all_hosts = (
            SoundTouchHostsService.VTUNER_HOSTS + SoundTouchHostsService.REQUIRED_HOSTS
        )
        wrong_ips = []
        for line in hosts_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not any(d in stripped for d in all_hosts):
                continue
            parts = stripped.split()
            if len(parts) >= 2 and parts[0] != expected_oct_ip:
                wrong_ips.append(f"{parts[1]}={parts[0]}")
        _add(
            "hosts_ip_correct",
            len(wrong_ips) == 0,
            (
                f"All host entries point to {expected_oct_ip}"
                if not wrong_ips
                else f"Host entries point to wrong IP: {', '.join(wrong_ips)} (expected {expected_oct_ip}). Check for stale entries."
            ),
            {"wrong": wrong_ips},
        )

    async def _check_system_config_present(self, ssh, _add):
        """Check 10: SystemConfigurationDB.xml exists on device."""
        sys_config_path = f"{_PERSISTENCE_DIR}/SystemConfigurationDB.xml"
        r = await ssh.execute(
            f"test -f {sys_config_path} && echo exists || echo missing"
        )
        sys_config_exists = "exists" in (r.output or "")
        _add(
            "system_config_present",
            sys_config_exists,
            (
                "SystemConfigurationDB.xml present"
                if sys_config_exists
                else "SystemConfigurationDB.xml missing. Device may not initialize properly."
            ),
            {},
        )
        return sys_config_exists

    async def _check_system_config_uuid(self, ssh, sys_exists, device_uuid, _add):
        """Check 11: UUID in SystemConfigurationDB.xml matches device."""
        if not sys_exists:
            _add("system_config_uuid_match", False, "Skipped: file missing", {})
            return
        if not device_uuid:
            _add("system_config_uuid_match", False, "Skipped: no device UUID", {})
            return
        verification = await self._verify_sys_config(ssh, device_uuid)
        uuid_file_match = verification.get("uuid_match", False)
        _add(
            "system_config_uuid_match",
            uuid_file_match,
            (
                "UUID in SystemConfigurationDB.xml matches device"
                if uuid_file_match
                else "UUID in SystemConfigurationDB.xml does not match device UUID"
            ),
            verification,
        )
