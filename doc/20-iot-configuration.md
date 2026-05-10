# IoT Configuration — AWS IoT Core & MQTT

SoundTouch devices use AWS IoT Core for remote management (power, volume, zones)
via MQTT over TLS with X.509 certificate authentication.

## Protocol Stack

```
Application:   AWS IoT Device Shadows (JSON)
Parsing:       RapidJSON
Session:       MQTT v3.1.1
Transport:     TLS v1.2
Network:       TCP/IP port 8883
```

---

## Configuration Files

### IoT.xml — Main Config
**Path**: `/mnt/nv/BoseApp-Persistence/1/IoT.xml`

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<Configuration clientID="577ecfcc-2db3-4989-92c9-76d7704f9fb3"
               iotEndpoint="a2bhvr9c4wn4ya.iot.us-east-1.amazonaws.com"
               deployment="PROD" />
```

- Each device has a **unique `clientID`** (UUID format)
- Both ST10 and ST20 use the same AWS IoT endpoint
- Hardcoded backup endpoint: `amqmidtcohfms.iot.us-east-1.amazonaws.com`

### Device-Specific Values (examples)
- **ST20**: `clientID="577ecfcc-2db3-4989-92c9-76d7704f9fb3"`
- **ST10**: `clientID="eb1a6d8f-0bb1-4aa7-9113-ea673fcef96e"`

---

## Certificate Files

| File | Location | Purpose |
|------|----------|---------|
| `iot-cert.pem.crt` | `/mnt/nv/IoTCerts/` | Device client certificate |
| `iot-private.pem.key` | `/mnt/nv/IoTCerts/` | Device private key (permissions: 700) |
| `rootCA.crt` | `/var/lib/iot/` | AWS IoT Root CA certificate |

### Certificate Registration Process

1. Device generates X.509 CSR (Certificate Signing Request)
2. CSR sent to `https://voice.api.bose.io/alexa/certificate`
3. Receives signed device certificate
4. Stores cert + key in `/mnt/nv/IoTCerts/`
5. Connects to AWS IoT using mutual TLS authentication

---

## MQTT Topics

### Device Shadow Operations
```
$aws/things/{clientID}/shadow/update
$aws/things/{clientID}/shadow/update/accepted
$aws/things/{clientID}/shadow/update/rejected
$aws/things/{clientID}/shadow/delete
```

### Shadow JSON Format

```json
{
  "state": {
    "desired": {},
    "reported": {
      "deviceState": "CONNECTED",
      "powerState": "ON",
      "zoneState": "...",
      "groupState": "..."
    }
  },
  "version": 0,
  "clientToken": "...",
  "timestamp": 0
}
```

### Example Messages

**Power state change**:
```json
{"state":{"reported":{"powerState":"ON","deviceState":"CONNECTED","timestamp":1703875200}}}
```

**Volume adjustment**:
```json
{"state":{"reported":{"volume":25,"muted":false}}}
```

**Zone configuration**:
```json
{"state":{"reported":{"zoneState":"master","groupMembers":["device1","device2"]}}}
```

**Disconnection**:
```json
{"state":{"reported":{"deviceState":"DISCONNECTED"}}}
```

---

## IoT Service Binary

- **Path**: `/opt/Bose/IoT`
- **Type**: ARM ELF 32-bit executable
- **Framework**: AWS IoT SDK for C++

### Service Management (Shepherd)

Config: `/opt/Bose/etc/Shepherd-noncore.xml`

```xml
<ShepherdConfig>
  <daemon name="STSCertified"/>
  <daemon name="IoT"/>
  <daemon name="TPDA">
    <arg>-c</arg>
    <arg>/opt/Bose/etc/Voice.xml</arg>
  </daemon>
</ShepherdConfig>
```

Process info (from `/var/run/shepherd/pids`):
- IoT service: PID 1837
- BoseApp: PID 1846

### Directory Creation (init script)

`/etc/init.d/SoundTouch` ensures:
```bash
mkdir -p /mnt/nv/BoseLog /mnt/nv/IoTCerts /mnt/nv/BoseApp-Persistence/1
mkdir -m 700 -p /mnt/nv/BoseApp-Persistence/1/Keys
```

---

## AWS IoT Policy (expected restrictions)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "arn:aws:iot:us-east-1:*:client/${iot:ClientId}"
    },
    {
      "Effect": "Allow",
      "Action": ["iot:Publish", "iot:Subscribe", "iot:Receive"],
      "Resource": [
        "arn:aws:iot:us-east-1:*:topic/$aws/things/${iot:ClientId}/shadow/*",
        "arn:aws:iot:us-east-1:*:topicfilter/$aws/things/${iot:ClientId}/shadow/*"
      ]
    }
  ]
}
```

Restrictions:
- Access limited to device's own `clientID` topics
- No wildcard subscriptions across devices
- IP/geolocation restrictions may apply
- Certificate revocation for unusual activity

---

## Monitoring (for research)

### Direct MQTT Access (with device credentials)
```bash
mosquitto_sub -h a2bhvr9c4wn4ya.iot.us-east-1.amazonaws.com \
  -p 8883 --cafile /var/lib/iot/rootCA.crt \
  --cert /mnt/nv/IoTCerts/iot-cert.pem.crt \
  --key /mnt/nv/IoTCerts/iot-private.pem.key \
  -t '$aws/things/{clientID}/shadow/#'
```

### Network Traffic Capture (less intrusive)
```bash
tcpdump -i eth0 -s0 -w soundtouch_iot.pcap \
  host a2bhvr9c4wn4ya.iot.us-east-1.amazonaws.com
```

---

## Common Log Messages

```
"Connection attempt %u to MQTT port at host %s"
"MQTT port not available. Retrying in %u seconds"
"Device connected with MQTT"
"got shadow response: accepted. Payload: %s"
"Failed to register device and get certificate, retrying"
"Successfully connected to MQTT server"
"Disconnecting from IoT server"
"UpdateShadow called when network is not ready"
```

---

## Troubleshooting

| Problem | Check |
|---------|-------|
| No IoT connectivity | Certificate files in `/mnt/nv/IoTCerts/` |
| Certificate errors | Registration endpoint (`voice.api.bose.io`) accessibility |
| MQTT failures | Both primary and backup endpoints |
| Config issues | IoT.xml format, clientID uniqueness |
| Service not starting | Shepherd config, process status |

---

## For Local Emulation

To replace AWS IoT Core locally:
1. Run a local MQTT broker (e.g. Mosquitto)
2. Create matching shadow topics
3. Accept device certificates or generate new ones
4. Implement shadow document handling (desired/reported state)

This is **optional** for basic operation — the local HTTP API (port 8090) provides
the same functionality. IoT is primarily used for remote/cloud-based control.
