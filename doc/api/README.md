# Bose SoundTouch API Schema Reference

Real XML responses crawled from SoundTouch devices (ST10, ST30, ST300).
Each category folder contains endpoint documentation with actual device responses.

**Source**: `.local/bose-api/device_schemas/` — crawled December 2025 from 3 devices.

**Devices crawled**:

| Model | DeviceID | Variant | Firmware |
|-------|----------|---------|----------|
| SoundTouch 30 Series III | B92C7D383488 | mojo | 27.0.6.46330 |
| SoundTouch 10 | 689E194F7D2F | rhino | 27.0.6.46330 |
| SoundTouch 300 | (tv) | — | 27.0.6.46330 |

---

## Categories

### [device-identity/](device-identity/README.md)
Device info, name, capabilities, feature matrix, Bluetooth, language.
Endpoints: `/info`, `/name`, `/capabilities`, `/supportedURLs`, `/bluetoothInfo`, `/language`, `/soundTouchConfigurationStatus`

### [playback/](playback/README.md)
Now playing state, remote control keys, source selection, content navigation.
Endpoints: `/nowPlaying`, `/now_playing`, `/nowSelection`, `/key`, `/select`

### [playback/presets.md](playback/presets.md)
Preset storage, structure, and OCT analysis of direct-URL vs. TuneIn behavior.
Endpoints: `/presets`, `/storePreset`, `/removePreset`, `/selectPreset`

### [playback/recents.md](playback/recents.md)
Playback history with 50 entries across TUNEIN, AMAZON, STORED_MUSIC.
Endpoints: `/recents`

### [audio/](audio/README.md)
Volume, bass, balance, DSP controls, tone EQ, speaker levels.
Endpoints: `/volume`, `/bass`, `/bassCapabilities`, `/balance`, `/DSPMonoStereo`, `/audiodspcontrols`, `/audioproducttonecontrols`, `/audioproductlevelcontrols`, `/speaker`, `/rebroadcastlatencymode`

### [sources/](sources/README.md)
Source enumeration, service availability matrix, DLNA media servers.
Endpoints: `/sources`, `/serviceAvailability`, `/listMediaServers`

### [network/](network/README.md)
Network interfaces, statistics, Wi-Fi profiles.
Endpoints: `/networkInfo`, `/netStats`, `/getActiveWirelessProfile`

### [zones/](zones/README.md)
Multiroom zone management, stereo pairing.
Endpoints: `/getZone`, `/setZone`, `/addZoneSlave`, `/removeZoneSlave`, `/getGroup`

### [system/](system/README.md)
Power management, clock, firmware updates, factory reset, standby.
Endpoints: `/powerManagement`, `/powersaving`, `/systemtimeout`, `/systemtimeoutcontrol`, `/clockDisplay`, `/clockTime`, `/factoryDefault`, `/swUpdateQuery`

### [cloud/](cloud/README.md)
Bose Cloud (Marge) sync state, bearer tokens. **EOL May 6, 2026.**
Endpoints: `/marge`, `/requestToken`, `/pushCustomerSupportInfoToMarge`

### [hdmi/](hdmi/README.md)
HDMI-CEC control and input assignment. **ST300 only.**
Endpoints: `/productcechdmicontrol`, `/producthdmiassignmentcontrols`

### [music-services/](music-services/README.md)
Account management, station search, content browsing, bookmarks.
Endpoints: `/setMusicServiceAccount`, `/setMusicServiceOAuthAccount`, `/removeMusicServiceAccount`, `/introspect`, `/searchStation`, `/addStation`, `/removeStation`, `/genreStations`, `/stationInfo`, `/trackInfo`, `/search`, `/navigate`, `/bookmark`

### [internal/](internal/README.md)
Pairing, setup, device internals, product identity, BCO reset.
Endpoints: `/pairLightswitch`, `/cancelPairLightswitch`, `/clearPairedList`, `/enterPairingMode`, `/setPairedStatus`, `/setPairingStatus`, `/enterBluetoothPairing`, `/clearBluetoothPaired`, `/setup`, `/slaveMsg`, `/masterMsg`, `/notification`, `/test`, `/pdo`, `/criticalError`, `/setProductSerialNumber`, `/setProductSoftwareVersion`, `/setComponentSoftwareVersion`, `/getBCOReset`, `/setBCOReset`

---

## Cross-References

| Topic | General Doc | API Schemas |
|-------|------------|-------------|
| Endpoint overview | [01-api-endpoints.md](../01-api-endpoints.md) | This index |
| Preset lifecycle | [03-preset-management.md](../03-preset-management.md) | [playback/presets.md](playback/presets.md) |
| Zone management | [04-zone-management.md](../04-zone-management.md) | [zones/](zones/README.md) |
| WebSocket events | [02-websocket-events.md](../02-websocket-events.md) | — |
| Cloud emulation | [50-cloud-emulation-concept.md](../50-cloud-emulation-concept.md) | [cloud/](cloud/README.md) |
| Network discovery | [31-network-discovery.md](../31-network-discovery.md) | [network/](network/README.md) |

## Model Differences

Many schemas include an `<!-- AGENT: Consolidated schema with model differences -->` header.
Known ST300-only endpoints: `audiodspcontrols`, `audioproducttonecontrols`, `audioproductlevelcontrols`, `productcechdmicontrol`, `producthdmiassignmentcontrols`, `systemtimeoutcontrol`.
