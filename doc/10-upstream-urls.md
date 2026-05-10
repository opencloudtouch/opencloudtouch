# Upstream Bose Cloud URLs & Domains

SoundTouch devices communicate with several Bose cloud services.
All are scheduled for shutdown on **May 6, 2026**.

## Core Service Domains

| Service | Domain | Purpose |
|---------|--------|---------|
| **Marge** | `streaming.bose.com` | Account management, streaming source providers, preset sync |
| **BMX Registry** | `content.api.bose.io` | Bose Media eXchange — service discovery and content registry |
| **Stats/Analytics** | `events.api.bosecm.com` | Telemetry, device events, usage statistics (SCMUDC) |
| **Software Update** | `worldwide.bose.com` | Firmware update checks and downloads (path: `/updates/soundtouch`) |
| **Voice/Alexa** | `voice.api.bose.io` | Token management for Amazon Alexa and IoT certificate registration |
| **OAuth Proxy** | `oauth.streaming.bose.com` | Bose-mediated OAuth token exchange (Spotify, etc.) |

---

## Internal / Development Domains

Discovered from firmware binary analysis and community research (SoundCork Issue #128):

### Marge & Auth Proxies
- `bose-test.apigee.net/margeproxy` — Integration/test proxy
- `bose-test.apigee.net/margeproxyefe`
- `streamingstg.bose.com` — Staging
- `streamingintoauth.bose.com` — Internal auth
- `streamingefeintoauth.bose.com` — Internal EFE auth
- `streamingefeint.bose.com`

### BMX & Content Registry
- `test.content.api.bose.io`
- `content.api.bose.io/bmx/registry/v1/services`
- `test.content.api.bose.io/bmx/int-registry/v1/services`
- `test.content.api.bose.io/bmx/efe-registry/v1/services`

### Stats & Analytics
- `eventsdev.api.bosecm.com`
- `eventsefe.api.bosecm.com`
- `eventsdev.bosecm.com`

### Software Updates
- `worldwide.bose.com/updates/soundtouch-int` — Internal builds
- `worldwide.bose.com/updates/soundtouch-efe` — EFE builds

---

## Third-Party Services

Devices also communicate directly with third-party providers:

- **Pandora**: `device-tuner.pandora.com`, `device-tuner-beta.savagebeast.com`
- **Amazon AVS**: `avs.na.amazonalexa.com`
- **Spotify**: via Bose OAuth proxy (not direct)

---

## On-Device Configuration Files

### `/opt/Bose/etc/SoundTouchSdkPrivateCfg.xml`
Primary URL configuration:
```xml
<SoundTouchSdkPrivateCfg>
  <margeServerUrl>https://streaming.bose.com</margeServerUrl>
  <statsServerUrl>https://events.api.bosecm.com</statsServerUrl>
  <swUpdateUrl>https://worldwide.bose.com/updates/soundtouch</swUpdateUrl>
  <bmxRegistryUrl>https://content.api.bose.io/bmx/registry/v1/services</bmxRegistryUrl>
</SoundTouchSdkPrivateCfg>
```

### `/opt/Bose/etc/Voice.xml`
```xml
<TPDATokenUrl>https://voice.api.bose.io</TPDATokenUrl>
```

### `/opt/Bose/etc/HandCraftedWebServer-SoundTouch.xml`
Internal local API mapping.

---

## Hardcoded Domain Validation (IsItBose)

The library `libBmxAccountHsm.so` contains a hardcoded regex:
```
^https:\/\/bose-[a-zA-Z0-9\.\_\-\$\%]\+\.apigee\.net\/
```

This regex ensures that certain BMX/account services must reside on the
`apigee.net` domain under a `bose-` prefix. This validation must be patched
(binary patching) if you want to redirect these services to a custom domain.

---

## Requirements for Offline Operation

To achieve full offline operation or redirect to a local replacement service,
**all** of the above domains must either be:
1. Redirected via DNS (device `/etc/hosts`)
2. Updated in the XML configuration files (`SoundTouchSdkPrivateCfg.xml`)
3. For domains not exposed in XML: binary patching or DNS-level redirection

See [11-device-redirect-methods.md](11-device-redirect-methods.md) for implementation details.

---

## Sources
- [SoundCork Issue #128](https://github.com/deborahgu/soundcork/issues/128)
- gesellix/Bose-SoundTouch firmware analysis
- Official Bose SoundTouch Web API v1.0 specification
