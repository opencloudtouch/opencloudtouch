# Frequently Asked Questions

Common questions from the OCT community, answered in one place.

---

## Backup & Restore

### What does the OCT setup wizard back up?

During the setup wizard, OCT creates full partition-level backups on the USB stick
plugged into your SoundTouch device. You'll find them in `/media/sda1/oct-backup/`:

| File | Contents | Typical Size |
|------|----------|-------------|
| `soundtouch-rootfs.tgz` | Complete root filesystem (`/`) — system binaries, Bose app, config | ~58 MB |
| `soundtouch-nv.tgz` | Persistent storage (`/mnt/nv`) — presets, tokens, WiFi config | ~10 KB |
| `soundtouch-update.tgz` | Firmware update cache (`/mnt/update`) — installer staging area | ~0.9 MB |

On top of those archives, the wizard also saves individual config files as `.bak`:

- `SoundTouchSdkPrivateCfg.xml.bak` — the cloud URL config (most important one)
- `hosts.bak` — the DNS override file

### Which partition is which?

SoundTouch devices (ST10, firmware 27.x) use a UBI flash layout with three partitions:

| Partition | Mount Point | Size | Access |
|-----------|-------------|------|--------|
| `ubi0:rootfs` | `/` | ~81.4 MB | Read-only (default) |
| `ubi1:persistent` | `/mnt/nv` | ~31.5 MB | Read-write |
| `ubi2:update` | `/mnt/update` | ~7.9 MB | Read-write |

The root filesystem is mounted read-only during normal operation. You need to
explicitly remount it before writing — see the restore steps below.

### How do I restore a full backup?

> **Prerequisites**: SSH access enabled (USB stick with `remote_services` file, see
> [30-device-access.md](30-device-access.md#enabling-remote-access)), backup files
> present on USB stick.

**Step 1 — SSH into the device:**
```bash
ssh -oHostKeyAlgorithms=ssh-rsa root@<SPEAKER-IP>
```

**Step 2 — Verify USB is mounted:**
```bash
grep '/media/' /proc/mounts
```
You should see something like `/dev/sda1 /media/sda1 vfat ...`. If nothing shows up,
unplug and re-insert the USB stick, then check again.

**Step 3 — Restore `/mnt/nv` (persistent data):**
```bash
cd / && tar xzf /media/sda1/oct-backup/soundtouch-nv.tgz
```
This partition is already writable — no remount needed.

**Step 4 — Restore `/mnt/update` (firmware cache):**
```bash
tar xzf /media/sda1/oct-backup/soundtouch-update.tgz
```
Also writable by default.

**Step 5 — Restore rootfs (system partition):**
```bash
# Make root filesystem writable
rw || mount -o remount,rw /

# Extract the backup
cd / && tar xzf /media/sda1/oct-backup/soundtouch-rootfs.tgz

# Lock it back down
mount -o remount,ro /
```

> The `rw` shortcut exists on some firmware versions. If it fails, `mount -o remount,rw /`
> is the universal fallback. Always remount read-only afterwards to protect against
> accidental writes.

**Step 6 — Reboot:**
```bash
reboot
```

The device restarts with original factory files. Your presets, WiFi config, and
cloud tokens are back as they were before OCT setup.

### I just want to undo the OCT config changes — do I need a full restore?

No. If you only want to revert the config file edits that OCT made (cloud URLs and
DNS overrides), a quick config restore is enough:

```bash
# Make root filesystem writable
rw || mount -o remount,rw /

# Restore original config files from individual backups
cp /media/sda1/oct-backup/SoundTouchSdkPrivateCfg.xml.bak \
   /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml
cp /media/sda1/oct-backup/hosts.bak /etc/hosts

# Lock it back down
mount -o remount,ro /

# Reboot to apply
reboot
```

After reboot, the device points back to the original Bose cloud servers.

### Can I restore from the OCT web UI?

Partially. The Setup Wizard (Step 8) offers config and hosts restore buttons that
handle the quick restore automatically. But full partition-level restore (rootfs,
persistent storage, firmware cache) is manual SSH only — the web UI doesn't
support extracting tar archives onto the device.

### What if I lost my USB stick / backups?

Without backups, your options are limited:

1. **Factory reset** via the device's physical buttons (refer to Bose support docs
   for your model). This resets presets and WiFi config but keeps the firmware.
2. **Manual config editing** — if you know what OCT changed, you can manually
   revert the XML config and `/etc/hosts` entries. See
   [11-device-redirect-methods.md](11-device-redirect-methods.md) for the redirect
   mechanics.

---

*More questions? Open an issue on [GitHub](https://github.com/scheilch/opencloudtouch/issues).*
