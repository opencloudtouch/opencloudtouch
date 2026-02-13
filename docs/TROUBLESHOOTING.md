# Troubleshooting Guide

Common issues and solutions for OpenCloudTouch deployment and operation.

---

## Device Discovery Issues

### No devices found

**Symptoms:**
- `GET /api/devices/discover` returns empty array
- UI shows "No devices found" after discovery
- Backend logs show `INFO: SSDP discovery complete: 0 devices found`

**Causes:**
1. **Network isolation:** Container not on same subnet as SoundTouch devices
2. **Multicast blocked:** Firewall or router blocking SSDP (UDP port 1900)
3. **WSL2 NAT mode:** Windows Subsystem for Linux uses NAT networking by default
4. **Docker bridge networking:** Container isolated from host network

**Solutions:**

#### Solution 1: Use host networking (Linux/Podman)
```bash
podman run --network host opencloudtouch:latest
```

#### Solution 2: WSL2 Mirrored Networking (Windows)
```ini
# File: %USERPROFILE%\.wslconfig
[wsl2]
networkingMode=mirrored
memory=4GB

[experimental]
hostAddressLoopback=true
```

Then restart WSL:
```powershell
wsl --shutdown
wsl
```

#### Solution 3: Windows Firewall Rule for SSDP
```powershell
New-NetFirewallRule -DisplayName "OpenCloudTouch SSDP Discovery" `
  -Direction Inbound `
  -Action Allow `
  -Protocol UDP `
  -LocalPort 1900 `
  -Program "System"
```

#### Solution 4: Fallback to Manual IPs
```bash
# Environment variable
OCT_MANUAL_DEVICE_IPS="192.168.1.100,192.168.1.101"

# Or via UI: Settings → Manual Device IPs
```

---

### Discovery finds devices but sync fails

**Symptoms:**
- `POST /api/devices/discover` returns devices
- `POST /api/devices/sync` fails with 500 error
- Logs show `ERROR: Failed to fetch device info from http://<ip>:8090/info`

**Causes:**
1. Device HTTP API (port 8090) not responding
2. Device firmware too old or unsupported
3. Network firewall blocking port 8090

**Diagnosis:**
```bash
# Test device API directly
curl http://<device-ip>:8090/info

# From inside container
podman exec opencloudtouch curl http://<device-ip>:8090/info
```

**Solutions:**
- Ensure device firmware is up-to-date (minimum: v4.5+)
- Check firewall rules allow TCP port 8090
- Verify device is on same subnet

---

## Container Issues

### Container won't start

**Symptoms:**
- `podman start opencloudtouch` fails immediately
- Container status shows "Exited (1)"

**Diagnosis:**
```bash
podman logs opencloudtouch
```

**Common errors and fixes:**

#### Error: `Address already in use (port 7777)`
Another process is using the port.

```bash
# Find process using port
netstat -tulpn | grep 7777

# Kill it or change OCT port
podman run -e OCT_PORT=8888 -p 8888:8888 opencloudtouch:latest
```

#### Error: `Permission denied: /data/oct.db`
Volume permissions issue.

```bash
# Fix permissions
sudo chown -R 1000:1000 /path/to/data-volume

# Or use rootful container
podman run --user root opencloudtouch:latest
```

#### Error: `Python module not found`
Corrupted image or failed build.

```bash
# Rebuild image
podman build -t opencloudtouch:latest .

# Or pull fresh image
podman pull ghcr.io/yourorg/opencloudtouch:latest
```

---

### Database locked error

**Symptoms:**
- `SQLite database is locked` errors in logs
- Operations hang or timeout

**Cause:**
Multiple container instances accessing same database file.

**Solution:**
```bash
# Stop all containers
podman stop opencloudtouch
podman rm opencloudtouch

# Restart single instance
podman run -d --name opencloudtouch \
  -v /path/to/data:/data \
  -p 7777:7777 \
  opencloudtouch:latest
```

---

### Container logs show WebSocket errors

**Symptoms:**
```
ERROR: WebSocket connection failed to ws://<device-ip>:8080/
```

**Cause:**
SoundTouch devices use WebSocket for real-time updates (now playing, volume changes).

**Impact:**
- Device control still works (HTTP API)
- Real-time updates won't work

**Solution:**
- Ensure port 8080 (WebSocket) is not blocked
- Check device supports WebSocket API (firmware 4.0+)

---

## Frontend Issues

### UI shows loading spinner forever

**Symptoms:**
- Frontend loads but displays infinite loading state
- No devices appear even after discovery

**Diagnosis:**
1. Open browser DevTools (F12) → Console tab
2. Check for error messages

**Common causes:**

#### CORS errors
```
Access to fetch at 'http://localhost:7777/api/devices' from origin 'http://localhost:5173' has been blocked by CORS policy
```

**Solution:**
```yaml
# config.yaml
cors_origins:
  - "http://localhost:5173"
  - "http://localhost:3000"
```

#### Backend not running
```
Failed to fetch: net::ERR_CONNECTION_REFUSED
```

**Solution:**
```bash
# Check backend health
curl http://localhost:7777/health

# If fails, start backend
cd apps/backend
source .venv/bin/activate
uvicorn opencloudtouch.main:app --host 0.0.0.0 --port 7777
```

#### Wrong backend URL in frontend
Check `apps/frontend/.env`:
```bash
VITE_API_BASE_URL=http://localhost:7777
```

---

### Presets not saving

**Symptoms:**
- Clicking "Save to Preset" button shows success toast
- Preset appears empty after page reload

**Diagnosis:**
```bash
# Check backend logs for errors
podman logs opencloudtouch | grep ERROR

# Test preset API directly
curl -X PUT http://localhost:7777/api/devices/<device-id>/presets/1 \
  -H "Content-Type: application/json" \
  -d '{"station_name":"Test","station_url":"http://test.com/stream"}'
```

**Common causes:**
1. Device communication failure
2. Database write error
3. Preset number out of range (must be 1-6)

**Solution:**
- Verify device is online: `curl http://<device-ip>:8090/presets`
- Check database file is writable: `ls -la /data/oct.db`

---

### Radio search returns no results

**Symptoms:**
- Searching for stations shows empty results
- Backend logs show `INFO: Radio search: query='test' results=0`

**Diagnosis:**
```bash
# Test RadioBrowser.info API directly
curl "https://de1.api.radio-browser.info/json/stations/search?name=BBC"
```

**Causes:**
1. RadioBrowser.info API down (rare)
2. Network proxy blocking HTTPS requests
3. DNS resolution failure

**Solution:**
- Check internet connectivity from container
- Try different search terms (search by country instead)
- Wait and retry (API may be temporarily unavailable)

---

## Network Issues

### Container can't reach devices on LAN

**Symptoms:**
- Discovery fails
- Device API calls timeout
- Works on host but not in container

**Diagnosis:**
```bash
# From container
podman exec -it opencloudtouch bash

# Test network
ping 192.168.1.100
curl http://192.168.1.100:8090/info
```

**Solutions:**

#### Use host networking
```bash
podman run --network host opencloudtouch:latest
```

#### Create macvlan network (advanced)
```bash
podman network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  -o parent=eth0 \
  soundtouch-network

podman run --network soundtouch-network opencloudtouch:latest
```

---

## Performance Issues

### Slow API responses

**Symptoms:**
- Frontend UI feels sluggish
- API calls take >2 seconds

**Diagnosis:**
```bash
# Check backend logs for slow queries
podman logs opencloudtouch | grep "Slow request"

# Test API response time
time curl http://localhost:7777/api/devices
```

**Solutions:**
- Reduce device count (large multiroom setups)
- Check database file size: `ls -lh /data/oct.db`
- Restart container to clear memory

---

### High memory usage

**Symptoms:**
- Container uses >500MB RAM
- System becomes unresponsive

**Diagnosis:**
```bash
podman stats opencloudtouch
```

**Solutions:**
- Limit container memory: `podman run -m 512m opencloudtouch:latest`
- Check for memory leaks in logs
- Restart container

---

## Configuration Issues

### Environment variables not applied

**Symptoms:**
- Settings in `.env` file ignored
- Config values don't match expectations

**Diagnosis:**
```bash
# Check loaded config
curl http://localhost:7777/api/system/info
```

**Solutions:**

#### Verify ENV variable prefix
All variables must start with `OCT_`:
```bash
OCT_LOG_LEVEL=DEBUG
OCT_MANUAL_DEVICE_IPS="192.168.1.100"
```

#### Check config file precedence
Priority (highest to lowest):
1. Environment variables
2. `config.yaml` in container
3. Default values

#### Restart after config changes
```bash
podman restart opencloudtouch
```

---

## Debugging Tools

### Enable debug logging

```bash
# Environment variable
OCT_LOG_LEVEL=DEBUG

# Or in config.yaml
log_level: DEBUG
```

### View structured logs

```bash
# All logs
podman logs opencloudtouch -f

# Filter errors only
podman logs opencloudtouch 2>&1 | grep ERROR

# Filter device operations
podman logs opencloudtouch 2>&1 | grep "device"
```

### Test SSDP discovery manually

```bash
# From host (requires Python)
cd apps/backend
source .venv/bin/activate
python -m opencloudtouch.devices.discovery.ssdp
```

---

## Getting Help

If issues persist:

1. **Check existing issues:** https://github.com/yourorg/opencloudtouch/issues
2. **Create new issue** with:
   - OpenCloudTouch version
   - Container logs (`podman logs opencloudtouch`)
   - Device model and firmware version
   - Network topology (Docker/Podman/WSL2/bare metal)

3. **Include diagnostics:**
   ```bash
   # Health check
   curl http://localhost:7777/health
   
   # System info
   curl http://localhost:7777/api/system/info
   
   # Container status
   podman inspect opencloudtouch
   ```
