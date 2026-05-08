"""
Device Setup Service

Orchestrates the device configuration process:
1. Check SSH connectivity
2. Make SSH persistent
3. Backup config
4. Modify BMX URL
5. Verify configuration
"""

import logging
from datetime import UTC, datetime
from typing import Awaitable, Callable, Dict, Optional

from opencloudtouch.core.config import get_config
from opencloudtouch.setup.models import (
    ModelInstructions,
    SetupProgress,
    SetupStatus,
    SetupStep,
    get_model_instructions,
)
from opencloudtouch.setup.ssh_client import (
    SoundTouchSSHClient,
    check_ssh_port,
)

logger = logging.getLogger(__name__)

# Type alias for progress callback
ProgressCallback = Callable[[SetupProgress], Awaitable[None]]


class SetupService:
    """
    Service for configuring SoundTouch devices.

    Handles the full setup flow from SSH connection to BMX URL modification.
    """

    def __init__(self, device_repo=None):
        self._active_setups: Dict[str, SetupProgress] = {}
        self._config = get_config()
        self._device_repo = device_repo

    def get_setup_status(self, device_id: str) -> Optional[SetupProgress]:
        """Get current setup status for a device."""
        return self._active_setups.get(device_id)

    def get_model_instructions(self, model_name: str) -> ModelInstructions:
        """Get setup instructions for a specific model."""
        return get_model_instructions(model_name)

    async def check_device_connectivity(self, ip: str) -> dict:
        """
        Check what connection methods are available for a device.

        Returns dict with ssh_available flag.
        """
        ssh_available = await check_ssh_port(ip)

        return {
            "ip": ip,
            "ssh_available": ssh_available,
            "ready_for_setup": ssh_available,
        }

    async def run_setup(
        self,
        device_id: str,
        ip: str,
        model: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SetupProgress:
        """
        Run the full setup process for a device.

        Args:
            device_id: Unique device identifier
            ip: Device IP address
            model: Device model name
            on_progress: Optional callback for progress updates

        Returns:
            Final SetupProgress with result
        """
        progress = SetupProgress(
            device_id=device_id,
            current_step=SetupStep.SSH_CONNECT,
            status=SetupStatus.PENDING,
            message="Starte Setup...",
        )
        self._active_setups[device_id] = progress

        async def update_progress(
            step: SetupStep, message: str, error: Optional[str] = None
        ):
            progress.current_step = step
            progress.message = message
            if error:
                progress.error = error
                progress.status = SetupStatus.FAILED
            if on_progress:
                await on_progress(progress)

        try:
            await update_progress(SetupStep.SSH_CONNECT, "Verbinde via SSH...")
            client = await self._connect_ssh(ip, update_progress, progress)
            if client is None:
                return progress

            await update_progress(SetupStep.SSH_PERSIST, "Aktiviere SSH dauerhaft...")
            await self._persist_ssh(client)

            await update_progress(SetupStep.CONFIG_BACKUP, "Erstelle Backup...")
            await self._backup_config(client)

            new_bmx_url = self._resolve_bmx_url()
            await update_progress(
                SetupStep.CONFIG_MODIFY, f"Setze BMX URL auf {new_bmx_url}..."
            )

            failed = await self._apply_bmx_url(
                client, new_bmx_url, update_progress, progress
            )
            if failed:
                await client.close()
                return progress

            await update_progress(SetupStep.VERIFY, "Verifiziere Konfiguration...")
            await self._verify_bmx_url(client, new_bmx_url)
            await client.close()

            await update_progress(SetupStep.COMPLETE, "Setup abgeschlossen!")
            progress.status = SetupStatus.CONFIGURED
            progress.completed_at = datetime.now(UTC)
            logger.info(f"Device {device_id} setup completed successfully")

            # Persist to device table
            if self._device_repo:
                await self._device_repo.update_setup_status(
                    device_id=device_id,
                    setup_status="configured",
                    ssh_permanent=True,
                    setup_completed_at=progress.completed_at,
                )

            return progress

        except Exception as e:
            logger.exception(f"Setup failed for device {device_id}")
            progress.status = SetupStatus.FAILED
            progress.error = str(e)
            progress.message = "Setup fehlgeschlagen"

            # Persist failure
            if self._device_repo:
                await self._device_repo.update_setup_status(
                    device_id=device_id,
                    setup_status="failed",
                )

            return progress
        finally:
            if device_id in self._active_setups:
                if progress.status == SetupStatus.CONFIGURED:
                    del self._active_setups[device_id]

    async def _connect_ssh(
        self,
        ip: str,
        update_progress: Callable,
        progress: "SetupProgress",
    ) -> Optional["SoundTouchSSHClient"]:
        """Connect to device via SSH. Returns client on success, None on failure."""
        client = SoundTouchSSHClient(ip)
        conn_result = await client.connect(timeout=15.0)
        if not conn_result.success:
            await update_progress(
                SetupStep.SSH_CONNECT,
                "SSH-Verbindung fehlgeschlagen",
                error=conn_result.error,
            )
            return None
        logger.info(f"SSH connected to {ip}")
        return client

    async def _persist_ssh(self, client: "SoundTouchSSHClient") -> None:
        """Make SSH persistent on the device (best-effort, does not fail setup)."""
        result = await client.execute("touch /mnt/nv/remote_services")
        if not result.success:
            logger.warning(f"Could not persist SSH: {result.error}")
        result = await client.execute("ls -la /mnt/nv/remote_services")
        if "remote_services" in (result.output or ""):
            logger.info("SSH persistence verified")

    async def _backup_config(self, client: "SoundTouchSSHClient") -> None:
        """Back up important device config files to /mnt/nv."""
        backup_dir = f"/mnt/nv/backup_oct_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        await client.execute(f"mkdir -p {backup_dir}")
        for filepath in [
            "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml",
            "/opt/Bose/etc/SoundTouchCfg.xml",
        ]:
            await client.execute(f"cp {filepath} {backup_dir}/ 2>/dev/null || true")
        logger.info(f"Config backup created in {backup_dir}")

    def _resolve_bmx_url(self) -> str:
        """Build the BMX registry URL for this OCT instance."""
        oct_server = (
            self._config.server_url or f"http://{self._config.host}:{self._config.port}"
        )
        return f"{oct_server}/bmx/registry/v1/services"

    async def _apply_bmx_url(
        self,
        client: "SoundTouchSSHClient",
        new_bmx_url: str,
        update_progress: Callable,
        progress: "SetupProgress",
    ) -> bool:
        """Write the new BMX URL into device config.

        Always edits /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml directly
        after remounting rw. The OverrideSdkPrivateCfg.xml approach does NOT
        work on SoundTouch 10/300 (firmware ignores it).

        Returns:
            True if the step failed (caller should abort), False on success.
        """
        config_path = "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"

        # Remount rw — required for editing /opt/Bose/etc/
        await client.execute("mount -o remount,rw /")

        sed_cmd = (
            f"sed -i 's|<bmxRegistryUrl>.*</bmxRegistryUrl>|"
            f"<bmxRegistryUrl>{new_bmx_url}</bmxRegistryUrl>|g' {config_path}"
        )
        result = await client.execute(sed_cmd)
        if not result.success:
            await update_progress(
                SetupStep.CONFIG_MODIFY,
                "Konfiguration konnte nicht geändert werden",
                error=result.error,
            )
            return True  # failed
        return False  # success

    async def _verify_bmx_url(
        self, client: "SoundTouchSSHClient", new_bmx_url: str
    ) -> None:
        """Verify that the BMX URL was written correctly (best-effort log only)."""
        result = await client.execute(
            "cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml | grep -i bmxRegistryUrl"
        )
        if new_bmx_url in (result.output or ""):
            logger.info("BMX URL verified successfully")
        else:
            logger.warning(f"BMX URL verification unclear: {result.output}")

    async def verify_setup(self, ip: str) -> dict:
        """
        Verify that a device is properly configured.

        Supports two setup strategies:
        - Strategy A (URL): BMX URL in config points directly to OCT server
        - Strategy B (Hosts): /etc/hosts redirects Bose domains to OCT via
          reverse proxy (identified by ``# OCT-START`` marker)

        Checks:
        - SSH is accessible
        - SSH is persistent
        - BMX URL points to our server OR hosts redirect is active
        """
        result = {
            "ip": ip,
            "ssh_accessible": False,
            "ssh_persistent": False,
            "bmx_configured": False,
            "hosts_redirect": False,
            "bmx_url": None,
            "verified": False,
        }

        # Check SSH
        ssh_available = await check_ssh_port(ip)
        result["ssh_accessible"] = ssh_available

        if not ssh_available:
            return result

        try:
            client = SoundTouchSSHClient(ip)
            await client.connect(timeout=10.0)

            # Check SSH persistence
            check = await client.execute(
                "test -f /mnt/nv/remote_services && echo 'yes'"
            )
            result["ssh_persistent"] = "yes" in check.output

            # Check BMX URL
            check = await client.execute(
                "cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml | grep -i bmxRegistryUrl"
            )
            result["bmx_url"] = check.output.strip()

            # Strategy A: BMX URL points directly to our server
            config = get_config()
            our_server = (
                config.station_descriptor_base_url
                or f"http://{config.host}:{config.port}"
            )
            result["bmx_configured"] = our_server in check.output

            # Strategy B: /etc/hosts redirects Bose domains to OCT
            hosts_check = await client.execute(
                "grep -c 'OCT-START' /etc/hosts 2>/dev/null || echo '0'"
            )
            result["hosts_redirect"] = hosts_check.output.strip() != "0"

            await client.close()

            # Either strategy counts as configured
            result["verified"] = all(
                [
                    result["ssh_accessible"],
                    result["ssh_persistent"],
                    result["bmx_configured"] or result["hosts_redirect"],
                ]
            )

        except Exception as e:
            logger.error(f"Verification failed: {e}")

        return result
