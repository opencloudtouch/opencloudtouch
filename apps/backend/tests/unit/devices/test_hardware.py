"""Tests for hardware profile lookup."""

import pytest

from opencloudtouch.devices.hardware import (
    DeviceHardwareProfile,
    UsbPortType,
    get_hardware_profile,
)


class TestUsbPortType:
    def test_enum_values(self):
        assert UsbPortType.MICRO_USB == "micro-usb"
        assert UsbPortType.USB_A == "usb-a"


class TestDeviceHardwareProfile:
    def test_has_usb_true(self):
        profile = DeviceHardwareProfile(
            product_name="Test",
            has_bluetooth=True,
            has_airplay=True,
            usb_ports=(UsbPortType.USB_A,),
            has_display=False,
        )
        assert profile.has_usb is True

    def test_has_usb_false(self):
        profile = DeviceHardwareProfile(
            product_name="Test",
            has_bluetooth=False,
            has_airplay=True,
            usb_ports=(),
            has_display=False,
        )
        assert profile.has_usb is False

    def test_frozen(self):
        profile = DeviceHardwareProfile(
            product_name="Test",
            has_bluetooth=True,
            has_airplay=True,
            usb_ports=(),
            has_display=False,
        )
        with pytest.raises(AttributeError):
            profile.product_name = "Changed"  # type: ignore[misc]


class TestGetHardwareProfile:
    """Test get_hardware_profile() lookup logic."""

    # ── Primary lookup: (variant, module_type) ───────────────────────

    @pytest.mark.parametrize(
        "variant, module_type, expected_name",
        [
            ("spotty", "sm2", "SoundTouch 20"),
            ("mojo", "sm2", "SoundTouch 30"),
            ("rhino", "sm2", "SoundTouch 10"),
            ("ginger", "sm2", "SoundTouch 300"),
            ("burns", "sm2", "SoundTouch SA-5"),
            ("nelson", "sm2", "Wave SoundTouch"),
            ("lisa", "sm2", "SoundTouch Stereo JC / SA-4"),
            ("triode", "sm2", "SoundTouch Cinemate"),
            ("marconi", "sm2", "Lifestyle / VideoWave"),
            ("bardeen", "sm2", "Lifestyle"),
            ("spotty", "scm", "SoundTouch 20"),
            ("mojo", "scm", "SoundTouch 30"),
            ("nelson", "scm", "Wave SoundTouch"),
            ("lisa", "scm", "SoundTouch Stereo JC / SA-4"),
            ("triode", "scm", "SoundTouch Cinemate"),
            ("marconi", "scm", "Lifestyle / VideoWave"),
        ],
    )
    def test_primary_lookup(self, variant, module_type, expected_name):
        profile = get_hardware_profile(variant, module_type)
        assert profile is not None
        assert profile.product_name == expected_name

    def test_case_insensitive(self):
        profile = get_hardware_profile("SPOTTY", "SM2")
        assert profile is not None
        assert profile.product_name == "SoundTouch 20"

    # ── SM2 vs SCM capabilities ──────────────────────────────────────

    def test_sm2_has_bluetooth(self):
        profile = get_hardware_profile("spotty", "sm2")
        assert profile is not None
        assert profile.has_bluetooth is True

    def test_scm_no_bluetooth(self):
        profile = get_hardware_profile("spotty", "scm")
        assert profile is not None
        assert profile.has_bluetooth is False

    def test_all_have_airplay(self):
        for variant in ("spotty", "mojo", "rhino"):
            for mt in ("sm2", "scm"):
                profile = get_hardware_profile(variant, mt)
                if profile:
                    assert profile.has_airplay is True

    # ── USB ports ────────────────────────────────────────────────────

    def test_st20_sm2_dual_usb(self):
        profile = get_hardware_profile("spotty", "sm2")
        assert profile is not None
        assert UsbPortType.MICRO_USB in profile.usb_ports
        assert UsbPortType.USB_A in profile.usb_ports
        assert profile.has_usb is True

    def test_bardeen_no_usb(self):
        profile = get_hardware_profile("bardeen", "sm2")
        assert profile is not None
        assert profile.usb_ports == ()
        assert profile.has_usb is False

    # ── Display ──────────────────────────────────────────────────────

    def test_st20_has_display(self):
        profile = get_hardware_profile("spotty", "sm2")
        assert profile is not None
        assert profile.has_display is True

    def test_st10_no_display(self):
        profile = get_hardware_profile("rhino", "sm2")
        assert profile is not None
        assert profile.has_display is False

    # ── Fallback: device_type ────────────────────────────────────────

    def test_fallback_by_device_type(self):
        profile = get_hardware_profile(
            variant=None,
            module_type="scm",
            device_type="SoundTouch Portable",
        )
        assert profile is not None
        assert profile.product_name == "SoundTouch Portable"

    def test_fallback_wireless_link(self):
        profile = get_hardware_profile(
            variant=None,
            module_type="sm2",
            device_type="SoundTouch Wireless Link adapter",
        )
        assert profile is not None
        assert profile.product_name == "SoundTouch Wireless Link"
        assert profile.has_bluetooth is True

    def test_unknown_variant_uses_device_type_fallback(self):
        profile = get_hardware_profile(
            variant="unknown_variant",
            module_type="sm2",
            device_type="SoundTouch Wireless Link adapter",
        )
        assert profile is not None
        assert profile.product_name == "SoundTouch Wireless Link"

    # ── Last-resort: module_type only ────────────────────────────────

    def test_last_resort_sm2(self):
        profile = get_hardware_profile(None, "sm2", "Custom Device")
        assert profile is not None
        assert profile.product_name == "Custom Device"
        assert profile.has_bluetooth is True
        assert profile.has_airplay is True

    def test_last_resort_scm(self):
        profile = get_hardware_profile(None, "scm")
        assert profile is not None
        assert profile.product_name == "Unknown SoundTouch"
        assert profile.has_bluetooth is False

    def test_last_resort_has_both_usb(self):
        profile = get_hardware_profile(None, "sm2")
        assert profile is not None
        assert UsbPortType.MICRO_USB in profile.usb_ports
        assert UsbPortType.USB_A in profile.usb_ports

    # ── None cases ───────────────────────────────────────────────────

    def test_none_variant_none_module_returns_none(self):
        assert get_hardware_profile(None, None) is None

    def test_none_module_with_variant_returns_none(self):
        assert get_hardware_profile("spotty", None) is None

    def test_unknown_everything_returns_none(self):
        assert get_hardware_profile(None, None, "Unknown") is None
