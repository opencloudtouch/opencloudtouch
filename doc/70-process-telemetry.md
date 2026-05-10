# Process: SCMUDC Telemetry

Device analytics and telemetry reporting to Bose cloud.

## Telemetry Flow

```mermaid
sequenceDiagram
    participant ST as SoundTouch Speaker
    participant App as Stockholm UI / BoseApp
    participant Stats as events.api.bosecm.com

    Note over ST,Stats: Event Collection
    ST->>ST: Track user interaction<br/>(preset select, volume change, etc.)
    App->>App: Track UI interaction<br/>(page view, button tap, etc.)

    Note over ST,Stats: Batch Upload
    ST->>Stats: POST /v1/scmudc/{deviceId}<br/>Content-Type: application/json<br/><br/>[{"time":"2024-12-18T10:30:00Z",<br/>  "origin":"gabbo",<br/>  "content":"BASE64_ENCODED_XML"}, ...]
    Stats-->>ST: 200 OK

    Note over App,Stats: Stockholm UI Events
    App->>Stats: POST /v1/scmudc/{deviceId}<br/>[{"time":"...",<br/>  "origin":"console",<br/>  "content":"BASE64_ENCODED_XML"}]
    Stats-->>App: 200 OK
```

## Event Structure

```mermaid
flowchart TD
    subgraph "JSON Wrapper"
        A[time: ISO 8601 timestamp]
        B[origin: gabbo / console / device]
        C[content: Base64-encoded XML]
    end

    C --> D[Base64 Decode]

    subgraph "XML Payload (decoded)"
        E["<ContentItem source='SPOTIFY'<br/>type='tracklisturl'<br/>location='spotify:playlist:123'>"]
        F["<itemName>My Playlist</itemName>"]
    end

    D --> E
    D --> F
```

## Event Origins

```mermaid
flowchart LR
    subgraph "Origin: gabbo"
        A[Speaker hardware events]
        B[Playback state changes]
        C[Preset selections]
        D[Volume adjustments]
    end

    subgraph "Origin: console"
        E[Stockholm UI interactions]
        F[Page views]
        G[Button taps]
    end

    subgraph "Origin: device"
        H[System events]
        I[Boot diagnostics]
        J[Error reports]
    end

    A --> K[JSON Batch]
    B --> K
    C --> K
    E --> K
    F --> K
    H --> K

    K --> L[POST /v1/scmudc/deviceId]
    L --> M[events.api.bosecm.com]
```

## For Local Emulation

```mermaid
flowchart TD
    A[Device sends POST /v1/scmudc/{deviceId}] --> B[Local service receives JSON batch]
    B --> C{Process or ignore?}
    C -->|Minimum| D[Return 200 OK<br/>Device satisfied, no retries]
    C -->|Optional| E[Base64-decode content field<br/>Parse XML payload<br/>Store for analytics]

    style D fill:#c8e6c9
    style E fill:#e1f5fe
```

The telemetry endpoint is **low priority** for cloud emulation. A simple `200 OK` response satisfies the device and prevents retry loops. The actual telemetry data is only useful for analytics and debugging.
