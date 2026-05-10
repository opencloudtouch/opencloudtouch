# Telnet:17000 Test Protocol

Step-by-step test procedure for verifying Telnet migration on each device model.

## Test Setup

- **Local Service**: OpenCloudTouch running on `http://<service-ip>:8000`
- **Tool**: `nc` (netcat), `telnet`, or any TCP client
- **Pre-check**: Note current device state via `GET :8090/info` and `GET :8090/presets`

---

## Test 1: Port Reachability

```bash
nc -z -w 2 <device-ip> 17000 && echo "OPEN" || echo "CLOSED"
```

| Result | Action |
|--------|--------|
| OPEN | Continue to Test 2 |
| CLOSED | Telnet method not available → use XML (Method 1) |

---

## Test 2: Shell Responsiveness

```bash
# Connect and check for prompt/banner
echo "getpdo CurrentSystemConfiguration" | nc -w 5 <device-ip> 17000
```

| Result | Action |
|--------|--------|
| URLs printed | Shell works, continue to Test 3 |
| "Command not found" | Shell exists but limited → use XML (Method 1) |
| Empty / timeout | Shell broken → use XML (Method 1) |

---

## Test 3: sys configuration (read-only test first)

Connect interactively:
```bash
nc <device-ip> 17000
```

Send:
```
getpdo CurrentSystemConfiguration
```

**Record the output** — these are the current URLs before any changes.

---

## Test 4: Write Single URL (non-destructive)

Still connected:
```
sys configuration statsServerUrl http://<service-ip>:8000
```

Expected: `OK`

Verify:
```
getpdo CurrentSystemConfiguration
```

Expected: `statsServerUrl` shows new value, others unchanged.

| Result | Action |
|--------|--------|
| OK + verified | `sys configuration` works, continue |
| Error / rejected | Command not supported → use XML (Method 1) |

---

## Test 5: envswitch boseurls (critical!)

```
envswitch boseurls set http://<service-ip>:8000 http://<service-ip>:8000/updates/soundtouch
```

Expected: `OK`

| Result | Action |
|--------|--------|
| OK | Both persistence layers writable, continue |
| "Command not found" | `envswitch` missing → **STOP** — values will revert on reboot |

---

## Test 6: Write All URLs

```
sys configuration margeServerUrl http://<service-ip>:8000
sys configuration statsServerUrl http://<service-ip>:8000
sys configuration bmxRegistryUrl http://<service-ip>:8000/bmx/registry/v1/services
sys configuration swUpdateUrl http://<service-ip>:8000/updates/soundtouch
envswitch boseurls set http://<service-ip>:8000 http://<service-ip>:8000/updates/soundtouch
```

Wait for `OK` after **each** line before sending the next.

Verify:
```
getpdo CurrentSystemConfiguration
```

All 4 URLs must show new values.

---

## Test 7: Account Pairing Check

```bash
curl -s http://<device-ip>:8090/info | grep margeAccountUUID
```

| Result | Action |
|--------|--------|
| `<margeAccountUUID>1234567</margeAccountUUID>` | Has account, skip pairing |
| `<margeAccountUUID/>` (empty) | Needs pairing → Test 7a or 7b |

### Test 7a: HTTP Pairing

```bash
curl -s -m 10 -X POST http://<device-ip>:8090/setMargeAccount \
  -H "Content-Type: application/xml" \
  -d '<PairDeviceWithAccount><accountId>1234567</accountId><userAuthToken>test</userAuthToken></PairDeviceWithAccount>'
```

| Result | Action |
|--------|--------|
| 200 OK | Pairing done |
| 404 / timeout / hang | Endpoint broken → Test 7b |

### Test 7b: Telnet Pairing Fallback

```
envswitch accountid set 1234567
```

Expected: `OK`

---

## Test 8: Reboot & Verify

1. **Power-cycle** the device (unplug power, wait 5s, plug back in)
2. Wait ~60s for boot
3. Check local service logs for `power_on` request from device
4. Verify:
```bash
curl -s http://<device-ip>:8090/info | grep margeURL
curl -s http://<device-ip>:8090/sources
curl -s http://<device-ip>:8090/presets
```

| Check | Expected |
|-------|----------|
| `margeURL` in `/info` | Points to local service |
| `/sources` | Contains TUNEIN, LOCAL_INTERNET_RADIO |
| `/presets` | Presets still intact |

---

## Test Matrix — Fill In Per Device

| Test | ST 10 | ST 20 | ST 300 | ST 30 | Wave III | Wave IV | Result |
|------|:-----:|:-----:|:------:|:-----:|:--------:|:-------:|--------|
| 1. Port open | | | | | | | |
| 2. Shell responsive | | | | | | | |
| 3. getpdo works | | | | | | | |
| 4. sys configuration | | | | | | | |
| 5. envswitch boseurls | | | | | | | |
| 6. All URLs written | | | | | | | |
| 7. Account pairing | | | | | | | |
| 8. Reboot + verify | | | | | | | |

**Legend**: ✅ Pass | ❌ Fail | ⚠️ Partial | — Not tested

---

## Rollback (if needed)

Reconnect Telnet and restore original URLs:
```
sys configuration margeServerUrl https://streaming.bose.com
sys configuration statsServerUrl https://events.api.bosecm.com
sys configuration bmxRegistryUrl https://content.api.bose.io/bmx/registry/v1/services
sys configuration swUpdateUrl https://worldwide.bose.com/updates/soundtouch
envswitch boseurls set https://streaming.bose.com https://worldwide.bose.com/updates/soundtouch
```

Power-cycle to apply.

---

## Notes from Community

- **Wave IV**: USB-Stick unlock failed entirely — Telnet:17000 was the **only** working method
- **ST Portable**: URLs work but `/setMargeAccount` missing → must use `envswitch accountid set`
- **SA-5 (FW 9.x)**: `envswitch` command doesn't exist — Telnet migration not possible
- **Timing**: Each command response takes ~100-500ms. Don't batch/pipeline.
