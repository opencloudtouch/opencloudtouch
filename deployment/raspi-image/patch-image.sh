#!/usr/bin/env bash
# ============================================================================
# OpenCloudTouch — Patch an existing Raspberry Pi image in-place
# ============================================================================
# Reads patch-manifest.txt and applies all operations to a mounted image.
# No hardcoded file lists — add/remove/change entries in the manifest.
#
# Usage:
#   ./patch-image.sh <image.img.xz>           # Decompress + patch + recompress
#   ./patch-image.sh <image.img>              # Patch in-place (no recompress)
#   ./patch-image.sh <image.img.xz> --no-xz  # Decompress + patch (leave as .img)
#   ./patch-image.sh <image.img> --manifest custom.txt  # Use custom manifest
#
# Requirements: Linux (or WSL2), sudo, xz-utils, xxd
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${SCRIPT_DIR}/patch-manifest.txt"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[PATCH]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

COUNTS_COPY=0
COUNTS_REMOVE=0
COUNTS_SYMLINK=0
COUNTS_PURGE=0
COUNTS_DISABLE=0
COUNTS_WRITE=0

# ============================================================================
# Parse arguments
# ============================================================================
IMAGE=""
RECOMPRESS=true

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <image.img[.xz]> [--no-xz] [--manifest <file>]"
    exit 1
fi

IMAGE="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-xz) RECOMPRESS=false; shift ;;
        --manifest) MANIFEST="$2"; shift 2 ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ ! -f "$IMAGE" ]]; then
    log_error "File not found: $IMAGE"
    exit 1
fi

if [[ ! -f "$MANIFEST" ]]; then
    log_error "Manifest not found: $MANIFEST"
    exit 1
fi

# Security: no symlinks, resolve path, verify magic bytes
if [[ -L "$IMAGE" ]]; then
    log_error "Refusing to process symlink: $IMAGE"
    exit 1
fi
IMAGE="$(realpath "$IMAGE")"

if [[ "$IMAGE" == *.xz ]]; then
    MAGIC=$(xxd -l 6 -p "$IMAGE" 2>/dev/null)
    if [[ "$MAGIC" != "fd377a585a00" ]]; then
        log_error "Not a valid xz archive (magic: $MAGIC)"
        exit 1
    fi
else
    MBR_SIG=$(xxd -s 510 -l 2 -p "$IMAGE" 2>/dev/null)
    if [[ "$MBR_SIG" != "55aa" ]]; then
        log_error "Not a valid disk image (MBR: $MBR_SIG)"
        exit 1
    fi
fi

# ============================================================================
# Decompress if needed
# ============================================================================
if [[ "$IMAGE" == *.xz ]]; then
    log_info "Decompressing ${IMAGE}..."
    xz -dk "$IMAGE"
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
    sudo mount "${LOOP}p1" /mnt/oct-patch/boot || \
    log_warn "Could not mount boot partition — /boot patches may not apply"

ROOT="/mnt/oct-patch"
log_info "Image mounted at ${ROOT}"

# ============================================================================
# Manifest execution engine
# ============================================================================
log_info "Applying manifest: $(basename "$MANIFEST")"

execute_copy() {
    local src="$1" target="$2" perms="$3"
    local full_src="${SCRIPT_DIR}/${src}"
    if [[ ! -f "$full_src" ]]; then
        log_warn "COPY source missing: ${src}"
        return
    fi
    sudo mkdir -p "$(dirname "${ROOT}${target}")"
    sudo install -m "$perms" "$full_src" "${ROOT}${target}"
    log_info "  COPY ${src} -> ${target}"
    (( COUNTS_COPY++ )) || true
}

execute_remove() {
    local target="$1"
    if [[ -e "${ROOT}${target}" ]] || [[ -L "${ROOT}${target}" ]]; then
        sudo rm -f "${ROOT}${target}"
        log_info "  REMOVE ${target}"
    fi
    (( COUNTS_REMOVE++ )) || true
}

execute_symlink() {
    local target="$1" link="$2"
    sudo mkdir -p "$(dirname "${ROOT}${link}")"
    sudo ln -sf "$target" "${ROOT}${link}"
    log_info "  SYMLINK ${link} -> ${target}"
    (( COUNTS_SYMLINK++ )) || true
}

execute_purge_pkg() {
    local pkg="$1"
    local list_file="${ROOT}/var/lib/dpkg/info/${pkg}.list"
    if [[ -f "$list_file" ]]; then
        log_info "  PURGE_PKG ${pkg}"
        while IFS= read -r f; do
            sudo rm -f "${ROOT}${f}" 2>/dev/null || true
        done < "$list_file"
        sudo sed -i "/^Package: ${pkg}$/,/^$/{s/^Status: install ok installed$/Status: deinstall ok config-files/}" \
            "${ROOT}/var/lib/dpkg/status" 2>/dev/null || true
        sudo rm -f "${ROOT}/var/lib/dpkg/info/${pkg}."* 2>/dev/null || true
        (( COUNTS_PURGE++ )) || true
    else
        log_info "  PURGE_PKG ${pkg} (not installed)"
    fi
}

execute_disable_service() {
    local svc="$1"
    sudo rm -f "${ROOT}/etc/systemd/system/multi-user.target.wants/${svc}.service" 2>/dev/null || true
    sudo rm -f "${ROOT}/etc/systemd/system/${svc}.service" 2>/dev/null || true
    log_info "  DISABLE_SERVICE ${svc}"
    (( COUNTS_DISABLE++ )) || true
}

execute_write() {
    local target="$1" perms="$2" content="$3"
    sudo mkdir -p "$(dirname "${ROOT}${target}")"
    printf '%s\n' "$content" | sudo tee "${ROOT}${target}" > /dev/null
    sudo chmod "$perms" "${ROOT}${target}"
    log_info "  WRITE ${target}"
    (( COUNTS_WRITE++ )) || true
}

# ============================================================================
# Parse manifest
# ============================================================================
IN_WRITE=false
WRITE_TARGET=""
WRITE_PERMS=""
WRITE_DELIM=""
WRITE_CONTENT=""

while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$IN_WRITE" == true ]]; then
        if [[ "$line" == "$WRITE_DELIM" ]]; then
            execute_write "$WRITE_TARGET" "$WRITE_PERMS" "$WRITE_CONTENT"
            IN_WRITE=false
            WRITE_CONTENT=""
        else
            [[ -n "$WRITE_CONTENT" ]] && WRITE_CONTENT="${WRITE_CONTENT}"$'\n'"${line}" || WRITE_CONTENT="$line"
        fi
        continue
    fi

    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue

    read -r cmd rest <<< "$line"

    case "$cmd" in
        COPY)
            read -r src target perms <<< "$rest"
            execute_copy "$src" "$target" "$perms"
            ;;
        REMOVE)
            read -r target <<< "$rest"
            execute_remove "$target"
            ;;
        SYMLINK)
            read -r target link <<< "$rest"
            execute_symlink "$target" "$link"
            ;;
        PURGE_PKG)
            read -r pkg <<< "$rest"
            execute_purge_pkg "$pkg"
            ;;
        DISABLE_SERVICE)
            read -r svc <<< "$rest"
            execute_disable_service "$svc"
            ;;
        WRITE)
            read -r target perms heredoc_marker <<< "$rest"
            WRITE_TARGET="$target"
            WRITE_PERMS="$perms"
            WRITE_DELIM="${heredoc_marker#<<}"
            IN_WRITE=true
            ;;
        *)
            log_warn "Unknown manifest command: ${cmd}"
            ;;
    esac
done < "$MANIFEST"

# ============================================================================
# Summary
# ============================================================================
log_info "--- Verification ---"
echo "  oct user: $(sudo grep '^oct:' "${ROOT}/etc/passwd" | cut -d: -f1 || echo 'MISSING!')"
echo "  userconfig: $(ls "${ROOT}/etc/systemd/system/multi-user.target.wants/userconfig.service" 2>/dev/null && echo 'ENABLED!' || echo 'disabled')"

log_info "Unmounting..."
sudo umount -R /mnt/oct-patch
sudo losetup -d "$LOOP"
LOOP=""

if [[ "$RECOMPRESS" == "true" ]]; then
    log_info "Recompressing (single-thread for Etcher compatibility)..."
    xz -9 "$IMG_FILE"
    log_info "Output: ${IMG_FILE}.xz"
    cd "$(dirname "${IMG_FILE}")"
    sha256sum "$(basename "${IMG_FILE}.xz")" > "$(basename "${IMG_FILE}.xz").sha256"
    cd - > /dev/null
fi

log_info "=== Done! ${COUNTS_COPY} copied, ${COUNTS_REMOVE} removed, ${COUNTS_SYMLINK} symlinks, ${COUNTS_PURGE} purged, ${COUNTS_DISABLE} disabled, ${COUNTS_WRITE} written ==="
