# TODO — Extraction Gaps & Future Research

Items that need hands-on device access or further research.

---

## Certificates & Keys to Extract

- [ ] Extract IoT client certificate from real device: `/mnt/nv/IoTCerts/iot-cert.pem.crt`
- [ ] Extract IoT private key: `/mnt/nv/IoTCerts/iot-private.pem.key`
- [ ] Extract AWS IoT Root CA: `/var/lib/iot/rootCA.crt`
- [ ] Dump full system trust store: `/etc/pki/tls/certs/ca-bundle.crt`
- [ ] Document exact CA chain used by Bose cloud services
- [ ] Analyze IoT certificate format (CN, SANs, validity, issuer)

## Configuration Files to Dump

- [ ] Full `SoundTouchSdkPrivateCfg.xml` from real device
- [ ] Full `Voice.xml` with TPDA token URL
- [ ] Full `Shepherd-noncore.xml` with service definitions
- [ ] `HandCraftedWebServer-SoundTouch.xml` internal API mapping
- [ ] `IoT.xml` with real clientID and endpoint
- [ ] `Sources.xml` with registered music accounts

## Binary Analysis

- [ ] Extract `libBmxAccountHsm.so` for IsItBose regex analysis
- [ ] Identify all hardcoded URLs in `BoseApp` binary
- [ ] Identify all hardcoded URLs in `IoT` binary
- [ ] Map SSL verification functions for potential bypass points
- [ ] Document binary format (ARM ELF 32-bit, exact version)

## Protocol Research

- [ ] Capture full `/power_on` request from real device boot
- [ ] Record Marge API responses for account/device queries
- [ ] Record BMX registry response format
- [ ] Record full preset sync flow (Marge ↔ device)
- [ ] Record Spotify token refresh flow end-to-end
- [ ] Capture SCMUDC telemetry batch with all event types
- [ ] Monitor AWS IoT MQTT shadow messages during state changes
- [ ] Document exact WebSocket handshake (protocol header "gabbo")

## Firmware Versions

- [ ] Catalog firmware versions and their behavioral differences
- [ ] Identify which versions enforce IsItBose check
- [ ] Identify which versions overwrite `/etc/hosts` on reboot
- [ ] Test XML config persistence across firmware updates

## Device Models

- [ ] Verify endpoint list consistency across ST10, ST20, ST30
- [ ] Test `/speaker` and `/playNotification` (ST-10 Series only?)
- [ ] Verify `/balance` availability on stereo-capable models
- [ ] Test advanced audio controls on high-end models

---

## Priority Order

1. **High**: Certificate extraction, config file dumps (needed for emulation)
2. **High**: `/power_on` and Marge API capture (needed for cloud replacement)
3. **Medium**: Binary analysis for redirect capability assessment
4. **Medium**: Full protocol capture for all cloud interactions
5. **Low**: Firmware version catalog, model-specific testing
