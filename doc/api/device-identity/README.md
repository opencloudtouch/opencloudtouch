# Device Identity & Capabilities

Endpoints for device identification, feature discovery, and configuration status.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [01-api-endpoints.md](../01-api-endpoints.md), [32-device-lifecycle.md](../32-device-lifecycle.md)

---

## GET /info

Complete device profile. Primary identification endpoint.

```xml
<info deviceID="B92C7D383488">
  <name>Living Room</name>
  <type>SoundTouch 30</type>
  <margeAccountUUID>3385796</margeAccountUUID>
  <components>
    <component>
      <componentCategory>SCM</componentCategory>
      <softwareVersion>27.0.6.46330.5043500 epdbuild.trunk.hepdswbld04.2022-08-04T11:20:29</softwareVersion>
      <serialNumber>T7319248914831159111551</serialNumber>
    </component>
    <component>
      <componentCategory>PackagedProduct</componentCategory>
      <serialNumber>059740942236574FE</serialNumber>
    </component>
  </components>
  <margeURL>https://streaming.bose.com</margeURL>
  <networkInfo type="SCM">
    <macAddress>B92C7D383488</macAddress>
    <ipAddress>192.0.2.78</ipAddress>
  </networkInfo>
  <networkInfo type="SMSC">
    <macAddress>E56DAC1C82EF</macAddress>
    <ipAddress>192.0.2.78</ipAddress>
  </networkInfo>
  <moduleType>sm2</moduleType>
  <variant>mojo</variant>
  <variantMode>normal</variantMode>
  <countryCode>GB</countryCode>
  <regionCode>GB</regionCode>
</info>
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `@deviceID` | string | MAC-based unique ID (12 hex chars) |
| `type` | string | Model name: `SoundTouch 10`, `SoundTouch 30`, `SoundTouch 300` |
| `margeAccountUUID` | string | 7-digit Bose Cloud account ID. Empty = not paired |
| `margeURL` | string | Cloud server URL. Key for migration → [11-device-redirect-methods.md](../11-device-redirect-methods.md) |
| `moduleType` | enum | `sm2` = Wi-Fi module type |
| `variant` | enum | `mojo` (ST30), `rhino` (ST10), others per model |
| `variantMode` | enum | `normal`, `setup` |
| `countryCode` | string | ISO 3166-1 alpha-2, affects service availability |
| `components[].componentCategory` | enum | `SCM` (system), `PackagedProduct` (hardware) |
| `components[].softwareVersion` | string | Full firmware version with build info |

### Model Differences

- **ST10**: No `SMSC` networkInfo entry
- **ST300**: Additional component entries for soundbar modules

---

## GET /name

Device display name. Writable via POST.

```xml
<name>Living Room</name>
```

**POST** `/name`: `<name>New Name</name>` → returns updated `/info`.

---

## GET /capabilities

Feature matrix. Determines which advanced endpoints are available.

```xml
<capabilities deviceID="B92C7D383488">
  <networkConfig>
    <dualMode>true</dualMode>
    <wsapiproxy>true</wsapiproxy>
    <allInterfacesSupported/>
    <wlanInterfaces/>
    <security/>
  </networkConfig>
  <dspCapabilities>
    <dspMonoStereo available="false"/>
  </dspCapabilities>
  <lightswitch>false</lightswitch>
  <clockDisplay>true</clockDisplay>
  <capability name="systemtimeout" url="/systemtimeout" info=""/>
  <capability name="rebroadcastlatencymode" url="/rebroadcastlatencymode" info=""/>
  <lrStereoCapable>false</lrStereoCapable>
  <bcoresetCapable>false</bcoresetCapable>
  <disablePowerSaving>true</disablePowerSaving>
</capabilities>
```

### Capability Flags

| Flag | When `true` |
|------|------------|
| `dualMode` | Ethernet + Wi-Fi simultaneously |
| `wsapiproxy` | WebSocket API proxy available |
| `dspMonoStereo` | `/DSPMonoStereo` endpoint works |
| `lightswitch` | Lightswitch pairing supported |
| `clockDisplay` | Has display for clock |
| `lrStereoCapable` | Can form stereo pair |
| `bcoresetCapable` | BCO reset available |
| `disablePowerSaving` | Can disable auto-standby |

### Model Differences

- **ST300**: Additional capabilities for `audiodspcontrols`, `audioproducttonecontrols`, `audioproductlevelcontrols`, `productcechdmicontrol`
- **ST10**: `lrStereoCapable=true` (can stereo-pair with another ST10)

---

## GET /supportedURLs

Complete API surface of the device. Returns all available endpoints.

→ Full list: [01-api-endpoints.md § Complete Endpoint List](../01-api-endpoints.md)

```xml
<supportedURLs deviceID="B92C7D383488">
  <URL location="/info"/>
  <URL location="/capabilities"/>
  <URL location="/powerManagement"/>
  <!-- ... 90+ more ... -->
</supportedURLs>
```

**93 endpoints** returned from ST30. Count varies by model.

---

## GET /bluetoothInfo

Bluetooth MAC address.

```xml
<BluetoothInfo BluetoothMACAddress="AA:BB:CC:DD:EE:02"/>
```

Single attribute. No status or pairing info — see `/enterBluetoothPairing` for pairing control.

---

## GET /language

System language setting.

```xml
<sysLanguage>0</sysLanguage>
```

| Value | Language |
|-------|----------|
| 0 | English |
| 1 | French |
| 2 | German |
| 3 | Spanish |
| 4 | Italian |
| 5 | Portuguese |
| 6 | Dutch |
| 7 | Swedish |
| 8 | Japanese |
| 9 | Chinese |
| 10 | Korean |

---

## GET /soundTouchConfigurationStatus

Setup completion status.

```xml
<soundTouchConfigurationStatus status="SOUNDTOUCH_CONFIGURED"/>
```

| Value | Meaning |
|-------|---------|
| `SOUNDTOUCH_CONFIGURED` | Setup complete, device operational |
| `SOUNDTOUCH_NOT_CONFIGURED` | First-time setup needed |
