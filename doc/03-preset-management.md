# Preset Management

SoundTouch devices support 6 preset slots for storing favorite audio content.

## Reading Presets

### GET /presets

```xml
<presets deviceID="...">
  <preset id="1" createdOn="1745991460" updatedOn="1745991460">
    <ContentItem source="SPOTIFY" type="tracklisturl"
                 location="/playback/container/c3Bv..."
                 sourceAccount="user@example.com"
                 isPresetable="true">
      <itemName>My Favorite Songs</itemName>
      <containerArt>https://i.scdn.co/image/...</containerArt>
    </ContentItem>
  </preset>
  <preset id="2">
    <ContentItem source="TUNEIN" type="station"
                 location="s12345" isPresetable="true">
      <itemName>Classic Rock Radio</itemName>
      <containerArt>https://cdn-radiotime-logos.tunein.com/...</containerArt>
    </ContentItem>
  </preset>
  <!-- slots 3-6 may be empty (no ContentItem) -->
</presets>
```

### ContentItem Fields

| Field | Description | Example |
|-------|-------------|---------|
| `source` | Music service | `SPOTIFY`, `TUNEIN`, `PANDORA`, `AMAZON` |
| `type` | Content type | `tracklisturl`, `station`, `track`, `playlist` |
| `location` | Service-specific ID | `/playback/container/c3Bv...`, `s12345` |
| `sourceAccount` | User account | `user@example.com` |
| `isPresetable` | Can be stored as preset | `true`/`false` |
| `itemName` | Display name | `My Playlist` |
| `containerArt` | Artwork URL | `https://i.scdn.co/...` |

### Timestamp Fields
- `createdOn` — Unix timestamp when preset was first stored
- `updatedOn` — Unix timestamp of last modification

---

## Writing Presets (Undocumented but Functional)

The official Bose API v1.0 marks `POST /presets` as "N/A".
However, the SoundTouch Plus community discovered working endpoints:

### POST /storePreset

Creates or updates a preset slot.

```xml
<preset id="1" createdOn="1640995200" updatedOn="1640995200">
  <ContentItem source="SPOTIFY" type="tracklisturl"
               location="spotify:playlist:123" isPresetable="true">
    <itemName>My Playlist</itemName>
  </ContentItem>
</preset>
```

Response: Updated preset configuration.

### POST /removePreset

Clears a preset slot:

```xml
<preset id="3"/>
```

Both endpoints trigger WebSocket `presetsUpdated` notifications.

---

## Selecting Presets

### Via Key Command (recommended)
```xml
<key state="press" sender="Gabbo">PRESET_1</key>
<key state="release" sender="Gabbo">PRESET_1</key>
```

Keys: `PRESET_1` through `PRESET_6`.

### Via Physical Device
- **Short press** preset button → play that preset
- **Long press** while content is playing → save current content to that preset

---

## Content Type Examples

| Source | Type | Description | Example Location |
|--------|------|-------------|------------------|
| `SPOTIFY` | `tracklisturl` | Playlist/Album | `/playback/container/c3Bv...` |
| `SPOTIFY` | `track` | Single Track | `/playback/container/c3Bv...` |
| `TUNEIN` | `station` | Radio Station | `s12345` |
| `PANDORA` | `station` | Pandora Station | `TR:station:12345` |
| `AMAZON` | `playlist` | Amazon Playlist | `amzn1.dv.gti...` |

---

## Presetability Check

Before storing, verify the content supports preset storage:
```
GET /now_playing → check ContentItem.isPresetable == "true"
```

---

## Persistence on Device

Presets are stored on the device filesystem at:
```
/mnt/nv/BoseApp-Persistence/1/
```

Changes persist across reboots.

---

## Known Behaviors

1. Max 6 presets (slots 1–6), hardware limitation
2. `createdOn`/`updatedOn` timestamps are Unix epoch seconds
3. Empty slots have no `<ContentItem>` child
4. The official Bose app and voice assistants (Alexa) can also modify presets
5. All preset changes emit WebSocket `presetsUpdated` events
