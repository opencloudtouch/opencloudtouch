# Deployment Scripts

All deployment related files for OpenCloudTouch container deployment.

> **Trademark Notice**: OpenCloudTouch (OCT) is not affiliated with Bose Corporation. Bose® and SoundTouch® are registered trademarks of Bose Corporation. See [TRADEMARK.md](../TRADEMARK.md) for details.

## 📁 Files

- **docker-compose.yml**: Docker Compose Konfiguration für Development
- **Dockerfile**: Root-Dockerfile (`../Dockerfile`) is used by compose


> Note: PowerShell deploy scripts are located at `tools/local-scripts/`.

## 🚀 Usage

### Local Development

```bash
# Start Docker compose (builds frontend automatically)
cd deployment/
docker-compose up --build

# OR: Podman lokal
look `tools/local-scripts/` (z. B. `run-container.ps1`)
```

**Note**: The Docker build now includes frontend compilation from source. No pre-build step required — just `docker-compose up --build` works out of the box.

### NAS/Server Deployment

```bash
cd deployment/
.\deploy-to-server.ps1
```

**Prerequisites**:
- PowerShell 7+
- SSH-Zugriff zu Target Server (user@targethost)
- Podman (für export-image.ps1)
- Docker (für docker-compose)

## 📝 Build Context

All scripts use the following paths (relative to `deployment/`):

```
deployment/
├── docker-compose.yml      → context: .., dockerfile: Dockerfile
├── export-image.ps1        → podman build -t opencloudtouch:latest ..
├── run-container.ps1       → podman build -f ../Dockerfile ..
└── deploy-to-server.ps1    → calls export-image.ps1
```

**Build Context**: `..` (Parent directory = Repository Root)  
**Dockerfile**: `../Dockerfile`

## 🔧 Configuration

### Environment Variables

```bash
# SSDP Discovery
OCT_DISCOVERY_TIMEOUT=10

# Manual Device IPs (if SSDP doesn't work)
OCT_MANUAL_DEVICE_IPS="192.168.1.100,192.168.1.101"

# Logging
OCT_LOG_LEVEL=INFO

# Database
OCT_DB_PATH=/data/oct.db
```

### Ports

- **Backend API**: 7777 (default)
- **Frontend**: Embedded in Backend (at Multi-stage Build)

### Volumes

- **data/**: SQLite DB, Config, Logs
- **config.yaml**: Optional (Overwrites Env Vars)

## 🧪 Testing

```bash
# Build Image (without start)
.\export-image.ps1

# Start Container (with Build)
siehe `tools/local-scripts/` (z. B. `run-container.ps1`)iner.ps1

# Start Container (without Build, existing image)
siehe `tools/local-scripts/` (z. B. `run-container.ps1`)iner.ps1 -NoBuild
```

## 🛠️ Troubleshooting

### Build Errors

```bash
# Podman: Build mit --no-cache
.\export-image.ps1 -NoCache

# Docker Compose: Clean rebuild
docker-compose build --no-cache
```

### SSDP Discovery funktioniert nicht

Windows Container don`t support SSDP:
```bash
# Use Manual IPs
siehe `tools/local-scripts/` (z. B. `run-container.ps1`)iner.ps1 -ManualIPs "192.168.1.100,192.168.1.101"
```

### Server SSH Errors

```bash
# SSH test connection
ssh user@targethost "docker version"

# Check Podman Container
ssh user@targethost "docker ps -a | grep opencloudtouch"
```

## 📄 Related Docs

- [Main README](../README.md): Project Overview
- [Backend README](../apps/backend/README.md): Backend Docs
- [SERVER-DEPLOYMENT.md](../SERVER-DEPLOYMENT.md): Server Deployment Guide
