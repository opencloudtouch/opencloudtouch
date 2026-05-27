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

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Check root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (use sudo)"
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
cd /opt/opencloudtouch
docker compose pull

# Restart with new image
log_info "Restarting OpenCloudTouch..."
docker compose down
docker compose up -d

# Wait for health check
log_info "Waiting for health check..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:7777/health >/dev/null 2>&1; then
        log_info "Health check passed!"
        break
    fi
    sleep 3
done

if ! curl -sf http://localhost:7777/health >/dev/null 2>&1; then
    log_warn "Health check did not pass within 60 seconds."
    log_warn "Check logs: docker compose -f ${COMPOSE_FILE} logs"
    exit 1
fi

# Cleanup old images
log_info "Cleaning up old images..."
docker image prune -f

# Show result
NEW_IMAGE=$(docker inspect --format='{{.Config.Image}}' opencloudtouch 2>/dev/null || echo "unknown")
echo ""
log_info "=========================================="
log_info "Update complete!"
log_info "Previous: ${CURRENT}"
log_info "Current:  ${NEW_IMAGE}"
log_info "=========================================="
