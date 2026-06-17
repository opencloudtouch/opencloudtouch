#!/bin/bash
# ============================================================================
# OpenCloudTouch First Boot Script
# ============================================================================
# Runs ONCE on the very first boot. Reads user config from boot partition,
# applies settings, pulls the Docker image, and starts the service.
# After successful completion, it disables itself.
# ============================================================================

set -euo pipefail

export LANG=C.UTF-8
export LC_ALL=C.UTF-8

# Persistent log location (survives reboot — /var/log is tmpfs)
LOG_DIR="/opt/opencloudtouch/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/firstboot.log"
CONFIG_FILE="/boot/firmware/oct-config.txt"
COMPOSE_FILE="/opt/opencloudtouch/docker-compose.yml"
STATUS_FILE="/opt/opencloudtouch/.firstboot-status"
TOTAL_STEPS=6

# Known configuration keys
KNOWN_KEYS="WIFI_SSID WIFI_PASSWORD WIFI_COUNTRY OCT_PORT TIMEZONE"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

step() {
    local num="$1"; shift
    log "[${num}/${TOTAL_STEPS}] $*"
}

log "======================================"
log "OpenCloudTouch First Boot"
log "======================================"

# ==== Step 1: Read user config from boot partition ====
step 1 "Reading configuration..."

if [[ -f "$CONFIG_FILE" ]]; then
    log "Found configuration at $CONFIG_FILE"

    # Parse config safely (no shell expansion of values)
    while IFS='=' read -r key value; do
        # Skip empty keys or keys with invalid characters
        if [[ "$key" =~ ^[a-z_][a-z0-9_]*$ ]]; then
            log "[WARN] Config key '$key' should be uppercase: ${key^^}"
            continue
        fi
        [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
        # Warn on unknown keys
        if ! echo "$KNOWN_KEYS" | grep -qw "$key"; then
            log "[WARN] Unknown config key: $key (ignored)"
            continue
        fi
        # Trim leading/trailing whitespace from value
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        # Strip surrounding quotes if present
        if [[ "$value" =~ ^\"(.*)\"$ ]] || [[ "$value" =~ ^\'(.*)\'$ ]]; then
            value="${BASH_REMATCH[1]}"
        fi
        printf -v "$key" '%s' "$value"
    done < <(grep -v '^\s*#' "$CONFIG_FILE" | grep -v '^\s*$')
else
    log "No configuration file found on boot partition. Using defaults."
    log "To configure Wi-Fi or settings, place oct-config.txt on the"
    log "FAT32 boot partition (labeled 'bootfs') before booting."
fi

# ==== Step 2: Apply system configuration ====
step 2 "Applying system configuration..."

NETWORK_AVAILABLE=true

# Configure Wi-Fi
if [[ -n "${WIFI_SSID:-}" ]] && [[ -n "${WIFI_PASSWORD:-}" ]]; then
    log "Configuring Wi-Fi: ${WIFI_SSID}"
    WIFI_COUNTRY="${WIFI_COUNTRY:-DE}"

    # Check if Wi-Fi hardware exists before attempting connection
    if command -v nmcli &>/dev/null && ! nmcli -t -f TYPE device 2>/dev/null | grep -q "^wifi$"; then
        log "[INFO] No Wi-Fi hardware found. Skipping Wi-Fi configuration."
        log "       This device likely uses ethernet only (e.g. Pi 2)."
        NETWORK_AVAILABLE=false
    # Use NetworkManager (default on Bookworm)
    elif command -v nmcli &>/dev/null; then
        nmcli radio wifi on
        # Keep profile idempotent across retries
        nmcli connection show "oct-wifi" &>/dev/null && \
            nmcli connection delete "oct-wifi" &>/dev/null || true
        nmcli device wifi connect "${WIFI_SSID}" \
            password "${WIFI_PASSWORD}" \
            name "oct-wifi" || {
            log "[WARN] Wi-Fi connection failed. Check SSID and password in oct-config.txt."
            log "       Log: ${LOG_FILE}"
            NETWORK_AVAILABLE=false
        }

        # Verify IP address was assigned
        if [[ "$NETWORK_AVAILABLE" == "true" ]]; then
            log "Waiting for IP address..."
            GOT_IP=false
            for i in $(seq 1 15); do
                if nmcli -g IP4.ADDRESS dev show wlan0 2>/dev/null | grep -q '.'; then
                    GOT_IP=true
                    break
                fi
                sleep 2
            done
            if [[ "$GOT_IP" == "false" ]]; then
                log "[WARN] Wi-Fi connected but no IP received (DHCP timeout)."
                NETWORK_AVAILABLE=false
            fi
        fi
    fi
fi

# Actual connectivity check (Wi-Fi failure does NOT mean no network —
# ethernet may be available, or Wi-Fi config was for a different location)
if [[ "$NETWORK_AVAILABLE" == "false" ]]; then
    log "Wi-Fi unavailable. Checking for other network connectivity (ethernet)..."
    # Wait briefly for DHCP on ethernet
    for i in $(seq 1 10); do
        if ping -c1 -W2 8.8.8.8 &>/dev/null || ping -c1 -W2 1.1.1.1 &>/dev/null; then
            log "[OK] Network available via ethernet or other interface."
            NETWORK_AVAILABLE=true
            break
        fi
        if (( i % 3 == 0 )); then
            log "Waiting for network... (${i}/10)"
        fi
        sleep 2
    done
    if [[ "$NETWORK_AVAILABLE" == "false" ]]; then
        log "[WARN] No network connectivity detected on any interface."
    fi
fi

# Configure OCT port
if [[ -n "${OCT_PORT:-}" ]]; then
    if [[ "$OCT_PORT" =~ ^[0-9]+$ ]] && (( OCT_PORT >= 1 && OCT_PORT <= 65535 )); then
        log "Setting OCT port to ${OCT_PORT}"
        sed -i "s/OCT_PORT=.*/OCT_PORT=${OCT_PORT}/" "$COMPOSE_FILE"
        sed -i "s|OCT_STATION_DESCRIPTOR_BASE_URL=http://localhost:[0-9]*|OCT_STATION_DESCRIPTOR_BASE_URL=http://localhost:${OCT_PORT}|" "$COMPOSE_FILE"
    else
        log "[ERROR] Invalid OCT_PORT value: ${OCT_PORT}. Must be 1-65535. Using default."
        unset OCT_PORT
    fi
fi

# Configure timezone (validate against system timezone database)
if [[ -n "${TIMEZONE:-}" ]]; then
    if [[ -f "/usr/share/zoneinfo/${TIMEZONE}" ]]; then
        log "Setting timezone to ${TIMEZONE}"
        timedatectl set-timezone "${TIMEZONE}" 2>&1 || log "[WARN] Failed to set timezone: ${TIMEZONE}"
    else
        log "[WARN] Invalid timezone: '${TIMEZONE}'. Ignoring."
        log "       Valid examples: Europe/Berlin, America/New_York, Asia/Tokyo"
        log "       Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
    fi
fi

# ==== Step 3: Wait for Docker ====
step 3 "Waiting for Docker daemon..."

for i in $(seq 1 30); do
    if docker info &>/dev/null; then
        log "Docker is ready."
        break
    fi
    if (( i % 5 == 0 )); then
        log "Still waiting for Docker... (${i}/30)"
    fi
    sleep 2
done

if ! docker info &>/dev/null; then
    log "[ERROR] Docker failed to start after 60 seconds."
    log "        Try: sudo systemctl restart docker"
    log "        Logs: sudo journalctl -u docker --no-pager -n 50"
    echo "FAILED $(date -Iseconds) docker-timeout" > "$STATUS_FILE"
    exit 1
fi

# ==== Step 4: Pull Docker image ====
step 4 "Pulling OpenCloudTouch Docker image..."
log "[INFO] This step can take several minutes on slow networks (up to 10 minutes)."

if [[ "$NETWORK_AVAILABLE" == "false" ]]; then
    log "[WARN] Network appears unavailable. Skipping Docker pull."
    log "       Checking for pre-loaded image..."
    if docker images | grep -q "ghcr.io/opencloudtouch/opencloudtouch"; then
        log "Using pre-loaded image."
    else
        log "[ERROR] No pre-loaded image and no network. Cannot start."
        log "        Fix network, then: sudo /opt/opencloudtouch/oct-firstboot.sh"
        echo "FAILED $(date -Iseconds) no-image-no-network" > "$STATUS_FILE"
        exit 1
    fi
else
    cd /opt/opencloudtouch
    docker compose pull --quiet || {
        log "[WARN] Docker pull failed. Checking for pre-loaded image..."
        if docker images | grep -q "ghcr.io/opencloudtouch/opencloudtouch"; then
            log "Using pre-loaded image."
        else
            log "[ERROR] No image available and pull failed."
            log "        Check: ip addr (verify IP), ping -c1 google.com (verify internet)"
            log "        Retry: sudo docker compose -f ${COMPOSE_FILE} pull"
            echo "FAILED $(date -Iseconds) pull-failed" > "$STATUS_FILE"
            exit 1
        fi
    }
fi

# ==== Determine configured port ====
HEALTH_PORT=$(grep -oP 'OCT_PORT=\K\d+' "$COMPOSE_FILE" 2>/dev/null | head -1 || echo "")
HEALTH_PORT=${HEALTH_PORT:-7777}

# ==== Step 5: Start OpenCloudTouch ====
step 5 "Starting OpenCloudTouch (port ${HEALTH_PORT})..."

cd /opt/opencloudtouch
docker compose up -d

# Wait for health check
log "Waiting for health check..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${HEALTH_PORT}/health" >/dev/null 2>&1; then
        log "[OK] OpenCloudTouch is healthy!"
        HEALTHY=true
        break
    fi
    if (( i % 5 == 0 )); then
        log "Still waiting... (${i}/30)"
    fi
    sleep 3
done

if [[ "$HEALTHY" == "false" ]]; then
    log "[WARN] Health check did not pass within 90 seconds."
    log "       Service may still be starting. Check: docker compose logs"
    log "       Firstboot will retry on next reboot."
    echo "INCOMPLETE $(date -Iseconds) health-check-timeout" > "$STATUS_FILE"
    # Do NOT disable firstboot — allow retry on next boot
    exit 0
fi

# ==== Step 6: Finalize ====
step 6 "Finalizing setup..."

# Disable firstboot service (only after successful health check)
log "Disabling firstboot service..."
systemctl disable oct-firstboot.service

# Remove sensitive config AFTER successful setup
if [[ -f "$CONFIG_FILE" ]]; then
    log "Removing config file (contains Wi-Fi password)..."
    grep -v 'PASSWORD' "$CONFIG_FILE" > "${CONFIG_FILE}.applied" 2>/dev/null || true
    rm -f "$CONFIG_FILE"
fi

# ==== Generate dynamic MOTD ====
MOTD_PORT=${HEALTH_PORT}

# Get IP address
log "Resolving network IP..."
IP_ADDR=""
for i in $(seq 1 20); do
    IP_ADDR=$(ip route get 1 2>/dev/null | grep -oP 'src \K[\d.]+' || echo "")
    [[ -n "$IP_ADDR" ]] && break
    sleep 1
done
if [[ -z "$IP_ADDR" ]]; then
    IP_ADDR=$(ip -6 route get 2001:4860:4860::8888 2>/dev/null | grep -oP 'src \K[0-9a-f:]+' || echo "")
fi
[[ -z "$IP_ADDR" ]] && IP_ADDR="<no-network>"

# Get container version tag
OCT_VERSION_TAG=$(docker inspect --format='{{.Config.Image}}' opencloudtouch 2>/dev/null | sed 's/.*://' || echo "unknown")

log "Generating MOTD (Port: ${MOTD_PORT}, IP: ${IP_ADDR})..."

LOCAL_URL="http://opencloudtouch.local:${MOTD_PORT}"
if [[ "$IP_ADDR" == "<no-network>" ]]; then
    IP_URL="No network IP yet - use opencloudtouch.local"
else
    IP_URL="http://${IP_ADDR}:${MOTD_PORT}"
fi

# Build MOTD with dynamic padding
W=56
HLINE=$(printf '═%.0s' $(seq 1 $W))
p() { printf "  ║%-${W}s║\n" "$1"; }

{
    echo ""
    echo "  ╔${HLINE}╗"
    printf "  ║%*s%s%*s║\n" $(( (W - 24) / 2 )) "" "OpenCloudTouch Appliance" $(( (W - 24) / 2 )) ""
    echo "  ╠${HLINE}╣"
    p "  Web UI:   $LOCAL_URL"
    p "            $IP_URL"
    p "  Version:  $OCT_VERSION_TAG"
    p ""
    p "  Update:   sudo /opt/opencloudtouch/oct-update.sh"
    p "  Logs:     sudo journalctl -u opencloudtouch"
    echo "  ╚${HLINE}╝"
    echo ""
} > /etc/motd

# Write completion marker
echo "COMPLETE $(date -Iseconds)" > "$STATUS_FILE"

# ==== Report ====
log "======================================"
log "First boot complete!"
log "Access OpenCloudTouch at:"
log "  ${LOCAL_URL}"
log "  ${IP_URL}"
log "======================================"
