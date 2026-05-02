# ADR-004: No Authentication

**Date:** 2026-03-29
**Status:** Accepted

## Context

OpenCloudTouch runs on a local home network to control Bose SoundTouch speakers.

## Decision

No authentication or authorization layer.

## Rationale

- Trusted local network environment (home/household)
- Bose SoundTouch devices themselves have no authentication
- Adding auth would create UX friction with zero security benefit on LAN
- Docker container binds to host network for SSDP multicast — already LAN-only
- No sensitive data (only device configs and radio station presets)

## Consequences

- Must NOT be exposed to the internet without additional reverse proxy + auth
- Documented in SECURITY.md as explicit design choice
- `OCT_ALLOW_DANGEROUS_OPERATIONS` flag guards destructive operations (test-only)
