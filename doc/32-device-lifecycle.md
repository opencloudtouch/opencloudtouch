# Device Lifecycle — Boot, Registration, and /power_on

## Boot Sequence

When a SoundTouch device powers on (hard boot, not standby wake):

```
1. Linux kernel boot
2. /etc/init.d/SoundTouch creates directories:
   - /mnt/nv/BoseLog
   - /mnt/nv/IoTCerts
   - /mnt/nv/BoseApp-Persistence/1
   - /mnt/nv/BoseApp-Persistence/1/Keys (mode 700)
3. Shepherd daemon starts services:
   - BoseApp (main application)
   - IoT (AWS IoT MQTT client)
   - TPDA (voice/Alexa)
4. BoseApp reads SoundTouchSdkPrivateCfg.xml for cloud URLs
5. Device announces via UPnP/SSDP and mDNS
6. Device calls POST /streaming/support/power_on to Marge
7. Device fetches source availability from cloud (TUNEIN, LOCAL_INTERNET_RADIO)
8. IoT connects to AWS IoT Core via MQTT/TLS
```

---

## The /power_on Request

At boot, the device sends comprehensive diagnostics to the cloud:

```
POST /streaming/support/power_on → streaming.bose.com (Marge)
```

### Request Body

```xml
<device-data>
    <device id="A81B6A536A98">
        <serialnumber>I6332527703739342000020</serialnumber>
        <firmware-version>27.0.6.46330.5043500 epdbuild.trunk.hepdswbld04.2022-08-04T11:20:29</firmware-version>
        <product product_code="SoundTouch 10 sm2" type="5">
            <serialnumber>069231P63364828AE</serialnumber>
        </product>
    </device>
    <diagnostic-data>
        <device-landscape>
            <rssi>Excellent</rssi>
            <gateway-ip-address>192.168.178.1</gateway-ip-address>
            <macaddresses>
                <macaddress>A81B6A536A98</macaddress>
                <macaddress>A81B6A849D99</macaddress>
            </macaddresses>
            <ip-address>192.168.178.35</ip-address>
            <network-connection-type>Wireless</network-connection-type>
        </device-landscape>
        <network-landscape>
            <network-data xmlns="http://www.Bose.com/Schemas/2012-12/NetworkMonitor/"/>
        </network-landscape>
    </diagnostic-data>
</device-data>
```

### Data Available in /power_on

| Field | Available | Notes |
|-------|:---------:|-------|
| Device ID (MAC) | ✅ | Primary identifier |
| Serial Number | ✅ | Hardware serial |
| Firmware Version | ✅ | Full version string |
| Product Code/Type | ✅ | Model identification |
| Product Serial | ✅ | Product-level serial |
| IP Address | ✅ | Current device IP |
| All MAC Addresses | ✅ | Multiple NICs |
| Signal Strength (RSSI) | ✅ | WiFi quality |
| Gateway IP | ✅ | Network info |
| Connection Type | ✅ | Wireless/Wired |
| Device Name | ❌ | Only from `/info` endpoint |
| Account ID | ❌ | Only from registration |
| Marge URL | ❌ | Only from `/info` endpoint |
| Regional Settings | ❌ | Only from `/info` endpoint |

---

## Critical Boot-Time Behavior

**TUNEIN/LOCAL_INTERNET_RADIO source availability**:

SoundTouch devices fetch source availability from the cloud **only at boot time**.
If the cloud (or local replacement) is **unreachable during a hard reboot**:
- `TUNEIN` and `LOCAL_INTERNET_RADIO` disappear from `/sources`
- These sources become completely unavailable until next reboot
- The local HTTP API (port 8090) continues to work otherwise

**→ Your local service MUST be running and reachable BEFORE the device boots.**

---

## Device Registration Flow

### Phase 1: Discovery (automatic)
- UPnP/SSDP multicast + mDNS browse → find device on LAN
- `GET /info` → enrich with detailed device data

### Phase 2: User Registration (manual)
```
POST /streaming/account/{accountId}/devices
```
```xml
<device deviceid="08DF1F0BA325">
    <name>Living Room Speaker</name>
</device>
```
Adds: user-friendly name, account association.

### Phase 3: Ongoing Updates (mixed)
- Periodic `/info` polling
- Discovery refresh
- User configuration changes
- `/power_on` at each boot

---

## Device Data Model (combined from all sources)

| Field | Source |
|-------|--------|
| `deviceID` | Discovery, `/info`, `/power_on` |
| `name` | User registration |
| `productCode` | `/info`, `/power_on` |
| `serialNumber` | `/info`, `/power_on` |
| `firmwareVersion` | `/info`, `/power_on` |
| `ipAddress` | Discovery, `/info`, `/power_on` |
| `macAddress` | Discovery, `/info`, `/power_on` |
| `accountID` | User registration |
| `margeURL` | `/info` |
| `countryCode` | `/info` |

---

## For Local Cloud Emulation

Implement `POST /streaming/support/power_on`:

1. Parse the XML request body
2. Extract device MAC as primary key
3. Look up or create device record
4. Update firmware, IP, network status
5. Return appropriate response (config instructions, migration data, etc.)

The `/power_on` endpoint enables **network-independent device identification** —
devices call in automatically, no need for LAN-based discovery.
