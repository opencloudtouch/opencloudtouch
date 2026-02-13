# Changelog

All notable changes to OpenCloudTouch are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Trivy container security scanning in CI/CD pipeline
- Dependabot configuration for automated dependency updates
- API documentation (docs/API.md)
- Troubleshooting guide (docs/TROUBLESHOOTING.md)
- Security policy (SECURITY.md)
- This changelog

### Changed
- Dependency injection migrated from global singletons to FastAPI app.state
- Pinned all dependencies to exact versions in pyproject.toml
- Added `pythonpath = src` to pytest.ini for CI compatibility

### Fixed
- Frontend type safety: replaced 'any' type with RawStationData interface
- CORS configuration now uses explicit default origins instead of wildcard
- SQLite index name collision between devices and presets tables
- RadioStation model consolidated into single source in radio/models.py
- XML namespace handling in SSDP discovery
- Indentation bug in IDeviceSyncService protocol
- Database filename typo in config.example.yaml (ct.db → oct.db)

### Security
- Enabled container vulnerability scanning (Trivy)
- Documented security considerations and threat model
- Added Dependabot for automated security updates

---

## [0.2.0] - 2026-02-01

### Added
- SSDP device discovery for automatic SoundTouch detection
- Preset management supporting slots 1-6
- RadioBrowser.info integration for internet radio search
- Manual device IP configuration for networks without multicast
- Multiroom group detection and display
- Volume control with debouncing
- Now playing information display
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
- Now playing information from SoundTouch API
- Simple web interface for device control
- Docker deployment support

### Known Issues
- No automatic device discovery (manual IP configuration required)
- Limited error handling in device communication
- No preset management

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
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

1. Update version in `apps/backend/pyproject.toml`
2. Update version in `apps/frontend/package.json`
3. Update this CHANGELOG.md (move Unreleased → new version)
4. Commit: `git commit -m "chore(release): bump version to vX.Y.Z"`
5. Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
6. Push: `git push && git push --tags`
7. GitHub Actions builds and publishes container image

---

**Maintained by:** OpenCloudTouch Contributors  
**License:** MIT  
**Repository:** https://github.com/yourorg/opencloudtouch
