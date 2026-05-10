# Playback History (Recents)

Last 50 played items. Ordered by `utcTime` descending (most recent first).

→ Parent: [playback/](README.md)
→ Related: [03-preset-management.md](../03-preset-management.md)

---

## GET /recents

```xml
<recents>
  <recent deviceID="B92C7D383488" utcTime="1769535608" id="2546069925">
    <contentItem source="TUNEIN" type="stationurl"
      location="/v1/playback/station/s158432" sourceAccount="" isPresetable="true">
      <itemName>Absolut relax</itemName>
      <containerArt>http://cdn-profiles.tunein.com/s158432/images/logog.png</containerArt>
    </contentItem>
  </recent>
  <recent deviceID="B92C7D383488" utcTime="1768742221" id="2250498478">
    <contentItem source="TUNEIN" type="stationurl"
      location="/v1/playback/station/s3115" sourceAccount="" isPresetable="true">
      <itemName>Charivari 98.6</itemName>
    </contentItem>
  </recent>
  <!-- ... up to 50 entries ... -->
</recents>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `@deviceID` | string | MAC-based device ID |
| `@utcTime` | unix timestamp | When played |
| `@id` | int | Unique entry ID (hash-based) |
| `contentItem` | element | Same structure as preset ContentItem |

**Note**: `contentItem` (lowercase 'c') in recents vs `ContentItem` (uppercase 'C') in presets.

---

## Source Distribution (from crawl)

Wohnzimmer ST30 — 50 entries:

| Source | Count | Example |
|--------|-------|---------|
| TUNEIN | 7 | Bayern 1, Charivari, Absolut relax |
| AMAZON | 30 | Elton John, Disney, Kinderlieder |
| STORED_MUSIC | 13 | DLNA server (NAS, local media) |

### AMAZON Content Item Structure

```xml
<contentItem source="AMAZON" type="tracklist"
  location="search/../catalog/albums/B001SP4TK8/#playable"
  sourceAccount="user@example.com" isPresetable="true">
  <itemName>Elton John</itemName>
</contentItem>
```

- `location`: Amazon catalog path with `#playable` suffix
- `sourceAccount`: Amazon account email
- Some entries use `#playable_0` or `#popular_tracks_playable` suffixes

### STORED_MUSIC Content Item Structure

```xml
<contentItem source="STORED_MUSIC"
  location="1$7$3F9"
  sourceAccount="4d696e69-444c-164e-9d41-b42e99ad6c47/0" isPresetable="true">
  <itemName>RTL Christmas Megastars CD 1</itemName>
</contentItem>
```

- `location`: DLNA object ID (numeric path)
- `sourceAccount`: UPnP device UUID + index

---

## Encoding Issues

Some entries show UTF-8 mojibake in the raw XML:

| Raw | Correct |
|-----|---------|
| `KÃ¶nig` | König |
| `LÃ¶wen` | Löwen |
| `fÃ¼r` | für |
| `VÃ¶llig` | Völlig |
| `EiskÃ¶nigin` | Eiskönigin |

The device stores content names as received from the music service.
OCT should handle encoding normalization when displaying recents.
