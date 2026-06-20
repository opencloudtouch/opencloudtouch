#!/bin/bash
# ============================================================================
# OpenCloudTouch Update Script
# ============================================================================
# Updates OpenCloudTouch to the latest version.
#
# Usage:
#   sudo /opt/opencloudtouch/oct-update.sh              # Update to latest
#   sudo /opt/opencloudtouch/oct-update.sh 1.2.3        # Update to specific version
# ============================================================================

set -euo pipefail

VERSION="${1:-latest}"
COMPOSE_FILE="/opt/opencloudtouch/docker-compose.yml"
LOG_DIR="/opt/opencloudtouch/logs"
LOG_FILE="${LOG_DIR}/update.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Persistent logging for postmortem diagnostics
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

# Check root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

if [[ "$VERSION" != "latest" ]] && [[ ! "$VERSION" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    log_error "Invalid version format: ${VERSION}"
    exit 1
fi

log_info "OpenCloudTouch Update"
log_info "Target version: ${VERSION}"
echo ""

# Get current version
CURRENT=$(docker inspect --format='{{.Config.Image}}' opencloudtouch 2>/dev/null || echo "unknown")
log_info "Current image: ${CURRENT}"

# Update image tag in compose file
if [[ "$VERSION" != "latest" ]]; then
    sed -i "s|ghcr.io/opencloudtouch/opencloudtouch:.*|ghcr.io/opencloudtouch/opencloudtouch:${VERSION}|" "$COMPOSE_FILE"
    log_info "Updated compose file to version ${VERSION}"
fi

# Pull new image
log_info "Pulling new image..."
log_info "This can take several minutes on slow networks."
cd /opt/opencloudtouch
docker compose pull

# Restart with new image
log_info "Restarting OpenCloudTouch..."
systemctl stop opencloudtouch.service || true
docker compose up -d
systemctl start opencloudtouch.service || true

# Determine configured port
UPDATE_PORT=$(grep -oP 'OCT_PORT=\K\d+' "$COMPOSE_FILE" 2>/dev/null | head -1 || echo "")
UPDATE_PORT=${UPDATE_PORT:-7777}

# Wait for health check
log_info "Waiting for health check (port ${UPDATE_PORT})..."
for i in $(seq 1 20); do
    if curl -sf "http://localhost:${UPDATE_PORT}/health" >/dev/null 2>&1; then
        log_info "Health check passed!"
        break
    fi
    sleep 3
done

if ! curl -sf "http://localhost:${UPDATE_PORT}/health" >/dev/null 2>&1; then
    log_warn "Health check did not pass within 60 seconds."
    log_warn "Check logs: docker compose -f ${COMPOSE_FILE} logs"
    log_warn "Previous image still available. To rollback:"
    log_warn "  docker compose -f ${COMPOSE_FILE} down"
    log_warn "  sed -i 's|ghcr.io/opencloudtouch/opencloudtouch:.*|${CURRENT}|' ${COMPOSE_FILE}"
    log_warn "  docker compose -f ${COMPOSE_FILE} up -d"
    exit 1
fi

# Cleanup old images (only after successful health check)
log_info "Cleaning up old images..."
if [[ "$CURRENT" != "unknown" ]]; then
    docker image rm "$CURRENT" 2>/dev/null || true
fi

# Refresh MOTD version to avoid stale version display after updates
MOTD_PORT=${UPDATE_PORT}
IP_ADDR=$(ip route get 1 2>/dev/null | grep -oP 'src \K[\d.]+' || echo "")
if [[ -z "$IP_ADDR" ]]; then
    IP_ADDR=$(ip -6 route get 2001:4860:4860::8888 2>/dev/null | grep -oP 'src \K[0-9a-f:]+' || echo "")
fi
[[ -z "$IP_ADDR" ]] && IP_ADDR="<no-network>"
NEW_IMAGE=$(docker inspect --format='{{.Config.Image}}' opencloudtouch 2>/dev/null || echo "unknown")
OCT_VERSION_TAG=$(echo "$NEW_IMAGE" | sed 's/.*://')
LOCAL_URL="http://opencloudtouch.local:${MOTD_PORT}"
if [[ "$IP_ADDR" == "<no-network>" ]]; then
    IP_URL="No network IP yet - use opencloudtouch.local"
else
    IP_URL="http://${IP_ADDR}:${MOTD_PORT}"
fi
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

# Show result
echo ""
log_info "=========================================="
log_info "Update complete!"
log_info "Previous: ${CURRENT}"
log_info "Current:  ${NEW_IMAGE}"
log_info "Log file: ${LOG_FILE}"
log_info "=========================================="
