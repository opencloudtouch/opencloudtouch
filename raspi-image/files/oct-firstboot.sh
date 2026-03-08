#!/bin/bash
# ============================================================================
# OpenCloudTouch First Boot Script
# ============================================================================
# Runs ONCE on the very first boot. Reads user config from boot partition,
# applies settings, pulls the Docker image, and starts the service.
# After successful completion, it disables itself.
# ============================================================================

set -euo pipefail

LOG_FILE="/var/log/oct-firstboot.log"
CONFIG_FILE="/boot/firmware/oct-config.txt"
COMPOSE_FILE="/opt/opencloudtouch/docker-compose.yml"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "======================================"
log "OpenCloudTouch First Boot"
log "======================================"

# ==== Read user config from boot partition ====
if [[ -f "$CONFIG_FILE" ]]; then
    log "Reading configuration from $CONFIG_FILE..."

    # Source config (simple KEY=VALUE format)
    # shellcheck disable=SC1090
    source <(grep -v '^\s*#' "$CONFIG_FILE" | grep -v '^\s*$')

    # ==== Configure Wi-Fi ====
    if [[ -n "${WIFI_SSID:-}" ]] && [[ -n "${WIFI_PASSWORD:-}" ]]; then
        log "Configuring Wi-Fi: ${WIFI_SSID}"
        WIFI_COUNTRY="${WIFI_COUNTRY:-DE}"

        # Use NetworkManager (default on Bookworm)
        if command -v nmcli &>/dev/null; then
            nmcli radio wifi on
            nmcli device wifi connect "${WIFI_SSID}" \
                password "${WIFI_PASSWORD}" \
                name "oct-wifi" || {
                log "[WARN] Wi-Fi connection failed. Check SSID and password."
            }
        else
            # Fallback: wpa_supplicant
            cat > /etc/wpa_supplicant/wpa_supplicant.conf << WPACFG
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=${WIFI_COUNTRY}

network={
    ssid="${WIFI_SSID}"
    psk="${WIFI_PASSWORD}"
    key_mgmt=WPA-PSK
}
WPACFG
            wpa_cli -i wlan0 reconfigure 2>/dev/null || true
        fi
    fi

    # ==== Configure OCT port ====
    if [[ -n "${OCT_PORT:-}" ]]; then
        log "Setting OCT port to ${OCT_PORT}"
        sed -i "s/OCT_PORT=7777/OCT_PORT=${OCT_PORT}/" "$COMPOSE_FILE"
    fi

    # ==== Configure timezone ====
    if [[ -n "${TIMEZONE:-}" ]]; then
        log "Setting timezone to ${TIMEZONE}"
        timedatectl set-timezone "${TIMEZONE}" || true
    fi

    # Remove sensitive config after reading
    log "Removing config file (contains Wi-Fi password)..."
    # Create a sanitized version without password
    grep -v 'PASSWORD' "$CONFIG_FILE" > "${CONFIG_FILE}.applied" 2>/dev/null || true
    rm -f "$CONFIG_FILE"
else
    log "No config file found at $CONFIG_FILE — using defaults."
fi

# ==== Ensure Docker is running ====
log "Waiting for Docker daemon..."
for i in $(seq 1 30); do
    if docker info &>/dev/null; then
        log "Docker is ready."
        break
    fi
    sleep 2
done

if ! docker info &>/dev/null; then
    log "[ERROR] Docker failed to start after 60 seconds."
    exit 1
fi

# ==== Pull latest OCT image ====
log "Pulling OpenCloudTouch Docker image..."
cd /opt/opencloudtouch
docker compose pull --quiet || {
    log "[WARN] Docker pull failed. Checking if image is pre-loaded..."
    if docker images | grep -q "opencloudtouch"; then
        log "Using pre-loaded image."
    else
        log "[ERROR] No image available. Check network connection."
        exit 1
    fi
}

# ==== Start OCT ====
log "Starting OpenCloudTouch..."
docker compose up -d

# Wait for health check
log "Waiting for health check..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:7777/health >/dev/null 2>&1; then
        log "[OK] OpenCloudTouch is healthy!"
        break
    fi
    sleep 3
done

if ! curl -sf http://localhost:7777/health >/dev/null 2>&1; then
    log "[WARN] Health check did not pass within 90 seconds."
    log "Service may still be starting. Check: docker compose logs"
fi

# ==== Disable firstboot service (run only once) ====
log "Disabling firstboot service..."
systemctl disable oct-firstboot.service

# ==== Report ====
IP_ADDR=$(hostname -I | awk '{print $1}')
log "======================================"
log "First boot complete!"
log "Access OpenCloudTouch at:"
log "  http://opencloudtouch.local:7777"
log "  http://${IP_ADDR}:7777"
log "======================================"
