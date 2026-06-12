"""
Device Setup Service

Provides connectivity checks, setup status, and verification.
The step-by-step wizard flow lives in wizard_routes.py / config_service.py.
"""

import logging
from typing import Dict, Optional

from opencloudtouch.core.config import get_config
from opencloudtouch.setup.models import (
    ModelInstructions,
    SetupProgress,
    get_model_instructions,
)
from opencloudtouch.setup.ssh_client import (
    SoundTouchSSHClient,
    check_ssh_port,
)

logger = logging.getLogger(__name__)


class SetupService:
    """
    Service for device setup helpers.

    The full setup flow is handled step-by-step via the wizard endpoints.
    This service provides connectivity checks, status tracking, and verification.
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
                "(cat /mnt/nv/OverrideSdkPrivateCfg.xml 2>/dev/null "
                "|| cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml) "
                "| grep -i bmxRegistryUrl"
            )
            result["bmx_url"] = check.output.strip()

            # Strategy A: BMX URL points directly to our server
            config = get_config()
            our_server = (
                config.station_descriptor_base_url
                or f"http://{config.host}:{config.port}"  # NOSONAR — LAN only
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
            logger.error("Verification failed: %s", e)

        return result
