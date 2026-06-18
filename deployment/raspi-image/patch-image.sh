#!/usr/bin/env bash
# ============================================================================
# OpenCloudTouch — Patch an existing Raspberry Pi image in-place
# ============================================================================
# Takes a previously built .img or .img.xz and applies the current state of
# deployment/raspi-image/files/ and stage scripts — without rebuilding from
# scratch. Ideal for rapid iteration on firstboot scripts, systemd services,
# and other config changes.
#
# Usage:
#   ./patch-image.sh <image.img.xz>           # Decompress + patch + recompress
#   ./patch-image.sh <image.img>              # Patch in-place (no recompress)
#   ./patch-image.sh <image.img.xz> --no-xz  # Decompress + patch (leave as .img)
#
# Requirements:
#   - Linux (or WSL2 on Windows)
#   - sudo (for losetup/mount)
#   - xz-utils, rsync
#
# What gets patched:
#   - /opt/opencloudtouch/oct-firstboot.sh
#   - /opt/opencloudtouch/oct-update.sh
#   - /opt/opencloudtouch/docker-compose.yml
#   - /etc/systemd/system/oct-firstboot.service
#   - /etc/systemd/system/opencloudtouch.service (from 01-configure-oct)
#   - /boot/firmware/oct-config.txt
#   - Removes userconf-pi package if installed
#   - Disables userconfig.service if enabled
#   - Applies systemd unit changes from stage scripts
#
# What is NOT patched (requires full rebuild):
#   - Base OS packages (Docker, avahi, etc.)
#   - Partition layout / filesystem size
#   - User creation (oct user must exist)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES_DIR="${SCRIPT_DIR}/files"
STAGE_DIR="${SCRIPT_DIR}/stage-opencloudtouch"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[PATCH]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ============================================================================
# Parse arguments
# ============================================================================
IMAGE=""
RECOMPRESS=true

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <image.img[.xz]> [--no-xz]"
    exit 1
fi

IMAGE="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-xz) RECOMPRESS=false; shift ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ ! -f "$IMAGE" ]]; then
    log_error "File not found: $IMAGE"
    exit 1
fi

# Security: validate path is not a symlink and is a regular file
if [[ -L "$IMAGE" ]]; then
    log_error "Refusing to process symlink: $IMAGE"
    exit 1
fi

# Security: resolve to absolute path to prevent path traversal
IMAGE="$(realpath "$IMAGE")"

# Security: verify magic bytes (xz: FD 37 7A 58 5A 00, raw img: partition table)
if [[ "$IMAGE" == *.xz ]]; then
    MAGIC=$(xxd -l 6 -p "$IMAGE" 2>/dev/null)
    if [[ "$MAGIC" != "fd377a585a00" ]]; then
        log_error "File is not a valid xz archive (bad magic: $MAGIC)"
        exit 1
    fi
else
    # Raw .img — check for MBR signature at offset 510-511 (0x55AA)
    MBR_SIG=$(xxd -s 510 -l 2 -p "$IMAGE" 2>/dev/null)
    if [[ "$MBR_SIG" != "55aa" ]]; then
        log_error "File is not a valid disk image (no MBR signature: $MBR_SIG)"
        exit 1
    fi
fi

# ============================================================================
# Decompress if needed
# ============================================================================
if [[ "$IMAGE" == *.xz ]]; then
    log_info "Decompressing ${IMAGE}..."
    xz -dk "$IMAGE"  # -k keeps original
    IMG_FILE="${IMAGE%.xz}"
else
    IMG_FILE="$IMAGE"
    RECOMPRESS=false
fi

log_info "Working with: ${IMG_FILE}"

# ============================================================================
# Mount image
# ============================================================================
cleanup() {
    log_info "Cleaning up..."
    sudo umount -R /mnt/oct-patch 2>/dev/null || true
    if [[ -n "${LOOP:-}" ]]; then
        sudo losetup -d "$LOOP" 2>/dev/null || true
    fi
    sudo rm -rf /mnt/oct-patch 2>/dev/null || true
}
trap cleanup EXIT

LOOP=$(sudo losetup --find --show --partscan "$IMG_FILE")
log_info "Loop device: ${LOOP}"

sudo mkdir -p /mnt/oct-patch
sudo mount "${LOOP}p2" /mnt/oct-patch
sudo mount "${LOOP}p1" /mnt/oct-patch/boot/firmware 2>/dev/null || \
    sudo mount "${LOOP}p1" /mnt/oct-patch/boot || true

ROOT="/mnt/oct-patch"
log_info "Image mounted at ${ROOT}"

# ============================================================================
# Apply patches
# ============================================================================

log_info "--- Patching OCT files ---"

# Core OCT files
sudo install -m 755 "${FILES_DIR}/oct-firstboot.sh" "${ROOT}/opt/opencloudtouch/oct-firstboot.sh"
sudo install -m 755 "${FILES_DIR}/oct-update.sh" "${ROOT}/opt/opencloudtouch/oct-update.sh"
sudo install -m 644 "${FILES_DIR}/docker-compose.yml" "${ROOT}/opt/opencloudtouch/docker-compose.yml"
sudo install -m 644 "${FILES_DIR}/oct-firstboot.service" "${ROOT}/etc/systemd/system/oct-firstboot.service"
sudo install -m 644 "${FILES_DIR}/oct-config.txt" "${ROOT}/boot/firmware/oct-config.txt"

log_info "--- Removing userconf-pi (if installed) ---"

# Remove userconf-pi package artifacts WITHOUT chroot (avoids arbitrary code execution
# from a potentially compromised image — Security: never run binaries from untrusted images)
if [[ -f "${ROOT}/var/lib/dpkg/info/userconf-pi.list" ]]; then
    log_info "Removing userconf-pi files from image..."
    # Remove files listed in the package manifest
    while IFS= read -r f; do
        sudo rm -f "${ROOT}${f}" 2>/dev/null || true
    done < "${ROOT}/var/lib/dpkg/info/userconf-pi.list"
    # Mark package as removed in dpkg database (scoped to userconf-pi block only)
    sudo sed -i '/^Package: userconf-pi$/,/^$/{s/^Status: install ok installed$/Status: deinstall ok config-files/}' \
        "${ROOT}/var/lib/dpkg/status" 2>/dev/null || true
    log_info "userconf-pi removed (file-based, no chroot)"
else
    log_info "userconf-pi not installed (good)"
fi

# Ensure userconfig.service is disabled/masked regardless
if [[ -f "${ROOT}/etc/systemd/system/multi-user.target.wants/userconfig.service" ]]; then
    sudo rm -f "${ROOT}/etc/systemd/system/multi-user.target.wants/userconfig.service"
    log_info "Disabled userconfig.service symlink"
fi
sudo rm -f "${ROOT}/etc/systemd/system/userconfig.service"

# Remove piwiz if present
sudo rm -f "${ROOT}/etc/xdg/autostart/piwiz.desktop"
sudo rm -f "${ROOT}/usr/share/applications/piwiz.desktop"

# Remove SSH rename banner
sudo rm -f "${ROOT}/etc/ssh/sshd_config.d/rename_user.conf"

log_info "--- Applying systemd units from stage ---"

# Autologin
sudo mkdir -p "${ROOT}/etc/systemd/system/getty@tty1.service.d"
cat << 'AUTOLOGIN' | sudo tee "${ROOT}/etc/systemd/system/getty@tty1.service.d/autologin.conf" > /dev/null
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin oct --noclear %I $TERM
AUTOLOGIN

# Re-enable getty (in case userconf-pi disabled it)
sudo ln -sf /lib/systemd/system/getty@.service \
    "${ROOT}/etc/systemd/system/getty.target.wants/getty@tty1.service" 2>/dev/null || true

# Ensure oct-firstboot is enabled
sudo ln -sf /etc/systemd/system/oct-firstboot.service \
    "${ROOT}/etc/systemd/system/multi-user.target.wants/oct-firstboot.service" 2>/dev/null || true

# Remove firstboot status (so it re-runs)
sudo rm -f "${ROOT}/opt/opencloudtouch/.firstboot-status"

log_info "--- Verifying ---"

# Quick verification
echo "  oct user: $(sudo grep '^oct:' "${ROOT}/etc/passwd" | cut -d: -f1 || echo 'MISSING!')"
echo "  firstboot: $(ls -la "${ROOT}/opt/opencloudtouch/oct-firstboot.sh" 2>/dev/null | awk '{print $5, $6, $7, $8}' || echo 'MISSING!')"
echo "  userconfig: $(ls "${ROOT}/etc/systemd/system/multi-user.target.wants/userconfig.service" 2>/dev/null && echo 'STILL ENABLED!' || echo 'disabled (good)')"
echo "  userconf-pi: $(grep -A2 '^Package: userconf-pi' "${ROOT}/var/lib/dpkg/status" 2>/dev/null | grep -q '^Status: install ok installed' && echo 'STILL INSTALLED!' || echo 'not installed (good)')"

# ============================================================================
# Unmount + recompress
# ============================================================================
log_info "Unmounting..."
sudo umount -R /mnt/oct-patch
sudo losetup -d "$LOOP"
LOOP=""

if [[ "$RECOMPRESS" == "true" ]]; then
    log_info "Recompressing (single-thread for Etcher compatibility)..."
    rm -f "${IMAGE}"  # Remove old .xz
    xz -9 "$IMG_FILE"
    log_info "Output: ${IMG_FILE}.xz"

    # Update checksum
    cd "$(dirname "${IMG_FILE}")"
    sha256sum "$(basename "${IMG_FILE}.xz")" > "$(basename "${IMG_FILE}.xz").sha256"
    cd - > /dev/null
    log_info "SHA256 updated"
else
    log_info "Output: ${IMG_FILE} (uncompressed)"
fi

log_info "=== Patch complete! Flash and test. ==="
