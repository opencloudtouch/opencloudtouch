# Process: Zone Management (Multiroom)

Create, modify, and dissolve multiroom zones.

## Zone Lifecycle

```mermaid
sequenceDiagram
    participant Client as API Client
    participant Master as Master Speaker
    participant Slave1 as Member Speaker 1
    participant Slave2 as Member Speaker 2
    participant WS as WebSocket Clients

    Note over Client,WS: CREATE ZONE — Sent to master
    Client->>Master: POST /setZone<br/><zone master="MASTER_MAC" senderIPAddress="client-ip"><br/>  <member ipaddress="slave1-ip">SLAVE1_MAC</member><br/>  <member ipaddress="slave2-ip">SLAVE2_MAC</member><br/></zone>
    Master->>Slave1: Internal: Join zone
    Master->>Slave2: Internal: Join zone
    Master->>WS: zoneUpdated event
    Slave1->>WS: zoneUpdated event
    Slave2->>WS: zoneUpdated event
    Master-->>Client: Zone config response

    Note over Client,WS: ADD MEMBER — Sent to master
    Client->>Master: POST /addZoneSlave<br/><zone master="MASTER_MAC"><br/>  <member ipaddress="new-ip">NEW_MAC</member><br/></zone>
    Master->>WS: zoneUpdated event

    Note over Client,WS: REMOVE MEMBER — Sent to master
    Client->>Master: POST /removeZoneSlave<br/><zone master="MASTER_MAC"><br/>  <member ipaddress="slave2-ip">SLAVE2_MAC</member><br/></zone>
    Master->>WS: zoneUpdated event

    Note over Client,WS: DISSOLVE ZONE
    Client->>Master: POST /setZone (empty)
    Master->>Slave1: Internal: Leave zone
    Master->>WS: zoneUpdated (empty master)
    Slave1->>WS: zoneUpdated (standalone)
```

## Zone States

```mermaid
stateDiagram-v2
    [*] --> Standalone
    Standalone --> Master: POST /setZone (as master)
    Standalone --> Slave: Added to zone via /addZoneSlave
    Master --> Standalone: Zone dissolved
    Slave --> Standalone: Removed via /removeZoneSlave
    Slave --> Standalone: Zone dissolved by master

    state Master {
        [*] --> Controlling
        Controlling --> Controlling: Add/Remove members
    }

    state Slave {
        [*] --> Following
        Following --> Following: Synced audio
    }
```

## Zone Audio Routing

```mermaid
flowchart TD
    subgraph Zone
        M[Master Speaker<br/>Controls playback] --> |Synced audio| S1[Member 1]
        M --> |Synced audio| S2[Member 2]
        M --> |Synced audio| S3[Member 3]
    end

    Client[API Client] --> |POST /key, /volume, /select| M
    Client -.-> |GET /getZone| M
    Client -.x |Commands ignored| S1
    Client -.x |Commands ignored| S2

    style M fill:#bbdefb
    style S1 fill:#e1f5fe
    style S2 fill:#e1f5fe
    style S3 fill:#e1f5fe
```

## Constraints

- Max ~6 devices per zone
- All devices must be on same network segment
- Only master accepts playback commands
- No authentication — any LAN client can manage zones
- Zone operations may take several seconds
