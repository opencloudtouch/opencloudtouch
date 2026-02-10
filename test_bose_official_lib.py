#!/usr/bin/env python3
"""Test official bosesoundtouchapi discovery."""
import sys
from bosesoundtouchapi import soundtouch_device

print("=" * 70)
print("Testing bosesoundtouchapi.soundtouch_device.discover_devices()")
print("(Official Bose library)")
print("=" * 70)

try:
    print("\nSearching for devices (timeout: 10s)...\n")
    devices = soundtouch_device.discover_devices(timeout=10)

    print(f"\n{'='*70}")
    print(f"RESULT: Found {len(devices)} device(s)")
    print('='*70)

    if len(devices) > 0:
        print("\nDevices found:")
        for device in devices:
            print(f"  ✅ {device.config.name} ({device.config.type}) at {device.config.host}")
        print(f"\n✅ Official Bose library WORKS! Found {len(devices)} devices")
        sys.exit(0)
    else:
        print("\n❌ Official Bose library also finds NOTHING!")
        print("This confirms: SSDP/UPnP discovery is broken for Bose devices")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(2)
