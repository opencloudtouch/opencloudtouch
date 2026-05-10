# Network Discovery — SSDP, mDNS, UPnP

SoundTouch devices advertise themselves via two discovery protocols.

## Protocol Comparison

| Protocol | Port | Multicast Address | Use Case |
|----------|------|-------------------|----------|
| **mDNS** (Bonjour) | 5353 | `224.0.0.251` | Service browsing via `.local` names |
| **SSDP** (UPnP) | 1900 | `239.255.255.250` | UPnP device/service discovery |

Both protocols are LAN-only (same network segment, no routing).

---

## mDNS / Bonjour Discovery

SoundTouch devices register as `_soundtouch._tcp` services.

### Browse for SoundTouch Devices
```bash
# macOS / Linux
dns-sd -B _soundtouch._tcp local.

# Resolve a specific device
dns-sd -L "Bose SoundTouch" _soundtouch._tcp local.

# Query with dig
dig @224.0.0.251 -p 5353 _soundtouch._tcp.local PTR +additional
```

### Monitor mDNS Traffic
```bash
sudo tcpdump -i any -n -s 0 -A 'port 5353' | grep -i soundtouch
```

---

## SSDP / UPnP Discovery

SoundTouch devices respond to UPnP discovery as:
- `urn:schemas-upnp-org:device:MediaRenderer:1`
- `upnp:rootdevice`

### Active Discovery (M-SEARCH)

Send an M-SEARCH request and listen for responses:

```bash
# Discover all UPnP devices
echo -e "M-SEARCH * HTTP/1.1\r\nHost:239.255.255.250:1900\r\nST:ssdp:all\r\nMan:\"ssdp:discover\"\r\nMX:3\r\n\r\n" \
  | nc -u 239.255.255.250 1900

# Discover only MediaRenderers (SoundTouch)
echo -e "M-SEARCH * HTTP/1.1\r\nHost:239.255.255.250:1900\r\nST:urn:schemas-upnp-org:device:MediaRenderer:1\r\nMan:\"ssdp:discover\"\r\nMX:5\r\n\r\n" \
  | nc -u 239.255.255.250 1900
```

### M-SEARCH Request Format
```
M-SEARCH * HTTP/1.1
HOST:239.255.255.250:1900
ST:ssdp:all
MAN:"ssdp:discover"
MX:3
```

### SSDP Response Format
```
HTTP/1.1 200 OK
CACHE-CONTROL:max-age=1800
DATE:Wed, 18 Dec 2024 10:30:00 GMT
EXT:
LOCATION:http://192.168.1.100:8090/device_description.xml
SERVER:Linux/3.0 UPnP/1.0 Device/1.0
ST:upnp:rootdevice
USN:uuid:12345678-1234-1234-1234-123456789012::upnp:rootdevice
```

### NOTIFY Advertisement (passive)
Devices periodically broadcast their presence:
```
NOTIFY * HTTP/1.1
HOST:239.255.255.250:1900
CACHE-CONTROL:max-age=1800
LOCATION:http://192.168.1.100:8090/device_description.xml
NT:upnp:rootdevice
NTS:ssdp:alive
USN:uuid:12345678-1234-1234-1234-123456789012::upnp:rootdevice
```

### Passive Listening
```bash
# Listen for NOTIFY messages (requires multicast join)
socat - UDP4-RECVFROM:1900,ip-add-membership=239.255.255.250:0.0.0.0,fork
```

---

## Device Description XML

The LOCATION URL from SSDP responses points to a UPnP device description:
```
http://192.168.1.100:8090/device_description.xml
```

This XML contains:
- Device name (`friendlyName`)
- Model name/number
- Serial number (MAC address)
- UPnP service list

---

## Discovery Data Collected

```
Name:           From UPnP friendlyName
Host:           IP address from response
Port:           Usually 8090
ModelID:        From UPnP modelName
SerialNo:       MAC address from UPnP
UPnPLocation:   Device description URL
UPnPUSN:        Unique Service Name
```

After discovery, enrich with `GET http://<ip>:8090/info` for full device details.

---

## Common Service Types

| Service | Protocol | Description |
|---------|----------|-------------|
| `_soundtouch._tcp` | mDNS | Bose SoundTouch |
| `_http._tcp` | mDNS | Web servers |
| `_airplay._tcp` | mDNS | AirPlay |
| `_ipp._tcp` | mDNS | Printers |
| `upnp:rootdevice` | SSDP | UPnP root devices |
| `urn:schemas-upnp-org:device:MediaRenderer:1` | SSDP | Media renderers |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No mDNS responses | Check mDNS daemon running, verify port 5353 not blocked |
| No SSDP responses | Check firewall allows UDP multicast on port 1900 |
| Inconsistent discovery | Device may be in standby; wake with physical button first |
| WSL2 multicast issues | Use `networkingMode=mirrored` + firewall UDP rules for 1900, 5353 |

### Test Device Reachability
```bash
# After discovery, verify device API access
curl -i http://<device-ip>:8090/info
```
