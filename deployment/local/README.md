# Local Deployment Scripts

**⚠️ This directory is gitignored - your personal scripts stay private!**

This folder contains **your personal deployment scripts** for your specific environment (TrueNAS, Docker, hosts, etc.).

Other developers will have their own `deployment/local/` with different configs.

---

## What Goes Here?

✅ **Personal deployment scripts:**
- `deploy-to-server.ps1` - Deploy to your remote server
- `deploy-local.ps1` - Run locally on your machine
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

### Use Environment Variables

```powershell
# deployment/local/.env (gitignored!)
NAS_HOST=truenas.home.local
NAS_USER=admin
NAS_PATH=/mnt/pool/apps/opencloudtouch

# Load in script:
Get-Content .env | ForEach-Object {
    $key, $val = $_ -split '=', 2
    Set-Item -Path "env:$key" -Value $val
}
```

### SSH Key Authentication

```bash
# Avoid password prompts
ssh-keygen -t ed25519 -f ~/.ssh/nas_deploy_key
ssh-copy-id -i ~/.ssh/nas_deploy_key.pub user@nas.local

# Use in scripts
ssh -i ~/.ssh/nas_deploy_key user@nas.local "podman ps"
```

### Test Before Deploy

```powershell
# Dry run mode
param([switch]$DryRun)

if ($DryRun) {
    Write-Host "Would deploy to: $NasHost" -ForegroundColor Yellow
    Write-Host "Would run: podman run ..." -ForegroundColor Yellow
    exit 0
}

# Actual deployment...
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
