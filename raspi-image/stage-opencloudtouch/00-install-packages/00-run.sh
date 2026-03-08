#!/bin/bash -e
# ============================================================================
# Stage: Install Docker Engine + system packages
# ============================================================================
# Installs Docker CE, Docker Compose v2 plugin, Avahi (mDNS), and other
# system packages needed for the OpenCloudTouch appliance.

on_chroot << 'CHROOT'

# ==== System packages ====
apt-get update
apt-get install -y --no-install-recommends \
    avahi-daemon \
    avahi-utils \
    ca-certificates \
    curl \
    gnupg \
    jq \
    lsb-release \
    net-tools

# ==== Docker CE ====
# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y --no-install-recommends \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-compose-plugin

# ==== Configure Docker ====
# Enable Docker service
systemctl enable docker

# Add oct user to docker group
usermod -aG docker oct

# Docker daemon configuration for RPi (cgroup driver, log rotation)
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'DAEMON'
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2"
}
DAEMON

# ==== Configure Avahi (mDNS) ====
# Enable avahi-daemon for .local hostname resolution
systemctl enable avahi-daemon

# Configure avahi for opencloudtouch.local
sed -i 's/#host-name=.*/host-name=opencloudtouch/' /etc/avahi/avahi-daemon.conf
sed -i 's/#domain-name=.*/domain-name=local/' /etc/avahi/avahi-daemon.conf
sed -i 's/#publish-hinfo=.*/publish-hinfo=yes/' /etc/avahi/avahi-daemon.conf
sed -i 's/#publish-workstation=.*/publish-workstation=yes/' /etc/avahi/avahi-daemon.conf

# ==== Cleanup ====
apt-get clean
rm -rf /var/lib/apt/lists/*

echo "[OK] Docker + system packages installed"

CHROOT
