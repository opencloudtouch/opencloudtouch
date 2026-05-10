# SCMUDC Telemetry — Device Analytics Events

SCMUDC = **Sound Control Management Usage Data Collection**.
Devices send telemetry to `events.api.bosecm.com` via `POST /v1/scmudc/{deviceId}`.

## Protocol

| Property | Value |
|----------|-------|
| Endpoint | `POST /v1/scmudc/{deviceId}` |
| Protocol Version | 3.1 |
| Content-Type | `text/json; charset=utf-8` |
| Auth | Bearer token |
| Payload | JSON with Base64-encoded XML |

---

## Event Origins

Three distinct sources generate events:

### 1. `"gabbo"` — SoundTouch App (Mobile/Desktop)
- Remote control via SoundTouch mobile/desktop app
- Highest frequency (primary control method)
- Events: `power-pressed`, `play-pressed`, `pause-pressed`, `skip-forward-pressed`, `stop-pressed`

### 2. `"console"` — Device Hardware Controls
- Physical buttons/controls on the speaker
- Lower frequency
- Events: `preset-pressed` (PRESET_1, PRESET_5, etc.), `power-pressed`

### 3. `"device"` — Internal System Actions
- Device's internal software systems
- Automatic responses to user actions
- Events: `play-item`, `preset-assigned`
- Contains **rich content metadata** (Base64-encoded XML)

---

## Event Data Structures

### Standard Button Events (gabbo/console)
```json
{
  "data": {
    "buttonId": "POWER",
    "origin": "gabbo"
  },
  "type": "power-pressed"
}
```

### Device Content Events
```json
{
  "data": {
    "contentItem": "PD94bWwgdmVyc2lvbj0...",
    "origin": "device",
    "preset": "none"
  },
  "type": "play-item"
}
```

The `contentItem` value is **Base64-encoded XML**:

```xml
<ContentItem source="SPOTIFY" type="tracklisturl"
             location="/playback/container/c3BvdGlmeTpwbGF5bGlzdDox..."
             sourceAccount="user@example.com" isPresetable="true">
    <itemName>Billie Eilish - bad guy (instrumental version)</itemName>
    <containerArt>https://i.scdn.co/image/ab67616d0000b273...</containerArt>
</ContentItem>
```

---

## Event Types

| Type | Origin | Trigger |
|------|--------|---------|
| `power-pressed` | gabbo, console | Power on/off |
| `play-pressed` | gabbo | Play control |
| `pause-pressed` | gabbo | Pause control |
| `stop-pressed` | gabbo | Stop playback |
| `skip-forward-pressed` | gabbo | Next track |
| `preset-pressed` | console | Physical preset button |
| `play-item` | device | Content playback started |
| `preset-assigned` | device | Preset stored |
| `source-state-changed` | device | Source switched |
| `art-changed` | device | Artwork/metadata updated |
| `play-state-changed` | device | Play/pause/stop state transition |

---

## Metadata in Events

All events include:
- `deviceID` — MAC address identifier
- `serialNumber` — hardware serial
- `softwareVersion` — firmware version
- Timestamps: both UTC and device monotonic time
- Events are batched and sent with consistent protocol versioning

---

## For Local Emulation

When emulating the Bose cloud, implement `POST /v1/scmudc/{deviceId}` to:
1. Accept and acknowledge telemetry (device expects 200 OK)
2. Optionally parse Base64 XML for content insights
3. Track user interaction patterns (app vs. hardware usage)
4. Detect device health anomalies from event sequences

The device will **continue sending** telemetry as long as `statsServerUrl` is configured.
