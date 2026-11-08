# Changelog

All notable changes to OpenCloudTouch are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_No changes yet._

---

## [2.0.0] - 2026-11-08

### Added
- Redesigned setup and restore wizards with a shared design, progress tracker, focus management and full keyboard and screen-reader support
- Redesigned app shell, presets page, local control, zones, firmware, settings, diagnostics, about and licenses pages with swipe navigation between devices, a sticky device switch bar and a native `<dialog>` based modal
- Remove button with a confirmation dialog for online and offline devices in presets and local control; saved presets are kept (#520)
- `/health` reports the server `uptime`; the About page shows "running since" (#521)
- Link to the licenses page on the About page, keeping the selected device (#528)
- Toast after every network scan that names the newly discovered devices
- `PUT /api/devices/{id}/source` switches a device to Bluetooth, AUX or AirPlay
- Translated restore step and validation messages via stable `message_code` / `message_params` (all 10 locales, English fallback)
- Cypress suites for responsive layout (overlap, overflow and clipping audit) and for axe accessibility of every wizard state
- Machine-readable `code`, `params` and `extra` in API error responses (`ErrorDetail`), `errors[].path`/`code` for field errors, `raise_coded()` and an error-code registry (`core/error_codes.py`); all existing keys are unchanged.
- Frontend: typed `ApiError` thrown by `throwIfNotOk` and translated messages via `getApiErrorMessage`/`getFieldErrors` (`errors.api.*` in all locales).

### Changed
- Renaming a device uses only the device REST API (`POST /name`, like the Bose app). The SSH fallback that edited `SystemConfigurationDB.xml` was removed, a failed rename now answers 502 and leaves the stored name unchanged; control characters in the name are rejected (422)
- The navigation entry "Presets" is now "Devices" (all 10 locales). The device card is the single place for a device: now playing with a source switch (Presets, Bluetooth, AUX), previous/next/play keys for sources with tracks, volume, presets and remove
- Preset rows are toggles: a tap starts, pauses or resumes the preset; a small button next to it changes the station (behaviour change: the tap on the name used to open the station search). "Presets" in the source switch plays the preset the device played last
- The "Local control" page (`/local`) was removed; it was not linked anywhere and its source chips did not switch anything. Its functions live on the device card
- Restore: backup timeout raised to 10 minutes; archive validation searches the whole archive
- Device cards load from a small in-memory cache that is warmed for the neighbouring devices only
- Settings: a failed log download shows a translated reason instead of failing silently (#527)
- Frontend: the wire-shape interface `ApiError` is now `ApiErrorBody`.
- `ErrorDetail` and `ErrorItem` are part of the generated OpenAPI schema.
- `/health` has a typed response model (`HealthResponse`) in the OpenAPI schema; the frontend type is generated from it.
- The SoundTouch WebSocket client uses the `websockets.asyncio` API and ignores `HTTP(S)_PROXY`/`ALL_PROXY` for LAN devices; minimum `websockets` is now 15.0.

### Fixed
- Devices without the OCT redirect block in `/etc/hosts` were reported as `configured` by the health check and the setup verification (the grep fallback printed a second `0`)
- A second device scan now gets an explicit "already in progress" event instead of a bare HTTP 409, so real failures are no longer labelled "already running"
- Layout overflow and overlap on the presets, local control, multi-room and settings pages, the swiper, the navigation and the empty state
- False "unexpected content" warnings when validating a restore archive
- Accessibility: skip link and `main` landmark, heading order, contrast tokens, translated `aria-label`s, `html lang` sync, toast roles and reduced-motion support
- ci(pr-review): welcome comment no longer repeats for returning contributors; merged PRs are now counted per author, returning contributors get a shorter message and the label `contributor:trusted`

---

## [1.4.2] - 2026-05-29

### Added
- ci): show computed version in release workflow run title
- kb-growth): add Pattern & Quality Scan script and update workflow
- pr-review): upgrade to gpt-4o with enhanced review prompt
-  improve PR review quality based on production data
-  add AI-powered PR review automation via oct-support (#278
### Fixed
- ci): update trivy-action from deleted 0.28.0 to v0.36.0
-  propagate OCT_PORT to all device-facing URLs (#268) (#277
-  detect device config status via /info margeURL at startup (#267) (#281
- pr-review): filter legacy 'AI Review' job name from CI status checks
-  prevent issue-handler from hijacking PR comments and fix comment-trigger auth
-  PR review waits for CI completion before reviewing/approving
-  resolve actual LAN IP for wizard server-info (#200) (#276
-  validate diff line numbers for inline review comments
-  use base.ref instead of base.sha for PR review checkout
- i18n): translate missing wizard and restore keys for all locales (#265
- issue-handler): handle 410 Gone for deleted issues (#264
- issue-handler): handle 410 Gone for deleted issues
- i18n): shorten USB volume label to SOUNDTOUCH for FAT32 compatibility (#253
### Changed
-  rename AI Review job to PR Review
## [1.2.8] - 2026-05-16

### Added
- restore-wizard): implement full restore wizard (005
-  add post-release workflow for updating CHANGELOG and creating announcement discussions
### Fixed
- setup): prevent false-positive proxy detection in wizard (#184
-  optimize Dockerfile with caching for apt and pip installations
## [1.1.1] - 2026-04-12

### Fixed
- **Config file path detection (Issue #78)** — Auto-detect config at `/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml` or `/mnt/nv/OverrideSdkPrivateCfg.xml`; redirect writes to writable `/mnt/nv/` when original is on read-only filesystem
- **Vite 8 rolldown compatibility** — Fix `manualChunks` config (function instead of object)

---

## [1.1.0] - 2026-03-21

### Added
- **Multi-Room Zone Management** — Create, manage and dissolve speaker zones directly from the UI
- **Setup Status Badge** — Gear icon on device cards shows live setup state (unknown/configured/outdated/failed/offline), persisted in DB
- **Health-Check Background Task** — Periodic SSH verification to detect outdated or offline devices
- **Dual-Strategy Setup Wizard** — Wizard auto-detects whether an HTTPS reverse proxy is available on port 443 and adapts the configuration strategy (hosts-only vs. BMX + hosts)
- **Wizard Completion Endpoint** — `POST /api/setup/wizard/complete` persists `setup_status = configured` in DB when wizard finishes

### Changed
- **Volume Slider** — Replaced with DOM-direct RAF slider (A3) to eliminate drag lag; `onVolumeChange` fires only on pointer-up
- **Preset UX** — Overhauled with play button, overwrite confirmation dialog, and station logos
- **Setup Wizard** — Removed guided/manual mode selector; wizard starts directly in guided mode renamed to "Geführte Installation"
- **UX Polish** — Improved volume slider, delete button, cloud badge, info box
- Multi-room zone card layout improved; master device correctly shown in zone member list

### Fixed
- BUG-03: `/etc/hosts` entries now always use numeric IP (resolved via `socket.gethostbyname`); hostname like `hera` is no longer written to hosts file
- Zone master injection re-applied; master device perspective preferred in `get_all_zones`
- Device card drag disabled to prevent accidental swipe-navigation
- Zone card blue border removed
- Slider drag lag eliminated by removing inline styles during drag

---

## [1.0.0] - 2026-03-09

### Added
- **Setup Wizard** — Manual device configuration via SSH and USB stick
- **Raspberry Pi SD card images** — Pre-built images for Pi 3/4/5 (arm64 + armhf)
- **Multi-arch Docker images** — amd64, arm64, arm/v7
- **Upgrade guide** (UPGRADING.md) — Version-to-version migration documentation
- **Documentation** — Bilingual Wiki pages (DE/EN), API docs, Troubleshooting guide
- Docker Compose deployment template
- This changelog

### Changed
- Docker image now supports `stable` tag for production use
- Pinned all dependencies to exact versions

### Fixed
- CORS configuration now uses explicit default origins instead of wildcard
- SQLite index name collision between devices and presets tables
- XML namespace handling in SSDP discovery
- Database filename typo in config (ct.db → oct.db)
- Pi-gen build compatibility for both arm64 and armhf architectures

### Security
- Container vulnerability scanning enabled
- Automated dependency security updates

---

## [0.2.0] - 2026-02-01

### Added
- SSDP device discovery for automatic SoundTouch detection
- Preset management supporting slots 1-6
- RadioBrowser.info integration for internet radio search
- Manual device IP configuration for networks without multicast
- Device swiper navigation for browsing multiple devices
- Mock mode for local development without physical devices
- Health check endpoint for container monitoring
- Comprehensive test suite (348 backend + 260 frontend + 36 E2E tests)

### Changed
- Migrated from monolith to Clean Architecture
- React UI rewritten with modern hooks and TypeScript
- Switched from Flask to FastAPI for backend
- Replaced synchronous HTTP with async httpx
- Containerized deployment with Docker/Podman support

### Fixed
- Device synchronization race conditions
- Preset loading reliability
- WebSocket connection handling

---

## [0.1.0] - 2026-01-15

### Added
- Initial release
- Basic device listing via manual configuration
- Basic web interface for device control
- Docker deployment support

### Known Issues
- No automatic device discovery (manual IP configuration required)
- Limited error handling in device communication
- No preset management

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | 2026-03-09 | Setup Wizard (manual), Multi-arch Docker, RasPi images |
| 0.2.0 | 2026-02-01 | Major release: SSDP discovery, presets, radio search |
| 0.1.0 | 2026-01-15 | Initial release: basic device control |

---

## Upgrade Notes

### Upgrading from 0.1.x to 0.2.x

**Database Migration:**
- Database schema changed (added presets table)
- Backup existing database: `cp /data/oct.db /data/oct.db.backup`
- Restart container - schema migrations run automatically

**Configuration Changes:**
- `config.yaml` format updated (see config.example.yaml)
- `CT_*` environment variables renamed to `OCT_*`
- CORS defaults changed from `["*"]` to explicit localhost origins

**API Breaking Changes:**
- `/api/devices/list` renamed to `/api/devices`
- Device ID field changed from `id` to `device_id`

---

## Release Process

Releases are fully automated via GitHub Actions:

1. Go to **Actions → Release → Run workflow**
2. Enter version number (e.g., `1.1.0`)
3. The workflow automatically:
   - Bumps version in all package files
   - Updates this CHANGELOG
   - Creates Git tag and GitHub Release
   - Builds and pushes Docker images (amd64, arm64, arm/v7)
   - Builds Raspberry Pi SD card images
   - Attaches all artifacts to the release

See [UPGRADING.md](UPGRADING.md) for version-specific migration guides.

---

**Maintained by:** OpenCloudTouch Contributors  
**License:** Apache License 2.0  
**Repository:** https://github.com/opencloudtouch/opencloudtouch
