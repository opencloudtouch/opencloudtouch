# System, Power & Clock

Power management, standby, clock display, firmware updates, and factory reset.

→ Parent: [API Schema Reference](../api/README.md)
→ Related: [32-device-lifecycle.md](../32-device-lifecycle.md), [62-process-device-boot.md](../62-process-device-boot.md)

---

## GET /powerManagement

```xml
<powerManagementResponse>
  <powerState>FullPower</powerState>
  <battery>
    <capable>false</capable>
  </battery>
</powerManagementResponse>
```

| Field | Type | Values |
|-------|------|--------|
| `powerState` | enum | `FullPower`, `PowerSaving`, `Standby`, `LowPowerStandby` |
| `battery.capable` | boolean | `true` only for SoundTouch Portable |

---

## GET /systemtimeout

Auto-standby configuration:

```xml
<systemtimeout>
  <powersaving_enabled>true</powersaving_enabled>
</systemtimeout>
```

When enabled, device enters standby after ~20 minutes of inactivity.

---

## GET /systemtimeoutcontrol *(ST300 only)*

Extended standby options:

```xml
<systemtimeoutcontrol>
  <autopowerdown>true</autopowerdown>
  <screensaver>false</screensaver>
</systemtimeoutcontrol>
```

| Field | Description |
|-------|-------------|
| `autopowerdown` | Auto power-off after timeout |
| `screensaver` | Display screensaver in standby |

---

## POST /powersaving

Enter power-saving mode. GET returns `<status>/powersaving</status>`.

---

## POST /standby

Enter standby mode. Similar to pressing POWER key.

---

## POST /lowPowerStandby

Deep sleep mode. Minimal power consumption, device not discoverable via SSDP.

---

## POST /userActivity

Signal user activity to reset the auto-standby timer.
Sent by the SoundTouch app when the user interacts with the device UI.

---

## GET /clockDisplay

Clock display settings (devices with display only):

```xml
<clockDisplay>
  <timezone>Europe/Berlin</timezone>
  <timeFormat>TIME_FORMAT_24HOUR_ID</timeFormat>
  <brightness>70</brightness>
</clockDisplay>
```

| Field | Type | Values |
|-------|------|--------|
| `timezone` | string | IANA timezone |
| `timeFormat` | enum | `TIME_FORMAT_12HOUR_ID`, `TIME_FORMAT_24HOUR_ID` |
| `brightness` | int | 0-100 display brightness |

**POST** `/clockDisplay`: Same structure to update settings.

---

## GET /clockTime

Current device time:

```xml
<clockTime utcTime="1701824606" cueMusic="0"
  timeFormat="TIME_FORMAT_12HOUR_ID" brightness="70"
  clockError="0" utcSyncTime="1701820350">
  <localTime year="2023" month="11" dayOfMonth="5" dayOfWeek="2"
    hour="19" minute="3" second="26"/>
</clockTime>
```

| Field | Type | Description |
|-------|------|-------------|
| `@utcTime` | unix timestamp | Current UTC time |
| `@utcSyncTime` | unix timestamp | Last NTP sync time |
| `@clockError` | int | Clock drift in seconds |
| `localTime` | element | Broken-down local time |

---

## GET /swUpdateQuery

Firmware update status:

```xml
<SWUpdateQueryResponse state="IDLE" percentComplete="0"/>
```

| State | Meaning |
|-------|---------|
| `IDLE` | No update in progress |
| `DOWNLOADING` | Firmware downloading |
| `INSTALLING` | Firmware installing |
| `COMPLETE` | Update complete, reboot needed |

### POST /swUpdateStart

Trigger firmware update download + install. Device must have valid `swUpdateUrl`.

### POST /swUpdateAbort

Abort an in-progress firmware update.

### POST /swUpdateCheck

Check for available firmware updates without installing.

**Post-cloud-shutdown**: Updates no longer available from `worldwide.bose.com`.
Must point `swUpdateUrl` to local server → [11-device-redirect-methods.md](../11-device-redirect-methods.md).

---

## POST /factoryDefault

Factory reset. **DESTRUCTIVE** — erases all settings, presets, Wi-Fi profiles.

GET returns `<status>/factoryDefault</status>`.
POST triggers the reset immediately. No confirmation prompt.
