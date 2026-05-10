# Cloud Emulation — Architecture Concept

How to build a local replacement for Bose's cloud services.

## Services to Emulate

| Bose Service | What it Does | Priority |
|-------------|--------------|:--------:|
| **Marge** (`streaming.bose.com`) | Account management, preset sync, recents, source providers | **Critical** |
| **BMX** (`content.api.bose.io`) | TuneIn, podcasts, media content registry | **High** |
| **Stats** (`events.api.bosecm.com`) | SCMUDC telemetry (device just needs 200 OK) | **Low** |
| **Updates** (`worldwide.bose.com`) | Firmware updates (block or serve cached versions) | **Low** |
| **OAuth** (`oauth.streaming.bose.com`) | Token exchange for Spotify, Pandora, etc. | **Medium** |
| **Voice** (`voice.api.bose.io`) | Alexa integration, IoT certificate registration | **Low** |

---

## Architecture Principles

### 1. Text-Based Storage
- All state in human-readable formats (XML, JSON)
- Small focused files per data aspect
- Easy debugging and manual inspection
- Optimized for small hardware (Raspberry Pi Zero 2W)

### 2. Mirror-First Strategy
- Keep mirror to real Bose cloud active as long as possible
- Switch from upstream to local only during:
  - Explicit migration
  - Sufficient local data accumulation
  - Upstream unavailability
- Record as much data as possible, even if not immediately used

### 3. Event-Driven State Management
- Process device events asynchronously
- Track event history in text files
- Support event replay and analysis

---

## Data Structure

```
data/
├── accounts/
│   └── {account-id}/
│       ├── account.json          # Account metadata
│       ├── account-events.log    # Account activity
│       └── devices/
│           └── {device-id}/
│               ├── lifecycle.json    # Device state history
│               ├── info.xml          # Device information
│               ├── presets.xml       # Device presets
│               ├── recents.xml       # Recent plays
│               ├── sources.xml       # Configured sources
│               └── events.log        # Device events
└── system/
    ├── discovery.log             # Discovery events
    └── migration.log             # Migration activities
```

---

## Key Endpoints to Implement

### Marge Service

```
POST /streaming/support/power_on          → Accept device boot notification
GET  /streaming/account/{id}              → Return account info
POST /streaming/account/{id}/devices      → Register device
GET  /streaming/account/{id}/device/{id}  → Get device details
GET  /streaming/account/{id}/device/{id}/group → Get stereo pair config
POST /streaming/account/{id}/group        → Create group (returns 7-digit ID)
DELETE /streaming/account/{id}/group/{id} → Dissolve group
POST /streaming/account/{id}/source       → Register music source
GET  /streaming/sourceproviders           → List available source providers
```

### BMX Service

```
GET /bmx/registry/v1/services            → Service discovery
```

### Stats/Telemetry

```
POST /v1/scmudc/{deviceId}               → Accept telemetry (return 200 OK)
```

### OAuth Proxy

```
POST /oauth/account/{id}/music/musicprovider/{provider}/token/cs  → Token exchange
POST /oauth/device/{id}/music/musicprovider/{provider}/token/cs3  → Token refresh
```

---

## Migration Flow

### Per-Device Migration

1. **Read device state**: `GET /info`, `GET /presets`, `GET /sources`
2. **Backup existing config**: Save `SoundTouchSdkPrivateCfg.xml`
3. **Redirect URLs**: Modify XML config or `/etc/hosts` (see [11-device-redirect-methods.md](11-device-redirect-methods.md))
4. **Inject CA**: If using HTTPS redirect (see [40-tls-and-certificates.md](40-tls-and-certificates.md))
5. **Reboot device**: Power cycle to pick up new config
6. **Verify**: Check that device calls your local service at boot

### Rollback
- Restore original `SoundTouchSdkPrivateCfg.xml` from backup
- Remove injected CA from trust store
- Power cycle

---

## Critical Implementation Notes

### Source Availability at Boot
The device fetches `TUNEIN` and `LOCAL_INTERNET_RADIO` availability **only at boot**.
Your local service must respond to source availability queries during boot, or these
sources disappear until next reboot.

### ETag Header Case Sensitivity Bug
SoundTouch firmware expects `ETag` header to be **exactly title-cased**.
If your server returns `etag` (lowercase), the device fails `If-None-Match` requests,
breaking preset synchronization. Force title-casing in your reverse proxy.

### Preset Sync
Presets are synced between cloud (Marge) and device. When emulating locally,
implement the Marge preset endpoints to keep cloud/device presets in sync.

---

## Community Projects

| Project | Language | Focus |
|---------|----------|-------|
| [SoundCork](https://github.com/deborahgu/soundcork) | Python | Pioneered cloud service emulation |
| [AfterTouch/gesellix](https://github.com/gesellix/Bose-SoundTouch) | Go | Comprehensive toolkit with service emulation |
| [ÜberBöse API](https://github.com/julius-d/ueberboese-api) | — | Advanced endpoint research |
| [SoundTouch Plus](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus) | Python | Home Assistant integration, API wiki |
| [SoundTouch Hook](https://github.com/CodeFinder2/bose-soundtouch-hook) | — | Runtime process instrumentation |
