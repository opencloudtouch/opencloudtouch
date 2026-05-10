# Zone Management — Multiroom Control

## Concepts

- **Master**: Controls zone playback, receives commands
- **Member (Slave)**: Follows master's playback, synchronized audio
- **Standalone**: Device not in any zone

| State | Description |
|-------|-------------|
| `STANDALONE` | Independent |
| `MASTER` | Controls a multiroom zone |
| `SLAVE` | Follows zone master |

Limits: typically max 6 devices per zone. All must be on the same network.

---

## API Endpoints

### GET /getZone

```xml
<zone master="ABCD1234EFGH">
    <member ipaddress="192.168.1.11">EFGH5678IJKL</member>
    <member ipaddress="192.168.1.12">IJKL9012MNOP</member>
</zone>
```

Empty response → device is standalone.

### POST /setZone

Create a new zone. Request sent to the **master** device:

```xml
<zone master="ABCD1234EFGH" senderIPAddress="192.168.1.10">
    <member ipaddress="192.168.1.11">EFGH5678IJKL</member>
    <member ipaddress="192.168.1.12">IJKL9012MNOP</member>
</zone>
```

### POST /addZoneSlave

Add a device to an existing zone. Sent to the **master**:

```xml
<zone master="ABCD1234EFGH">
    <member ipaddress="192.168.1.13">MNOP3456QRST</member>
</zone>
```

### POST /removeZoneSlave

Remove a device from a zone. Sent to the **master**:

```xml
<zone master="ABCD1234EFGH">
    <member ipaddress="192.168.1.13">MNOP3456QRST</member>
</zone>
```

### Dissolving a Zone

Send an empty `/setZone` or remove all members individually.

---

## WebSocket Events

Zone changes trigger `zoneUpdated` events:

```xml
<updates deviceID="689E19B8BB8A">
    <zoneUpdated deviceID="689E19B8BB8A">
        <zone master="ABCD1234EFGH">
            <member ipaddress="192.168.1.11">EFGH5678IJKL</member>
        </zone>
    </zoneUpdated>
</updates>
```

---

## Identifiers

- `master` attribute = device ID (MAC address, uppercase hex, no colons)
- `<member>` text content = device ID of the member
- `ipaddress` attribute = IP of the member device (optional but recommended)

---

## Known Behaviors

1. Zone commands may take several seconds to complete
2. Only specific device types can be zone masters
3. Audio synchronization quality depends on network bandwidth/latency
4. All devices must be on the same network segment
5. No authentication for zone operations — any LAN client can manage zones
6. IP addresses in zone configs are optional but recommended for reliability
