# Bose SoundTouch Protocol Documentation

Complete reverse-engineered documentation of the Bose SoundTouch ecosystem:
device API, cloud services, IoT infrastructure, and migration strategies.

Compiled from community research (SoundCork, ÜberBöse API, SoundTouch Plus Wiki,
gesellix/Bose-SoundTouch) and our own analysis.

## Document Index

### 1. Device API (Local HTTP)
- [01-api-endpoints.md](01-api-endpoints.md) — All 103 discovered REST endpoints on port 8090
- [02-websocket-events.md](02-websocket-events.md) — Real-time WebSocket events on port 8080
- [03-preset-management.md](03-preset-management.md) — Preset CRUD (including undocumented write endpoints)
- [04-zone-management.md](04-zone-management.md) — Multiroom zone control
- **[api/](api/README.md)** — Real XML schemas crawled from ST10/ST30/ST300 devices
  - [api/device-identity/](api/device-identity/README.md) — /info, /capabilities, /supportedURLs, /name, /bluetoothInfo
  - [api/playback/](api/playback/README.md) — /nowPlaying, /key, /select + [presets](api/playback/presets.md), [recents](api/playback/recents.md)
  - [api/audio/](api/audio/README.md) — /volume, /bass, /balance, DSP controls (ST300)
  - [api/sources/](api/sources/README.md) — /sources, /serviceAvailability, /listMediaServers
  - [api/music-services/](api/music-services/README.md) — Account management, station search, content navigation
  - [api/network/](api/network/README.md) — /networkInfo, /netStats, Wi-Fi profiles
  - [api/zones/](api/zones/README.md) — /getZone, /setZone, stereo pairing
  - [api/system/](api/system/README.md) — Power, clock, firmware, factory reset
  - [api/cloud/](api/cloud/README.md) — Marge sync, bearer tokens (EOL May 2026)
  - [api/hdmi/](api/hdmi/README.md) — HDMI-CEC, input assignment (ST300 only)
  - [api/internal/](api/internal/README.md) — Pairing, setup, device internals, BCO reset

### 2. Cloud Services (Upstream Bose)
- [10-upstream-urls.md](10-upstream-urls.md) — All Bose cloud domains and their purposes
- [11-device-redirect-methods.md](11-device-redirect-methods.md) — XML config, /etc/hosts, binary patching
- [12-spotify-account-flow.md](12-spotify-account-flow.md) — Spotify OAuth token exchange via Bose proxy
- [13-scmudc-telemetry.md](13-scmudc-telemetry.md) — Device telemetry/analytics event format

### 3. IoT & MQTT Infrastructure
- [20-iot-configuration.md](20-iot-configuration.md) — AWS IoT Core setup, certificates, MQTT topics

### 4. Device Access & Discovery
- [30-device-access.md](30-device-access.md) — SSH/Telnet access via USB stick, firmware files
- [31-network-discovery.md](31-network-discovery.md) — SSDP, mDNS, UPnP discovery protocols
- [32-device-lifecycle.md](32-device-lifecycle.md) — Boot sequence, /power_on, registration flow

### 5. TLS & Certificates
- [40-tls-and-certificates.md](40-tls-and-certificates.md) — Custom CA injection, trust store, HTTPS setup

### 6. Cloud Emulation (for self-hosting)
- [50-cloud-emulation-concept.md](50-cloud-emulation-concept.md) — Architecture for replacing Bose cloud locally
- [51-undocumented-features.md](51-undocumented-features.md) — Community-discovered APIs and behaviors

### 7. Process Diagrams (Mermaid)
- [60-process-overview.md](60-process-overview.md) — System context, port overview, process index
- [61-process-device-discovery.md](61-process-device-discovery.md) — SSDP/mDNS → UPnP → `/info` enrichment
- [62-process-device-boot.md](62-process-device-boot.md) — Boot sequence → `/power_on` → source availability
- [63-process-preset-lifecycle.md](63-process-preset-lifecycle.md) — Read / Store / Remove / Select presets
- [64-process-zone-management.md](64-process-zone-management.md) — Create / Add / Remove / Dissolve multiroom zones
- [65-process-spotify-account.md](65-process-spotify-account.md) — OAuth → cloud registration → device sync
- [66-process-device-migration.md](66-process-device-migration.md) — Redirect methods, CA injection, rollback
- [67-process-device-access.md](67-process-device-access.md) — USB stick → SSH enable → filesystem layout
- [68-process-websocket-monitoring.md](68-process-websocket-monitoring.md) — Connection → event types → processing
- [69-process-iot-mqtt.md](69-process-iot-mqtt.md) — Certificates → MQTT → Device Shadows
- [70-process-telemetry.md](70-process-telemetry.md) — SCMUDC event batches → Base64 XML

### 8. Test Protocols
- [71-test-telnet-migration.md](71-test-telnet-migration.md) — Step-by-step Telnet:17000 test per device model

### Appendix
- [90-community-projects.md](90-community-projects.md) — SoundCork, ÜberBöse, SoundTouch Plus, AfterTouch
- [91-todo-extraction-gaps.md](91-todo-extraction-gaps.md) — Known gaps, items for future device extraction

---

**Sources**: gesellix/Bose-SoundTouch, SoundCork (deborahgu), ÜberBöse API (julius-d),
SoundTouch Plus Wiki (thlucas1), Official Bose SoundTouch Web API v1.0/v1.1 PDF.

**Bose Cloud Shutdown**: May 6, 2026 — all cloud services will be discontinued.
