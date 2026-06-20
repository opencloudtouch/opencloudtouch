# Raspberry Pi Model Compatibility Guide

This guide helps you identify your Raspberry Pi model and choose the correct OpenCloudTouch image.

## Quick Reference Table

| Model | CPU | Architecture | Recommended Image | Notes |
|-------|-----|--------------|-------------------|-------|
| **Pi 5** (all) | Cortex-A76 | ARMv8 (64-bit) | **arm64** | Best performance |
| **Pi 4 Model B** | Cortex-A72 | ARMv8 (64-bit) | **arm64** | All RAM variants (1/2/4/8 GB) |
| **Pi 3 Model B+** | Cortex-A53 | ARMv8 (64-bit) | **arm64** | Recommended, 32-bit also works |
| **Pi 3 Model B** | Cortex-A53 | ARMv8 (64-bit) | **arm64** | Recommended, 32-bit also works |
| **Pi 3 Model A+** | Cortex-A53 | ARMv8 (64-bit) | **arm64** | Recommended, 32-bit also works |
| **Pi 2 Model B v1.2** | Cortex-A53 | ARMv8 (64-bit) | **arm64** | Only v1.2! Check board revision |
| **Pi 2 Model B v1.0** | Cortex-A7 | ARMv7 (32-bit) | ✅ **armhf** | Original Pi 2, no 64-bit |
| **Pi Zero 2 W** | Cortex-A53 | ARMv8 (64-bit) | **arm64** | Smaller form factor |
| Pi Zero W | ARM1176 | ARMv6 (32-bit) | ❌ **Not supported** | CPU too old |
| Pi Zero | ARM1176 | ARMv6 (32-bit) | ❌ **Not supported** | CPU too old |
| Pi 1 Model B+/A+ | ARM1176 | ARMv6 (32-bit) | ❌ **Not supported** | CPU too old |

## Why Does Architecture Matter?

- **64-bit (arm64)**: Modern, faster, more RAM support, better software compatibility
- **32-bit (armhf)**: Older, limited to 4 GB RAM per process, less efficient
- **ARMv6**: Too old for modern Docker and OpenCloudTouch

OpenCloudTouch requires **ARMv7** (32-bit) or **ARMv8** (64-bit) minimum.

## How to Identify Your Pi Model

### Visual Identification

1. **Look at the board**: Model name is usually printed near the GPIO pins or SD card slot
   - Example: "Raspberry Pi 3 Model B V1.2"
   
2. **Check the processor chip**: Look for "BCM" marking
   - BCM2835 → Pi 1 / Pi Zero (not supported)
   - BCM2836 → Pi 2 v1.0 (armhf)
   - BCM2837 → Pi 2 v1.2 / Pi 3 (arm64)
   - BCM2711 → Pi 4 (arm64)
   - BCM2712 → Pi 5 (arm64)

3. **Count connectors**:
   - **1 HDMI port** (full-size) → Pi 2 or Pi 3
   - **2 micro-HDMI ports** → Pi 4 or Pi 5
   - **Mini HDMI** → Pi Zero family

### Software Identification

If you already have an OS running:

```bash
# Check model
cat /proc/cpuinfo | grep Model

# Check CPU architecture
uname -m
# Output: aarch64 = 64-bit, armv7l = 32-bit, armv6l = too old

# Check board revision code
cat /proc/cpuinfo | grep Revision
# Look up the revision code: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html
```

### Pi 2 Special Case: v1.0 vs v1.2

The Raspberry Pi 2 Model B has two versions:

- **v1.0** (2015): BCM2836, Cortex-A7, **32-bit only** → use **armhf** image
- **v1.2** (late 2016): BCM2837, Cortex-A53, **64-bit capable** → use **arm64** image

**How to tell them apart:**
- Check the board revision: `cat /proc/cpuinfo | grep Revision`
  - `a01041` / `a21041` → v1.0 (armhf)
  - `a02042` / `a22042` → v1.2 (arm64)
- Or check the chip marking: BCM2836 → v1.0, BCM2837 → v1.2

## Decision Tree

```
┌─ Do you have a Raspberry Pi?
│
├─ Yes → Which model?
│   │
│   ├─ Pi 5 → ✅ Use arm64 image
│   ├─ Pi 4 → ✅ Use arm64 image
│   ├─ Pi 3 → ✅ Use arm64 image (preferred) or armhf
│   ├─ Pi 2 Model B →┐
│   │                 ├─ Check revision →┐
│   │                 │                   ├─ v1.2 (2016+) → ✅ Use arm64
│   │                 │                   └─ v1.0 (2015) → ✅ Use armhf
│   │
│   ├─ Pi Zero 2 W → ✅ Use arm64 image
│   ├─ Pi Zero / Zero W → ❌ Not supported (ARMv6)
│   └─ Pi 1 (any variant) → ❌ Not supported (ARMv6)
│
└─ No → Consider x86_64 Docker deployment instead
```

## Image Selection Summary

| Your Pi | Image Filename | Flash Tool |
|---------|---------------|------------|
| Pi 5, Pi 4, Pi 3, Pi 2 v1.2, Zero 2 W | `opencloudtouch_Pi3-4-5-Zero2W_raspios-bookworm-arm64.img.xz` | Raspberry Pi Imager or Balena Etcher |
| Pi 2 v1.0 | `opencloudtouch_Pi2v1.0_raspios-bookworm-armhf.img.xz` | Raspberry Pi Imager or Balena Etcher |

## Still Unsure?

If you're not sure which image to use:

1. Try the **arm64** image first (works on all Pi 3/4/5 and Zero 2 W)
2. If the Pi doesn't boot or shows kernel panics, you likely have:
   - A Pi 2 v1.0 → try **armhf** instead
   - A Pi 1 / Pi Zero (old) → not supported, need a newer Pi

## Additional Resources

- [Official Raspberry Pi Model Comparison](https://www.raspberrypi.com/products/)
- [Board Revision Codes](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-revision-codes)
- [OpenCloudTouch Raspi Releases](https://github.com/opencloudtouch/opencloudtouch-infra/releases)

## Recommendations

- **Best value for OpenCloudTouch**: Raspberry Pi 4 (2 GB or 4 GB)
- **Budget option**: Raspberry Pi 3 Model B+ (if you already have one)
- **Latest & greatest**: Raspberry Pi 5 (overkill but works perfectly)
- **Compact**: Pi Zero 2 W (if space is tight, but slower performance)
