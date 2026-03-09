# Upgrade Guide

This guide helps you upgrade between OpenCloudTouch versions.

---

## Upgrading to v1.0.0 (from v0.2.x)

### What's New

- **Setup Wizard** — Guided device configuration (manual + guided mode)
- **1500+ tests** — Comprehensive test suite (backend, frontend, E2E)
- **Multi-arch Docker images** — amd64, arm64, arm/v7
- **Raspberry Pi SD card images** — Pre-built images for Pi 3/4/5
- **Security scanning** — Trivy container scanning in CI/CD
- **Automated dependency updates** — Dependabot for Python + npm
- **Full documentation** — GitHub Wiki with bilingual pages (DE/EN)

### Docker Upgrade

```bash
# Pull new version
docker pull ghcr.io/scheilch/opencloudtouch:1.0.0

# Stop old container
docker stop opencloudtouch
docker rm opencloudtouch

# Start with new image
docker run -d \
  --name opencloudtouch \
  --network host \
  -v opencloudtouch-data:/data \
  -e OCT_DISCOVERY_ENABLED=true \
  ghcr.io/scheilch/opencloudtouch:1.0.0
```

### Docker Compose Upgrade

```bash
# Update image tag in docker-compose.yml to 1.0.0 (or "stable")
# Then:
docker compose pull
docker compose up -d
```

### Configuration Changes

| Setting | v0.2.x | v1.0.0 | Action |
|---------|--------|--------|--------|
| Env prefix | `OCT_*` | `OCT_*` | No change |
| Database | `/data/oct.db` | `/data/oct.db` | No change |
| Config file | `config.yaml` | `config.yaml` | No change |
| Default port | 7777 | 7777 | No change |

**No breaking changes** in v1.0.0. Your existing configuration and database will work without modifications.

### Database

- Schema migrations run automatically on startup
- Recommended: Back up before upgrading

```bash
# Backup (Docker volume)
docker cp opencloudtouch:/data/oct.db ./oct.db.backup

# Or if using bind mount
cp /path/to/data/oct.db /path/to/data/oct.db.backup
```

### Raspberry Pi

If using the SD card image:

1. Download the new `.img.xz` from the [Releases page](https://github.com/scheilch/opencloudtouch/releases)
2. Back up your data: `ssh oct@opencloudtouch "cp /data/oct.db /data/oct.db.backup"`
3. Flash new image to SD card
4. Boot and restore data if needed

---

## Upgrading to v0.2.0 (from v0.1.x)

### Breaking Changes

**API Changes:**
- `/api/devices/list` → `/api/devices`
- Device ID field: `id` → `device_id`

**Configuration Changes:**
- Environment variables renamed: `CT_*` → `OCT_*`
- CORS defaults changed from `["*"]` to explicit localhost origins
- Database filename: `ct.db` → `oct.db`

### Database Migration

```bash
# Backup existing database
cp /data/ct.db /data/oct.db.backup

# Rename (if using old filename)
mv /data/ct.db /data/oct.db

# Restart — schema migrations run automatically
docker restart opencloudtouch
```

### Configuration Migration

```bash
# Rename environment variables
# Old: CT_HOST, CT_PORT, CT_DB_PATH
# New: OCT_HOST, OCT_PORT, OCT_DB_PATH

# Update docker-compose.yml or docker run command
```

---

## General Upgrade Tips

1. **Always back up** your database before upgrading
2. **Check the [CHANGELOG](CHANGELOG.md)** for breaking changes
3. **Use specific version tags** (e.g., `1.0.0`) instead of `latest` in production
4. **Test first** by running the new version alongside the old one on a different port
5. **Check health endpoint** after upgrade: `curl http://localhost:7777/health`

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 1.0.0 | 2026-03-09 | Setup Wizard, Multi-arch Docker, RasPi images, 1500+ tests |
| 0.2.0 | 2026-02-01 | SSDP discovery, presets, radio search, Clean Architecture |
| 0.1.0 | 2026-01-15 | Initial release, basic device control |

---

**Need help?** Open an [issue](https://github.com/scheilch/opencloudtouch/issues) or check the [Wiki](https://github.com/scheilch/opencloudtouch/wiki).
