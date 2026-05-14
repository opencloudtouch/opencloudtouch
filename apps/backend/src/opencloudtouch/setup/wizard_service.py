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

from opencloudtouch.setup.account_pairing_service import ensure_account_uuid
from opencloudtouch.setup.backup_service import SoundTouchBackupService
from opencloudtouch.setup.config_service import SoundTouchConfigService
from opencloudtouch.setup.hosts_service import SoundTouchHostsService
from opencloudtouch.setup.ssh_client import SoundTouchSSHClient, check_ssh_port
from opencloudtouch.setup.wizard_helpers import snapshot_config_files, ssh_operation

logger = logging.getLogger(__name__)


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

        async with ssh_operation(device_ip, "modify-config") as ssh:
            config_service = SoundTouchConfigService(ssh)

            await snapshot_config_files(
                ssh,
                self._audit_repo,
                device_ip,
                config_service.CONFIG_CANDIDATES,
                "before_modify_config",
            )

            result = await config_service.modify_bmx_url(target_host)

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
                "old_url": "bmx.bose.com",
                "new_url": target_host,
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
        """Ensure device has a margeAccountUUID - set one via Telnet if missing.

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
            return {"success": False, "error": "Device repository not available"}

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
