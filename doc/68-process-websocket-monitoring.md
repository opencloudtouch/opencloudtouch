# Process: WebSocket Monitoring

Real-time event monitoring via WebSocket on port 8080.

## Connection & Event Flow

```mermaid
sequenceDiagram
    participant Client as WebSocket Client
    participant ST as SoundTouch Speaker (port 8080)

    Note over Client,ST: Connection
    Client->>ST: WebSocket Upgrade<br/>ws://device-ip:8080/<br/>Sec-WebSocket-Protocol: gabbo
    ST-->>Client: 101 Switching Protocols<br/>Sec-WebSocket-Protocol: gabbo

    loop Keep-Alive (every 30s)
        Client->>ST: WebSocket Ping
        ST-->>Client: WebSocket Pong
    end

    Note over Client,ST: Events (push from speaker)
    ST-->>Client: <updates deviceID="...">\n  <nowPlayingUpdated>...</nowPlayingUpdated>\n</updates>

    ST-->>Client: <updates deviceID="...">\n  <volumeUpdated>...</volumeUpdated>\n</updates>

    ST-->>Client: <updates deviceID="...">\n  <presetsUpdated>...</presetsUpdated>\n</updates>

    ST-->>Client: <updates deviceID="...">\n  <zoneUpdated>...</zoneUpdated>\n</updates>

    Note over Client: Reconnect on disconnect (5s interval)
```

## Event Types

```mermaid
flowchart LR
    subgraph "WebSocket Events"
        A[nowPlayingUpdated]
        B[volumeUpdated]
        C[presetsUpdated]
        D[zoneUpdated]
        E[connectionStateUpdated]
        F[bassUpdated]
    end

    subgraph "Triggers"
        G[Track change, Play/Pause/Stop]
        H[Volume up/down, Mute toggle]
        I[Preset stored/removed]
        J[Zone created/dissolved/modified]
        K[WiFi signal change]
        L[Bass EQ adjusted]
    end

    G --> A
    H --> B
    I --> C
    J --> D
    K --> E
    L --> F
```

## Event Processing

```mermaid
flowchart TD
    A[WebSocket Message Received] --> B[Parse XML]
    B --> C{Event Type?}

    C -->|nowPlayingUpdated| D[Update UI:<br/>track, artist, album,<br/>artwork, playStatus]
    C -->|volumeUpdated| E[Update UI:<br/>targetvolume, actualvolume,<br/>muteenabled]
    C -->|presetsUpdated| F[Refresh preset list]
    C -->|zoneUpdated| G{master empty?}
    C -->|connectionStateUpdated| H[Update connection indicator]
    C -->|bassUpdated| I[Update bass slider]

    G -->|Yes| J[Zone dissolved —<br/>device is standalone]
    G -->|No| K[Zone active —<br/>show members]
```

## Connection Parameters

| Parameter | Value |
|-----------|-------|
| Protocol | `ws://` (unencrypted) |
| Port | 8080 |
| Path | `/` |
| Sub-Protocol | `gabbo` |
| Auth | None |
| Ping interval | 30 seconds |
| Pong timeout | 10 seconds |
| Reconnect interval | 5 seconds |
| Buffer size | 1024–2048 bytes |
