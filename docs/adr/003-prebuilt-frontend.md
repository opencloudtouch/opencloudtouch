# ADR-003: Pre-built Frontend in CI

**Date:** 2026-03-29
**Status:** Accepted

## Context

The Docker image must support linux/arm/v7 (Raspberry Pi 2/3). Rolldown (Vite's bundler) has no native ARM32 musl binding, making in-container frontend builds impossible on that architecture.

## Decision

Build the frontend in a CI job (`frontend-tests`) and pass the static output as a build artifact to the Docker build stage.

## Rationale

- Eliminates Node.js from the production Docker image (smaller, fewer CVEs)
- Solves the Rolldown ARM32 musl binding issue
- Frontend output is platform-independent (HTML/CSS/JS)
- Build happens on fast CI runners, not on slow ARM devices

## Consequences

- Frontend build artifact must be available before Docker build starts (job dependency)
- `frontend-dist` artifact has short retention (1 day, only needed during pipeline)
