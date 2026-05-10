# Pairing, Setup & Internal Endpoints

Accessory pairing, initial setup, device internals, product identity, and reset functions.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [30-device-access.md](../30-device-access.md), [32-device-lifecycle.md](../32-device-lifecycle.md)

---

## Accessory Pairing

### POST /pairLightswitch

Start pairing a Bose SoundTouch Lightswitch:

```xml
<pairLightswitch/>
```

Response: `<status>/pairLightswitch</status>`

---

### POST /cancelPairLightswitch

Cancel ongoing Lightswitch pairing.

---

### POST /clearPairedList

Remove all paired accessories (Lightswitch, Boselink remotes).

---

### POST /enterPairingMode

Enter general pairing mode (Bluetooth, accessories):

```xml
<enterPairingMode/>
```

---

### POST /setPairedStatus

Set pairing status for a specific accessory.

---

### POST /setPairingStatus

Update device pairing state. Internal — used by pairing flow.

---

## Bluetooth Pairing

### POST /enterBluetoothPairing

Enter Bluetooth discoverable mode:

```xml
<enterBluetoothPairing/>
```

Device becomes visible for BT pairing for ~120 seconds.

---

### POST /clearBluetoothPaired

Remove all paired Bluetooth devices.

→ See also: [device-identity/ § /bluetoothInfo](../device-identity/README.md)

---

## Initial Setup

### POST /setup

Device initial setup endpoint. Used during first-time Wi-Fi configuration.
Part of the SoundTouch app onboarding flow.

---

## Internal Messaging

### POST /slaveMsg

Send internal message to a zone slave device. Used by zone master for
synchronization commands. Not intended for external use.

---

### POST /masterMsg

Send internal message to the zone master. Used by slaves for status reporting.

---

### GET /notification

Notification endpoint. Returns notification queue status.
Different from `/playNotification` (which triggers audio).

---

### GET /test

Device self-test endpoint. Returns test status.
Behavior varies by firmware version.

---

### GET /pdo

Product Data Object — low-level device configuration query.
Same system queried by Telnet `getpdo` command.

→ See [71-test-telnet-migration.md](../71-test-telnet-migration.md) for Telnet `getpdo` usage.

---

### GET /criticalError

Returns critical error state (if any):

```xml
<criticalError/>
```

Empty when no error. Populated during hardware failures or firmware corruption.

---

## Product Identity (write-only)

Factory provisioning endpoints. **POST-only**, used during manufacturing.

### POST /setProductSerialNumber

Set device serial number. Locked after initial provisioning.

### POST /setProductSoftwareVersion

Register software version. Updated during firmware install.

### POST /setComponentSoftwareVersion

Register component firmware version (DSP, Bluetooth module, etc.).

---

## BCO Reset

### GET /getBCOReset

BCO (Bose Cloud Operations) reset state:

```xml
<bcoreset/>
```

### POST /setBCOReset

Trigger BCO reset — clears cloud registration and re-initializes cloud connection.
Less destructive than `/factoryDefault` — preserves Wi-Fi and presets.

Only available if `bcoresetCapable=true` in `/capabilities`.
