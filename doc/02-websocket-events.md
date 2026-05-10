# WebSocket Events — Real-time Device Monitoring

## Connection

| Property | Value |
|----------|-------|
| Protocol | `ws://` (unencrypted) |
| Port | **8080** (different from HTTP API 8090!) |
| Path | `/` |
| Full URL | `ws://192.168.1.10:8080/` |
| Sub-Protocol | `gabbo` |
| Auth | None required |

## Message Format

All events arrive as XML wrapped in `<updates>`:

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<updates deviceID="689E19B8BB8A">
    <nowPlayingUpdated deviceID="689E19B8BB8A">
        <nowPlaying deviceID="689E19B8BB8A" source="SPOTIFY">
            <track>Song Title</track>
            <artist>Artist Name</artist>
            <album>Album Name</album>
            <playStatus>PLAY_STATE</playStatus>
        </nowPlaying>
    </nowPlayingUpdated>
</updates>
```

## Keep-Alive

Client sends WebSocket ping frames. Server responds with pong.
Recommended intervals:
- Ping: every 30 seconds
- Pong timeout: 10 seconds
- Reconnect interval: 5 seconds
- Read/write buffer: 1024–2048 bytes

---

## Event Types

### 1. nowPlayingUpdated
Playback state, track, or settings changed.

Triggers: track change, play/pause/stop, shuffle/repeat toggle.

Key fields:
- `source` — SPOTIFY, TUNEIN, BLUETOOTH, etc.
- `track`, `artist`, `album`, `stationName`
- `playStatus` — `PLAY_STATE`, `PAUSE_STATE`, `STOP_STATE`, `BUFFERING_STATE`
- `shuffleSetting` — `SHUFFLE_OFF`, `SHUFFLE_ON`
- `repeatSetting` — `REPEAT_OFF`, `REPEAT_ONE`, `REPEAT_ALL`
- `art` with `artImageStatus` — artwork URL
- Time info (when available): duration, position

### 2. volumeUpdated
Volume level or mute changed.

```xml
<volumeUpdated deviceID="...">
    <volume>
        <targetvolume>50</targetvolume>
        <actualvolume>50</actualvolume>
        <muteenabled>false</muteenabled>
    </volume>
</volumeUpdated>
```

Notes:
- `targetvolume` ≠ `actualvolume` while volume is transitioning
- Check `muteenabled` for mute state

### 3. connectionStateUpdated
Network connectivity or signal strength changed.

Key fields:
- Connection state (connected/disconnected)
- Signal strength

### 4. presetsUpdated
Preset configuration changed. This is a **read-only notification** — the event
fires when presets are modified through the app, device buttons, or (undocumented)
`/storePreset` and `/removePreset` endpoints.

```xml
<presetsUpdated deviceID="...">
    <preset id="1">
        <ContentItem source="SPOTIFY" ...>
            <itemName>My Playlist</itemName>
        </ContentItem>
    </preset>
</presetsUpdated>
```

### 5. zoneUpdated
Multiroom zone membership changed.

```xml
<zoneUpdated deviceID="...">
    <zone master="ABCD1234EFGH">
        <member ipaddress="192.168.1.11">EFGH5678IJKL</member>
    </zone>
</zoneUpdated>
```

Empty `master` → zone dissolved, device is standalone.

### 6. bassUpdated
Bass equalizer changed.

```xml
<bassUpdated deviceID="...">
    <bass>
        <targetbass>-3</targetbass>
        <actualbass>-3</actualbass>
    </bass>
</bassUpdated>
```

### 7. Additional Events (from official API v1.0 §7.1)

| WebSocket Event Name | Trigger |
|----------------------|---------|
| `NowPlayingChange` | Playback changes |
| `VolumeChange` | Volume adjustments |
| `BassChange` | Bass adjustments |
| `PresetsChangedNotifyUI` | Preset modifications |
| `RecentsUpdatedNotifyUI` | Recently played list updated |
| `AcctModeChangedNotifyUI` | Account mode changes |
| `ErrorNotification` | Device errors |
| `ZoneMapChange` | Zone configuration |
| `SWUpdateStatusChange` | Firmware update status |
| `SiteSurveyResultsChange` | WiFi site survey |
| `SourcesChange` | Source list changes |
| `NowSelectionChange` | Current selection |
| `NetworkConnectionStatus` | Network state |
| `InfoChange` | Device info changes |

---

## Security

- Connections are **unencrypted** (`ws://`, not `wss://`)
- **No authentication** required
- Only devices on the same LAN can connect
- No sensitive data transmitted

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | Check port 8080 not blocked by firewall |
| Frequent disconnects | Check network stability, increase ping interval |
| No events | Set handlers before connecting; enable unknown event handler to debug |
