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
ExecStartPre=-/bin/sh -c 'timeout 30 /usr/bin/docker compose pull --quiet 2>/dev/null || true'
ExecStart=/usr/bin/docker compose up --remove-orphans
ExecStop=/usr/bin/docker compose down
Restart=always
RestartSec=10
TimeoutStartSec=300
PrivateTmp=yes
NoNewPrivileges=yes

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
    sed -i 's/^#\?RuntimeWatchdogSec=.*/RuntimeWatchdogSec=15/' /etc/systemd/system.conf
fi

# ==== Optimize for SD card longevity ====
# Reduce writes: tmpfs for logs and tmp
cat >> /etc/fstab << 'FSTAB'
# SD card optimization: tmpfs for high-write directories
tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=100M 0 0
tmpfs /var/log tmpfs defaults,noatime,nosuid,nodev,size=50M 0 0
FSTAB

# ==== OCT Log Buffering (SD-card friendly) ====
# OCT logs are written to tmpfs and synced to SD every 4 hours.
# On boot: restore last logs from SD → tmpfs.
# On shutdown: flush tmpfs → SD.
# This reduces SD writes from continuous to ~6x/day.

mkdir -p /opt/opencloudtouch/logs-persistent

cat > /usr/local/bin/oct-log-sync << 'LOGSYNC'
#!/bin/bash
# Sync OCT logs from tmpfs to persistent SD storage
LOG_TMP="/opt/opencloudtouch/logs"
LOG_SD="/opt/opencloudtouch/logs-persistent"
mkdir -p "$LOG_TMP" "$LOG_SD"
rsync -a --delete "$LOG_TMP/" "$LOG_SD/"
LOGSYNC
chmod +x /usr/local/bin/oct-log-sync

# tmpfs mount for OCT logs (50MB, sufficient for days of buffered logs)
cat >> /etc/fstab << 'FSTAB2'
tmpfs /opt/opencloudtouch/logs tmpfs defaults,noatime,nosuid,nodev,size=50M,uid=1000,gid=1000 0 0
FSTAB2

# Restore logs from SD on boot (before OCT starts)
cat > /etc/systemd/system/oct-log-restore.service << 'RESTORE'
[Unit]
Description=Restore OCT logs from SD to tmpfs
After=local-fs.target
Before=opencloudtouch.service oct-firstboot.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'mkdir -p /opt/opencloudtouch/logs && cp -a /opt/opencloudtouch/logs-persistent/. /opt/opencloudtouch/logs/ 2>/dev/null || true'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
RESTORE
systemctl enable oct-log-restore.service

# Periodic sync: every 4 hours
cat > /etc/systemd/system/oct-log-sync.service << 'SYNCSVC'
[Unit]
Description=Sync OCT logs to SD card

[Service]
Type=oneshot
ExecStart=/usr/local/bin/oct-log-sync
SYNCSVC

cat > /etc/systemd/system/oct-log-sync.timer << 'TIMER'
[Unit]
Description=Periodic OCT log sync to SD card

[Timer]
OnBootSec=30min
OnUnitActiveSec=4h
Persistent=true

[Install]
WantedBy=timers.target
TIMER
systemctl enable oct-log-sync.timer

# Flush logs on shutdown (so nothing is lost on clean reboot)
cat > /etc/systemd/system/oct-log-flush.service << 'FLUSH'
[Unit]
Description=Flush OCT logs to SD before shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/oct-log-sync

[Install]
WantedBy=shutdown.target reboot.target halt.target
FLUSH
systemctl enable oct-log-flush.service

# ==== MOTD will be generated dynamically on first boot ====
# (after port and network configuration are known)
# See: /opt/opencloudtouch/oct-firstboot.sh

echo "[OK] OpenCloudTouch configured"

CHROOT
