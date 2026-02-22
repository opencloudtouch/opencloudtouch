# Preset Playback – Technical Reference

**Stand**: 2026-02-22  
**Status**: Working (MVP)

This document describes how OpenCloudTouch (OCT) enables preset playback on Bose SoundTouch devices after the Bose Cloud shutdown.

## Overview

SoundTouch devices support 6 hardware presets (buttons 1-6). After the cloud shutdown, the original TuneIn-based presets no longer work. OCT provides an alternative using `LOCAL_INTERNET_RADIO` source with direct stream URLs.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SoundTouch Device                            │
│  1. Fetches /bmx/registry/v1/services on boot                  │
│  2. Stores presets locally (XML)                                │
│  3. On preset button: calls location URL                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OCT Server                                   │
│  - /bmx/registry/v1/services → Service registry                │
│  - /core02/svc-bmx-adapter-orion/prod/orion/station?data=...   │
│    → Decodes base64 JSON, returns BmxPlaybackResponse          │
└─────────────────────────────────────────────────────────────────┘
```

## Preset XML Format

### Working Format: LOCAL_INTERNET_RADIO

```xml
<preset id="4">
  <ContentItem source="LOCAL_INTERNET_RADIO" 
               type="stationurl" 
               location="http://content.api.bose.io:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data={BASE64_DATA}"
               sourceAccount="" 
               isPresetable="true">
    <itemName>Station Name</itemName>
  </ContentItem>
</preset>
```

### Base64 Data Payload

The `data` query parameter contains base64url-encoded JSON:

```json
{
  "streamUrl": "http://absolut-relax.live-sm.absolutradio.de/absolut-relax/stream/mp3",
  "name": "Absolut Relax",
  "imageUrl": "https://example.com/logo.png"
}
```

**Encoding in PowerShell:**
```powershell
$json = '{"streamUrl":"http://stream.example.com/radio.mp3","name":"My Station"}'
$base64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
# Result: eyJzdHJlYW1VcmwiOiJodHRwOi8vc3RyZWFtLmV4YW1wbGUuY29tL3JhZGlvLm1wMyIsIm5hbWUiOiJNeSBTdGF0aW9uIn0=
```

**Encoding in Python:**
```python
import base64
import json

data = {"streamUrl": "http://stream.example.com/radio.mp3", "name": "My Station"}
base64_data = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
```

## API Endpoints

### 1. BMX Registry Service

**Endpoint:** `GET /bmx/registry/v1/services`

Called by device on boot. Returns available services.

**Response:**
```json
{
  "_links": {
    "bmx_services_availability": {"href": "../servicesAvailability"}
  },
  "askAgainAfter": 60000,
  "bmx_services": [
    {
      "_links": {...},
      "id": {"name": "orion", "value": 999},
      "baseUrl": "http://192.168.178.108:7777/core02/svc-bmx-adapter-orion/prod",
      "assets": {"name": "OCT Radio", "description": "OpenCloudTouch"},
      "streamTypes": ["liveRadio"],
      "askAdapter": false
    }
  ]
}
```

### 2. Orion Station Playback

**Endpoint:** `GET /core02/svc-bmx-adapter-orion/prod/orion/station?data={base64}`

Called by device when preset is pressed.

**Request:**
- `data` (query param): Base64url-encoded JSON with `streamUrl`, `name`, `imageUrl`

**Response:**
```json
{
  "audio": {
    "hasPlaylist": true,
    "isRealtime": true,
    "maxTimeout": 60,
    "streamUrl": "http://absolut-relax.live-sm.absolutradio.de/absolut-relax/stream/mp3",
    "streams": [
      {
        "hasPlaylist": true,
        "isRealtime": true,
        "streamUrl": "http://absolut-relax.live-sm.absolutradio.de/absolut-relax/stream/mp3"
      }
    ]
  },
  "imageUrl": "https://example.com/logo.png",
  "name": "Absolut Relax",
  "streamType": "liveRadio",
  "_links": {
    "bmx_nowplaying": {"href": "http://192.168.178.108:7777/bmx/orion/now-playing"},
    "bmx_reporting": {"href": "http://192.168.178.108:7777/bmx/orion/reporting"}
  }
}
```

## Device Configuration

### Required hosts File Entries

The device must redirect Bose domains to OCT server:

```
192.168.178.108  streaming.bose.com
192.168.178.108  content.api.bose.io
192.168.178.108  events.api.bosecm.com
192.168.178.108  bmx.bose.com
```

### Device XML Settings

Key settings in device's `/mnt/nv/product.xml`:

```xml
<margeURL>http://content.api.bose.io:7777</margeURL>
<statsServerUrl>http://content.api.bose.io:7777/stats</statsServerUrl>
```

## Complete Example

### 1. Encode Stream Data

```python
import base64
import json

stream_data = {
    "streamUrl": "http://absolut-relax.live-sm.absolutradio.de/absolut-relax/stream/mp3",
    "name": "Absolut Relax",
    "imageUrl": ""
}
encoded = base64.urlsafe_b64encode(json.dumps(stream_data).encode()).decode()
print(encoded)
# eyJzdHJlYW1VcmwiOiJodHRwOi8vYWJzb2x1dC1yZWxheC5saXZlLXNtLmFic29sdXRyYWRpby5kZS9hYnNvbHV0LXJlbGF4L3N0cmVhbS9tcDMiLCJuYW1lIjoiQWJzb2x1dCBSZWxheCIsImltYWdlVXJsIjoiIn0=
```

### 2. Store Preset on Device

```powershell
$preset = @"
<preset id="4">
  <ContentItem source="LOCAL_INTERNET_RADIO" 
               type="stationurl" 
               location="http://content.api.bose.io:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data=eyJzdHJlYW1VcmwiOiJodHRwOi8vYWJzb2x1dC1yZWxheC5saXZlLXNtLmFic29sdXRyYWRpby5kZS9hYnNvbHV0LXJlbGF4L3N0cmVhbS9tcDMiLCJuYW1lIjoiQWJzb2x1dCBSZWxheCIsImltYWdlVXJsIjoiIn0="
               sourceAccount="" 
               isPresetable="true">
    <itemName>Absolut Relax OCT</itemName>
  </ContentItem>
</preset>
"@

Invoke-RestMethod -Uri "http://192.168.178.79:8090/preset" -Method Post -Body $preset -ContentType "application/xml"
```

### 3. Play Preset

```powershell
$key = '<key state="press" sender="Gabbo">PRESET_4</key>'
Invoke-RestMethod -Uri "http://192.168.178.79:8090/key" -Method Post -Body $key -ContentType "application/xml"
```

### 4. Verify Playback

```powershell
Invoke-RestMethod -Uri "http://192.168.178.79:8090/now_playing"
# Returns: source=LOCAL_INTERNET_RADIO, playStatus=PLAY_STATE
```

## Why Not TuneIn?

The original TuneIn source (`source="TUNEIN"`) requires additional Bose-proprietary endpoints that are complex to reverse-engineer. When attempting TuneIn playback, the device returns HTTP 500.

`LOCAL_INTERNET_RADIO` is simpler:
- Device calls the `location` URL directly
- OCT decodes the base64 payload
- Returns stream URL in BMX format
- Device plays the stream

## Troubleshooting

### Device Not Calling OCT

1. Check hosts file: `ssh root@device "cat /etc/hosts"`
2. Verify OCT reachable: `curl http://oct-server:7777/health`
3. Reboot device after hosts file changes

### Preset Not Playing

1. Check OCT logs: `podman logs opencloudtouch-local`
2. Verify orion endpoint: `curl "http://oct:7777/core02/svc-bmx-adapter-orion/prod/orion/station?data=..."`
3. Ensure stream URL is valid MP3/AAC URL

### BMX Registry Not Loading

1. Check `/bmx/registry/v1/services` endpoint returns valid JSON
2. Verify `_links` field is present (required by device)
3. Check `askAgainAfter` is not too short (min 60000ms)

## Related Files

- [apps/backend/src/opencloudtouch/bmx/routes.py](../apps/backend/src/opencloudtouch/bmx/routes.py) - BMX endpoint implementation
- [apps/backend/tests/unit/bmx/test_orion_adapter.py](../apps/backend/tests/unit/bmx/test_orion_adapter.py) - Unit tests
- [docs/USB_SETUP_LOG.md](USB_SETUP_LOG.md) - Device configuration via USB
