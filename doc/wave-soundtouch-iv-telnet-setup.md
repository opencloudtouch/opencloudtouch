# Wave SoundTouch IV — Telnet Port 17000 Setup Guide

**Status:** ✅ Community-Verified (SoundCork Issue #309)  
**Applies to:** Bose Wave SoundTouch IV (sm2 firmware 27.0.6, 15.x, 9.x)  
**Alternative to:** USB provisioning (not supported on Wave IV)

---

## Overview

The **Wave SoundTouch IV** does not support USB provisioning via the standard `remote_services` method. However, it provides **Telnet access on port 17000** with a sufficient command set to configure OpenCloudTouch server URLs.

This method is **simpler than the Service Port serial cable** and requires no hardware modification or device disassembly.

### Community Success

- ✅ **@akpdw** (SoundCork): Provided working command syntax
- ✅ **@jakovasaur** (SoundCork): Confirmed all commands working on firmware 27.0.6
- ✅ **@pointy56** (SoundCork): Verified Telnet 17000 + Service Port serial methods
- ✅ Multiple OpenCloudTouch community members (testing in progress)

---

## Prerequisites

- Wave SoundTouch IV connected to your local network
- IP address of your Wave device (check your router or Bose SoundTouch app)
- OpenCloudTouch server running and reachable from Wave device
- Telnet client (built-in on Windows 10+, macOS, Linux)

---

## Step 1: Enable Telnet (Windows Only)

If you're on **Windows 10/11**, Telnet might be disabled by default.

**Enable it:**
1. Open **Control Panel** → **Programs** → **Turn Windows features on or off**
2. Check **Telnet Client**
3. Click **OK** and wait for installation

**Alternative:** Use **PuTTY** (download from [putty.org](https://www.putty.org/))

---

## Step 2: Connect to Wave via Telnet

Open a terminal (Command Prompt, PowerShell, macOS Terminal, or Linux shell) and connect:

```bash
telnet <wave-ip-address> 17000
```

**Example:**
```bash
telnet 192.168.1.100 17000
```

**Expected output:**
```
Trying 192.168.1.100...
Connected to 192.168.1.100.
Escape character is '^]'.
```

**⚠️ Note:** The prompt is invisible — just type commands and press Enter.

---

## Step 3: Configure OpenCloudTouch URLs

**⚠️ CRITICAL:** Type commands carefully. Telnet has **no prompt feedback** — just type and press Enter.

Copy-paste the commands below ONE BY ONE, replacing `<oct-server>` with your server's hostname or IP.

### Example: Using hostname `opencloudtouch.local`

```bash
sys configuration bmxRegistryUrl http://opencloudtouch.local:8080/bmx/registry/v1/services
sys configuration margeServerUrl http://opencloudtouch.local:8080/marge
sys configuration statsServerUrl http://opencloudtouch.local:8080
sys configuration swUpdateUrl http://opencloudtouch.local:8080/updates/soundtouch
envswitch boseurls set http://opencloudtouch.local:8080/marge http://opencloudtouch.local:8080/updates/soundtouch
```

### Example: Using IP address `192.168.1.50`

```bash
sys configuration bmxRegistryUrl http://192.168.1.50:8080/bmx/registry/v1/services
sys configuration margeServerUrl http://192.168.1.50:8080/marge
sys configuration statsServerUrl http://192.168.1.50:8080
sys configuration swUpdateUrl http://192.168.1.50:8080/updates/soundtouch
envswitch boseurls set http://192.168.1.50:8080/marge http://192.168.1.50:8080/updates/soundtouch
```

**⚠️ Important Notes:**
- Use **`http://`** (not `https://`)
- Include the **port number** (default OCT: `8080`, default SoundCork: `8000`)
- Wave IV firmware does **NOT** support TLS/HTTPS on these endpoints
- `.home` TLD may cause issues — prefer `.local` or IP addresses

---

## Step 4: Verify Configuration

Before rebooting, verify that URLs were applied correctly:

```bash
getpdo CurrentSystemConfiguration
```

**Expected output:**
```xml
<CurrentSystemConfiguration>
  <bmxRegistryUrl>http://opencloudtouch.local:8080/bmx/registry/v1/services</bmxRegistryUrl>
  <margeServerUrl>http://opencloudtouch.local:8080/marge</margeServerUrl>
  ...
</CurrentSystemConfiguration>
```

**✅ If URLs match:** Proceed to reboot.  
**❌ If URLs are wrong:** Re-run the `sys configuration` commands.

---

## Step 5: Reboot Wave

```bash
sys reboot
```

**What happens:**
- Telnet connection will close
- Wave reboots (takes ~60 seconds)
- After reboot, Wave will contact OpenCloudTouch server instead of Bose cloud

---

## Step 6: Verify in OpenCloudTouch

1. Open OpenCloudTouch web interface: `http://<oct-server>:8080`
2. Navigate to **Devices**
3. Your Wave SoundTouch IV should appear with status **Online**

**If device does NOT appear:**
- Check that OCT server is reachable from Wave's network
- Check OCT logs: `docker logs opencloudtouch-backend -f`
- Reconnect via Telnet and verify URLs with `getpdo CurrentSystemConfiguration`

---

## Troubleshooting

### Cannot connect via Telnet

**Symptom:** `Connection refused` or `Unable to connect`

**Solutions:**
1. Verify Wave is powered on and connected to network
2. Verify IP address is correct (ping the Wave: `ping <wave-ip>`)
3. Check firewall rules on your computer (allow outgoing Telnet port 17000)
4. Try from a different device (macOS/Linux if Windows fails)

### Commands not working

**Symptom:** `Command not found` or no response

**Root Cause:** Limited command set in older firmware versions

**Solutions:**

1. **Check current firmware:**
   - Bose SoundTouch app → Device Settings → About
   - Expected: **27.0.6** (latest official version)

2. **Firmware update via Micro-USB:**
   - Download Wave IV firmware from [archive.org/details/bose-soundtouch-software-and-firmware](https://archive.org/details/bose-soundtouch-software-and-firmware)
   - File: `bose-wave-soundtouch-27.0.6.bin`
   - Connect Wave via Micro-USB cable to computer
   - Open browser: `http://203.0.113.1:17008/update.html`
   - Upload `.bin` file
   - Wait 10-15 minutes (LED blinks during update)

3. **Factory reset before firmware update (if needed):**
   - Unplug power
   - Hold **Preset 1 + Volume Down**
   - Plug power while holding buttons
   - Release when LED blinks rapidly (10-15 seconds)
   - Wait 2-3 minutes for reset to complete

**⚠️ Warning:** Factory reset erases all presets, network settings, and zones

### Wave still contacts Bose cloud after reboot

**Symptom:** Presets don't work, OCT shows device offline

**Solutions:**
1. Reconnect via Telnet and verify URLs: `getpdo CurrentSystemConfiguration`
2. If URLs are correct but Wave ignores them: Try **factory reset** then repeat setup
3. Factory reset: Hold Wi-Fi button while plugging power cable until LED blinks (2-3 minutes)

---

## Limitations

### What works:
- ✅ TuneIn presets (via OpenCloudTouch)
- ✅ Multi-room zones
- ✅ WebSocket updates
- ✅ Device control via OCT web UI
- ✅ Spotify Connect (if configured)

### What does NOT work:
- ❌ SSH access (Wave IV does not support SSH via USB or Telnet)
- ❌ Advanced diagnostics (limited Telnet command set)
- ❌ File system access (read-only via Telnet)

---

## Advanced: Service Port Serial Cable Alternative

If Telnet port 17000 does not work (rare, but possible on very old firmware), you can use the **Service Port** (3.5mm jack) with a serial UART adapter.

**Note on naming:** This port is sometimes referred to as "ETAP" in older community write-ups. That name comes from Bose's service manual, where it labels a *different* connector — the Wave IV's Service Port is a standard 3-pole (TRS) jack, not the 4-pole connector the "ETAP" name implies.

### Hardware Requirements

- **FTDI USB-UART adapter** (e.g., CP2102, FT232RL), 3.3V
- **3.5mm TRS cable** (3-conductor: Tip-Ring-Sleeve)
- **Pinout:** Tip=RX, Ring=TX, Sleeve=GND
- No signal inversion needed with a standard FTDI FT232RL breakout board at 3.3V (confirmed by @dl9sec)

### Serial Settings

- Baud rate: **115200**
- Data bits: **8**
- Parity: **None**
- Stop bits: **1**
- Flow control: **None**

### UBoot Access Method

1. Connect serial cable to Wave's Service Port (3.5mm jack on pedestal)
2. Open terminal (PuTTY, screen, minicom) with settings above
3. Boot Wave and watch serial output
4. Press **Shift+U** when "Autoboot in 1 seconds..." appears
5. UBoot prompt: `=>` appears
6. Enable remote_services:
   ```bash
   setenv optargs init=/bin/sh
   setenv rootfs_perms rw
   run nand_boot  # or run nand_boot2 depending on kernel
   ```
7. At shell prompt `sh-3.2#`:
   ```bash
   touch /etc/remote_services
   reboot -f
   ```

**Detailed step-by-step guide:** [SoundCork Issue #309](https://github.com/deborahgu/soundcork/issues/309) by @pointy56

**When to use this:**
- Telnet port 17000 not available (check with `telnet <ip> 17000`)
- Very old firmware (pre-9.x) without Telnet support
- Advanced troubleshooting or bootloop recovery

---

## Community Success Stories

- **@pointy56** (SoundCork #309): Successfully enabled SSH via the Service Port, then used Telnet 17000 for config
- **@jakovasaur** (SoundCork #309): Confirmed all Telnet commands working on Wave IV firmware 27.0.6
- **@akpdw** (SoundCork #309): Provided command syntax for SoundCork (compatible with OCT)
- **@dl9sec**: Confirmed the Service Port pinout and that a standard FT232RL breakout board at 3.3V needs no signal inversion

---

## Next Steps

1. ✅ **Set up your Wave via Telnet** (this guide)
2. ⏳ **Wait for OpenCloudTouch v1.5.2** (Telnet auto-config in wizard)
3. 🚀 **Test presets and multi-room** (report issues on GitHub)

---

## Feedback

This setup method is **experimental**. If you encounter issues or have improvements:
- Open an issue: [github.com/opencloudtouch/opencloudtouch/issues](https://github.com/opencloudtouch/opencloudtouch/issues)
- Join the discussion: [github.com/opencloudtouch/opencloudtouch/discussions](https://github.com/opencloudtouch/opencloudtouch/discussions)

**Testing Wave IV Telnet support is tracked in Issue #352.**

---

**Last updated:** 2026-06-10  
**Tested on:** Wave SoundTouch IV (sm2), firmware 27.0.6
