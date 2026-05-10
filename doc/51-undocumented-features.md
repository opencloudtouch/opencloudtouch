# Undocumented Features & Community Discoveries

APIs and behaviors not in the official Bose SoundTouch Web API v1.0,
discovered through reverse engineering by SoundCork, ÜberBöse API, and others.

---

## Cloud-Side Discoveries (Marge/BMX)

### 1. Stereo Pairing & Cloud Groups

Marge exposes group endpoints for persistent configurations like stereo pairs (two ST-10s).
These are different from the local `/getGroup` API.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/marge/streaming/account/{account}/device/{device}/group` | Get group config (returns `<group/>` if ungrouped) |
| POST | `/marge/streaming/account/{account}/group` | Create group (returns 7-digit group ID) |
| DELETE | `/marge/streaming/account/{account}/group/{group}` | Dissolve group |

### 2. SCMUDC Analytics Events

Devices report telemetry to cloud including `play-state-changed`, `preset-pressed`,
`power-pressed`, `source-state-changed`, `art-changed`.

- **Endpoint**: `POST /v1/scmudc/{deviceId}`
- First extensively documented by ÜberBöse API project
- See [13-scmudc-telemetry.md](13-scmudc-telemetry.md) for full details

### 3. Power-On Lifecycle

At boot, devices contact the cloud with diagnostic data:

- **Endpoint**: `POST /streaming/support/power_on`
- Reports: serial number, IP, firmware version, RSSI, gateway
- **Critical**: TUNEIN and LOCAL_INTERNET_RADIO source availability is fetched
  from the cloud **only at boot**. If cloud is unreachable during power cycle,
  these sources vanish until next boot. (ÜberBöse API Issue #3)

### 4. OAuth & Service Tokens

Music service integration uses token management endpoints:

- **Endpoint**: `POST /oauth/device/{deviceId}/music/musicprovider/{providerId}/token/{tokenType}`
- Used to refresh/validate tokens for Spotify, Pandora, etc.
- See [12-spotify-account-flow.md](12-spotify-account-flow.md)

---

## Local API Discoveries (Port 8090)

### Working but Undocumented Endpoints

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/storePreset` | POST | Full preset creation/update (SoundTouch Plus Wiki) |
| `/removePreset` | POST | Complete preset deletion |
| `/clockTime` | GET/POST | Device time management |
| `/clockDisplay` | GET/POST | Clock display settings |
| `/networkInfo` | GET | Network information |
| `/balance` | GET/POST | Stereo balance control |
| `/name` | GET | Read device name |
| `/recents` | GET | Recently played content |
| `/serviceAvailability` | GET | Check service availability |
| `/introspect` | GET | Source introspection data |
| `/bluetoothInfo` | GET | Bluetooth pairing status |

### 103 Total Endpoints

From `GET /supportedURLs`, 103 endpoints are supported on real devices.
Only 19 are in the official API v1.0. See [01-api-endpoints.md](01-api-endpoints.md) for the full list.

---

## Firmware Behaviors

### ETag Case-Sensitivity Bug
- **Discovery**: SoundCork Issue #129
- **Detail**: Firmware expects `ETag` header exactly title-cased
- If server returns `etag` (lowercase), device fails `If-None-Match` requests
- **Breaks**: Preset synchronization efficiency
- **Fix**: Force title-casing via reverse proxy (Nginx, mitmproxy)

### IsItBose Domain Validation
- `libBmxAccountHsm.so` contains hardcoded regex enforcing `bose-*.apigee.net` domains
- Prevents connection to non-Bose domains even with correct URL in config
- Must be binary-patched to use custom domains
- See [11-device-redirect-methods.md](11-device-redirect-methods.md)

### Stockholm Internal App
The device firmware's internal web app ("Stockholm") makes AJAX/XML calls:
- Internal domains: `Marge` (XML-based), `Gabbo` (app-send based)
- JS controllers for volume, presets, sources, etc.
- Reference: SoundCork Issue #128

---

## Community Extensions (in progress)

### Radio-Browser.info Integration
Effort to add `radio-browser.info` as native source provider, replacing TuneIn dependency.
- Requires new source provider entry in emulated `/streaming/sourceproviders`
- Status: Research phase (SoundCork Issue #150)

---

## References

- [SoundCork](https://github.com/deborahgu/soundcork)
- [ÜberBöse API](https://github.com/julius-d/ueberboese-api)
- [SoundTouch Plus Wiki](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/SoundTouch-WebServices-API)
- [IsItBose regex research](https://github.com/deborahgu/soundcork/issues/62)
- [SoundTouch Hook](https://github.com/CodeFinder2/bose-soundtouch-hook)
