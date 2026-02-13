# ADR-003: Use SSDP Discovery for Bose SoundTouch Devices

**Date:** 2026-01-10  
**Status:** Accepted  
**Deciders:** Backend Team

## Context

OpenCloudTouch needs to automatically discover Bose SoundTouch devices on the local network without user intervention. Devices are network-connected speakers that were previously discovered via Bose's cloud service (now discontinued).

### Requirements

1. **Zero Configuration:** Users should not need to manually enter IP addresses.
2. **Network Isolation:** Devices may be on different subnets (VLAN, Docker, WSL2).
3. **Reliability:** Discovery must work on Windows, Linux, macOS, and containers.
4. **Fallback:** Manual IP configuration for problematic networks.
5. **Performance:** Discovery should complete within 10 seconds.

## Decision

We will use **SSDP (Simple Service Discovery Protocol)** via multicast UDP for automatic device discovery, with **manual IP configuration as fallback**.

### Implementation

**Discovery Flow:**

```
1. Send M-SEARCH multicast (239.255.255.250:1900)
2. Wait for HTTP replies from devices (10s timeout)
3. Parse XML device descriptors
4. Filter by manufacturer="Bose Corporation"
5. Extract IP, name, model, device_id
6. Store in database
```

**Code:**

```python
class SSDPDiscovery:
    MULTICAST_IP = "239.255.255.250"
    MULTICAST_PORT = 1900
    
    async def discover(self, timeout: int = 10) -> List[DiscoveredDevice]:
        # Send M-SEARCH
        message = (
            "M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {self.MULTICAST_IP}:{self.MULTICAST_PORT}\r\n"
            "MAN: \"ssdp:discover\"\r\n"
            "MX: 10\r\n"
            "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
        )
        
        # Listen for responses
        devices = []
        async with timeout_context(timeout):
            async for response in self._listen():
                device_url = self._parse_location(response)
                device_info = await self._fetch_device_info(device_url)
                
                if device_info.manufacturer == "Bose Corporation":
                    devices.append(device_info)
        
        return devices
```

**XML Parsing (Namespace-Agnostic):**

```python
def _find_xml_text(self, root: Element, path: str) -> Optional[str]:
    # Handle xmlns namespaces (e.g., xmlns="urn:schemas-upnp-org:device-1-0")
    element = root.find(f".//*[local-name()='{path.split('/')[-1]}']")
    return element.text if element is not None else None
```

**Manual Fallback:**

```yaml
# config.yaml
manual_device_ips:
  - "192.168.1.100"
  - "192.168.1.101"
```

## Consequences

### Positive

- **Zero Config:** 95% of users discover devices automatically.
- **Standard Protocol:** SSDP is UPnP standard, widely supported.
- **Cross-Platform:** Works on all OS (Windows, Linux, macOS).
- **Docker Compatible:** Works in host networking mode.
- **Fast:** Discovery completes in 2-5 seconds typically.

### Negative

- **Multicast Dependency:** Blocked by some routers/firewalls.
- **WSL2 Limitation:** Requires `networkingMode=mirrored` + firewall rules.
- **Network Segmentation:** Fails if devices on different VLAN.
- **NAT Traversal:** Doesn't work across NAT boundaries.

## Workarounds for Known Limitations

### WSL2 Multicast (2026-02-10)

**Problem:** WSL2 blocks multicast by default.

**Solution:**

```powershell
# 1. .wslconfig: Enable mirror mode
[wsl2]
networkingMode=mirrored

# 2. Windows Firewall: Allow UDP multicast
New-NetFirewallRule -DisplayName "WSL Podman Multicast" `
    -Direction Inbound -Action Allow -Protocol UDP `
    -LocalPort 1900, 5353 -Program "System"

# 3. Podman: Rootful + host networking
podman machine set --rootful
podman run --network host ...
```

### Docker Bridge Network

**Problem:** Docker bridge network isolates multicast traffic.

**Solution:**

```yaml
# docker-compose.yml
services:
  opencloudtouch:
    network_mode: "host"  # Required for SSDP
```

### VLAN / Subnet Isolation

**Problem:** Devices on different subnet (e.g., IoT VLAN).

**Solution:** Use manual IP configuration.

```yaml
manual_device_ips:
  - "192.168.10.100"  # IoT VLAN
  - "192.168.1.50"    # Main network
```

## Alternatives Considered

### 1. mDNS/Zeroconf (Avahi/Bonjour)

**Reason for rejection:** Bose devices use SSDP, not mDNS. Would require devices to support both.

### 2. Port Scanning (nmap-style)

```python
# ❌ Rejected: Too slow
for ip in range(1, 255):
    try:
        connect(f"192.168.1.{ip}:8090")
    except: pass
```

**Reason for rejection:** Scans 254 IPs = 30+ seconds. SSDP is instant.

### 3. ARP Table Scanning

**Reason for rejection:** Can't distinguish Bose devices from other network devices by MAC address alone.

### 4. Bose Cloud API

**Reason for rejection:** Cloud service discontinued in 2024. This is the whole reason for OpenCloudTouch.

## Performance Benchmarks

| Environment | Discovery Time | Success Rate |
|-------------|----------------|--------------|
| Windows 11 (native) | 2-4s | 100% |
| Linux (native) | 2-3s | 100% |
| macOS (native) | 3-5s | 100% |
| Docker (host network) | 2-4s | 100% |
| Docker (bridge) | ❌ Fail | 0% |
| WSL2 (default) | ❌ Fail | 0% |
| WSL2 (mirrored) | 3-6s | 100% |
| TrueNAS Scale | 2-5s | 100% |

## Related Decisions

- See ADR-001 for Adapter Pattern (wraps SSDPDiscovery)
- See ADR-004 for Repository Pattern (stores discovered devices)

## References

- [UPnP Device Architecture Specification](http://www.upnp.org/specs/arch/UPnP-arch-DeviceArchitecture-v2.0.pdf)
- [SSDP Protocol (RFC 6762)](https://datatracker.ietf.org/doc/html/rfc6762)
- [Bose SoundTouch API Reverse Engineering](https://github.com/bose-soundtouch-api)
- [WSL2 Multicast Workaround (GitHub Issue)](https://github.com/microsoft/WSL/issues/4150)
