# Device Access — SSH, Telnet, and Filesystem

How to gain root access to a SoundTouch device for configuration, backup, and migration.

## Prerequisites

- Bose SoundTouch device (ST10, ST20, ST30, etc.)
- USB stick (any size)
- Network access to device

---

## Enabling Remote Access

### Step 1: Prepare USB Drive
On your computer, create an empty file in the USB root:
```bash
touch /path/to/mounted/usb/remote_services
```
The file must be named exactly `remote_services` — just its existence triggers SSH/Telnet.

### Step 2: Insert and Reboot
1. Insert USB stick into the SoundTouch device
2. Power-cycle the device (unplug power, wait 5 seconds, plug back in)
3. Wait for boot to complete (~60 seconds)

### Step 3: Connect via SSH or Telnet

#### SSH (preferred)
```bash
ssh -oHostKeyAlgorithms=ssh-rsa root@<device-ip>
```
- **No password required** for root
- Must specify `-oHostKeyAlgorithms=ssh-rsa` (device uses old RSA keys)

#### Telnet (via Docker if no client installed)
```bash
docker run --rm -it alpine:edge ash -c 'apk add -U inetutils-telnet && telnet <device-ip> 23'
```
- Login: `root` (no password)

### Example Output
```
... --- ..- -. -.. - --- ..- -.-. ....

        ____  ____  _____ _________
       / __ )/ __ \/ ___// _______/
      / __  / / / /\__ \/  __/
 ____/ /_/ / /_/ /___/ / /___
/_________/\____//____/_____/

Device name: "A Sound Machine"
Country EU, Region (not set)
Module type: scm
root@spotty:~#
```

---

## Device Filesystem Structure

### Key Directories

| Path | Purpose |
|------|---------|
| `/opt/Bose/` | Main application directory |
| `/opt/Bose/BoseApp` | Main application binary (ARM ELF) |
| `/opt/Bose/IoT` | IoT service binary |
| `/opt/Bose/lib/` | Shared libraries (incl. `libBmxAccountHsm.so`) |
| `/opt/Bose/etc/` | Configuration files |
| `/mnt/nv/` | Non-volatile persistent storage |
| `/mnt/nv/BoseApp-Persistence/1/` | App data (presets, sources, config) |
| `/mnt/nv/IoTCerts/` | IoT certificates and keys |
| `/mnt/nv/BoseLog/` | Device logs |
| `/etc/pki/tls/certs/` | System trust store |

### Configuration Files

| File | Purpose |
|------|---------|
| `/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml` | Cloud service URLs (Marge, stats, updates, BMX) |
| `/opt/Bose/etc/Voice.xml` | Voice/Alexa configuration |
| `/opt/Bose/etc/Shepherd-noncore.xml` | Service daemon configuration |
| `/opt/Bose/etc/HandCraftedWebServer-SoundTouch.xml` | Internal API mapping |
| `/mnt/nv/BoseApp-Persistence/1/IoT.xml` | AWS IoT configuration |
| `/mnt/nv/BoseApp-Persistence/1/Sources.xml` | Registered music sources |

---

## Step 4: View Current Configuration

```bash
cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml
```

Note the URLs for:
- `margeServerUrl` — streaming/account
- `statsServerUrl` — telemetry
- `swUpdateUrl` — firmware updates
- `bmxRegistryUrl` — content registry

---

## Backup Before Modification

Always backup before changing anything:
```bash
cp /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml.bak
cp /etc/hosts /etc/hosts.bak
```

For full device backup:
```bash
# Copy key files to USB or via scp
scp root@<device-ip>:/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml ./backup/
scp root@<device-ip>:/mnt/nv/BoseApp-Persistence/1/IoT.xml ./backup/
scp root@<device-ip>:/mnt/nv/BoseApp-Persistence/1/Sources.xml ./backup/
scp root@<device-ip>:/mnt/nv/IoTCerts/* ./backup/certs/
```

---

## Partition Layout (ST10, Firmware 27.x)

The flash storage uses UBI with three partitions:

| Partition | Mount Point | Size | Access | Contents |
|-----------|-------------|------|--------|----------|
| `ubi0:rootfs` | `/` | ~81.4 MB | Read-only (default) | System binaries, Bose app, config |
| `ubi1:persistent` | `/mnt/nv` | ~31.5 MB | Read-write | Presets, tokens, WiFi config, logs |
| `ubi2:update` | `/mnt/update` | ~7.9 MB | Read-write | Firmware installer cache |

The root filesystem is mounted read-only during normal operation. To write to it:
```bash
rw || mount -o remount,rw /
# ... make changes ...
mount -o remount,ro /
```
The `rw` shortcut exists on some firmware versions; `mount -o remount,rw /` is the universal fallback.

---

## Filesystem Notes

- Root filesystem is typically **read-only**
- To make writable: `mount -o remount,rw /` or the `rw` command (if available)
- `/mnt/nv/` is persistent non-volatile storage (survives reboots)
- `/opt/Bose/` may be overwritten by firmware updates
- Private keys in `/mnt/nv/IoTCerts/` should be stored with mode 700

---

## Restore Procedure

If something goes wrong, restore from the OCT wizard backups on your USB stick
(`/media/sda1/oct-backup/`). Full details and step-by-step instructions are in
the [FAQ — Backup & Restore](FAQ.md#how-do-i-restore-a-full-backup).

### Quick Restore (config only)

Reverts only the cloud URL and DNS changes made by OCT:
```bash
rw || mount -o remount,rw /
cp /media/sda1/oct-backup/SoundTouchSdkPrivateCfg.xml.bak /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml
cp /media/sda1/oct-backup/hosts.bak /etc/hosts
mount -o remount,ro /
reboot
```

### Full Partition Restore

Restores all three partitions from the tar archives created by the OCT wizard:
```bash
# Persistent data (already writable)
cd / && tar xzf /media/sda1/oct-backup/soundtouch-nv.tgz
tar xzf /media/sda1/oct-backup/soundtouch-update.tgz

# Root filesystem (needs remount)
rw || mount -o remount,rw /
cd / && tar xzf /media/sda1/oct-backup/soundtouch-rootfs.tgz
mount -o remount,ro /

reboot
```

> The OCT web UI (Setup Wizard Step 8) can do the quick config restore automatically.
> Full partition restore is manual SSH only.

---

## Extracting Certificates for Analysis

```bash
# Copy device certificate (for IoT/MQTT research)
scp root@<device-ip>:/mnt/nv/IoTCerts/iot-cert.pem.crt ./
scp root@<device-ip>:/mnt/nv/IoTCerts/iot-private.pem.key ./
scp root@<device-ip>:/var/lib/iot/rootCA.crt ./

# View system trust store
ssh root@<device-ip> "cat /etc/pki/tls/certs/ca-bundle.crt | head -50"
```

---

## Important Warnings

1. **Don't brick your device** — always backup before modifying binaries
2. **Firmware updates** may reset config files in `/opt/Bose/etc/`
3. **Persistent storage** `/mnt/nv/` usually survives updates
4. **The `remote_services` USB trigger** only needs to be done once per boot
5. **Keep your firmware version noted** — different versions have different behaviors
