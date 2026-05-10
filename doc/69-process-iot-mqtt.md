# Process: IoT MQTT Communication

AWS IoT Core connection for remote device management.

## Certificate Registration & MQTT Connection

```mermaid
sequenceDiagram
    participant ST as SoundTouch Speaker
    participant Voice as voice.api.bose.io
    participant AWS as AWS IoT Core<br/>(a2bhvr9c4wn4ya.iot.us-east-1.amazonaws.com)

    Note over ST,AWS: Certificate Registration (one-time)
    ST->>ST: Generate X.509 CSR
    ST->>Voice: POST /alexa/certificate<br/>(CSR payload)
    Voice-->>ST: Signed device certificate
    ST->>ST: Store cert → /mnt/nv/IoTCerts/iot-cert.pem.crt
    ST->>ST: Store key → /mnt/nv/IoTCerts/iot-private.pem.key (mode 700)

    Note over ST,AWS: MQTT Connection (every boot)
    ST->>AWS: TCP Connect :8883
    ST->>AWS: TLS 1.2 Handshake<br/>Client cert: iot-cert.pem.crt<br/>Root CA: /var/lib/iot/rootCA.crt
    AWS-->>ST: TLS Established (mutual auth)
    ST->>AWS: MQTT CONNECT<br/>clientID from /mnt/nv/.../IoT.xml
    AWS-->>ST: CONNACK (success)

    Note over ST,AWS: Shadow Operations
    ST->>AWS: SUBSCRIBE $aws/things/{clientID}/shadow/update/accepted
    ST->>AWS: SUBSCRIBE $aws/things/{clientID}/shadow/update/rejected
    ST->>AWS: PUBLISH $aws/things/{clientID}/shadow/update<br/>{"state":{"reported":{"deviceState":"CONNECTED","powerState":"ON"}}}
    AWS-->>ST: shadow/update/accepted
```

## MQTT Topic Structure

```mermaid
flowchart TD
    subgraph "Device Shadow Topics"
        A["$aws/things/{clientID}/shadow/update"]
        B["$aws/things/{clientID}/shadow/update/accepted"]
        C["$aws/things/{clientID}/shadow/update/rejected"]
        D["$aws/things/{clientID}/shadow/delete"]
    end

    subgraph "Shadow Document"
        E["state.desired → Commands from cloud/app"]
        F["state.reported → Current device state"]
    end

    ST[SoundTouch Speaker] -->|PUBLISH| A
    ST -->|SUBSCRIBE| B
    ST -->|SUBSCRIBE| C
    A --> E
    A --> F
```

## Shadow State Changes

```mermaid
sequenceDiagram
    participant App as Remote App / Cloud
    participant AWS as AWS IoT Core
    participant ST as SoundTouch Speaker

    Note over App,ST: Power On
    ST->>AWS: PUBLISH shadow/update<br/>{"reported":{"powerState":"ON",<br/>"deviceState":"CONNECTED"}}

    Note over App,ST: Volume Change
    ST->>AWS: PUBLISH shadow/update<br/>{"reported":{"volume":25,"muted":false}}

    Note over App,ST: Zone Change
    ST->>AWS: PUBLISH shadow/update<br/>{"reported":{"zoneState":"master",<br/>"groupMembers":["dev1","dev2"]}}

    Note over App,ST: Disconnect
    ST->>AWS: PUBLISH shadow/update<br/>{"reported":{"deviceState":"DISCONNECTED"}}
    Note over ST: Last Will & Testament may also fire
```

## Protocol Stack

```mermaid
flowchart TB
    A[Application: AWS IoT Device Shadows — JSON] --> B[Parsing: RapidJSON]
    B --> C[Session: MQTT v3.1.1]
    C --> D[Transport: TLS v1.2 — Mutual Auth]
    D --> E[Network: TCP/IP port 8883]

    style A fill:#e1f5fe
    style D fill:#fff9c4
    style E fill:#f3e5f5
```

## IoT Configuration Files

| File | Path | Content |
|------|------|---------|
| IoT.xml | `/mnt/nv/BoseApp-Persistence/1/` | clientID (UUID), iotEndpoint, deployment |
| iot-cert.pem.crt | `/mnt/nv/IoTCerts/` | Device client certificate |
| iot-private.pem.key | `/mnt/nv/IoTCerts/` | Device private key (mode 700) |
| rootCA.crt | `/var/lib/iot/` | AWS IoT Root CA |
| Shepherd-noncore.xml | `/opt/Bose/etc/` | IoT service configuration |
