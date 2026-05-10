# Network Information

Network interfaces, statistics, and Wi-Fi profile management.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [31-network-discovery.md](../31-network-discovery.md)

---

## GET /networkInfo

Detailed network interface list:

```xml
<networkInfo wifiProfileCount="3">
  <interfaces>
    <interface type="ETHERNET_INTERFACE" name="eth0"
      macAddress="B92C7D383488" ipAddress=""
      state="NETWORK_ETHERNET_DISCONNECTED"/>
    <interface type="WIFI_INTERFACE" name="wlan0"
      macAddress="E56DAC1C82EF" ipAddress="192.0.2.78"
      ssid="HomeNetwork" frequencyKHz="5180000"
      state="NETWORK_WIFI_CONNECTED" signal="EXCELLENT_SIGNAL"
      mode="STATION"/>
    <interface type="WIFI_INTERFACE" name="wlan1"
      macAddress="F45EAB0B71DF"
      state="NETWORK_WIFI_DISCONNECTED"/>
  </interfaces>
</networkInfo>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `@wifiProfileCount` | int | Number of stored Wi-Fi profiles |
| `@type` | enum | `ETHERNET_INTERFACE`, `WIFI_INTERFACE` |
| `@name` | string | Linux interface name: `eth0`, `wlan0`, `wlan1` |
| `@macAddress` | string | 12-char hex MAC |
| `@ipAddress` | string | IPv4 address (empty if disconnected) |
| `@ssid` | string | Connected Wi-Fi network name |
| `@frequencyKHz` | int | Wi-Fi frequency in kHz (5180000 = 5.18 GHz / channel 36) |
| `@state` | enum | See state table |
| `@signal` | enum | `EXCELLENT_SIGNAL`, `GOOD_SIGNAL`, `MARGINAL_SIGNAL` |
| `@mode` | enum | `STATION` (client mode) |

### Interface States

| State | Meaning |
|-------|---------|
| `NETWORK_WIFI_CONNECTED` | Active Wi-Fi connection |
| `NETWORK_WIFI_DISCONNECTED` | Wi-Fi interface up, not connected |
| `NETWORK_ETHERNET_CONNECTED` | Ethernet cable plugged in |
| `NETWORK_ETHERNET_DISCONNECTED` | No ethernet cable |

### Interfaces per Model

| Model | eth0 | wlan0 | wlan1 |
|-------|------|-------|-------|
| ST30 | ✅ | ✅ (primary Wi-Fi) | ✅ (setup AP) |
| ST10 | ❌ (no ethernet) | ✅ | ✅ |
| ST300 | ✅ | ✅ | ✅ |

---

## GET /netStats

Low-level network statistics:

```xml
<network-data>
  <!-- Interface bindings, RSSI, frequency, packet counts -->
</network-data>
```

More detailed than `/networkInfo`. Includes RSSI values, packet statistics, interface bindings.
Useful for diagnosing connectivity issues.

---

## GET /getActiveWirelessProfile

Current Wi-Fi connection details:

```xml
<wireless-profile>
  <ssid>HomeNetwork</ssid>
</wireless-profile>
```

Returns the SSID of the currently connected Wi-Fi network.
---

## POST /performWirelessSiteSurvey

Scan for available Wi-Fi networks. Returns SSID list with signal strength and security type.
Asynchronous — results may take a few seconds to populate.

---

## POST /addWirelessProfile

Connect to a new Wi-Fi network:

```xml
<wirelessProfile ssid="NetworkName" security="WPA2" password="..."/>
```

**Warning**: If the new network is unreachable, the device may become inaccessible.
Use only when physically near the device to recover via USB setup if needed.

---

## POST /setWiFiRadio

Configure Wi-Fi radio settings (band preference, power level).
Rarely needed — device auto-selects optimal settings.
