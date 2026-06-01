"""Device rename via SSH.

Updates the <DeviceName> tag in SystemConfigurationDB.xml on the device.
Reuses the existing SSH infrastructure from the setup wizard.
"""

import logging
import re

from xml.sax.saxutils import escape as xml_escape

from opencloudtouch.setup.wizard_helpers import ssh_operation

logger = logging.getLogger(__name__)

_SYS_CONFIG_PATH = "/mnt/nv/BoseApp-Persistence/1/SystemConfigurationDB.xml"
_DEVICE_NAME_RE = re.compile(r"(<DeviceName>)(.*?)(</DeviceName>)", re.DOTALL)


async def rename_device_via_ssh(device_ip: str, new_name: str) -> None:
    """Rename a SoundTouch device by updating SystemConfigurationDB.xml.

    Reads the existing XML, replaces the <DeviceName> tag, and writes back.
    If the file doesn't exist, raises an error (device must be provisioned).

    Args:
        device_ip: IP address of the device
        new_name: New device name (must be pre-validated: 1-30 chars)

    Raises:
        RuntimeError: If the file doesn't exist or write fails
    """
    escaped_name = xml_escape(new_name)

    async with ssh_operation(device_ip, "rename-device") as ssh:
        # Read existing config
        read_result = await ssh.execute(f"cat {_SYS_CONFIG_PATH}")
        if not read_result.success or not read_result.output:
            raise RuntimeError(
                f"Could not read {_SYS_CONFIG_PATH} — device may not be provisioned"
            )

        xml_content = read_result.output.strip()

        # Replace DeviceName
        if _DEVICE_NAME_RE.search(xml_content):
            new_xml = _DEVICE_NAME_RE.sub(rf"\g<1>{escaped_name}\g<3>", xml_content)
        else:
            raise RuntimeError(
                "<DeviceName> tag not found in SystemConfigurationDB.xml"
            )

        # Write back atomically
        await ssh.execute("mount -o remount,rw /")
        try:
            write_result = await ssh.execute(
                f"cat > {_SYS_CONFIG_PATH} << 'XMLEOF'\n{new_xml}\nXMLEOF"
            )
            if not write_result.success:
                raise RuntimeError(
                    f"Failed to write {_SYS_CONFIG_PATH}: {write_result.error}"
                )
        finally:
            await ssh.execute("mount -o remount,ro /")

        logger.info("Device %r renamed to %r via SSH", device_ip, new_name)
