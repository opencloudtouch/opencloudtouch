# OpenCloudTouch Raspberry Pi Image Builder

Builds ready-to-flash SD card images for Raspberry Pi 2/3/4/5.

## Supported Platforms

| Image | Architecture | Supported Models |
|-------|-------------|-----------------|
| `opencloudtouch_Pi3-4-5-Zero2W_raspios-bookworm-arm64.img.xz` | 64-bit (aarch64) | **RPi 3, 4, 5, Zero 2 W, Pi 2 v1.2** |
| `opencloudtouch_Pi2v1.0_raspios-bookworm-armhf.img.xz` | 32-bit (armv7l) | **RPi 2 Model B v1.0 only** |

> **Note:** Pi 3 is 64-bit capable — use **arm64** for better performance. Pi 2 Model B has two versions: v1.0 (32-bit) and v1.2 (64-bit). See [MODEL-GUIDE.md](./MODEL-GUIDE.md) for detailed identification instructions.
>
> **Not supported:** Raspberry Pi 1, Pi Zero, Pi Zero W (ARMv6 architecture — too old for Docker)

## What's Included

- Raspberry Pi OS Lite (headless, no desktop)
- Docker Engine + Docker Compose v2
- OpenCloudTouch container (auto-starts on boot)
- mDNS/Avahi (`opencloudtouch.local`)
- Automatic Wi-Fi config via `oct-config.txt` on boot partition
- **Automatic filesystem expansion** on first boot (expands root partition to full SD card capacity)

## Usage

### Flash the Image

```bash
# Download the image for your Pi model
# RPi 3/4/5 → arm64, RPi 2 → armhf

# Using Raspberry Pi Imager (recommended):
# 1. Select "Use custom" → choose the .img.xz file
# 2. Configure hostname, SSH, Wi-Fi in advanced settings
# 3. Flash to SD card

# Using Balena Etcher:
# 1. Select the .img.xz file (no need to extract)
# 2. Select your SD card
# 3. Flash
```

### Wi-Fi Configuration (Headless)

After flashing, mount the boot partition and edit `oct-config.txt`:

```ini
# oct-config.txt — OpenCloudTouch Configuration
WIFI_SSID=MyNetwork
WIFI_PASSWORD=MyPassword
WIFI_COUNTRY=DE
OCT_PORT=7777
```

### First Boot

1. Insert SD card, connect power
2. Wait ~3-10 minutes (first boot: partition resize, Docker pull, container start) - On slow networks this can take longer; keep power connected and watch the boot screen/logs.
3. Access: `http://opencloudtouch.local:7777`
4. SSH: `ssh oct@opencloudtouch.local` (password: `opencloudtouch`)

**Note:** The system will automatically reboot once during first boot to complete filesystem expansion. This is normal and expected.

## Building Locally

Requires Linux (Debian/Ubuntu) or Docker.

```bash
# Build arm64 image (RPi 3/4/5)
./build.sh --arch arm64

# Build armhf image (RPi 2 Model B v1.0 only)
./build.sh --arch armhf

# Build both
./build.sh --arch all
```

### Build Dependencies

- Docker (for pi-gen containerized build)
- ~10 GB disk space
- ~15-30 minutes build time

## Project Structure

```
raspi-image/
├── build.sh                     # Main build entry point
├── config                       # pi-gen configuration
├── stage-opencloudtouch/        # Custom pi-gen stage
│   ├── 00-install-packages/     # System packages (Docker, avahi)
│   ├── 01-configure-oct/        # OCT Docker setup + systemd services
│   └── 02-finalize/             # Cleanup + firstboot setup
├── files/                       # Files to embed in the image
│   ├── docker-compose.yml       # Production compose file
│   ├── oct-firstboot.sh         # First-boot script
│   ├── oct-firstboot.service    # systemd service for firstboot
│   ├── oct-update.sh            # Update helper script
│   └── oct-config.txt           # User config template
└── MODEL-GUIDE.md               # Pi model identification guide
```

## CI/CD

Images are built automatically via GitHub Actions:
- **On release**: Both arm64 and armhf images are built and attached to the GitHub Release
- **Manual**: Trigger via `workflow_dispatch`

## Customization

### Environment Variables

All `OCT_*` variables from the main project are supported. Set them in
`/opt/opencloudtouch/docker-compose.yml` on the running Pi, or in `oct-config.txt`
on the boot partition before first boot.

### SSH Access

SSH is enabled by default:
- User: `oct`
- Default password: `opencloudtouch`
- Or use SSH key authentication for better security
- Or configure SSH keys via Raspberry Pi Imager advanced settings

## Troubleshooting

### Filesystem Not Expanding

**Symptom:** Docker fails to pull the image with "no space left on device" error.

**Cause:** Filesystem expansion failed or didn't run.

**Solution:**
1. SSH into the Pi: `ssh oct@opencloudtouch.local`
2. Check if expansion ran: `ls -l /var/lib/oct-expanded`
   - If file exists: expansion completed successfully
   - If missing: expansion didn't run or failed
3. Check expansion logs: `journalctl -u oct-expand-fs.service`
4. Manual expansion:
   ```bash
   sudo raspi-config --expand-rootfs nonint
   sudo reboot
   ```
5. Verify disk space after reboot: `df -h /`

### Service Status Checks

```bash
# Check if filesystem expansion completed
systemctl status oct-expand-fs.service

# Check if firstboot ran
systemctl status oct-firstboot.service

# Check if OCT is running
systemctl status opencloudtouch.service
docker compose -f /opt/opencloudtouch/docker-compose.yml ps

# View logs
journalctl -u oct-expand-fs.service -n 50
journalctl -u oct-firstboot.service -n 50
journalctl -u opencloudtouch.service -n 50
```

### First Boot Takes Too Long

**Expected timeline:**
- 1-2 minutes: Filesystem expansion + reboot
- 2-3 minutes: Wi-Fi config, Docker pull, service start
- **Total: 3-4 minutes**

If it takes longer:
- Check network: `ping 8.8.8.8`
- Check Docker pull progress: `docker compose -f /opt/opencloudtouch/docker-compose.yml logs`
- Check if image was pre-loaded: `docker images | grep opencloudtouch`
