# Local Deployment Scripts

**ℹ️ Scripts are versioned in Git, configuration is in `.env` (gitignored)**

This folder contains deployment scripts for remote server deployment. Each developer configures their own `.env` file.

---

## Quick Start

### 1. Create Your Configuration

```powershell
# Copy template to .env
cp .env.template .env

# Edit .env with your infrastructure
notepad .env  # Windows
nano .env     # Linux/Mac
```

### 2. Configure Your Infrastructure

```bash
# .env file (this is YOUR personal config, gitignored!)
DEPLOY_HOST=your-server-hostname
DEPLOY_USER=your-username
REMOTE_DATA_PATH=/path/to/container/data
CONTAINER_PORT=7777
```
- `export-image.ps1` - Export Docker image
- `clear-database.ps1` - Clear your local DB
- `run-e2e-tests-remote.ps1` - Test on remote server

✅ **Personal configs:**
- `hosts.txt` - Your server IPs
- `credentials.env` - Your SSH keys/passwords
- `docker-compose.override.yml` - Local Docker tweaks

❌ **DON'T put here:**
- Shared configs (use root `config.example.yaml`)
- Generic scripts useful for all devs (use `scripts/` or npm scripts)

---

## Examples for New Developers

### Example 1: Deploy to Remote Server (PowerShell)

```powershell
# deployment/local/deploy-to-server.ps1
param(
    [string]$NasHost = "your-nas.local",
    [string]$NasUser = "yourusername"
)

# Build image
docker build -t opencloudtouch:latest .

# Export image
docker save opencloudtouch:latest -o opencloudtouch.tar

# Upload to NAS
scp opencloudtouch.tar $NasUser@${NasHost}:/mnt/pool/apps/opencloudtouch/

# Load and run on NAS
ssh $NasUser@$NasHost @"
    podman load < /mnt/pool/apps/opencloudtouch/opencloudtouch.tar
    podman stop opencloudtouch || true
    podman rm opencloudtouch || true
    podman run -d --name opencloudtouch -p 7777:7777 opencloudtouch:latest
"@

Write-Host "Deployed to http://${NasHost}:7777" -ForegroundColor Green
```

### Example 2: Deploy to Docker Compose

```yaml
# deployment/local/docker-compose.override.yml
services:
  opencloudtouch:
    environment:
      - OCT_MANUAL_DEVICE_IPS=192.168.1.100,192.168.1.101
      - OCT_LOG_LEVEL=DEBUG
    volumes:
      - ./data-local:/app/data
    ports:
      - "7777:7777"
```

```bash
# Run with override
docker-compose -f ../docker-compose.yml -f docker-compose.override.yml up
```

### Example 3: Clear Local Database

```powershell
# deployment/local/clear-database.ps1
$DbPath = "../../data-local/oct.db"

if (Test-Path $DbPath) {
    Remove-Item $DbPath -Force
    Write-Host "Database cleared: $DbPath" -ForegroundColor Green
} else {
    Write-Host "No database found at: $DbPath" -ForegroundColor Yellow
}
```

### Example 4: Export Image for Offline Install

```powershell
# deployment/local/export-image.ps1
param(
    [string]$OutputPath = "opencloudtouch-image.tar"
)

docker build -t opencloudtouch:latest .
docker save opencloudtouch:latest -o $OutputPath

$size = (Get-Item $OutputPath).Length / 1MB
Write-Host "Exported: $OutputPath ($([math]::Round($size, 2)) MB)" -ForegroundColor Green
```

---

## Getting Started

1. **Copy your existing scripts** from `tools/local-scripts/` here:
   ```powershell
   Copy-Item ../../tools/local-scripts/deploy-*.ps1 .
   Copy-Item ../../tools/local-scripts/export-image.ps1 .
   Copy-Item ../../tools/local-scripts/clear-database.ps1 .
   ```

2. **Customize for your environment:**
   - Update hostnames, IPs, paths
   - Add your credentials (use env vars or .env files)
   - Test locally before running on servers

3. **Keep it simple:**
   - One script per task
   - Document what it does
   - Use parameters for flexibility

---

## Tips

## Available Configuration Options

See [.env.template](.env.template) for all available options:

```bash
# Remote Server
DEPLOY_HOST=server-hostname
DEPLOY_USER=username
DEPLOY_USE_SUDO=false

# Container Settings
CONTAINER_NAME=opencloudtouch
CONTAINER_TAG=opencloudtouch:latest

# Paths
REMOTE_DATA_PATH=/path/to/container/data
REMOTE_IMAGE_PATH=/tmp
LOCAL_DATA_PATH=./deployment/data-local

# Network
CONTAINER_PORT=7777

# Optional: Manual Device IPs
MANUAL_DEVICE_IPS=192.168.1.100,192.168.1.101
```

---

## Deployment Scripts

### deploy-to-server.ps1

Deploy to remote server via SSH (uses .env configuration).

```powershell
.\deploy-to-server.ps1              # Full build + deploy
.\deploy-to-server.ps1 -SkipBuild   # Use existing image
.\deploy-to-server.ps1 -UseSudo     # Use sudo for docker
```

### deploy-local.ps1

Deploy locally using Podman (Windows WSL2 + Rootful mode).

```powershell
.\deploy-local.ps1                   # Full build + deploy
.\deploy-local.ps1 -SkipBuild        # Use existing image
```

### clear-database.ps1

Clear database on remote server.

```powershell
.\clear-database.ps1                 # Uses .env config
```

### export-image.ps1

Export Docker image to tar file for manual transfer.

```powershell
.\export-image.ps1                   # Creates opencloudtouch-image.tar
```

---

## SSH Key Authentication

Avoid password prompts in deployment:

```bash
# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/deploy_key

# Copy to remote server
ssh-copy-id -i ~/.ssh/deploy_key.pub user@server

# Test connection
ssh -i ~/.ssh/deploy_key user@server "docker ps"
```

Add to `.ssh/config` for easier access:

```
Host myserver
  HostName server.example.com
  User deployuser
  IdentityFile ~/.ssh/deploy_key
```

Then use hostname in `.env`:

```bash
DEPLOY_HOST=myserver
```

---

## Troubleshooting

### "Permission denied" on SSH
```bash
# Add your key to ssh-agent
ssh-add ~/.ssh/nas_deploy_key
```

### "Port already in use"
```powershell
# Find and kill process on port 7777
$proc = Get-NetTCPConnection -LocalPort 7777 -ErrorAction SilentlyContinue
if ($proc) {
    Stop-Process -Id $proc.OwningProcess -Force
}
```

### "Image not found"
```bash
# Verify Docker build
docker images | grep opencloudtouch

# Rebuild
npm run docker:build
```

---

## Resources

- [Docker Compose Override Docs](https://docs.docker.com/compose/extends/)
- [Podman Rootless Containers](https://podman.io/getting-started/)
- [PowerShell Remoting over SSH](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/ssh-remoting-in-powershell)

---

**Remember:** These are YOUR personal scripts. Customize freely, but don't commit! 🔒
