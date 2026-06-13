#!/bin/bash
# ============================================================================
# OpenCloudTouch Filesystem Expansion Script
# ============================================================================
# Runs ONCE on the very first boot, BEFORE Docker and other services.
# Expands the root filesystem to use the full SD card capacity.
# After expansion, the system reboots and this service disables itself.
# ============================================================================

set -euo pipefail

LOG_FILE="/var/log/oct-expand-fs.log"
FLAG_FILE="/var/lib/oct-expanded"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "======================================"
log "OpenCloudTouch Filesystem Expansion"
log "======================================"

# ==== Check if already expanded ====
if [[ -f "$FLAG_FILE" ]]; then
    log "Filesystem already expanded (flag file exists). Exiting."
    exit 0
fi

# ==== Expand root filesystem ====
log "Expanding root filesystem to full SD card capacity..."

# Method 1: Use raspi-config (preferred, handles everything automatically)
if command -v raspi-config &>/dev/null; then
    log "Using raspi-config --expand-rootfs"
    raspi-config --expand-rootfs nonint
    EXPANSION_STATUS=$?
else
    # Method 2: Manual expansion using growpart + resize2fs
    log "raspi-config not found. Using manual expansion..."
    
    # Detect root device and partition
    ROOT_PART=$(findmnt -n -o SOURCE /)
    ROOT_DEV=$(lsblk -no pkname "$ROOT_PART")
    PART_NUM=$(echo "$ROOT_PART" | grep -o '[0-9]*$')
    
    log "Root partition: $ROOT_PART (device: /dev/$ROOT_DEV, partition: $PART_NUM)"
    
    # Grow partition to fill disk
    if command -v growpart &>/dev/null; then
        growpart "/dev/$ROOT_DEV" "$PART_NUM" || {
            log "[WARN] growpart failed or partition already at maximum size"
        }
    else
        log "[ERROR] growpart not found. Install cloud-guest-utils."
        exit 1
    fi
    
    # Resize filesystem
    resize2fs "$ROOT_PART" || {
        log "[ERROR] resize2fs failed"
        exit 1
    }
    
    EXPANSION_STATUS=0
fi

# ==== Create flag file ====
if [[ $EXPANSION_STATUS -eq 0 ]]; then
    log "Filesystem expansion successful."
    mkdir -p "$(dirname "$FLAG_FILE")"
    touch "$FLAG_FILE"
    
    # Disable this service (run only once)
    log "Disabling oct-expand-fs.service..."
    systemctl disable oct-expand-fs.service
    
    # Reboot to apply changes
    log "Rebooting to complete expansion..."
    log "======================================"
    sync
    reboot
else
    log "[ERROR] Filesystem expansion failed with status $EXPANSION_STATUS"
    exit 1
fi
