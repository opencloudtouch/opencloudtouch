# Device Redirect Methods

Four methods to redirect SoundTouch devices from Bose cloud to a local service.

## Overview of Targets

These domains need redirection for offline operation:

| Domain | Service |
|--------|---------|
| `streaming.bose.com` | Marge (accounts, streaming) |
| `worldwide.bose.com` | Software updates |
| `events.api.bosecm.com` | Telemetry/analytics |
| `content.api.bose.io` | BMX registry |
| `bose-prod.apigee.net` | Apigee gateway |

---

## Method 1: XML Configuration Modification (Recommended)

The cleanest, most granular approach. Modifies the device's native config file.

### Details
- **File**: `/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml`
- **Mechanism**: Firmware reads this XML at boot to determine service URLs
- **Requires**: SSH access

### Implementation

```xml
<SoundTouchSdkPrivateCfg>
  <margeServerUrl>http://192.168.1.10:8000/marge</margeServerUrl>
  <statsServerUrl>http://192.168.1.10:8000</statsServerUrl>
  <swUpdateUrl>http://192.168.1.10:8000/updates/soundtouch</swUpdateUrl>
  <bmxRegistryUrl>http://192.168.1.10:8000/bmx/registry/v1/services</bmxRegistryUrl>
</SoundTouchSdkPrivateCfg>
```

### Pros & Cons

| Pros | Cons |
|------|------|
| Granular — redirect specific services | Requires SSH/root access |
| Persistent — survives most updates | XML syntax errors can cause boot issues |
| Native — uses built-in mechanism | |

---

## Method 2: /etc/hosts DNS Override

Global DNS redirect at the OS level within the device.

### Details
- **File**: `/etc/hosts`
- **Mechanism**: Overrides DNS resolution before external lookups
- **Resolution order**: Device uses `/etc/nsswitch.conf` with `hosts: files dns`
  → `/etc/hosts` is checked **before** any DNS query

### Implementation

```text
192.168.1.10  streaming.bose.com
192.168.1.10  worldwide.bose.com
192.168.1.10  events.api.bosecm.com
192.168.1.10  content.api.bose.io
```

### Pros & Cons

| Pros | Cons |
|------|------|
| Simple, easy to understand | Requires SSH/root access |
| Universal — affects all processes | HTTPS causes SSL cert errors (need custom CA) |
| | Some firmware versions overwrite `/etc/hosts` on reboot |

---

## Method 3: Binary Patching

Low-level modification of compiled binaries to change hardcoded URL patterns.

### Targets
- `/opt/Bose/BoseApp` — main application binary
- `/opt/Bose/IoT` — IoT service binary
- `/opt/Bose/lib/libBmxAccountHsm.so` — BMX account validation library

### The IsItBose Regex Patch

`libBmxAccountHsm.so` contains a hardcoded regex that enforces Bose/Apigee domains:
```
^https:\/\/bose-[a-zA-Z0-9\.\_\-\$\%]\+\.apigee\.net\/
```

Patch with sed (replace with a broad match, **same string length**):
```bash
sed "s#\^https:....bose.\+apigee..net..#http[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]*#g" \
  < libBmxAccountHsm.so.orig > libBmxAccountHsm.so.patched
```

### URL Replacement
Use a hex editor to find strings like `https://streaming.bose.com` and replace
with a custom URL of **exactly the same length** (pad with nulls if needed).

### Procedure
1. Copy binary from device to PC
2. Patch URL strings and/or regex with hex editor or `sed`
3. Copy patched file back to device
4. Restore permissions: `chmod +x`
5. Reboot device

### Pros & Cons

| Pros | Cons |
|------|------|
| Bypasses config — works when firmware ignores XML | **High risk** of bricking |
| Catches hardcoded URLs not in config files | Custom URLs must be **same length** as original |
| | Must be re-applied after firmware updates |
| | Requires binary reverse engineering knowledge |

---

## Method 4: Telnet Diagnostic Shell (Port 17000) — No SSH Required

Uses the device's built-in diagnostic shell. **No USB stick, no SSH unlock needed.**

Community-validated by 5+ independent users across ST 10, ST 20, ST 300, Wave III, Wave IV
(gesellix/Bose-SoundTouch #221, #236, soundcork #141, #228).

### Details
- **Port**: TCP 17000 (plain text, line-oriented, no auth)
- **Mechanism**: `sys configuration` + `envswitch boseurls set` write to two parallel persistence layers
- **Requires**: Network access only — no SSH, no USB stick
- **Limitation**: Cannot install custom CA → HTTP-only redirect (no HTTPS)

### Critical: Both Persistence Layers Required

The device has **two** URL persistence layers. If you only write `sys configuration`,
the `envswitch` layer silently restores old values on reboot. **Always write both:**

### Implementation

Connect via plain TCP (no Telnet option negotiation needed):
```bash
# Connect
nc device-ip 17000
# or: telnet device-ip 17000
```

Send commands **one at a time**, wait for `OK` response before sending the next:

```
sys configuration margeServerUrl http://192.168.1.10:8000
OK
sys configuration statsServerUrl http://192.168.1.10:8000
OK
sys configuration bmxRegistryUrl http://192.168.1.10:8000/bmx/registry/v1/services
OK
sys configuration swUpdateUrl http://192.168.1.10:8000/updates/soundtouch
OK
envswitch boseurls set http://192.168.1.10:8000 http://192.168.1.10:8000/updates/soundtouch
OK
```

Verify the values were applied:
```
getpdo CurrentSystemConfiguration
```

**Do NOT send `sys reboot` over Telnet.** Reboot the device manually (power cycle or web UI).

### Account Pairing (if margeAccountUUID is empty)

After factory reset, the device has no account UUID. Check via `GET :8090/info`.
If `<margeAccountUUID/>` is empty:

**Option A** — HTTP endpoint (if supported by firmware):
```xml
POST http://device-ip:8090/setMargeAccount

<PairDeviceWithAccount>
  <accountId>1234567</accountId>
  <userAuthToken>doesnotmatter</userAuthToken>
</PairDeviceWithAccount>
```

**Option B** — Telnet fallback (if `/setMargeAccount` is missing or hangs):
```
envswitch accountid set 1234567
```

The account ID is any 7-digit number. If the device already has one (from `/info`), reuse it.

### Preflight Checklist

Before attempting Telnet migration:

1. **TCP connect test**: `nc -z device-ip 17000` (must succeed within 2s)
2. **Banner check**: Device prints a prompt after connecting (~1s)
3. **Command test**: `getpdo CurrentSystemConfiguration` must return URLs, not "Command not found"
4. If any check fails → fall back to Method 1 (XML via SSH)

### Device Compatibility

| Model | FW 27.0.6 | Notes |
|-------|:---------:|-------|
| ST 10 | ✅ | Multiple independent confirmations |
| ST 20 | ✅ | Multiple independent confirmations |
| ST 300 | ✅ | Confirmed |
| Wave III | ✅ | Needs pairing fallback via `envswitch accountid set` |
| Wave IV | ✅ | **Only method that worked** — USB unlock failed on this model |
| ST 30 | ❓ | Same FW family, expected to work, unverified |
| ST 520 | ❓ | USB unlock reported failing, Telnet:17000 untested |
| SA-5 (FW 9.x) | ❌ | `envswitch` command not available on older shell |
| ST Portable (recent FW) | ⚠️ | URLs work, but `/setMargeAccount` missing → needs Telnet pairing fallback |

### Pros & Cons

| Pros | Cons |
|------|------|
| **No SSH/USB required** — works over network only | Cannot install custom CA (HTTP only, no HTTPS) |
| No filesystem modification — uses native config API | Not available on all firmware versions (SA-5, some Portables) |
| Both persistence layers written → survives reboot | Must send commands one-by-one (wait for OK each time) |
| Safe — commands fail cleanly, no partial state | |

---

## Comparison

| Method | Use Case | Ease | Safety | Persistence | Granularity |
|--------|----------|:----:|:------:|:-----------:|:-----------:|
| XML Config | Logical service redirect | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Telnet:17000 | **No SSH needed** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| `/etc/hosts` | Quick global DNS | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| Binary Patch | Bypass hardcoded checks | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ |

---

## Common Scenarios

### A: XML Config Only (ideal)
If firmware doesn't enforce `IsItBose` check for your URLs, XML modification alone suffices.

### B: XML Config + Binary Patch (locked firmware)
If the device ignores XML settings because `libBmxAccountHsm.so` validates against Bose regex:
- **Symptom**: Device ignores config or fails to connect despite correct URL
- **Fix**: Patch `IsItBose` regex **and** modify XML

### C: /etc/hosts + Custom CA (clean deep redirect)
Redirect DNS to your local server's IP. Requires:
1. Local server handles HTTPS on port 443
2. Root CA injected into device trust store
3. Automated: AfterTouch/SoundCork migration endpoints support this

### D: /etc/hosts + Binary Patch (no certificate management)
Use `/etc/hosts` for DNS + patch binary to skip SSL verification.
Less secure, higher brick risk.

### E: Triple-Threat (total isolation)
For completely dark environments (no internet):
1. XML → point all URLs to local services
2. Binary Patch → neutralize `IsItBose`
3. `/etc/hosts` → redirect hardcoded domains not in XML (analytics, NTP)

### F: Telnet Only (no SSH, no USB stick)
For devices where USB unlock doesn't work (Wave IV) or SSH is unavailable:
1. Telnet:17000 → write all 4 URLs + `envswitch boseurls set`
2. Verify with `getpdo CurrentSystemConfiguration`
3. If `margeAccountUUID` empty → `envswitch accountid set <id>` or `POST /setMargeAccount`
4. Power-cycle device manually
5. **HTTP only** — no HTTPS possible without SSH for CA injection

---

## Recommendation

1. **Try Method 4 (Telnet:17000) first** — no SSH/USB needed, safe, works on 90% of devices
2. **Fall back to Method 1 (XML via SSH)** — if Telnet port is closed or commands rejected
3. **Verify connectivity** — check logs for "IsItBose" or validation failures
4. **Apply Method 3 (Binary Patch)** only if Method 1 is actively blocked by firmware
5. **Avoid Method 2 (`/etc/hosts`)** unless prepared for SSL certificate management
