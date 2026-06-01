# UPGRADING.md

# OpenCloudTouch Upgrade Guide

This guide explains how to upgrade OpenCloudTouch deployments. It covers Docker-based setups, Raspberry Pi images, breaking changes, database migrations, and troubleshooting.

---

## 1. Upgrade with Docker

**Recommended for most users.**

### Steps

1. **Pull the latest stable image:**
   ```sh
   docker pull ghcr.io/opencloudtouch/opencloudtouch:stable
   ```
2. **Restart with Docker Compose:**
   ```sh
   docker compose up -d
   ```
   *If you use a custom compose file, adjust the path accordingly.*

3. **Verify the update:**
   ```sh
   docker compose ps
   docker logs <container_name>
   ```

**Note:** Your data in `/data` (or the configured volume) is preserved.

---

## 2. Upgrade with Raspberry Pi Image

**For users running OpenCloudTouch directly on a Raspberry Pi.**

### Steps

1. **Backup your data:**
   - All persistent data is stored in `/data` on the SD card.
   - Copy `/data` to a safe location:
     ```sh
     sudo cp -r /data /mnt/backup/
     ```
2. **Flash the new image:**
   - Download the latest `.img` file from the [releases page](https://github.com/opencloudtouch/opencloudtouch/releases).
   - Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) or `dd` to flash the SD card.
3. **Restore the SD card:**
   - After flashing, insert the SD card and boot.
   - The `/data` partition will be preserved if you did not overwrite it. If you wiped the card, copy your backup back to `/data`.

**Tip:** Never overwrite `/data` unless you want a clean start.

---

## 3. Breaking Changes by Major Version

**Always read this section before upgrading across major versions.**

| Version | Breaking Changes |
|---------|-----------------|
| 2.x     | - Device config format changed (see `docs/bose-config-files.md`)
           - API endpoint `/api/v1/preset` removed, use `/api/v2/preset` |
| 1.x     | - Initial release, no breaking changes |

*See the [CHANGELOG.md](CHANGELOG.md) for full details.*

---

## 4. Database Migrations

- **Alembic** handles all schema migrations automatically on startup (Docker and Pi).
- No manual steps required for standard upgrades.
- If you see migration errors, check container logs or `journalctl -u opencloudtouch` (on Pi).

---

## 5. Troubleshooting

### Common Issues

#### 1. Container fails to start after upgrade
- **Check logs:**
  ```sh
  docker logs <container_name>
  ```
- **Possible causes:**
  - Port already in use
  - Invalid config file (see `docs/bose-config-files.md`)
  - Database migration failed

#### 2. Data missing after upgrade
- **Check if `/data` is mounted correctly.**
- **Restore from backup if needed.**

#### 3. Alembic migration errors
- **Solution:**
  - Remove `alembic_version` table only if you know what you are doing.
  - Restore from backup if unsure.

#### 4. Web UI not reachable
- **Check container/network status:**
  ```sh
  docker compose ps
  docker network ls
  ```
- **Check firewall settings.**

---

For further help, see the [FAQ](doc/FAQ.md) or open an issue on GitHub.
