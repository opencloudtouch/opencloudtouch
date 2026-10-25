# Architecture

**OpenCloudTouch** is a **modular monolith** serving as a local-network bridge between Bose SoundTouch devices and open radio services (RadioBrowser). It runs as a single Docker container with host networking.

## Why Monolith?

- Local-network appliance — no geographic scaling needed
- Single household use — no multi-tenancy
- Low complexity — 12 modules, ~5000 LOC backend
- Simple deployment — one container, one command (`docker run`)

## System Overview

```
┌──────────────────────────────────────────────────────────┐
│ Docker Container (host network)                           │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │ FastAPI Application                                 │  │
│  │                                                     │  │
│  │  Routes → Services → Repositories → SQLite          │  │
│  │                                                     │  │
│  │  External Adapters:                                 │  │
│  │  ├─ Bose Device API (bosesoundtouchapi)             │  │
│  │  ├─ SSDP Discovery (UDP multicast)                  │  │
│  │  ├─ RadioBrowser (httpx)                            │  │
│  │  └─ TuneIn (httpx, stream resolution)               │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │ React SPA (pre-built static files via Starlette)    │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
         ↕                           ↕
   Local Network                RadioBrowser.org
   (Bose devices)
```

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `core` | Config, logging, exceptions, DI, repository base |
| `devices` | Discovery, sync, CRUD, health checks, capabilities |
| `presets` | Preset management (1-6 per device), device programming |
| `zones` | Multi-room zone management |
| `radio` | RadioBrowser search provider |
| `settings` | User settings persistence |
| `setup` | SSH/USB device configuration wizard |
| `setup/wizard/` | Step-organized subpackage (one file per wizard step under `setup/wizard/`, mixins composed in `wizard/service.py`, routers aggregated in `wizard/router.py`) |
| `bmx` | Bose Media Exchange emulation |
| `marge` | Bose cloud API emulation (XML) |
| `recents` | Recently played items |
| `swupdate` | Firmware update emulation |
| `discovery` | SSDP/UPnP + manual fallback |

## Dependency Flow

```
Routes (HTTP layer)
  ↓
Services (business logic)
  ↓
Repositories (data access via BaseRepository)
  ↓
SQLite (/data/oct.db via aiosqlite)
```

Cross-module dependencies are minimal:
- `presets` → `devices` (DeviceRepository for preset sync)
- `zones` → `devices` (DeviceRepository for zone enrichment)
- `setup` → `devices` (DeviceRepository for setup context)
- `bmx` → `devices`, `radio` (stream resolution)
- `marge` → `devices` (Bose cloud emulation)

## Design Patterns

| Pattern | Usage |
|---------|-------|
| Repository | All data access via BaseRepository subclasses |
| Adapter | External APIs (Bose, RadioBrowser, SSDP) |
| Factory | Mock/Real adapter selection based on `OCT_MOCK_MODE` |
| Dependency Injection | FastAPI `Depends()` + `app.state` |
| Strategy | RadioProvider interface with pluggable providers |
| Observer (SSE) | Streaming discovery progress to browser |

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite | Single-user appliance, no concurrent write pressure, zero-config |
| FastAPI | Async-native, auto OpenAPI docs, Pydantic validation |
| Pre-built frontend | Eliminates Node.js from Docker image, solves ARM32 Rolldown issue |
| Host networking | Required for SSDP multicast discovery on local network |
| No authentication | Trusted local network only (documented in SECURITY.md) |
| `setup/wizard/step8_finalize_verify.py` stays unsplit | Holds both `finalize_device`/`verify_setup` flows (largest file in the package) because they share `_verify_sys_config` and are both driven by the same frontend component (`Step8Verification.tsx`); see #466 item 1. Renumbered from `step7_finalize_verify.py`/`Step7Verification.tsx` when #469 inserted the NTP step ahead of it. |

## Real-Time Architecture

Device discovery uses Server-Sent Events (SSE):

```
Browser → GET /api/discover/stream → FastAPI → SSDP multicast → Network
Browser ← event: device_found ←── FastAPI ←── device response
Browser ← event: completed ←────── FastAPI
```

## API Response Formats

| Path | Format | Audience |
|------|--------|----------|
| `/api/*` | JSON | Frontend SPA |
| `/marge/*` | XML | Bose device firmware |
| `/bmx/*` | JSON/XML | Bose device firmware |
| `/swupdate/*` | XML | Bose device firmware |

## API error format

Every `/api/*` error is an `ErrorDetail` JSON object (`core/exceptions.py`). The keys
`code`, `params` and `extra` are always present (`null` when unset); all other keys are
unchanged from the original RFC 7807-inspired format. Only a few errors carry a `code`
today (`device_not_found`, `device_unreachable`, `not_found`, `validation_error`,
`internal_error`); radio, SSH, external-service, restore and most route-level errors are
already `ErrorDetail` but have `code: null` until their domain migration (see the
error-code rollout specs).

```json
{
  "type": "validation_error",
  "title": "Invalid Request Data",
  "status": 422,
  "detail": "Request validation failed",
  "instance": "/api/mqtt/config",
  "errors": [
    {
      "field": "body.port",
      "path": "port",
      "message": "Invalid value",
      "type": "value_error",
      "code": "mqtt_invalid_port"
    }
  ],
  "code": "validation_error",
  "params": null,
  "extra": null
}
```

- `type` is the coarse category (derived from the HTTP status); `code` is the precise,
  stable identifier (`^[a-z][a-z0-9_]*$`, prefixed by domain when feature-specific, for
  example `mqtt_invalid_host`). Codes are public contract and are never renamed after release.
- `params` is a flat `{string: string}` map for message interpolation (values are coerced
  with `str()`); `extra` carries structured data the client needs (not for translation).
- `errors[].field` is the legacy dotted location (`body.port`); `errors[].path` is the same
  location without the leading `body.`/`query.`/`path.`/`header.` segment (`port`,
  `config.url`). Clients map field errors with `path`.
- Status conventions: `DomainValidationError` → 400, request-body validation → 422,
  unknown resource → 404, state conflict → 409, upstream failures → 502/503/504.
  `raise_coded` enforces this: for status ≥ 500 the given text is only logged and the
  response carries the generic text ("An unexpected error occurred. Please try again
  later."); clients show the translated `code` instead.

**Code format.** `raise_coded` and `DomainValidationError(code=…)` reject codes that do not match
`^[a-z][a-z0-9_]*$` with a `ValueError`. `extra` is passed through `jsonable_encoder`; a value
that cannot be serialised is dropped (with a warning) instead of breaking the error response.

**Raising coded errors.** Use `raise_coded(status, code, detail, *, field=None, params=None,
extra=None, title=None)` from any route or service. Pydantic validators signal a code with
`raise ValueError("code:my_code")`; the validation handler then sets `errors[].code` to
`my_code` and `message` to `"Invalid value"`. Model-level validators have no field
(`field: "body"`, `path: ""`); raise `raise_coded(422, code, ..., field="<name>")` from the
service when a field attribution is needed.

**Registry rule.** Every code is a constant in `core/error_codes.py`. A test checks the
pattern, uniqueness and that no code from the committed snapshot
(`tests/unit/core/error_codes_snapshot.txt`) was removed or renamed. Feature changes add
their constants to both.

**Never put secrets, stack traces, filesystem paths or raw exception text into `params`,
`extra` or the `detail` of a 5xx response.**

The frontend turns the response into a typed `ApiError` (`api/types.ts`) and shows
translated messages through `getApiErrorMessage` / `getFieldErrors` (`utils/apiErrors.ts`),
using the keys `errors.api.<code>` in all locales. The `bmx/` routes keep the Bose protocol
formats and are out of scope.

## Security

- Parameterized SQL queries (no injection risk)
- `defusedxml` for all XML parsing (XXE protection)
- Non-root container user
- CORS configurable origins
- RFC 7807 error responses (no internal details leaked)
- Stream URL scheme validation (SSRF mitigation)
