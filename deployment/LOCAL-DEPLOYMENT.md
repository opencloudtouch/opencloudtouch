# Local Development Deployment

Quick guide for deploying OpenCloudTouch locally with Podman for UI development and testing.

## Quick Start

```powershell
# Deploy with mock devices (default)
.\deployment\deploy-local.ps1

# Access UI
http://localhost:7777
```

## Features

### Mock Mode (Default)
- **Enabled by default** for local development
- Provides 3 fake devices:
  - ST10 - "Living Room"
  - ST30 - "Schlafzimmer"  
  - ST300 - "Küche"
- No real device discovery (SSDP/UPnP skipped)
- Allows testing UI without real hardware

### Parameters

```powershell
# Rebuild without cache
.\deployment\deploy-local.ps1 -NoCache

# Skip image build (use existing)
.\deployment\deploy-local.ps1 -SkipBuild

# Disable mock mode (use real discovery)
.\deployment\deploy-local.ps1 -MockMode:$false

# Custom port
.\deployment\deploy-local.ps1 -Port 8080

# Verbose output
.\deployment\deploy-local.ps1 -Verbose
```

## Container Management

```powershell
# View logs (follow)
podman logs opencloudtouch-local -f

# Stop container
podman stop opencloudtouch-local

# Restart container
podman restart opencloudtouch-local

# Remove container
podman rm -f opencloudtouch-local

# Remove container + data
podman rm -f opencloudtouch-local
Remove-Item -Recurse -Force .\data-local
```

## API Endpoints

With mock mode enabled:

```powershell
# Health check (shows mock_mode: true)
Invoke-RestMethod http://localhost:7777/health

# Discover devices (returns 3 mock devices)
Invoke-RestMethod http://localhost:7777/api/devices/discover

# Sync devices to database
Invoke-RestMethod http://localhost:7777/api/devices/sync -Method POST

# List devices
Invoke-RestMethod http://localhost:7777/api/devices
```

## Development Workflow

1. **Make changes** to frontend or backend code
2. **Rebuild + Redeploy**:
   ```powershell
   podman rm -f opencloudtouch-local
   .\deployment\deploy-local.ps1
   ```
   Frontend is automatically built during Docker image build — no separate build step needed.
3. **Test UI** at http://localhost:7777
4. **View logs** for debugging:
   ```powershell
   podman logs opencloudtouch-local -f
   ```

## Mock vs. Real Devices

| Feature | Mock Mode | Real Mode |
|---------|-----------|-----------|
| Discovery | 3 fake devices | SSDP + Manual IPs |
| Device Info | Static mock data | HTTP queries to devices |
| UI Testing | ✅ Full UI testable | ✅ Full UI testable |
| Device Control | ❌ Not possible | ✅ Full control |
| Network Required | ❌ No | ✅ Yes |

## Troubleshooting

### Container won't start
```powershell
# Check logs
podman logs opencloudtouch-local

# Check if port is already in use
netstat -ano | findstr :7777

# Use different port
.\deployment\deploy-local.ps1 -Port 8080
```

### UI shows no devices
```powershell
# Trigger sync manually
Invoke-RestMethod http://localhost:7777/api/devices/sync -Method POST

# Verify mock mode is enabled
Invoke-RestMethod http://localhost:7777/health
# → Should show "mock_mode": true
```

### Database persistence
- Local database: `.\data-local\ct.db`
- Survives container restarts
- Delete `data-local` folder to reset

## Notes

- **Mock mode** is intended for UI development only
- To test real device interaction, use `-MockMode:$false` and ensure devices are on network
- Log level is DEBUG by default for local deployment
- Frontend build artifacts are included in Docker image
