"""
Static hardware profile lookup for SoundTouch devices.

Maps (variant, module_type) to physical hardware capabilities that
cannot be detected via the device API at runtime.

Data sources:
- firmware_index.xml (variant ↔ product mapping, USB support)
- Real device /info dumps (variant, moduleType fields)
- Bose product documentation (USB port types, Bluetooth, AirPlay)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class UsbPortType(str, Enum):
    """Physical USB port type on the device."""

    MICRO_USB = "micro-usb"
    USB_A = "usb-a"


@dataclass(frozen=True)
class DeviceHardwareProfile:
    """Static hardware profile for a SoundTouch device model."""

    product_name: str
    has_bluetooth: bool
    has_airplay: bool
    usb_ports: tuple[UsbPortType, ...]
    has_display: bool

    @property
    def has_usb(self) -> bool:
        return len(self.usb_ports) > 0


# ---------------------------------------------------------------------------
# Lookup table keyed by (variant, module_type).
#
# Bluetooth:  SCM = False, SM2 = True (user directive: assume BT for all sm2)
# AirPlay:    All generations (user confirmed: AirPlay since Gen I)
# USB ports:  Verified from firmware_index.xml USBPATH + product teardowns.
#             ST20/ST30 sm2 span Gen II (Micro-USB) and Gen III (USB-A)
#             → both listed since generation is not detectable via API.
# Display:    ST20/ST30/Wave have OLED; ST10/ST300/SA-5/Link do not.
# ---------------------------------------------------------------------------

_PROFILES: dict[tuple[str, str], DeviceHardwareProfile] = {
    # ── SM2 (Gen II+) standalone speakers ──────────────────────────────
    ("spotty", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch 20",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.MICRO_USB, UsbPortType.USB_A),
        has_display=True,
    ),
    ("mojo", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch 30",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.MICRO_USB, UsbPortType.USB_A),
        has_display=True,
    ),
    ("rhino", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch 10",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.MICRO_USB,),
        has_display=False,
    ),
    # ── SM2 soundbar / amplifier / adapter ─────────────────────────────
    ("ginger", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch 300",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=False,
    ),
    ("burns", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch SA-5",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=False,
    ),
    # Wireless Link uses generic sm2 firmware, variant not in filename
    # but device reports variant via /info
    # ── SM2 home theater systems ───────────────────────────────────────
    ("nelson", "sm2"): DeviceHardwareProfile(
        product_name="Wave SoundTouch",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A, UsbPortType.MICRO_USB),
        has_display=True,
    ),
    ("lisa", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch Stereo JC / SA-4",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=False,
    ),
    ("triode", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch Cinemate",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=False,
    ),
    ("marconi", "sm2"): DeviceHardwareProfile(
        product_name="Lifestyle / VideoWave",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=True,
    ),
    ("bardeen", "sm2"): DeviceHardwareProfile(
        product_name="Lifestyle",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(),  # No USBPATH in firmware_index.xml
        has_display=False,
    ),
    # ── SCM (Gen I) standalone speakers ────────────────────────────────
    ("spotty", "scm"): DeviceHardwareProfile(
        product_name="SoundTouch 20",
        has_bluetooth=False,
        has_airplay=True,
        usb_ports=(UsbPortType.MICRO_USB,),
        has_display=True,
    ),
    ("mojo", "scm"): DeviceHardwareProfile(
        product_name="SoundTouch 30",
        has_bluetooth=False,
        has_airplay=True,
        usb_ports=(UsbPortType.MICRO_USB,),
        has_display=True,
    ),
    # ── SCM (Gen I) home theater systems ───────────────────────────────
    ("nelson", "scm"): DeviceHardwareProfile(
        product_name="Wave SoundTouch",
        has_bluetooth=False,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A, UsbPortType.MICRO_USB),
        has_display=True,
    ),
    ("lisa", "scm"): DeviceHardwareProfile(
        product_name="SoundTouch Stereo JC / SA-4",
        has_bluetooth=False,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=False,
    ),
    ("triode", "scm"): DeviceHardwareProfile(
        product_name="SoundTouch Cinemate",
        has_bluetooth=False,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=False,
    ),
    ("marconi", "scm"): DeviceHardwareProfile(
        product_name="Lifestyle / VideoWave",
        has_bluetooth=False,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=True,
    ),
}

# Fallback lookup by (device_type, module_type) for devices that may not
# report a variant or report an unknown one.  device_type comes from the
# /info <type> field, e.g. "SoundTouch 20".
_TYPE_FALLBACKS: dict[tuple[str, str], DeviceHardwareProfile] = {
    ("SoundTouch Portable", "scm"): DeviceHardwareProfile(
        product_name="SoundTouch Portable",
        has_bluetooth=False,
        has_airplay=True,
        usb_ports=(UsbPortType.MICRO_USB,),
        has_display=True,
    ),
    ("SoundTouch Wireless Link adapter", "sm2"): DeviceHardwareProfile(
        product_name="SoundTouch Wireless Link",
        has_bluetooth=True,
        has_airplay=True,
        usb_ports=(UsbPortType.USB_A,),
        has_display=False,
    ),
}


def get_hardware_profile(
    variant: Optional[str],
    module_type: Optional[str],
    device_type: Optional[str] = None,
) -> Optional[DeviceHardwareProfile]:
    """Look up the static hardware profile for a SoundTouch device.

    Args:
        variant: Internal codename from /info (spotty, rhino, mojo, …)
        module_type: Hardware platform from /info (scm or sm2)
        device_type: Product name from /info <type> field, used as fallback

    Returns:
        Hardware profile or None if device is unknown.
    """
    if variant and module_type:
        key = (variant.lower(), module_type.lower())
        profile = _PROFILES.get(key)
        if profile:
            return profile

    if device_type and module_type:
        fallback_key = (device_type, module_type.lower())
        profile = _TYPE_FALLBACKS.get(fallback_key)
        if profile:
            return profile

    # Last resort: derive minimal profile from module_type alone
    if module_type:
        is_sm2 = module_type.lower() == "sm2"
        return DeviceHardwareProfile(
            product_name=device_type or "Unknown SoundTouch",
            has_bluetooth=is_sm2,
            has_airplay=True,
            usb_ports=(UsbPortType.MICRO_USB, UsbPortType.USB_A),
            has_display=False,
        )

    return None
