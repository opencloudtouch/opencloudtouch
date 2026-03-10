# Changelog

All notable changes to OpenCloudTouch are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_No changes yet._

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
**Repository:** https://github.com/scheilch/opencloudtouch
