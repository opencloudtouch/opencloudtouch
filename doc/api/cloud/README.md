# Bose Cloud (Marge) Endpoints

Cloud sync state, bearer tokens, support diagnostics.
**All cloud services EOL May 6, 2026** — these endpoints require local emulation after shutdown.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [50-cloud-emulation-concept.md](../50-cloud-emulation-concept.md), [10-upstream-urls.md](../10-upstream-urls.md)

---

## GET /marge

Cloud synchronization introspection. Returns account and sync statistics:

```xml
<MargeClientIntrospectResponse
  fullaccountetagmatch="false"
  fullaccountsize="187588"
  presetsetagmatch="false"
  presetssize="4521"
  numpresets="6"
  recentsetagmatch="false"
  recentssize="0"
  numrecents="50"
  sourcesetagmatch="false"
  sourcessize="0"
  numsources="6"
  devicesetagmatch="false"
  devicessize="0"
  numdevices="3"
  currentstate="Active"/>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `fullaccountsize` | int | Total account data size in bytes |
| `numpresets` | int | Number of stored presets (0-6) |
| `numrecents` | int | Number of recent items (max 50) |
| `numsources` | int | Number of music service accounts |
| `numdevices` | int | Number of devices on this account |
| `currentstate` | enum | `Active`, `Idle`, `Syncing` |
| `*etagmatch` | boolean | Whether local data matches cloud (etag comparison) |
| `*size` | int | Payload size for each data category |

**Key insight**: `fullaccountsize=187588` (~183 KB) is the full Bose Cloud account payload.
This is what gets synced at boot via `margeURL` → [62-process-device-boot.md](../62-process-device-boot.md).

---

## GET /requestToken

Bearer token for Bose Cloud API access:

```xml
<bearertoken value="Bearer fZK8a3nVuLh0nw1xVu/plr1UDR..."/>
```

Used by the device for authenticated cloud requests (firmware updates, account sync).
Token is generated locally on the device using embedded certificates.

→ Certificate details: [40-tls-and-certificates.md](../40-tls-and-certificates.md)

---

## POST /setMargeAccount

Pair device with a Bose Cloud account:

```xml
<PairDeviceWithAccount>
  <accountId>1234567</accountId>
  <userAuthToken>token-from-bose-oauth</userAuthToken>
</PairDeviceWithAccount>
```

**Known issues** (from device crawl):
- Returns 404 on some firmware versions
- Hangs/times out on some ST10 units
- Missing entirely on SoundTouch Portable

**Fallback**: Telnet `envswitch accountid set <7-digit-id>` → [71-test-telnet-migration.md](../71-test-telnet-migration.md)

---

## POST /pushCustomerSupportInfoToMarge

Push diagnostic data to Bose Cloud support system.

GET returns `<status>/pushCustomerSupportInfoToMarge</status>`.

Sends device logs, configuration, and error reports to `streaming.bose.com`.
After cloud shutdown, this endpoint becomes a no-op (device sends, nobody receives).
