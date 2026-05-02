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

## Security

- Parameterized SQL queries (no injection risk)
- `defusedxml` for all XML parsing (XXE protection)
- Non-root container user
- CORS configurable origins
- RFC 7807 error responses (no internal details leaked)
- Stream URL scheme validation (SSRF mitigation)
