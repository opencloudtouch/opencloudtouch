# Process: Device Discovery

How SoundTouch devices are found on the local network.

## Sequence Diagram

```mermaid
sequenceDiagram
    participant App as Controller App
    participant Net as Local Network
    participant ST as SoundTouch Speaker

    Note over App,ST: Phase 1 — Passive Discovery (SSDP NOTIFY)
    ST->>Net: NOTIFY * HTTP/1.1 (ssdp:alive)<br/>LOCATION: http://ip:8090/device_description.xml<br/>NT: upnp:rootdevice<br/>CACHE-CONTROL: max-age=1800
    Net-->>App: Multicast 239.255.255.250:1900

    Note over App,ST: Phase 1 — Active Discovery (SSDP M-SEARCH)
    App->>Net: M-SEARCH * HTTP/1.1<br/>ST: urn:schemas-upnp-org:device:MediaRenderer:1<br/>MAN: "ssdp:discover"<br/>MX: 3
    Net-->>ST: Multicast 239.255.255.250:1900
    ST-->>App: HTTP/1.1 200 OK<br/>LOCATION: http://ip:8090/device_description.xml<br/>USN: uuid:xxx::upnp:rootdevice

    Note over App,ST: Phase 1 — mDNS Discovery (parallel)
    App->>Net: _soundtouch._tcp.local PTR query
    Net-->>ST: Multicast 224.0.0.251:5353
    ST-->>App: PTR response: device._soundtouch._tcp.local<br/>SRV: 0 0 8090 device.local<br/>A: 192.168.x.x

    Note over App,ST: Phase 2 — UPnP Description
    App->>ST: GET /device_description.xml
    ST-->>App: XML: friendlyName, modelName,<br/>serialNumber, UDN

    Note over App,ST: Phase 3 — Device Enrichment
    App->>ST: GET /info (port 8090)
    ST-->>App: XML: deviceID, name, type,<br/>firmwareVersion, margeAccountUUID,<br/>macAddress, ipAddress, moduleType,<br/>variant, countryCode

    Note over App: Device registered with full profile
```

## Data Flow

```mermaid
flowchart TD
    A[SSDP M-SEARCH / NOTIFY] -->|IP, Location URL| B[UPnP Device Description]
    C[mDNS Browse _soundtouch._tcp] -->|Hostname, Port| B
    B -->|friendlyName, modelName, serialNo| D[GET /info]
    D -->|deviceID, firmware, accountUUID,<br/>macAddress, countryCode| E[Complete Device Profile]

    style A fill:#e1f5fe
    style C fill:#e1f5fe
    style E fill:#c8e6c9
```

## Collected Data per Phase

| Field | SSDP/mDNS | UPnP XML | GET /info |
|-------|:---------:|:--------:|:---------:|
| IP Address | ✅ | ✅ | ✅ |
| Port (8090) | ✅ | — | — |
| Device Name | — | ✅ | ✅ |
| Model | — | ✅ | ✅ |
| MAC / Serial | — | ✅ | ✅ |
| Firmware | — | — | ✅ |
| Account UUID | — | — | ✅ |
| Country Code | — | — | ✅ |
| Module Type | — | — | ✅ |
