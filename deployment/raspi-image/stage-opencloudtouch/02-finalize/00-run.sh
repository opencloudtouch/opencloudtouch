#!/bin/bash -e
# ============================================================================
# Stage: Finalize Image
# ============================================================================
# Final cleanup, pre-pull Docker image, and prepare for first boot.

on_chroot << 'CHROOT'

# ==== Purge userconf-pi (the "Please enter new username" wizard) ====
# In Bookworm, userconf-pi provides userconfig.service which shows an
# interactive username prompt on first boot. Our image has user 'oct'
# pre-created by pi-gen, so this MUST NOT run.
apt-get purge -y userconf-pi 2>/dev/null || true

# Remove userconfig service files (belt-and-suspenders — purge should
# handle this, but if the package was only partially installed or held
# by raspberrypi-sys-mods, we remove manually)
rm -f /etc/systemd/system/userconfig.service
rm -f /lib/systemd/system/userconfig.service
rm -f /etc/systemd/system/multi-user.target.wants/userconfig.service

# Mask the service so it cannot be re-enabled by post-install hooks.
# NOTE: systemctl is not functional inside a pi-gen chroot — create
# the mask symlink directly on the filesystem.
ln -sf /dev/null /etc/systemd/system/userconfig.service

# Remove SSH login blocker that prevents login until user is renamed
rm -f /etc/ssh/sshd_config.d/rename_user.conf

# Remove userconf.txt if present (prevents race condition where the
# service reads it and tries to run user-creation interactively)
rm -f /boot/firmware/userconf.txt
rm -f /boot/userconf.txt

# ==== Disable first-boot wizard (piwiz — desktop variant) ====
# Raspberry Pi OS Bookworm shows a desktop wizard on first boot.
# We preconfigure everything, so disable it.
rm -f /etc/xdg/autostart/piwiz.desktop
rm -f /usr/share/applications/piwiz.desktop

# ==== Ensure keyboard is pre-configured (no interactive prompt) ====
cat > /etc/default/keyboard << 'KEYBOARD'
XKBMODEL="pc105"
XKBLAYOUT="us"
XKBVARIANT=""
XKBOPTIONS=""
BACKSPACE="guess"
KEYBOARD
# Note: The file write above is sufficient — dpkg-reconfigure is unreliable
# inside a pi-gen chroot (no running systemd/debconf), so we skip it.

# ==== Verify user 'oct' exists ====
if ! id oct &>/dev/null; then
    echo "[ERROR] User 'oct' does not exist! pi-gen FIRST_USER_NAME failed."
    echo "        Creating user manually as fallback..."
    useradd -m -s /bin/bash -G sudo,docker oct
    echo "oct:opencloudtouch" | chpasswd
fi

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
