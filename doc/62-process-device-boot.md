# Process: Device Boot & Registration

What happens when a SoundTouch device powers on (hard boot, not standby).

## Boot Sequence

```mermaid
sequenceDiagram
    participant HW as Hardware
    participant Kernel as Linux Kernel
    participant Init as /etc/init.d/SoundTouch
    participant Shepherd as Shepherd Daemon
    participant BoseApp as BoseApp
    participant IoT as IoT Service
    participant Net as Network
    participant Marge as streaming.bose.com
    participant AWS as AWS IoT Core

    HW->>Kernel: Power applied
    Kernel->>Init: Start init scripts
    Init->>Init: mkdir /mnt/nv/BoseLog
    Init->>Init: mkdir /mnt/nv/IoTCerts
    Init->>Init: mkdir /mnt/nv/BoseApp-Persistence/1
    Init->>Init: mkdir -m 700 .../1/Keys

    Init->>Shepherd: Start daemon manager
    Shepherd->>BoseApp: Start main application
    Shepherd->>IoT: Start IoT client
    Shepherd->>Shepherd: Start TPDA (voice/Alexa)

    BoseApp->>BoseApp: Read SoundTouchSdkPrivateCfg.xml<br/>(cloud URLs)

    Note over BoseApp,Net: Network Announcement
    BoseApp->>Net: UPnP/SSDP NOTIFY (port 1900)
    BoseApp->>Net: mDNS register _soundtouch._tcp

    Note over BoseApp,Marge: Cloud Registration
    BoseApp->>Marge: POST /streaming/support/power_on<br/>(device-data XML with diagnostics)
    Marge-->>BoseApp: 200 OK

    Note over BoseApp,Marge: Source Availability (CRITICAL!)
    BoseApp->>Marge: Fetch source availability
    Marge-->>BoseApp: TUNEIN, LOCAL_INTERNET_RADIO available

    Note over IoT,AWS: IoT Connection
    IoT->>AWS: MQTT CONNECT (TLS 1.2, port 8883)<br/>Client cert from /mnt/nv/IoTCerts/
    AWS-->>IoT: CONNACK
    IoT->>AWS: SUBSCRIBE $aws/things/{clientID}/shadow/#
    IoT->>AWS: PUBLISH shadow/update<br/>{"reported":{"deviceState":"CONNECTED"}}

    Note over BoseApp: Device ready for commands<br/>HTTP API on :8090, WebSocket on :8080
```

## Critical: Source Availability at Boot

```mermaid
flowchart TD
    A[Device Boot] --> B{Cloud reachable<br/>during boot?}
    B -->|Yes| C[TUNEIN + LOCAL_INTERNET_RADIO<br/>available in /sources]
    B -->|No| D[TUNEIN + LOCAL_INTERNET_RADIO<br/>MISSING from /sources]
    D --> E[Sources unavailable<br/>until next hard reboot!]
    C --> F[Normal operation]

    style D fill:#ffcdd2
    style E fill:#ffcdd2
    style F fill:#c8e6c9
```

## /power_on Request Content

```mermaid
classDiagram
    class DeviceData {
        +Device device
        +DiagnosticData diagnosticData
    }
    class Device {
        +string id (MAC)
        +string serialnumber
        +string firmwareVersion
        +Product product
    }
    class Product {
        +string productCode
        +string type
        +string serialnumber
    }
    class DiagnosticData {
        +DeviceLandscape deviceLandscape
        +NetworkLandscape networkLandscape
    }
    class DeviceLandscape {
        +string rssi
        +string gatewayIpAddress
        +string[] macaddresses
        +string ipAddress
        +string networkConnectionType
    }

    DeviceData --> Device
    DeviceData --> DiagnosticData
    Device --> Product
    DiagnosticData --> DeviceLandscape
```
