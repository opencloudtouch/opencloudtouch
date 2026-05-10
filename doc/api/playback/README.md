# Playback & Content Control

Endpoints for playback status, remote control, and source selection.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [presets.md](presets.md), [recents.md](recents.md), [02-websocket-events.md](../02-websocket-events.md)

---

## GET /nowPlaying

Current playback state. Primary status endpoint.

```xml
<nowPlaying deviceID="B92C7D383488" source="TUNEIN">
  <ContentItem source="TUNEIN" type="stationurl"
    location="/v1/playback/station/s158432" sourceAccount="" isPresetable="true">
    <itemName>Absolut relax</itemName>
    <containerArt>http://cdn-profiles.tunein.com/s158432/images/logog.png</containerArt>
  </ContentItem>
  <track>Track Name</track>
  <artist>Artist Name</artist>
  <album>Album Name</album>
  <stationName>Absolut relax</stationName>
  <art artImageStatus="IMAGE_PRESENT">https://...</art>
  <playStatus>PLAY_STATE</playStatus>
  <shuffleSetting>SHUFFLE_OFF</shuffleSetting>
  <repeatSetting>REPEAT_OFF</repeatSetting>
</nowPlaying>
```

### Idle State

When nothing is playing:

```xml
<nowPlaying deviceID="B92C7D383488" source="INVALID_SOURCE">
  <ContentItem source="INVALID_SOURCE" isPresetable="false"/>
</nowPlaying>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `@source` | enum | Active source. `INVALID_SOURCE` when idle |
| `ContentItem` | element | Full content reference → reusable in `/select`, `/storePreset` |
| `playStatus` | enum | `PLAY_STATE`, `PAUSE_STATE`, `STOP_STATE`, `BUFFERING_STATE` |
| `shuffleSetting` | enum | `SHUFFLE_OFF`, `SHUFFLE_ON` |
| `repeatSetting` | enum | `REPEAT_OFF`, `REPEAT_ONE`, `REPEAT_ALL` |
| `stationName` | string | Radio station name (TuneIn/internet radio) |
| `track` / `artist` / `album` | string | Metadata (Spotify, Amazon, STORED_MUSIC) |

### Source Values

| Source | Description | Presetable |
|--------|-------------|-----------|
| `TUNEIN` | TuneIn internet radio | ✅ |
| `INTERNET_RADIO` | Direct URL radio | ⚠️ Limited |
| `LOCAL_INTERNET_RADIO` | OCT-served radio | ✅ |
| `SPOTIFY` | Spotify Connect | ✅ |
| `AMAZON` | Amazon Music | ✅ |
| `BLUETOOTH` | Bluetooth audio | ❌ |
| `AUX` | AUX input | ❌ |
| `AIRPLAY` | AirPlay | ❌ |
| `STORED_MUSIC` | DLNA/UPnP media server | ✅ |
| `INVALID_SOURCE` | Nothing playing (idle) | ❌ |

---

## GET /now_playing

Alias for `/nowPlaying`. Identical response. Both endpoints coexist on the device.

---

## GET /nowSelection

Currently selected preset (if any):

```xml
<preset id="0" source="INVALID_SOURCE">
  <ContentItem source="INVALID_SOURCE" isPresetable="false"/>
</preset>
```

When a preset is active: `id="1"..`id="6"` with full `ContentItem`.

---

## POST /key

Remote control key simulation. **Must send press + release pair.**

```xml
<!-- Press -->
<key state="press" sender="Gabbo">PLAY</key>
<!-- Release (send ~100ms after press) -->
<key state="release" sender="Gabbo">PLAY</key>
```

Response: `<status>/key</status>`

### Key States

| State | Meaning |
|-------|---------|
| `press` | Key down |
| `release` | Key up |
| `repeat` | Key held (volume ramp) |

### Key Values

**Playback**: `PLAY`, `PAUSE`, `STOP`, `PREV_TRACK`, `NEXT_TRACK`, `PLAY_PAUSE`
**Presets**: `PRESET_1` .. `PRESET_6`
**Volume**: `VOLUME_UP`, `VOLUME_DOWN`, `MUTE`
**Power**: `POWER`
**Rating**: `THUMBS_UP`, `THUMBS_DOWN`, `BOOKMARK`
**Input**: `AUX_INPUT`
**Shuffle/Repeat**: `SHUFFLE_OFF`, `SHUFFLE_ON`, `REPEAT_OFF`, `REPEAT_ONE`, `REPEAT_ALL`

### Sender Values

| Sender | Origin |
|--------|--------|
| `Gabbo` | SoundTouch app (default, use this) |
| `IrRemote` | IR remote control |
| `Console` | Device hardware buttons |
| `LightswitchRemote` | Lightswitch accessory |

---

## POST /select

Select an audio source or content item. Body = `ContentItem` XML.

```xml
<ContentItem source="TUNEIN" type="stationurl"
  location="/v1/playback/station/s158432" sourceAccount="">
  <itemName>Absolut relax</itemName>
</ContentItem>
```

Response: `<status>/select</status>`

### ContentItem Structure

This is the **universal content reference** reused across `/nowPlaying`, `/presets`, `/recents`, `/select`, `/storePreset`.

| Attribute | Type | Description |
|-----------|------|-------------|
| `source` | enum | Source type (see table above) |
| `type` | string | `stationurl`, `tracklisturl`, `uri` |
| `location` | string | Source-specific path |
| `sourceAccount` | string | Service account (email for AMAZON, empty for TUNEIN) |
| `isPresetable` | boolean | Can be stored as preset |
| `itemName` | element | Display name |
| `containerArt` | element | Artwork URL |

→ See [presets.md](presets.md) for preset-specific ContentItem details.

---

## POST /playbackRequest

Alternative playback control endpoint. Accepts playback action commands.
Less commonly used than `/key` — same functionality, different XML structure.

---

## POST /userPlayControl

User-level play control (play/pause/stop). Used by some SoundTouch app versions
instead of `/key`.

---

## POST /userTrackControl

Track skip control (next/previous). Companion to `/userPlayControl`.

---

## POST /userRating

Rate current track (thumbs up/down). Alternative to `THUMBS_UP`/`THUMBS_DOWN` keys.

---

## GET /playNotification

Triggers a double beep notification sound on the device.
No request body needed. Audio-only feedback.

Different from `POST /speaker` which plays arbitrary audio URLs.
