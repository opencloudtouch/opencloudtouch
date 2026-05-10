# Process Overview — Bose SoundTouch Ecosystem

All major processes in the Bose SoundTouch ecosystem, visualized.

## Process Index

| # | Process | Description | Diagram |
|---|---------|-------------|---------|
| 1 | [Device Discovery](61-process-device-discovery.md) | SSDP/mDNS → `/info` enrichment | Sequence |
| 2 | [Device Boot & Registration](62-process-device-boot.md) | Power-on → cloud call-in → source availability | Sequence |
| 3 | [Preset Lifecycle](63-process-preset-lifecycle.md) | Read / Store / Remove / Select presets | Sequence |
| 4 | [Zone Management](64-process-zone-management.md) | Create / Add / Remove / Dissolve multiroom zones | Sequence |
| 5 | [Spotify Account Flow](65-process-spotify-account.md) | OAuth → cloud registration → device sync | Sequence |
| 6 | [Device Migration](66-process-device-migration.md) | Redirect → CA injection → reboot → verify | Sequence |
| 7 | [Device Access (SSH)](67-process-device-access.md) | USB stick → enable SSH → connect | Sequence |
| 8 | [WebSocket Monitoring](68-process-websocket-monitoring.md) | Connect → subscribe → event handling | Sequence |
| 9 | [IoT MQTT Communication](69-process-iot-mqtt.md) | Certificate → MQTT → Device Shadows | Sequence |
| 10 | [Telemetry (SCMUDC)](70-process-telemetry.md) | Device events → JSON batches → cloud | Sequence |

## System Context Diagram

```mermaid
C4Context
    title Bose SoundTouch Ecosystem — System Context

    Person(user, "User", "Controls speakers via app or hardware buttons")

    System(speaker, "SoundTouch Speaker", "Bose SoundTouch 10/20/30")

    System_Ext(marge, "Marge Service", "streaming.bose.com — Accounts, presets, sources")
    System_Ext(bmx, "BMX Service", "content.api.bose.io — TuneIn, content registry")
    System_Ext(stats, "SCMUDC", "events.api.bosecm.com — Telemetry")
    System_Ext(iot, "AWS IoT Core", "MQTT shadows, remote control")
    System_Ext(updates, "Update Service", "worldwide.bose.com — Firmware")
    System_Ext(oauth, "OAuth Proxy", "oauth.streaming.bose.com — Spotify/Pandora tokens")
    System_Ext(spotify, "Spotify", "accounts.spotify.com")

    System(localservice, "OpenCloudTouch", "Local replacement for Bose cloud services")

    Rel(user, speaker, "Physical buttons, IR remote")
    Rel(user, localservice, "Web UI (HTTP)")
    Rel(speaker, marge, "HTTPS — boot, presets, accounts")
    Rel(speaker, bmx, "HTTPS — content discovery")
    Rel(speaker, stats, "HTTPS — telemetry batches")
    Rel(speaker, iot, "MQTT/TLS — shadows, remote control")
    Rel(speaker, updates, "HTTPS — firmware checks")
    Rel(speaker, oauth, "HTTPS — token exchange")
    Rel(oauth, spotify, "OAuth2 — token refresh")
    Rel(localservice, speaker, "HTTP/WS — API port 8090/8080")
```

## Communication Ports

```mermaid
graph LR
    subgraph "SoundTouch Speaker"
        A[HTTP API :8090]
        B[WebSocket :8080]
        C[SSH :22]
        D[Telnet :23]
        E[Diagnostic :17000]
    end

    subgraph "Cloud Services"
        F[Marge :443]
        G[BMX :443]
        H[SCMUDC :443]
        I[AWS IoT :8883]
        J[Updates :443]
    end

    subgraph "Local Network"
        K[SSDP :1900 UDP]
        L[mDNS :5353 UDP]
    end

    A -->|REST XML| F
    A -->|REST XML| G
    A -->|JSON POST| H
    A -->|MQTT TLS| I
    A -->|REST XML| J
    K -.->|Multicast 239.255.255.250| A
    L -.->|Multicast 224.0.0.251| A
```
