# TLS & Certificates — Custom CA for SoundTouch Devices

SoundTouch devices communicate with Bose cloud over HTTPS.
For local service replacement, devices must trust your custom Root CA.

## The Problem

When you redirect Bose domains (via `/etc/hosts` or XML config) to a local server:
1. Device expects HTTPS on port 443
2. Your local server's certificate is not signed by a trusted CA
3. **TLS handshake fails** → device refuses to connect

---

## TLS Compatibility

SoundTouch speakers run **OpenSSL 1.0.2** — supports up to TLS 1.2.

| Property | Value |
|----------|-------|
| Min TLS | 1.2 |
| Cipher suites | `ECDHE-RSA-AES128-GCM-SHA256`, `ECDHE-RSA-AES256-GCM-SHA384`, `ECDHE-RSA-CHACHA20-POLY1305` |
| Legacy support | `RSA-AES128-GCM-SHA256`, `RSA-AES256-GCM-SHA384` |
| Key type | RSA |

---

## Solution: Custom CA Certificate

### Step 1: Generate Root CA and Server Certificate

Generate a Root CA, then issue a certificate covering all Bose cloud hostnames:

**Required domain coverage** (Subject Alternative Names):
- Wildcards: `*.api.bose.io`, `*.api.bosecm.com`
- Specific: `streaming.bose.com`, `worldwide.bose.com`, `content.api.bose.io`,
  `events.api.bosecm.com`, `voice.api.bose.io`, `bose-prod.apigee.net`,
  `media.bose.io`, `downloads.bose.com`, `oauth.streaming.bose.com`
- Your local hostname (e.g. `soundtouch.fritz.box`)

### Step 2: Inject CA into Device Trust Store

#### Via SSH (manual)

```bash
# Copy CA to device
scp ca.crt root@<SPEAKER-IP>:/tmp/

# Make filesystem writable and append to trust store
ssh root@<SPEAKER-IP> "(rw || mount -o remount,rw /) && \
  cat /tmp/ca.crt >> /etc/pki/tls/certs/ca-bundle.crt"
```

#### Trust Store Locations

| Method | Path | Notes |
|--------|------|-------|
| Append to bundle | `/etc/pki/tls/certs/ca-bundle.crt` | Simplest, but firmware update may overwrite |
| Symlink in certs dir | `/etc/ssl/certs/` + hash symlink | More robust, needs `c_rehash` |
| Custom directory | `/usr/share/ca-certificates/custom/` | Clean separation |

### Step 3: Verify Connectivity

After injecting the CA, test from the device:
```bash
ssh root@<SPEAKER-IP> "curl -v https://streaming.bose.com/"
```
Should show successful TLS handshake with your local server.

---

## Binding to Port 443

Speakers expect HTTPS on the **default port 443**. Options:

### 1. Port Forwarding (recommended)
Run service on port 8443, forward 443 → 8443 via iptables/firewall.

### 2. Linux Capabilities
```bash
sudo setcap 'cap_net_bind_service=+ep' ./soundtouch-service
```

### 3. Reverse Proxy (Nginx)
```nginx
server {
    listen 443 ssl;
    server_name streaming.bose.com content.api.bose.io events.api.bosecm.com worldwide.bose.com;

    ssl_certificate /path/to/server.crt;
    ssl_certificate_key /path/to/server.key;
    ssl_protocols TLSv1.2;
    ssl_ciphers 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384';

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Alternative: Skip SSL Verification (not recommended)

If you cannot manage certificates, binary-patch the device to skip verification:
- **Target**: `libBmxAccountHsm.so` or `BoseApp`
- **Mechanism**: Force SSL verification function to return "success" unconditionally
- **Risk**: Breaks all TLS security, higher brick risk

---

## Certificates to Extract from Real Devices

For research and emulation, extract these from a working device:

| File | Location | Purpose |
|------|----------|---------|
| IoT client cert | `/mnt/nv/IoTCerts/iot-cert.pem.crt` | Device's AWS IoT identity |
| IoT private key | `/mnt/nv/IoTCerts/iot-private.pem.key` | Device's private key |
| AWS Root CA | `/var/lib/iot/rootCA.crt` | AWS IoT CA for MQTT |
| System trust store | `/etc/pki/tls/certs/ca-bundle.crt` | All trusted CAs |

```bash
# Extract all certificates
mkdir -p ./device-certs
scp root@<DEVICE-IP>:/mnt/nv/IoTCerts/iot-cert.pem.crt ./device-certs/
scp root@<DEVICE-IP>:/mnt/nv/IoTCerts/iot-private.pem.key ./device-certs/
scp root@<DEVICE-IP>:/var/lib/iot/rootCA.crt ./device-certs/
scp root@<DEVICE-IP>:/etc/pki/tls/certs/ca-bundle.crt ./device-certs/
```

---

## Warnings

1. **Firmware updates** may reset `ca-bundle.crt` → re-inject CA after updates
2. **Private keys** are device-specific — each device has its own
3. **Certificate registration** at `voice.api.bose.io/alexa/certificate` may stop working after cloud shutdown
4. **Backup everything** before modifying the trust store
