# Changelog

All notable changes to OpenCloudTouch are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_No changes yet._

---

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
