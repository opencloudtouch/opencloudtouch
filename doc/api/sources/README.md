# Sources & Service Availability

Source enumeration, service matrix, and local media server discovery.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [01-api-endpoints.md § Source Management](../01-api-endpoints.md)

---

## GET /sources

All configured sources with status:

```xml
<sources deviceID="B92C7D383488">
  <sourceItem source="AUX" sourceAccount="AUX" status="READY"
    isLocal="true" multiroomallowed="true">AUX IN</sourceItem>
  <sourceItem source="STORED_MUSIC"
    sourceAccount="4d696e69-444c-164e-9d41-b42e99ad6c47/0"
    status="UNAVAILABLE" isLocal="false" multiroomallowed="true">
    NAS Music Server</sourceItem>
  <sourceItem source="AMAZON" sourceAccount="user@example.com"
    status="READY" isLocal="false" multiroomallowed="true">
    user@example.com</sourceItem>
  <sourceItem source="SPOTIFY" sourceAccount="SpotifyConnectUserName"
    status="UNAVAILABLE" isLocal="false" multiroomallowed="true">
    SpotifyConnectUserName</sourceItem>
  <sourceItem source="TUNEIN" status="READY"
    isLocal="false" multiroomallowed="true"/>
  <sourceItem source="LOCAL_INTERNET_RADIO" status="READY"
    isLocal="false" multiroomallowed="true"/>
</sources>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `@source` | enum | Source type identifier |
| `@sourceAccount` | string | Account ID (email, UUID, or placeholder) |
| `@status` | enum | `READY`, `UNAVAILABLE` |
| `@isLocal` | boolean | Local input (AUX, BT) vs. network service |
| `@multiroomallowed` | boolean | Can play in multiroom zone |

### All Sources (from ST30 crawl)

| Source | Account | Status | Local | Multiroom |
|--------|---------|--------|-------|-----------|
| `AUX` | `AUX` | READY | ✅ | ✅ |
| `STORED_MUSIC` | DLNA UUID | UNAVAILABLE | ❌ | ✅ |
| `AIRPLAY` | default | UNAVAILABLE | ❌ | ❌ |
| `UPNP` | default | UNAVAILABLE | ❌ | ✅ |
| `QPLAY` | default (×2) | UNAVAILABLE | ✅ | ✅ |
| `AMAZON` | user@example.com | READY | ❌ | ✅ |
| `AMAZON` | otheruser@example.com | READY | ❌ | ✅ |
| `BLUETOOTH` | — | UNAVAILABLE | ✅ | ✅ |
| `NOTIFICATION` | — | UNAVAILABLE | ❌ | ✅ |
| `SPOTIFY` | SpotifyConnect | UNAVAILABLE | ❌ | ✅ |
| `SPOTIFY` | SpotifyAlexa | UNAVAILABLE | ❌ | ✅ |
| `ALEXA` | — | READY | ❌ | ✅ |
| `TUNEIN` | — | READY | ❌ | ✅ |
| `LOCAL_INTERNET_RADIO` | — | READY | ❌ | ✅ |

**Note**: Multiple accounts per source possible (2× AMAZON, 2× SPOTIFY, 2× QPLAY).

---

## GET /serviceAvailability

Service availability matrix with error reasons:

```xml
<serviceAvailability>
  <services>
    <service type="PANDORA" isAvailable="false" reason="PANDORA_GEO_RESTRICTION_ERROR"/>
    <service type="AIRPLAY" isAvailable="true"/>
    <service type="AMAZON" isAvailable="true"/>
    <service type="BLUETOOTH" isAvailable="false" reason="INVALID_SOURCE_TYPE"/>
    <service type="DEEZER" isAvailable="true"/>
    <service type="LOCAL_INTERNET_RADIO" isAvailable="true"/>
    <service type="SPOTIFY" isAvailable="true"/>
    <service type="TUNEIN" isAvailable="true"/>
    <!-- ... -->
  </services>
</serviceAvailability>
```

### Full Matrix (ST30, Germany)

| Service | Available | Reason if unavailable |
|---------|-----------|----------------------|
| AIRPLAY | ✅ | — |
| AMAZON | ✅ | — |
| DEEZER | ✅ | — |
| LOCAL_INTERNET_RADIO | ✅ | — |
| LOCAL_MUSIC | ✅ | — |
| RADIOPLAYER | ✅ | — |
| SIRIUSXM_EVEREST | ✅ | — |
| SPOTIFY | ✅ | — |
| TUNEIN | ✅ | — |
| ALEXA | ❌ | (no reason) |
| BMX | ❌ | (no reason) |
| BLUETOOTH | ❌ | `INVALID_SOURCE_TYPE` |
| NOTIFICATION | ❌ | (no reason) |
| PANDORA | ❌ | `PANDORA_GEO_RESTRICTION_ERROR` |
| QPLAY | ❌ | (no reason) |
| STORED_MUSIC_MEDIA_RENDERER | ❌ | (no reason) |
| UPNP | ❌ | (no reason) |

**Key insight**: `isAvailable` indicates platform support, not current connectivity.
PANDORA is geo-blocked outside US. BLUETOOTH shows `INVALID_SOURCE_TYPE` because BT is a hardware input, not a service.

---

## GET /listMediaServers

DLNA/UPnP media servers discovered on local network:

```xml
<ListMediaServersResponse>
  <media_server id="fa095ecc-e13e-40e7-8e6c-DDEEFF334455"
    mac="" ip="192.0.2.1"
    manufacturer="Generic" model_name="Home Router"
    friendly_name="Home Mediaserver"
    model_description="Home Router"
    location="http://192.0.2.1:49000/MediaServerDevDesc.xml"/>
  <media_server id="fa095ecc-e13e-40e7-8e6c-c80e148577d0"
    mac="" ip="192.0.2.7"
    manufacturer="Generic" model_name="Network Device"
    friendly_name="mediaserver2"
    location="http://192.0.2.7:49000/MediaServerDevDesc.xml"/>
</ListMediaServersResponse>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `@id` | UUID | UPnP device UUID |
| `@ip` | string | Server IP address |
| `@manufacturer` | string | UPnP manufacturer string |
| `@friendly_name` | string | Display name |
| `@location` | URL | UPnP device description URL |
| `@mac` | string | MAC address (often empty) |

Use `sourceAccount` from `/sources` (STORED_MUSIC) to reference a specific server in `/select`.

---

## Source Selection Shortcuts

Convenience endpoints that switch to the last-used source of a specific type.
All POST-only, no request body.

### POST /selectLastSource

Switch to the last active source (any type).

### POST /selectLastWiFiSource

Switch to the last active Wi-Fi-based source (TUNEIN, SPOTIFY, AMAZON, etc.).

### POST /selectLastSoundTouchSource

Switch to the last active SoundTouch source (cloud-based services).

### POST /selectLocalSource

Switch to a local source (AUX, BLUETOOTH).

---

## GET /sourceDiscoveryStatus

Source discovery progress. Returns which sources have been scanned and are ready.

---

## POST /nameSource

Rename a source's display name:

```xml
<nameSource source="AUX" sourceAccount="AUX">
  <friendlyName>Turntable</friendlyName>
</nameSource>
```

The renamed label appears in the SoundTouch app and `/sources` response.

→ Music service accounts: [music-services/](../music-services/README.md)
