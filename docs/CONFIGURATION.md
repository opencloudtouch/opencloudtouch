# OpenCloudTouch Configuration Guide

**Version**: 0.2.0  
**Last Updated**: 2026-02-11

This document describes all configuration options for OpenCloudTouch backend.

---

## Configuration Methods

OpenCloudTouch supports **3 configuration methods** (in order of precedence):

1. **Environment Variables** (highest priority)
2. **Config File** (`config.yaml`)
3. **Built-in Defaults** (fallback)

Configuration is handled by **Pydantic Settings** with automatic validation.

---

## Environment Variables

All environment variables use the **`OCT_`** prefix to avoid conflicts.

### Core Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OCT_HOST` | string | `0.0.0.0` | API bind address (use `0.0.0.0` for Docker) |
| `OCT_PORT` | int | `7777` | API port |
| `OCT_LOG_LEVEL` | enum | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `OCT_DB_PATH` | path | `/data/oct.db` | SQLite database file path |

### Discovery Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OCT_DISCOVERY_ENABLED` | bool | `true` | Enable SSDP/UPnP auto-discovery |
| `OCT_DISCOVERY_TIMEOUT` | int | `10` | SSDP discovery timeout in seconds |
| `OCT_MANUAL_DEVICE_IPS` | list | `[]` | Comma-separated device IPs (fallback) |

**Example**:
```bash
export OCT_MANUAL_DEVICE_IPS="192.168.178.78,192.168.178.79"
```

### Advanced Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OCT_MOCK_MODE` | bool | `false` | Use mock devices for testing (no real hardware needed) |
| `OCT_CORS_ORIGINS` | list | `["*"]` | Allowed CORS origins (comma-separated) |
| `OCT_MAX_DEVICE_POLL_INTERVAL` | int | `30` | Device status polling interval (seconds) |

---

## Config File (`config.yaml`)

OpenCloudTouch can load configuration from a **YAML file**.

### Using Config File in Docker

**Mount config file as volume**:
```bash
docker run -d \
  --name opencloudtouch \
  --network host \
  -v /path/to/config.yaml:/app/config.yaml:ro \
  -v oct-data:/data \
  opencloudtouch:latest
```

**Mount via Docker Compose**:
```yaml
# docker-compose.yml
services:
  opencloudtouch:
    image: opencloudtouch:latest
    network_mode: host
    volumes:
      - ./config.yaml:/app/config.yaml:ro  # Read-only
      - oct-data:/data
```

### Config File Format

```yaml
# config.yaml - OpenCloudTouch Configuration
# Environment variables take precedence over this file

# Core Settings
host: "0.0.0.0"
port: 7777
log_level: "INFO"
db_path: "/data/oct.db"

# Discovery Settings
discovery:
  enabled: true
  timeout: 10
  manual_ips:
    - "192.168.178.78"
    - "192.168.178.79"

# CORS Settings
cors:
  origins:
    - "http://localhost:5173"  # Vite dev server
    - "https://myapp.example.com"

# Mock Mode (for testing without hardware)
mock_mode: false

# Device Polling
max_device_poll_interval: 30
```

**Loading Priority**:
- `OCT_PORT=8080` (env) **overrides** `port: 7777` (config.yaml)
- `port: 7777` (config.yaml) **overrides** built-in default `7777`

---

## Environment-Specific Configurations

### Development (Local)

```bash
# .env.development
OCT_LOG_LEVEL=DEBUG
OCT_MOCK_MODE=true
OCT_DISCOVERY_ENABLED=false
OCT_MANUAL_DEVICE_IPS=192.168.1.100,192.168.1.101
```

### Production (Docker)

```bash
# docker-compose.yml
environment:
  OCT_LOG_LEVEL: INFO
  OCT_DISCOVERY_ENABLED: true
  OCT_DB_PATH: /data/oct.db
```

### Testing (CI/CD)

```bash
# GitHub Actions / CI
export OCT_MOCK_MODE=true
export OCT_DB_PATH=:memory:
export OCT_LOG_LEVEL=WARNING
```

---

## Configuration Validation

OpenCloudTouch validates configuration **on startup** using Pydantic.

### Valid Configuration
```bash
docker logs opencloudtouch
# [INFO] Environment validation passed
# [INFO] Data directory OK
# [INFO] Database exists
# [INFO] Starting application on 0.0.0.0:7777
```

### Invalid Configuration
```bash
docker run -e OCT_PORT=invalid opencloudtouch:latest
# [ERROR] OCT_PORT must be numeric (got: invalid)
# Exit code: 1
```

---

## Common Configuration Scenarios

### Scenario 1: Change Port

**Environment Variable**:
```bash
docker run -e OCT_PORT=8080 -p 8080:8080 opencloudtouch:latest
```

**Config File**:
```yaml
# config.yaml
port: 8080
```

### Scenario 2: Manual Device IPs (No Discovery)

```bash
docker run \
  -e OCT_DISCOVERY_ENABLED=false \
  -e OCT_MANUAL_DEVICE_IPS="192.168.1.10,192.168.1.20" \
  opencloudtouch:latest
```

### Scenario 3: Debug Logging

```bash
docker run -e OCT_LOG_LEVEL=DEBUG opencloudtouch:latest
```

### Scenario 4: Custom Database Location

```bash
docker run \
  -e OCT_DB_PATH=/data/custom.db \
  -v /my/data:/data \
  opencloudtouch:latest
```

### Scenario 5: Mock Mode (Testing Without Hardware)

```bash
docker run -e OCT_MOCK_MODE=true opencloudtouch:latest
```

---

## Troubleshooting Configuration

### Check Current Configuration

**Via Logs**:
```bash
docker logs opencloudtouch | grep "Starting application"
# [INFO] Starting application on 0.0.0.0:7777
# [INFO] Database: /data/oct.db
# [INFO] Discovery: true
```

**Via API**:
```bash
curl http://localhost:7777/health
# {"status":"healthy","version":"0.2.0"}
```

### Common Issues

**Issue**: "Data directory is not writable"
```bash
# Fix permissions:
docker exec opencloudtouch ls -ld /data
# drwxr-xr-x 2 oct oct 4096 ...
```

**Issue**: "OCT_LOG_LEVEL must be one of: DEBUG, INFO, ..."
```bash
# Valid values only:
export OCT_LOG_LEVEL=INFO  # ✅
export OCT_LOG_LEVEL=info  # ❌ (case-sensitive!)
```

**Issue**: Devices not found
```bash
# Enable debug logging:
docker run -e OCT_LOG_LEVEL=DEBUG opencloudtouch:latest
# Check logs for SSDP discovery details
```

---

## Configuration Reference (Code)

Configuration is defined in: **`apps/backend/src/opencloudtouch/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    """Application configuration with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_prefix="OCT_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    # Core
    host: str = "0.0.0.0"
    port: int = 7777
    log_level: str = "INFO"
    db_path: str = "/data/oct.db"
    
    # Discovery
    discovery_enabled: bool = True
    discovery_timeout: int = 10
    manual_device_ips: list[str] = []
    
    # Mock mode
    mock_mode: bool = False
```

---

## Best Practices

1. **Use Environment Variables in Docker** - Easier to override per deployment
2. **Use Config File for Development** - Track in Git, share with team
3. **Never commit secrets** - Use `.env.local` (in `.gitignore`)
4. **Validate on startup** - Application fails fast on invalid config
5. **Document defaults** - Users should know what happens without config

---

## See Also

- [Deployment Guide](../../deployment/README.md)
- [Environment Variables Example](../../.env.example)
- [Config File Example](../../config.example.yaml)
- [Docker Compose Example](../../deployment/docker-compose.yml)
