# OpenCloudTouch Raspberry Pi Image Builder

Builds ready-to-flash SD card images for Raspberry Pi 2/3/4/5.

## Supported Platforms

| Image | Architecture | Supported Models |
|-------|-------------|-----------------|
| `opencloudtouch-arm64.img.xz` | 64-bit (aarch64) | RPi 3, 4, 5 |
| `opencloudtouch-armhf.img.xz` | 32-bit (armv7l) | RPi 2, 3 (32-bit) |

## What's Included

- Raspberry Pi OS Lite (headless, no desktop)
- Docker Engine + Docker Compose v2
- OpenCloudTouch container (auto-starts on boot)
- mDNS/Avahi (`opencloudtouch.local`)
- Automatic Wi-Fi config via `oct-config.txt` on boot partition
- Automatic resize of root partition on first boot

## Usage

### Flash the Image

```bash
# Download the image for your Pi model
# RPi 3/4/5 → arm64, RPi 2 → armhf

# Using Raspberry Pi Imager (recommended):
# 1. Select "Use custom" → choose the .img.xz file
# 2. Configure hostname, SSH, Wi-Fi in advanced settings
# 3. Flash to SD card

# Or using dd (Linux/macOS):
xz -d opencloudtouch-arm64.img.xz
sudo dd if=opencloudtouch-arm64.img of=/dev/sdX bs=4M status=progress
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
2. Wait ~2-3 minutes (first boot takes longer: resize, Docker pull)
3. Access: `http://opencloudtouch.local:7777`

## Building Locally

Requires Linux (Debian/Ubuntu) or Docker.

```bash
# Build arm64 image (RPi 3/4/5)
./build.sh --arch arm64

# Build armhf image (RPi 2)
./build.sh --arch armhf

# Build both
./build.sh --arch all
```

### Build Dependencies

- Docker (for pi-gen containerized build)
- ~10 GB disk space
- ~15-30 minutes build time

## Architecture

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
└── .github/workflows/
    └── build-raspi-image.yml    # CI/CD for image builds
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
- Default password: `opencloudtouch` (change on first login!)
- Or configure SSH keys via Raspberry Pi Imager advanced settings
