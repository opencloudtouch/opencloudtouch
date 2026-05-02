# ADR-001: SQLite as Database

**Date:** 2026-03-29
**Status:** Accepted

## Context

OpenCloudTouch needs persistent storage for device configurations, presets, and settings.

## Decision

Use SQLite (via aiosqlite) as the sole database.

## Rationale

- Single-user local appliance — no concurrent write pressure
- Zero configuration required — just a file on disk
- Portable — easy backup/restore, works on all target platforms (x86, ARM)
- In-memory mode for testing (`:memory:`)
- No external service dependency

## Consequences

- No multi-instance write concurrency (acceptable for single-household use)
- Schema migrations managed manually per module (version ranges)
