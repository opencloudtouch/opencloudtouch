# Preset Storage & Structure

Real preset XML schemas from device crawl + OCT preset analysis.

→ Parent: [playback/](README.md)
→ Related: [03-preset-management.md](../03-preset-management.md), [63-process-preset-lifecycle.md](../63-process-preset-lifecycle.md)

---

## GET /presets

Returns all 6 preset slots. Empty slots are omitted.

```xml
<presets>
  <preset id="1" createdOn="1546285701" updatedOn="1546696770">
    <ContentItem source="TUNEIN" type="stationurl"
      location="/v1/playback/station/s24854" sourceAccount="" isPresetable="true">
      <itemName>Bayern 1</itemName>
      <containerArt>http://cdn-profiles.tunein.com/s24854/images/logoq.png?t=153565</containerArt>
    </ContentItem>
  </preset>
  <preset id="2" createdOn="1546684636" updatedOn="1546684636">
    <ContentItem source="TUNEIN" type="stationurl"
      location="/v1/playback/station/s3115" sourceAccount="" isPresetable="true">
      <itemName>Charivari 98.6</itemName>
      <containerArt>http://cdn-radiotime-logos.tunein.com/s3115q.png</containerArt>
    </ContentItem>
  </preset>
  <!-- ... presets 3-6 ... -->
</presets>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `@id` | int | Slot 1-6 |
| `@createdOn` | unix timestamp | First stored |
| `@updatedOn` | unix timestamp | Last updated |
| `ContentItem` | element | Universal content reference → [playback/README.md](README.md) |

---

## POST /storePreset *(undocumented)*

Store current playback as preset:

```xml
<preset id="1"/>
```

Stores whatever is currently playing in slot `id`. Returns `<status>/storePreset</status>`.

---

## POST /removePreset *(undocumented)*

```xml
<preset id="1"/>
```

Clears the preset slot. Returns `<status>/removePreset</status>`.

---

## POST /selectPreset

Play a stored preset:

```xml
<preset id="1"/>
```

Equivalent to `POST /key` with `PRESET_1`.

---

## GET /preset?id=N — Does NOT Exist

Individual preset endpoints return **404** from RomPager:

```
HTTP 404 — Object Not Found
```

All 6 `preset_N_kitchen.xml` crawl files confirm this. Presets are **only** accessible via `/presets` (plural).

---

## Preset Analysis: Direct URL vs. TuneIn

**Source**: `.local/bose-api/PRESET_ANALYSIS_OCT.md`

### Problem

Preset 1 stored with `source="INTERNET_RADIO"` and a direct HTTPS stream URL → `INVALID_SOURCE` on playback.
Presets 2-6 stored with `source="TUNEIN"` and relative TuneIn paths → work perfectly.

### Comparison

| Property | TuneIn (works ✅) | Direct URL (fails ❌) |
|----------|-------------------|----------------------|
| `source` | `TUNEIN` | `INTERNET_RADIO` |
| `location` | `/v1/playback/station/s158432` | `https://stream.absolutrelax.de/...` |
| `type` | `stationurl` | — |
| `sourceAccount` | `""` (empty) | — |

### Root Cause

Bose devices **cannot resolve direct HTTPS stream URLs** via the `INTERNET_RADIO` source.
The TuneIn source uses relative paths that the device resolves through the TuneIn/Marge backend.
After cloud shutdown, `TUNEIN` source resolution must be handled by the OCT backend.

→ Solution: OCT proxy endpoint `/stations/preset/{n}` — see [50-cloud-emulation-concept.md](../50-cloud-emulation-concept.md)

---

## Real Preset Data

### Wohnzimmer (ST30)

| Slot | Source | Station | TuneIn ID |
|------|--------|---------|-----------|
| 1 | TUNEIN | Bayern 1 | s24854 |
| 2 | TUNEIN | Charivari 98.6 | s3115 |
| 3 | TUNEIN | Bayern 3 | s14991 |
| 4 | TUNEIN | Absolut relax | s158432 |
| 5 | TUNEIN | MDR JUMP | s6634 |
| 6 | TUNEIN | Radio Brocken | s17231 |

### Küche (ST10) — mixed (from crawl)

| Slot | Source | Station | Note |
|------|--------|---------|------|
| 1 | INTERNET_RADIO | Absolut Relax (direct) | ❌ Fails — INVALID_SOURCE |
| 2 | TUNEIN | Charivari 98.6 | ✅ Works |
| 3 | TUNEIN | Bayern 3 | ✅ Works |
| 4 | TUNEIN | Absolut relax | ✅ Works |
| 5 | TUNEIN | MDR JUMP | ✅ Works |
| 6 | TUNEIN | Radio Brocken | ✅ Works |
