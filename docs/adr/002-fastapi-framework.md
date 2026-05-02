# ADR-002: FastAPI as Web Framework

**Date:** 2026-03-29
**Status:** Accepted

## Context

Need an async Python web framework for REST API + SSE streaming.

## Decision

Use FastAPI with Uvicorn as ASGI server.

## Rationale

- Native async/await support (critical for concurrent device communication)
- Automatic OpenAPI documentation generation
- Pydantic v2 integration for request/response validation
- Built-in dependency injection via `Depends()`
- SSE support via `StreamingResponse`
- Large ecosystem and community

## Consequences

- Pydantic models required for all API schemas
- Exception handlers must be registered globally for RFC 7807 compliance
