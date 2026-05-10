# Zone & Multiroom Control

Multiroom zone management and stereo pairing.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [04-zone-management.md](../04-zone-management.md), [64-process-zone-management.md](../64-process-zone-management.md)

---

## GET /getZone

Current zone membership. Empty when not in a zone:

```xml
<zone/>
```

When active:

```xml
<zone master="B92C7D383488">
  <member ipaddress="192.168.1.11">689E194F7D2F</member>
  <member ipaddress="192.168.1.12">A81B6A292399</member>
</zone>
```

| Field | Type | Description |
|-------|------|-------------|
| `@master` | string | DeviceID of zone master |
| `member` | element | Slave device: deviceID as text, IP as attribute |

---

## POST /setZone

Create a new zone with this device as master:

```xml
<zone master="B92C7D383488" senderIPAddress="192.168.1.10">
  <member ipaddress="192.168.1.11">689E194F7D2F</member>
</zone>
```

Response: `<status>/setZone</status>`

**Important**: `senderIPAddress` must be the master's IP.

---

## POST /addZoneSlave

Add a device to an existing zone:

```xml
<zone master="B92C7D383488">
  <member ipaddress="192.168.1.12">A81B6A292399</member>
</zone>
```

Response: `<status>/addZoneSlave</status>`

---

## POST /removeZoneSlave

Remove a device from a zone:

```xml
<zone master="B92C7D383488">
  <member ipaddress="192.168.1.12">A81B6A292399</member>
</zone>
```

Response: `<status>/removeZoneSlave</status>`

To dissolve a zone completely, remove all slaves. Zone auto-dissolves when only master remains.

---

## GET /getGroup

Stereo pair group status. ST10-specific feature:

```xml
<group/>
```

When paired:

```xml
<group id="..." name="Stereo Pair">
  <roles>
    <groupRole>
      <deviceId>689E194F7D2F</deviceId>
      <role>LEFT</role>
      <ipAddress>192.168.1.11</ipAddress>
    </groupRole>
    <groupRole>
      <deviceId>A81B6A292399</deviceId>
      <role>RIGHT</role>
      <ipAddress>192.168.1.12</ipAddress>
    </groupRole>
  </roles>
</group>
```

### POST /addGroup

Create a new stereo pair group.

### POST /removeGroup

Dissolve a stereo pair.

### POST /updateGroup

Modify group configuration (e.g. swap L/R assignment).

---

## Zone vs. Group

| Feature | Zone (Multiroom) | Group (Stereo Pair) |
|---------|-------------------|---------------------|
| Purpose | Same audio on multiple speakers | Two speakers as L/R stereo |
| Max devices | Many | 2 |
| Endpoints | `/setZone`, `/addZoneSlave` | `/addGroup`, `/updateGroup` |
| Latency | Uses rebroadcast sync | Hardware-level sync |
| Model support | All SoundTouch | ST10 only (lrStereoCapable) |

→ Audio sync settings: [audio/ § rebroadcastlatencymode](../audio/README.md)
