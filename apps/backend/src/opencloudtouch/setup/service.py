"""
Device Setup Service

Orchestrates the device configuration process:
1. Check SSH connectivity
2. Make SSH persistent
3. Backup config
4. Modify BMX URL
5. Verify configuration
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Callable, Awaitable

from opencloudtouch.core.config import get_config
from opencloudtouch.setup.models import (
    SetupStatus,
    SetupStep,
    SetupProgress,
    get_model_instructions,
    ModelInstructions,
)
from opencloudtouch.setup.ssh_client import (
    SoundTouchSSHClient,
    SoundTouchTelnetClient,
    check_ssh_port,
    check_telnet_port,
)

logger = logging.getLogger(__name__)

# Type alias for progress callback
ProgressCallback = Callable[[SetupProgress], Awaitable[None]]


class SetupService:
    """
    Service for configuring SoundTouch devices.

    Handles the full setup flow from SSH connection to BMX URL modification.
    """

    def __init__(self):
        self._active_setups: Dict[str, SetupProgress] = {}
        self._config = get_config()

    def get_setup_status(self, device_id: str) -> Optional[SetupProgress]:
        """Get current setup status for a device."""
        return self._active_setups.get(device_id)

    def get_model_instructions(self, model_name: str) -> ModelInstructions:
        """Get setup instructions for a specific model."""
        return get_model_instructions(model_name)

    async def check_device_connectivity(self, ip: str) -> dict:
        """
        Check what connection methods are available for a device.

        Returns dict with ssh_available, telnet_available flags.
        """
        ssh_available = await check_ssh_port(ip)
        telnet_available = await check_telnet_port(ip)

        return {
            "ip": ip,
            "ssh_available": ssh_available,
            "telnet_available": telnet_available,
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
            # Step 1: Connect via SSH
            await update_progress(SetupStep.SSH_CONNECT, "Verbinde via SSH...")

            client = SoundTouchSSHClient(ip)
            conn_result = await client.connect(timeout=15.0)

            if not conn_result.success:
                await update_progress(
                    SetupStep.SSH_CONNECT,
                    "SSH-Verbindung fehlgeschlagen",
                    error=conn_result.error,
                )
                return progress

            logger.info(f"SSH connected to {ip}")

            # Step 2: Make SSH persistent
            await update_progress(SetupStep.SSH_PERSIST, "Aktiviere SSH dauerhaft...")

            result = await client.execute("touch /mnt/nv/remote_services")
            if not result.success:
                logger.warning(f"Could not persist SSH: {result.error}")
                # Continue anyway - might already be persistent

            # Verify
            result = await client.execute("ls -la /mnt/nv/remote_services")
            if "remote_services" in result.output:
                logger.info("SSH persistence verified")

            # Step 3: Backup config
            await update_progress(SetupStep.CONFIG_BACKUP, "Erstelle Backup...")

            backup_dir = (
                f"/mnt/nv/backup_oct_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            await client.execute(f"mkdir -p {backup_dir}")

            # Backup important files
            files_to_backup = [
                "/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml",
                "/opt/Bose/etc/SoundTouchCfg.xml",
            ]
            for filepath in files_to_backup:
                await client.execute(f"cp {filepath} {backup_dir}/ 2>/dev/null || true")

            logger.info(f"Config backup created in {backup_dir}")

            # Step 4: Read current config
            await update_progress(
                SetupStep.CONFIG_MODIFY, "Lese aktuelle Konfiguration..."
            )

            result = await client.execute(
                "cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml | grep -i bmxRegistryUrl"
            )
            current_bmx_url = result.output.strip() if result.success else "Unknown"
            logger.info(f"Current BMX URL: {current_bmx_url}")

            # Build our BMX URL
            oct_server = (
                self._config.server_url
                or f"http://{self._config.host}:{self._config.port}"
            )
            new_bmx_url = f"{oct_server}/bmx/registry/v1/services"

            # Step 5: Modify config
            await update_progress(
                SetupStep.CONFIG_MODIFY, f"Setze BMX URL auf {new_bmx_url}..."
            )

            # Check if we can write to /opt/Bose (usually read-only)
            # Try creating override in /mnt/nv instead
            result = await client.execute(
                "test -w /opt/Bose/etc && echo 'writable' || echo 'readonly'"
            )

            if "readonly" in result.output:
                logger.info("Root filesystem is read-only, using override mechanism")

                # Copy config to /mnt/nv for override
                await client.execute(
                    "cp /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml /mnt/nv/SoundTouchSdkPrivateCfg.xml"
                )

                # Modify the copy using sed
                sed_cmd = f"sed -i 's|<bmxRegistryUrl>.*</bmxRegistryUrl>|<bmxRegistryUrl>{new_bmx_url}</bmxRegistryUrl>|g' /mnt/nv/SoundTouchSdkPrivateCfg.xml"
                result = await client.execute(sed_cmd)

                if not result.success:
                    await update_progress(
                        SetupStep.CONFIG_MODIFY,
                        "Konfiguration konnte nicht geändert werden",
                        error=result.error,
                    )
                    await client.close()
                    return progress

                # Note: Device needs to be configured to read from /mnt/nv override
                # This might require additional steps depending on firmware version
                logger.warning(
                    "Config written to /mnt/nv - may need additional override setup"
                )
            else:
                # Direct modification (if filesystem is writable)
                sed_cmd = f"sed -i 's|<bmxRegistryUrl>.*</bmxRegistryUrl>|<bmxRegistryUrl>{new_bmx_url}</bmxRegistryUrl>|g' /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml"
                result = await client.execute(sed_cmd)

                if not result.success:
                    await update_progress(
                        SetupStep.CONFIG_MODIFY,
                        "Konfiguration konnte nicht geändert werden",
                        error=result.error,
                    )
                    await client.close()
                    return progress

            # Step 6: Verify
            await update_progress(SetupStep.VERIFY, "Verifiziere Konfiguration...")

            # Read back and verify
            result = await client.execute(
                "cat /mnt/nv/SoundTouchSdkPrivateCfg.xml 2>/dev/null || "
                "cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml | grep -i bmxRegistryUrl"
            )

            if new_bmx_url in result.output:
                logger.info("BMX URL verified successfully")
            else:
                logger.warning(f"BMX URL verification unclear: {result.output}")

            # Close connection
            await client.close()

            # Step 7: Complete
            await update_progress(SetupStep.COMPLETE, "Setup abgeschlossen!")
            progress.status = SetupStatus.CONFIGURED
            progress.completed_at = datetime.utcnow()

            logger.info(f"Device {device_id} setup completed successfully")
            return progress

        except Exception as e:
            logger.exception(f"Setup failed for device {device_id}")
            progress.status = SetupStatus.FAILED
            progress.error = str(e)
            progress.message = "Setup fehlgeschlagen"
            return progress
        finally:
            # Cleanup
            if device_id in self._active_setups:
                if progress.status == SetupStatus.CONFIGURED:
                    del self._active_setups[device_id]

    async def verify_setup(self, ip: str) -> dict:
        """
        Verify that a device is properly configured.

        Checks:
        - SSH is accessible
        - SSH is persistent
        - BMX URL points to our server
        """
        result = {
            "ip": ip,
            "ssh_accessible": False,
            "ssh_persistent": False,
            "bmx_configured": False,
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
                "cat /mnt/nv/SoundTouchSdkPrivateCfg.xml 2>/dev/null || "
                "cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml | grep -i bmxRegistryUrl"
            )
            result["bmx_url"] = check.output.strip()

            # Verify it points to our server
            config = get_config()
            our_server = config.server_url or f"http://{config.host}:{config.port}"
            result["bmx_configured"] = our_server in check.output

            await client.close()

            # Overall verification
            result["verified"] = all(
                [
                    result["ssh_accessible"],
                    result["ssh_persistent"],
                    result["bmx_configured"],
                ]
            )

        except Exception as e:
            logger.error(f"Verification failed: {e}")

        return result


# Singleton instance
_setup_service: Optional[SetupService] = None


def get_setup_service() -> SetupService:
    """Get or create the setup service singleton."""
    global _setup_service
    if _setup_service is None:
        _setup_service = SetupService()
    return _setup_service
