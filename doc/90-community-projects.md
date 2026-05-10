# Community Projects & References

Projects and resources relevant to SoundTouch reverse engineering and local operation.

---

## Active Projects

### SoundCork
- **Repo**: https://github.com/deborahgu/soundcork
- **Language**: Python
- **Focus**: Pioneered cloud service interception and emulation
- **Key contributions**:
  - Service emulation architecture (Marge, BMX)
  - BMX/Marge endpoint discovery
  - Device migration strategies
  - IsItBose regex research (Issue #62)
  - Comprehensive internal JS controller analysis (Issue #128)
  - ETag case-sensitivity bug (Issue #129)
  - Radio-Browser.info integration research (Issue #150)

### AfterTouch (gesellix/Bose-SoundTouch)
- **Repo**: https://github.com/gesellix/Bose-SoundTouch
- **Language**: Go
- **Focus**: Comprehensive toolkit — CLI client, service emulation, web UI
- **Key contributions**:
  - Full Go client library for all 103 endpoints
  - `soundtouch-service` local cloud replacement
  - `soundtouch-backup` cloud/speaker data backup
  - Web management UI with migration wizard
  - Real-time WebSocket event monitoring
  - Extensive documentation of Bose protocols

### ÜberBöse API
- **Repo**: https://github.com/julius-d/ueberboese-api
- **Language**: —
- **Focus**: Advanced API research and endpoint discovery
- **Key contributions**:
  - SCMUDC telemetry format documentation
  - Boot-time source availability behavior (Issue #3)
  - Advanced endpoint discovery beyond official API

### SoundTouch Plus (Home Assistant)
- **Repo**: https://github.com/thlucas1/homeassistantcomponent_soundtouchplus
- **Language**: Python
- **Focus**: Home Assistant integration component
- **Key contributions**:
  - [Comprehensive API Wiki](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/wiki/SoundTouch-WebServices-API)
  - Documented `POST /storePreset` and `POST /removePreset` (officially "N/A")
  - Real-world testing across many device models

### SoundTouch Hook
- **Repo**: https://github.com/CodeFinder2/bose-soundtouch-hook
- **Focus**: Runtime process instrumentation via Frida
- **Use case**: Monitor/override internal behavior, handle unknown hostnames,
  deep-hook service discovery logic

---

## Official Documentation

### Bose SoundTouch Web API v1.0
- **PDF**: https://assets.bosecreative.com/m/496577402d128874/original/SoundTouch-Web-API.pdf
- **Date**: January 7, 2026
- **Scope**: 19 official endpoints, WebSocket events
- **Gaps**: Missing many functional endpoints, `POST /presets` marked "N/A"

### Bose SoundTouch Web API v1.1
- More recent, additional details
- Not widely available

### Bose End-of-Life Announcement
- **URL**: https://www.bose.com/soundtouch-end-of-life
- **Cloud shutdown**: May 6, 2026
- All cloud services discontinued

---

## Key Community Findings

| Finding | Source | Impact |
|---------|--------|--------|
| 103 endpoints (vs 19 official) | AfterTouch | Most functionality undocumented |
| `storePreset`/`removePreset` work | SoundTouch Plus Wiki | Full preset CRUD possible |
| IsItBose regex in binaries | SoundCork #62 | Must patch for custom domains |
| ETag case-sensitivity bug | SoundCork #129 | Breaks preset sync |
| Boot-time source availability | ÜberBöse #3 | TUNEIN vanishes if cloud unreachable at boot |
| Marge group endpoints | SoundCork | Stereo pairing via cloud API |
| SCMUDC telemetry format | ÜberBöse | Base64-encoded XML in JSON events |
| Device SSH via USB stick | Community | `remote_services` file enables root access |
