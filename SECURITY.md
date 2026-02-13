# Security Policy

## Supported Versions

Security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting Vulnerabilities

**DO NOT** create public GitHub issues for security vulnerabilities.

Instead, please report security issues privately by emailing:

**security@opencloudtouch.org** *(replace with actual contact)*

You should receive a response within 48 hours. If the issue is confirmed, we will:

1. Develop a fix in a private repository
2. Release a security patch
3. Publish a security advisory
4. Credit you in the release notes (if desired)

---

## Security Considerations

### Threat Model

OpenCloudTouch is designed for **trusted local networks only**:

- ✅ **In-scope:** Home LAN, private network
- ❌ **Out-of-scope:** Public internet, untrusted networks

**Assumption:** All devices on the LAN are trusted.

---

### Network Exposure

#### No Authentication

OpenCloudTouch **does not implement authentication**. This is intentional:

- Target use case: Single household/LAN
- SoundTouch devices themselves have no authentication
- Adding auth would complicate local control

**⚠️ WARNING:** Never expose OpenCloudTouch directly to the internet without reverse proxy authentication.

#### CORS Configuration

Default CORS origins allow local development:

```yaml
cors_origins:
  - "http://localhost:3000"
  - "http://localhost:5173"
  - "http://localhost:7777"
```

**Production:** Update `config.yaml` to restrict origins:

```yaml
cors_origins:
  - "http://truenas.local:7777"
  - "http://192.168.1.50:7777"
```

**Never use `["*"]` in production** - this allows any origin to access your API.

---

### Container Security

#### Non-Root User

Container runs as UID 1000 (non-root):

```dockerfile
RUN adduser --disabled-password --gecos '' --uid 1000 octouch
USER octouch
```

#### Read-Only Filesystem

Recommended deployment uses read-only root filesystem:

```bash
podman run --read-only \
  -v /data/oct:/data:rw \
  opencloudtouch:latest
```

Only `/data` volume needs write access.

#### Minimal Attack Surface

- Exposed port: **7777 only** (HTTP API + frontend)
- No SSH, no shell access by default
- Minimal base image (python:3.11-slim-bookworm)

---

### Dependency Security

#### Automated Scanning

- **Dependabot:** Weekly dependency updates (Mondays 06:00 UTC)
- **Trivy:** Container vulnerability scanning in CI/CD
- **Bandit:** Python security linter (pre-commit hook)

#### Pinned Dependencies

All production dependencies are pinned to exact versions:

```python
# requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
```

This prevents supply-chain attacks via unexpected updates.

---

### Known Limitations

#### 1. No HTTPS by Default

API runs on HTTP, not HTTPS.

**Mitigation:** Use reverse proxy (nginx, Caddy) for TLS termination:

```nginx
server {
  listen 443 ssl;
  ssl_certificate /path/to/cert.pem;
  ssl_certificate_key /path/to/key.pem;
  
  location / {
    proxy_pass http://localhost:7777;
  }
}
```

#### 2. SQLite Concurrency

SQLite database has limited concurrent write support.

**Impact:** Not a security issue but may cause "database locked" errors under heavy load.

**Mitigation:** Single-user application; acceptable risk.

#### 3. No Rate Limiting

API has no rate limits.

**Impact:** Local network DoS possible.

**Mitigation:** Firewall rules at network level; acceptable for trusted LAN.

---

### Best Practices for Deployment

#### 1. Network Segmentation

Place OpenCloudTouch on IoT VLAN separate from main network:

```
Main LAN: 192.168.1.0/24
IoT VLAN: 192.168.10.0/24 (SoundTouch devices + OpenCloudTouch)
```

#### 2. Firewall Rules

Restrict access to OpenCloudTouch port:

```bash
# Allow only from specific subnet
iptables -A INPUT -p tcp --dport 7777 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 7777 -j DROP
```

#### 3. Regular Updates

Enable Dependabot PRs and monitor for security advisories:

```yaml
# .github/dependabot.yml (already configured)
version: 2
updates:
  - package-ecosystem: "pip"
    schedule:
      interval: "weekly"
```

#### 4. Container Image Verification

Verify image signatures before running:

```bash
# Pull from official registry
podman pull ghcr.io/yourorg/opencloudtouch:v0.2.0

# Inspect image for vulnerabilities
podman inspect opencloudtouch:latest | grep "securityopt"
```

---

### Responsible Disclosure Timeline

We follow industry-standard disclosure timeline:

1. **Day 0:** Vulnerability reported privately
2. **Day 1-7:** Confirmation and triage
3. **Day 7-30:** Develop and test fix
4. **Day 30:** Public disclosure + patch release

Critical vulnerabilities may be expedited.

---

## Security Checklist for Users

Before deploying OpenCloudTouch:

- [ ] Deploy on trusted LAN only (not internet-facing)
- [ ] Update `cors_origins` in config.yaml (remove wildcards)
- [ ] Use reverse proxy with HTTPS if remote access needed
- [ ] Enable Dependabot alerts in GitHub repository
- [ ] Review container image scan results in CI
- [ ] Set firewall rules to restrict port 7777 access
- [ ] Use read-only container filesystem
- [ ] Keep container image updated (watch GitHub releases)

---

## Acknowledgments

We thank security researchers who responsibly disclose vulnerabilities.

Hall of Fame: *(future researcher credits will appear here)*

---

**Last Updated:** 2026-02-13  
**Next Review:** 2026-08-13 (6 months)
