# ADR-005: Host Network Mode

**Date:** 2026-03-29
**Status:** Accepted

## Context

SSDP device discovery requires sending and receiving UDP multicast packets on the local network (239.255.255.250:1900).

## Decision

Run the Docker container with `--network host`.

## Rationale

- SSDP multicast requires direct access to the host's network interfaces
- Bridge networking blocks multicast packets from reaching the container
- WSL2 mirrored networking + host mode enables development on Windows
- Bose devices respond to the host IP, not a container-internal IP

## Consequences

- Container shares the host's network namespace (no port isolation)
- Port 7777 must be available on the host
- CORS origins must include the host's actual IP for frontend access
- Documented in deployment README and .wslconfig requirements
