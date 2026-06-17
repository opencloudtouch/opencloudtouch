#!/bin/bash -e
# ============================================================================
# Stage: Finalize Image
# ============================================================================
# Final cleanup, pre-pull Docker image, and prepare for first boot.

on_chroot << 'CHROOT'

# ==== Disable graphical first-boot wizard ====
# pi-gen's DISABLE_FIRST_BOOT_USER_RENAME=1 (set in build.sh) prevents
# the text-mode userconfig.service from ever being activated.
# We only need to clean up piwiz (graphical wizard) as a precaution.
rm -f /etc/xdg/autostart/piwiz.desktop
rm -f /usr/share/applications/piwiz.desktop

# ==== Enable console autologin (appliance mode) ====
# For headless operation, auto-login as 'oct' user
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << 'AUTOLOGIN'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin oct --noclear %I $TERM
AUTOLOGIN

# ==== Pre-pull the OCT Docker image ====
# This makes first boot MUCH faster (no download needed)
# Note: This requires Docker to be running during build.
# If running in pi-gen Docker build, this may not work — the firstboot
# script will handle pulling as a fallback.

if systemctl is-active docker &>/dev/null; then
    echo "Pre-pulling OpenCloudTouch Docker image..."
    docker pull ghcr.io/opencloudtouch/opencloudtouch:latest || \
        echo "[WARN] Could not pre-pull image. Will be downloaded on first boot."
else
    echo "[INFO] Docker not running during build. Image will be pulled on first boot."
fi

# ==== System cleanup ====
apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -rf /tmp/*
rm -rf /var/tmp/*

# Clear logs
find /var/log -type f -exec truncate -s 0 {} \; 2>/dev/null || true

# Clear bash history
rm -f /root/.bash_history
rm -f /home/oct/.bash_history

echo "[OK] Image finalized"

CHROOT
