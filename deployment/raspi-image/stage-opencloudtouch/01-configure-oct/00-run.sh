#!/bin/bash -e
# ============================================================================
# Stage: Configure OpenCloudTouch
# ============================================================================
# Sets up the OCT Docker Compose deployment, systemd services,
# firstboot script, and update helper.

on_chroot << 'CHROOT'

# ==== Create OCT directory structure ====
mkdir -p /opt/opencloudtouch
mkdir -p /opt/opencloudtouch/data
chown -R oct:oct /opt/opencloudtouch

CHROOT

# ==== Copy files into the image ====
# docker-compose.yml
install -m 644 files/docker-compose.yml "${ROOTFS_DIR}/opt/opencloudtouch/docker-compose.yml"

# Firstboot script
install -m 755 files/oct-firstboot.sh "${ROOTFS_DIR}/opt/opencloudtouch/oct-firstboot.sh"

# Update script
install -m 755 files/oct-update.sh "${ROOTFS_DIR}/opt/opencloudtouch/oct-update.sh"

# Firstboot systemd service
install -m 644 files/oct-firstboot.service "${ROOTFS_DIR}/etc/systemd/system/oct-firstboot.service"

# Config template on boot partition
install -m 644 files/oct-config.txt "${ROOTFS_DIR}/boot/firmware/oct-config.txt"

on_chroot << 'CHROOT'

# ==== Enable systemd services ====

# Create OCT systemd service (starts Docker Compose)
cat > /etc/systemd/system/opencloudtouch.service << 'SERVICE'
[Unit]
Description=OpenCloudTouch
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/opencloudtouch
ExecStartPre=/usr/bin/docker compose pull --quiet
ExecStart=/usr/bin/docker compose up --remove-orphans
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SERVICE

# Enable OCT service (starts on every boot)
systemctl enable opencloudtouch.service

# Enable firstboot service (runs once, then disables itself)
systemctl enable oct-firstboot.service

# ==== Configure system for appliance mode ====

# Reduce boot time: disable unnecessary services
systemctl disable apt-daily.service 2>/dev/null || true
systemctl disable apt-daily.timer 2>/dev/null || true
systemctl disable apt-daily-upgrade.service 2>/dev/null || true
systemctl disable apt-daily-upgrade.timer 2>/dev/null || true

# Enable hardware watchdog (auto-reboot on hang)
if [ -f /etc/systemd/system.conf ]; then
    sed -i 's/#RuntimeWatchdogSec=.*/RuntimeWatchdogSec=15/' /etc/systemd/system.conf
fi

# ==== Optimize for SD card longevity ====
# Reduce writes: tmpfs for logs and tmp
cat >> /etc/fstab << 'FSTAB'
# SD card optimization: tmpfs for high-write directories
tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=100M 0 0
tmpfs /var/log tmpfs defaults,noatime,nosuid,nodev,size=50M 0 0
FSTAB

# ==== Set MOTD ====
cat > /etc/motd << 'MOTD'

  ╔═══════════════════════════════════════════╗
  ║         OpenCloudTouch Appliance          ║
  ╠═══════════════════════════════════════════╣
  ║  Web UI: http://opencloudtouch.local:7777 ║
  ║  Update: sudo /opt/opencloudtouch/        ║
  ║          oct-update.sh                    ║
  ║  Docs:   https://github.com/opencloudtouch/ ║
  ║          opencloudtouch/wiki              ║
  ╚═══════════════════════════════════════════╝

MOTD

echo "[OK] OpenCloudTouch configured"

CHROOT
