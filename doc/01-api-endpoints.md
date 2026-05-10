# Bose SoundTouch Web API — Endpoint Reference

All endpoints live on port **8090** (HTTP, XML, no authentication).
103 endpoints discovered from real devices via `GET /supportedURLs`.

## Basics

| Property | Value |
|----------|-------|
| Protocol | HTTP REST-like |
| Data Format | XML request/response |
| Port | 8090 |
| Base URL | `http://<device-ip>:8090/` |
| Auth | None required |
| Encoding | UTF-8 |
| Timeout | 10 seconds recommended |
| Real-time | WebSocket on port 8080 → [02-websocket-events.md](02-websocket-events.md) |
| Schemas | Real XML responses → [api/](api/README.md) |

---

## Complete Endpoint Index (103)

### Device Identity → [api/device-identity/](api/device-identity/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/info` | GET | Device name, type, firmware, MAC, IP, margeURL |
| `/capabilities` | GET | Feature matrix — determines available advanced endpoints |
| `/supportedURLs` | GET | All 93+ available endpoints for this device |
| `/name` | GET/POST | Device display name |
| `/bluetoothInfo` | GET | Bluetooth MAC address |
| `/language` | GET/POST | System language (0=EN, 2=DE, ...) |
| `/soundTouchConfigurationStatus` | GET | Setup completion status |
| `/networkInfo` | GET | Network interfaces, Wi-Fi SSID, signal strength |

### Playback & Media → [api/playback/](api/playback/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/nowPlaying` | GET | Current playback state, track metadata |
| `/now_playing` | GET | Alias for `/nowPlaying` |
| `/nowSelection` | GET | Currently selected preset (if any) |
| `/key` | POST | Remote control key press (press + release) |
| `/select` | POST | Select audio source / content item |
| `/playbackRequest` | POST | Alternative playback control |
| `/userPlayControl` | POST | User-level play/pause/stop |
| `/userTrackControl` | POST | Track skip (next/previous) |
| `/userRating` | POST | Rate current track (thumbs up/down) |
| `/playNotification` | GET | Trigger double beep notification |

### Presets & Favorites → [api/playback/presets.md](api/playback/presets.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/presets` | GET | All 6 preset slots |
| `/storePreset` | POST | Store current playback as preset *(undocumented)* |
| `/removePreset` | POST | Clear a preset slot *(undocumented)* |
| `/selectPreset` | POST | Play a stored preset |
| `/recents` | GET | Last 50 played items → [recents.md](api/playback/recents.md) |
| `/bookmark` | POST | Bookmark current track/station |

### Volume & Audio → [api/audio/](api/audio/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/volume` | GET/POST | Volume level (0-100) + mute state |
| `/bass` | GET/POST | Bass level |
| `/bassCapabilities` | GET | Bass range for this device |
| `/balance` | GET/POST | L/R balance (-7 to +7) |
| `/DSPMonoStereo` | GET/POST | Mono/stereo toggle |
| `/audiodspcontrols` | GET/POST | Audio modes, video sync *(ST300 only)* |
| `/audioproducttonecontrols` | GET/POST | Advanced bass/treble EQ *(ST300 only)* |
| `/audioproductlevelcontrols` | GET/POST | Speaker levels *(ST300 only)* |
| `/speaker` | POST | TTS / audio URL notification playback |
| `/rebroadcastlatencymode` | GET/POST | Multiroom audio sync mode |

### Sources & Content → [api/sources/](api/sources/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sources` | GET | All configured sources with status |
| `/serviceAvailability` | GET | Service availability matrix with error reasons |
| `/listMediaServers` | GET | DLNA/UPnP media servers on local network |
| `/sourceDiscoveryStatus` | GET | Source scanning progress |
| `/nameSource` | POST | Rename a source's display name |
| `/selectLastSource` | POST | Switch to last active source |
| `/selectLastWiFiSource` | POST | Switch to last Wi-Fi source |
| `/selectLastSoundTouchSource` | POST | Switch to last cloud source |
| `/selectLocalSource` | POST | Switch to local source (AUX, BT) |

### Music Services → [api/music-services/](api/music-services/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/setMusicServiceAccount` | POST | Register music service account |
| `/setMusicServiceOAuthAccount` | POST | OAuth-based account registration (Spotify) |
| `/removeMusicServiceAccount` | POST | Remove music service |
| `/introspect` | GET | Registered accounts and sync state |
| `/searchStation` | POST | Search radio stations |
| `/addStation` | POST | Add station to favorites |
| `/removeStation` | POST | Remove station from favorites |
| `/genreStations` | GET | Browse stations by genre |
| `/stationInfo` | GET | Station metadata |
| `/trackInfo` | GET | Extended track info (⚠️ timeouts on AirPlay/DLNA) |
| `/search` | POST | Generic content search |
| `/navigate` | POST | Browse content hierarchy (DLNA) |

### Zone & Multiroom → [api/zones/](api/zones/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/getZone` | GET | Current zone membership |
| `/setZone` | POST | Create multiroom zone |
| `/addZoneSlave` | POST | Add device to zone |
| `/removeZoneSlave` | POST | Remove device from zone |
| `/getGroup` | GET | Stereo pair status (ST10 only) |
| `/addGroup` | POST | Create stereo pair |
| `/removeGroup` | POST | Dissolve stereo pair |
| `/updateGroup` | POST | Modify pair config (swap L/R) |

### Network → [api/network/](api/network/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/networkInfo` | GET | Interfaces, IPs, Wi-Fi details |
| `/netStats` | GET | Low-level network statistics, RSSI |
| `/getActiveWirelessProfile` | GET | Current Wi-Fi SSID |
| `/performWirelessSiteSurvey` | POST | Scan for Wi-Fi networks |
| `/addWirelessProfile` | POST | Connect to new Wi-Fi |
| `/setWiFiRadio` | POST | Wi-Fi radio settings |

### System & Power → [api/system/](api/system/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/powerManagement` | GET | Power state, battery capability |
| `/systemtimeout` | GET/POST | Auto-standby config |
| `/systemtimeoutcontrol` | GET/POST | Extended standby *(ST300 only)* |
| `/powersaving` | POST | Enter power-saving mode |
| `/standby` | POST | Enter standby |
| `/lowPowerStandby` | POST | Deep sleep (not discoverable) |
| `/userActivity` | POST | Reset auto-standby timer |
| `/clockDisplay` | GET/POST | Clock display settings |
| `/clockTime` | GET/POST | Device time |
| `/swUpdateQuery` | GET | Firmware update status |
| `/swUpdateCheck` | POST | Check for firmware updates |
| `/swUpdateStart` | POST | Start firmware update |
| `/swUpdateAbort` | POST | Abort firmware update |
| `/factoryDefault` | POST | Factory reset (**destructive**) |

### Cloud (Marge) — EOL May 2026 → [api/cloud/](api/cloud/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/marge` | GET | Cloud sync state, account stats |
| `/requestToken` | GET | Bearer token for cloud API |
| `/setMargeAccount` | POST | Pair device with Bose Cloud account |
| `/pushCustomerSupportInfoToMarge` | POST | Send diagnostics to cloud |

### HDMI *(ST300 only)* → [api/hdmi/](api/hdmi/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/productcechdmicontrol` | GET/POST | HDMI-CEC mode |
| `/producthdmiassignmentcontrols` | GET/POST | HDMI input button mapping |

### Pairing, Setup & Internal → [api/internal/](api/internal/README.md)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/pairLightswitch` | POST | Start Lightswitch pairing |
| `/cancelPairLightswitch` | POST | Cancel Lightswitch pairing |
| `/clearPairedList` | POST | Remove all paired accessories |
| `/enterPairingMode` | POST | Enter general pairing mode |
| `/setPairedStatus` | POST | Set accessory pairing status |
| `/setPairingStatus` | POST | Update pairing state |
| `/enterBluetoothPairing` | POST | Enter BT discoverable mode |
| `/clearBluetoothPaired` | POST | Remove all BT pairings |
| `/setup` | POST | Initial device setup |
| `/slaveMsg` | POST | Internal zone slave message |
| `/masterMsg` | POST | Internal zone master message |
| `/notification` | GET | Notification queue status |
| `/test` | GET | Device self-test |
| `/pdo` | GET | Product Data Object (low-level config) |
| `/criticalError` | GET | Critical error state |
| `/setProductSerialNumber` | POST | Factory provisioning |
| `/setProductSoftwareVersion` | POST | Factory provisioning |
| `/setComponentSoftwareVersion` | POST | Factory provisioning |
| `/getBCOReset` | GET | BCO reset state |
| `/setBCOReset` | POST | Cloud registration reset |

---

## Error Handling

| Status | Meaning |
|--------|---------|
| `200 OK` | Success |
| `400 Bad Request` | Malformed XML or missing required fields |
| `404 Not Found` | Endpoint not available on this device/firmware |
| `500 Internal Server Error` | Device error |

---

## References

- [Official Bose SoundTouch Web API v1.0 PDF](https://assets.bosecreative.com/m/496577402d128874/original/SoundTouch-Web-API.pdf)
- [SoundTouch Plus Wiki](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/SoundTouch-WebServices-API)
- **[api/](api/README.md)** — Real XML response schemas crawled from ST10, ST30, ST300 devices
