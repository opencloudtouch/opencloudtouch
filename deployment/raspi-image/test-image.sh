#!/usr/bin/env bash
# ============================================================================
# OpenCloudTouch Raspberry Pi Image Smoke Tests
# ============================================================================
# Validates a mounted Raspi image for correct structure, packages, and config.
#
# Usage:
#   sudo ./test-image.sh <mount-point> <expected-version> <arch>
#
# To add a new test:
#   1. Write a function: test_my_check() { ... }
#   2. Add it to the TESTS array at the bottom
#   3. Done — the harness handles pass/fail counting and output
#
# Test function contract:
#   - Access the mounted image via $ROOTFS (first arg)
#   - Access expected version via $VERSION (second arg)
#   - Access architecture via $ARCH (third arg)
#   - Return 0 for PASS, non-zero for FAIL
#   - Use echo for optional failure detail (captured by harness)
# ============================================================================

set -euo pipefail

ROOTFS="${1:?Usage: $0 <mount-point> <expected-version> <arch>}"
VERSION="${2:?Usage: $0 <mount-point> <expected-version> <arch>}"
ARCH="${3:?Usage: $0 <mount-point> <expected-version> <arch>}"

FAIL=0
PASS=0
TOTAL=0

# ============================================================================
# Test harness
# ============================================================================
run_test() {
    local label="$1"
    local func="$2"
    TOTAL=$((TOTAL + 1))

    printf "T%-3s %-40s " "$TOTAL" "$label"

    local output
    if output=$($func 2>&1); then
        echo "PASS"
        PASS=$((PASS + 1))
    else
        if [ -n "$output" ]; then
            echo "FAIL ($output)"
        else
            echo "FAIL"
        fi
        FAIL=$((FAIL + 1))
    fi
}

# ============================================================================
# Test definitions
# ============================================================================

test_directory_structure() {
    [ -d "$ROOTFS/opt/opencloudtouch" ] && \
    [ -d "$ROOTFS/opt/opencloudtouch/data" ]
}

test_docker_compose_exists() {
    [ -f "$ROOTFS/opt/opencloudtouch/docker-compose.yml" ]
}

test_docker_compose_image_ref() {
    grep -q "ghcr.io/opencloudtouch/opencloudtouch" \
        "$ROOTFS/opt/opencloudtouch/docker-compose.yml"
}

test_docker_compose_version_match() {
    # Verify the image tag is not 'latest' when a specific version was provided
    if [ "$VERSION" = "latest" ]; then
        return 0  # skip check for dev builds
    fi
    local actual
    actual=$(grep -oP 'ghcr\.io/opencloudtouch/opencloudtouch:\K[^\s"]+' \
        "$ROOTFS/opt/opencloudtouch/docker-compose.yml" | head -1)
    [ "$actual" = "$VERSION" ] || {
        echo "expected '$VERSION', got '$actual'"
        return 1
    }
}

test_firstboot_script() {
    [ -f "$ROOTFS/opt/opencloudtouch/oct-firstboot.sh" ] && \
    [ -x "$ROOTFS/opt/opencloudtouch/oct-firstboot.sh" ]
}

test_update_script() {
    [ -f "$ROOTFS/opt/opencloudtouch/oct-update.sh" ] && \
    [ -x "$ROOTFS/opt/opencloudtouch/oct-update.sh" ]
}

test_oct_service_installed() {
    [ -f "$ROOTFS/etc/systemd/system/opencloudtouch.service" ]
}

test_firstboot_service_installed() {
    [ -f "$ROOTFS/etc/systemd/system/oct-firstboot.service" ]
}

test_oct_service_enabled() {
    [ -L "$ROOTFS/etc/systemd/system/multi-user.target.wants/opencloudtouch.service" ] || {
        echo "not enabled"
        return 1
    }
}

test_firstboot_service_enabled() {
    [ -L "$ROOTFS/etc/systemd/system/multi-user.target.wants/oct-firstboot.service" ] || {
        echo "not enabled"
        return 1
    }
}

test_boot_config() {
    find "$ROOTFS/boot" -name "oct-config.txt" 2>/dev/null | grep -q .
}

test_docker_installed() {
    [ -f "$ROOTFS/usr/bin/dockerd" ]
}

test_avahi_installed() {
    [ -f "$ROOTFS/usr/sbin/avahi-daemon" ]
}

test_user_oct_exists() {
    grep -q "^oct:" "$ROOTFS/etc/passwd"
}

test_user_oct_docker_group() {
    grep -q "docker.*oct" "$ROOTFS/etc/group"
}

test_ssh_enabled() {
    [ -L "$ROOTFS/etc/systemd/system/multi-user.target.wants/ssh.service" ] || \
    [ -L "$ROOTFS/etc/systemd/system/sshd.service" ]
}

test_correct_kernel() {
    # armhf needs kernel7.img (32-bit); arm64 needs kernel8.img (64-bit)
    local bootdir
    bootdir="$(find "$ROOTFS/boot" -name 'firmware' -type d 2>/dev/null | head -1)"
    bootdir="${bootdir:-$ROOTFS/boot}"

    if [ "$ARCH" = "armhf" ]; then
        [ -f "$bootdir/kernel7.img" ] || [ -f "$bootdir/kernel7l.img" ] || {
            local found
            found="$(ls "$bootdir"/kernel*.img 2>/dev/null | xargs -I{} basename {} | tr '\n' ' ')"
            echo "need kernel7.img, found: ${found:-none}"
            return 1
        }
    else
        [ -f "$bootdir/kernel8.img" ] || {
            local found
            found="$(ls "$bootdir"/kernel*.img 2>/dev/null | xargs -I{} basename {} | tr '\n' ' ')"
            echo "need kernel8.img, found: ${found:-none}"
            return 1
        }
    fi
}

# ============================================================================
# Test registry — add new tests here
# ============================================================================

echo ""
echo "========================================"
echo "  Smoke Tests: ${ARCH} (v${VERSION})"
echo "========================================"

run_test "OCT directory structure"            test_directory_structure
run_test "docker-compose.yml exists"          test_docker_compose_exists
run_test "docker-compose.yml image ref"       test_docker_compose_image_ref
run_test "docker-compose.yml version match"   test_docker_compose_version_match
run_test "oct-firstboot.sh executable"        test_firstboot_script
run_test "oct-update.sh executable"           test_update_script
run_test "opencloudtouch.service installed"   test_oct_service_installed
run_test "oct-firstboot.service installed"    test_firstboot_service_installed
run_test "opencloudtouch.service enabled"     test_oct_service_enabled
run_test "oct-firstboot.service enabled"      test_firstboot_service_enabled
run_test "oct-config.txt on boot partition"   test_boot_config
run_test "Docker CE installed"                test_docker_installed
run_test "Avahi daemon installed"             test_avahi_installed
run_test "User 'oct' exists"                  test_user_oct_exists
run_test "User 'oct' in docker group"         test_user_oct_docker_group
run_test "SSH service enabled"                test_ssh_enabled
run_test "Correct kernel for arch"            test_correct_kernel

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "========================================"
echo "  Results: ${PASS}/${TOTAL} passed, ${FAIL} failed"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
