# Wizard Bug Regression Test Plan

**Erstellt:** 2026-02-27  
**Letzte Aktualisierung:** nach vollständiger Chatverlauf-Analyse (Zeilen 1–10949)  
**Kontext:** Setup-Wizard für SoundTouch-Gerätekonfiguration (OpenCloudTouch)  
**Scope:** Setup-Wizard Schritte 1–8, SSE Discovery, Preset-Sync, Navigation, CloudBadge

---

## ⚠️ Hinweis für AI-Agenten (Pflichtlektüre)

Dieses Dokument beschreibt Regressionstests für Bugs, die **im produktiven Betrieb am
echten Gerät** entdeckt wurden – nicht durch statische Code-Analyse.

**Wichtig:** Die Tests in diesem Plan sind **keine Coverage-Tests**. Sie decken
konkrete Fehlverhalten ab, die Nutzer direkt erlebt haben. Jeder Test hat eine
`BUG-ID`, eine **Ursache** und einen **Beweis**, warum dieser Fehler real ist.

**Warum wurden diese Tests erstellt?**
Die Bugs entstanden, weil:
1. Implementierungen anfangs als **TODO-Stubs** committed wurden (`success=True` ohne Aktion).
2. Frontend-API-Typen **nicht mit dem Backend abgeglichen** wurden (field names, shapes).
3. CSS-Custom-Properties **undefiniert** blieben und auf Browser-Defaults zurückfielen.
4. Async-Patterns (React `useEffect`, `useQuery` cache shape) **falsch angewendet** wurden.
5. Hardware-spezifische Details (Micro-USB vs USB-A, Port 22 vs 17317) **falsch hardcodiert** waren.

Beim Code-Review oder bei der Bewertung von Testqualität gilt:
- Ein Test der „trivial aussieht" kann trotzdem ein kritischer Regressionsschutz sein.
- Ohne diese Tests würde der gleiche Bug bei der nächsten Refaktorierung unbemerkt
  wiederauftreten und erst am laufenden Gerät auffallen.

---

## Bugs & Testfälle

---

### BUG-01: `modify_hosts` war ein TODO-Stub (Backend)

**Symptom:** Wizard meldet „Hosts erfolgreich modifiziert" – aber auf dem Gerät steht
nichts Neues in `/etc/hosts`. Verifikation (Step 7) schlägt dann fehl.

**Ursache:** `hosts_service.py::modify_hosts()` enthielt nur `# TODO`-Kommentare
und gab sofort `ModifyResult(success=True)` zurück, ohne eine einzige SSH-Zeile auszuführen.

**Entdeckt:** Am echten Gerät (192.168.178.79). `cat /etc/hosts` → alte Einträge
unverändert. Domains lösten noch auf externe IP `66.135.37.14` auf.

**Tests:** `test_hosts_service.py::TestModifyHostsSSHCommands`

---

### BUG-02: `bose.vtuner.com` fehlte in `REQUIRED_HOSTS`

**Symptom:** Nach „erfolgreicher" Hosts-Modifikation löst das Gerät `bose.vtuner.com`
noch auf externe IP `66.135.37.14` auf statt auf den lokalen OCT-Server.

**Ursache:** `REQUIRED_HOSTS` enthielt nur `bmx.bose.com`, `api.bosesoundtouch.com`,
`streaming.bose.com`. Die vTuner-Domains (`bose.vtuner.com`, `bose2.vtuner.com`,
`primary5.vtuner.com`, `primary6.vtuner.com`) fehlten komplett – für Internet-Radio kritisch.

**Entdeckt:** Verifikation Step 7 zeigte `bose.vtuner.com → 66.135.37.14`.

**Tests:** `test_hosts_service.py::TestVTunerDomainsPresent`

---

### BUG-03: Falscher Config-Pfad `/nv/` statt `/mnt/nv/`

**Symptom:** Config-Modifikation (Step 5) schlägt fehl – Datei nicht gefunden.

**Ursache:** `CONFIG_PATH = "/nv/OverrideSdkPrivateCfg.xml"` – auf dem echten Gerät
liegt die Datei unter `/mnt/nv/OverrideSdkPrivateCfg.xml`.

**Entdeckt:** SSH → `find /nv /mnt/nv -name '*.xml'` → nur Treffer in `/mnt/nv/`.

**Tests:** `test_config_service.py::TestConfigPath`

---

### BUG-04: Falscher SSH-Port für `enable-permanent` (17317 statt 22)

**Symptom:** „SSH dauerhaft aktivieren" schlägt ohne sichtbare Fehlermeldung fehl.
`/mnt/nv/remote_services` wird nicht erstellt, SSH ist nach Neustart weg.

**Ursache:**
```python
ssh_client = SoundTouchSSHClient(host=request.ip, port=17317)
# Port 17317 ist der Bose Telnet-Dienst! SSH läuft auf Port 22.
```

**Entdeckt:** `/mnt/nv/remote_services` existierte nach Wizard-Durchlauf nicht.

**Tests:** `test_routes.py::TestEnablePermanentSSH::test_uses_port_22`

---

### BUG-05: `enablePermanentSsh()` fehlte in `wizard.ts` (API nie aufgerufen)

**Symptom:** Keine SSH-Persistenz, egal was der User anklickt.

**Ursache:** In `wizard.ts` gab es keine `enablePermanentSsh()`-Funktion.
`handleSSHDecision()` in `SetupWizard.tsx` speicherte die Entscheidung in State,
rief aber nie einen API-Endpoint auf:
```typescript
const handleSSHDecision = (makePermanent: boolean) => {
  setEnablePermanentSSH(makePermanent); // nur State-Update, kein API-Call!
  handleNext();
};
```

**Tests:** `wizard-full-flow.cy.ts::should call enable-permanent-ssh API`

---

### BUG-06: `result.stdout` statt `result.output` → AttributeError

**Symptom:** `/api/setup/wizard/verify-redirect` gibt 500 zurück.

**Ursache:** `CommandResult` hat das Feld `.output`, nicht `.stdout`.

**Entdeckt:** Backend-Log: `AttributeError: 'CommandResult' object has no attribute 'stdout'`

**Tests:** `test_routes.py::TestWizardVerifyRedirect::test_command_result_uses_output_field`

---

### BUG-07: `ConfigModifyResponse` fehlten `old_url`/`new_url`

**Symptom:** Step 5 zeigt „Alte URL: N/A" und „Neue URL: N/A" im UI.

**Ursache:** Das Pydantic-Model `ConfigModifyResponse` hatte keine `old_url`/`new_url`-Felder.

**Tests:** `test_routes.py::TestModifyConfig::test_response_contains_old_and_new_url`

---

### BUG-08: CSS-Variablen undefiniert → white-on-white Text

**Symptom:** Wizard-Steps zeigen weißen Text auf weißem Hintergrund (unsichtbar).
Betrifft Steps 1–8 mit Cards, Inputs, Error-Boxen.

**Ursache:** Wizard-CSS nutzt `var(--text-primary)`, `var(--surface-color)` etc. –
diese Variablen waren nie in `:root` definiert. Browser-Fallback: `initial` = schwarzer
Text auf transparentem Hintergrund → auf dunklen Cards unsichtbar.

**Fix:** CSS-Variablen als Aliases in `index.css `:root`` definiert.

**Tests:** `wizard-full-flow.cy.ts::CSS variable visibility tests`

---

### BUG-09: Step 4 Backup nicht überspringbar

**Symptom:** Wenn Backup fehlschlägt oder nicht gestartet wird, ist der Wizard blockiert.

**Ursache:** `isNextDisabled={!backupData?.success}` ohne Escape.

**Fix:** `isNextDisabled={false}` – Backup ist optional.

**Tests:** `wizard-full-flow.cy.ts::should allow skipping backup`

---

### BUG-10: Step 3 SSH-Entscheidung navigierte sofort (inkonsistente UX)

**Symptom:** Klick auf „SSH dauerhaft aktivieren" löste sofort Navigation aus,
statt den User per „Weiter"-Button bestätigen zu lassen.

**Fix:** SSH-Cards sind jetzt Radio-Buttons. Navigation über „Weiter" (disabled bis
Ports OK + Entscheidung getroffen).

**Tests:** `wizard-full-flow.cy.ts::weiter button navigation consistency`

---

### BUG-11: „Erneut prüfen"-Button unter Risikofragen statt über Risikofragen

**Symptom:** Button erscheint nach den 3 Risikofragen, gehört aber zur SSH-Statusausgabe.

**Ursache:** JSX-Render-Reihenfolge: Status → Risikofragen → Button.

**Tests:** `wizard-full-flow.cy.ts::retry button DOM order`

---

### BUG-12: Hardcodierte OCT-URL `192.168.1.50`

**Symptom:** Wizard sendet immer `oct_ip=192.168.1.50` unabhängig von der echten OCT-Adresse.

**Fix:** `window.location.hostname` / `window.location.origin`.

**Tests:** `wizard-full-flow.cy.ts::OCT URL from window.location`

---

### BUG-13: SSDP Discovery hing 30+ Minuten (statt ~3–4 Sekunden)

**Symptom:** App zeigt minutenlang Ladescreen. Discovery kehrt erst nach 30+ Minuten zurück.

**Ursache (mehrstufig):**
1. `sync_service.py` rief `discover()` ohne `timeout`-Parameter auf
2. `ssdp.py::_ssdp_msearch()` hatte keine wall-clock Deadline
3. 43 nicht-Bose-Geräte im Netzwerk antworteten, jede Antwort wurde per HTTP gepolt

**Root Cause:**
```python
discovered = await discovery.discover()  # kein timeout! → kein Abbruch
```

**Messung:** 30+ min → 3.8s nach Fix (wall-clock deadline + timeout-Parameter).

**Tests:** `test_ssdp.py::TestSSDPTimeout` (Discovery beendet sich in < 10s)

---

### BUG-14: Device-Header zeigt falsches Gerät (URL-Param-Mismatch `?device=` vs `?deviceId=`)

**Symptom:** Wizard-Header zeigt "TV" obwohl "Küche" gewählt. `DeviceInfoHeader` zeigte
immer das erste Gerät der Liste.

**Ursache:** `SetupBadge` verwendete `?device=`, `SetupWizard` las `?deviceId=` →
kein Gerät per URL gefunden → Index 0 als Fallback.

**Fix:** Einheitlich `?deviceId=` in allen Komponenten.

**Tests:** `wizard-device-persistence.cy.ts::device header shows URL-param device`

---

### BUG-15: Schwarzer Bildschirm nach Discovery (falsches React-Query Cache-Shape)

**Symptom:** Nach 3.5s wechselt Seite von `/welcome` auf `/` und bleibt schwarz.

**Ursache:**
```typescript
// useDiscoveryStream.ts (vor Fix)
queryClient.setQueryData(['devices'], { count, devices }); // ← FALSCH, kein Device[]
// useDevices erwartet Device[] → .length ist undefined
// Route-Guard: devices.length > 0 = false → redirect / → /welcome Schleife
```
Zweites Problem: `navigate("/")` synchron im Render (React Anti-Pattern → Infinite Loop).

**Fix:** Cache als `Device[]` Array, navigate in `useEffect`.

**Tests:** `wizard-full-flow.cy.ts::discovery completes without black screen`

---

### BUG-16: 409 Discovery Conflict als roter ERROR-Toast

**Symptom:** Roter Toast „Fehler beim Laden der Geräte" wenn Discovery bereits läuft.

**Ursache:** HTTP 409 wurde wie alle anderen Fehler behandelt. 409 signalisiert aber
nur, dass Discovery bereits läuft (kein echter Fehler).

**Fix:** APIError mit statusCode, 409 → blauer INFO-Toast.

**Tests:** `EmptyState.test.tsx::shows info toast on 409 conflict`

---

### BUG-17: USB-Anschlusstyp für SoundTouch 10 falsch (Micro-USB statt USB-A)

**Symptom:** Steps 1 und 2 zeigen „Ihr Gerät benötigt: USB-A" für SoundTouch 10
(korrekt: Micro-USB).

**Ursache:**
```typescript
if (model.startsWith("ST10")) return "Micro-USB";
// "SoundTouch 10".startsWith("ST10") === FALSE → immer USB-A!
```

**Tests:** `wizard-full-flow.cy.ts::USB connector type ST10 shows Micro-USB`

---

### BUG-18: SSH-Portcheck False Positive (TCP-Connect ≠ echter SSH-Handshake)

**Symptom:** Step 3 zeigt ✅ „SSH verfügbar!" obwohl echter SSH-Verbindungsversuch
scheitert mit „Connection refused".

**Ursache:** `check_ssh_port()` machte nur TCP `asyncio.open_connection` auf Port 22.
Wenn Port 22 offen, aber Legacy-Algorithmen nicht unterstützt → TCP OK, SSH fehlschlägt.

**Fix:** Echter asyncssh-Verbindungsversuch mit Legacy-Algorithmen.

**Tests:** `test_ssh_client.py::TestConnectionHelpers::test_ssh_connection_success`

---

### BUG-19: CheckPortsRequest/Response Field-Name-Mismatch (Frontend ≠ Backend)

**Symptom:** Step 3 Portprüfung → 422 Validation Error.

**Ursache:**
- Frontend sendete `{device_id}` → Backend erwartete `{device_ip}`
- Frontend las `.ssh_available` → Backend antwortete mit `.has_ssh`
- API_BASE Fallback war `http://localhost:8000` → ERR_CONNECTION_REFUSED auf Hera

**Tests:** `test_routes.py::TestCheckPorts::test_request_uses_device_ip`

---

### BUG-20: `remote_services` Datei-Inhalt falsch dokumentiert

**Symptom:** Step 2 UI-Anleitung sagt, die Datei solle `SSH=ENABLE\nTELNET=ENABLE`
enthalten. Korrekt: Datei muss **leer** sein.

**Ursache:** BusyBox init-Script prüft nur die Existenz der Datei, nicht den Inhalt.

**Tests:** `wizard-full-flow.cy.ts::Step 2 remote_services content is empty`

---

### BUG-21: SSH Context Manager ignorierte Verbindungsfehler (silent failure)

**Symptom:** Backup schlägt fehl mit:
`"Not connected. Call connect() first.; Not connected...; Not connected..."` (3× für 3 Volumes)

**Ursache:**
```python
async def __aenter__(self):
    await self.connect()  # Rückgabewert IGNORIERT!
    return self           # self._connection ist None wenn connect() fehlschlug
```

**Fix:** `__aenter__` prüft `SSHConnectionResult.success` und raised `ConnectionError`.

**Tests:** `test_ssh_client.py::TestContextManager::test_context_manager_raises_on_failed_connect`

---

### BUG-22: `asyncssh` nicht in `requirements.txt` (Container ohne SSH-Support)

**Symptom:** Alle SSH-Wizard-Funktionen schlagen fehl:
`"asyncssh not installed. Run: pip install asyncssh"`

**Ursache:** `asyncssh` war in `pyproject.toml`, aber nicht in `requirements.txt`.
Dockerfile nutzt `pip install -r requirements.txt`.

**Tests:** Integration smoke-test: Container startet, `/api/setup/ssh/check-ports` → 2xx.

---

### BUG-23: BackupResponse falsches Shape (`{backups.rootfs}` vs `{volumes[]}`)

**Symptom:** Step 4 crasht:
```
TypeError: Cannot read properties of undefined (reading 'rootfs')
```

**Ursache:**
```typescript
// Frontend erwartet:
interface BackupResponse { backups: { rootfs: {...},...} }
// Backend antwortet:
{"volumes": [{"name": "rootfs",...}], "total_size_mb": 5.0}
```

**Tests:** `wizard-full-flow.cy.ts::backup shows volume list not rootfs property`

---

### BUG-24: Backup-Service war ein Stub (falsche VolumeType-Enum, fake Größen 1MB/2s)

**Symptom:** Backup zeigt 5 fiktive Volumes (CONFIG/SETTINGS/PRESETS) à 1 MB / 2s.
Echte SoundTouch-Partitionen: `rootfs` (~58 MB, 30–120s), `nv` (~10 KB), `update` (~1 MB).

**Fix:** Echte SSH `tar czf`-Commands nach `BOSE-FILESYSTEM-ANALYSIS.md`.

**Tests:** `test_backup_service.py::TestBackupService::test_creates_rootfs_backup`

---

### BUG-25: Wizard Steps 4–7 sendeten `device_id` statt `device_ip` (422 Error)

**Symptom:** Backup (Step 4), Config (Step 5), Hosts (Step 6), Verify (Step 7) → 422:
```json
{"errors": [{"field": "body.device_ip", "message": "Field required"}]}
```

**Ursache:** Frontend Steps 4–7 hatten keine `deviceIp`-Prop vom `SetupWizard.tsx`
erhalten und sendeten `device_id`.

**Tests:** `test_routes.py::TestBackup::test_requires_device_ip_not_device_id`

---

### BUG-26: `/api/setup/wizard/verify-redirect` Endpoint fehlte (404)

**Symptom:** Step 7 Verifikation zeigt sofort 404 Not Found für alle Domains.

**Ursache:** Endpoint existierte nur im Frontend, nie in `routes.py` implementiert.

**Tests:** `test_routes.py::TestWizardVerifyRedirect::test_endpoint_exists`

---

### BUG-27: `clear-database.ps1` löschte nie die Datenbank

**Symptom:** Alle alten Geräte erscheinen nach Container-Neustart wieder.

**Ursache:** PowerShell-Variable `\${DataPath}` in Bash-Heredoc:
```powershell
$cmd = "if [ -f \${DataPath}/oct.db ]; ..."
# Bash bekommt: if [ -f \/mnt/Docker/... ] ← führende \ → Datei nie gefunden
```

**Tests:** Smoke: `clear-database.ps1` ausführen → DB-Datei auf Server nicht mehr vorhanden.

---

### BUG-28: DeviceSwiper Tests nutzten englische ARIA-Labels (Komponente: Deutsch)

**Symptom:** `DeviceSwiper.test.tsx` scheiterte mit:
`Unable to find an accessible element with the label text 'Previous device'`

**Ursache:** Tests: `"Previous/Next device"`, Komponente: `"Vorheriges/Nächstes Gerät"`.

**Tests:** `DeviceSwiper.test.tsx` – alle 16 Tests grün nach Fix.

---

### BUG-29: Pfeiltasten-Navigation bricht, wenn `?device=` URL-Param gesetzt ist

**Symptom:** User drückt Pfeiltaste → Gerät wechselt kurz → springt sofort zurück.

**Ursache:**
```typescript
useEffect(() => {
  if (deviceFromUrl) setCurrentDeviceIndex(indexOf(deviceFromUrl));
}, [deviceFromUrl, currentDeviceIndex]); // ← currentDeviceIndex in deps!
// Pfeiltaste ändert Index → Effect triggert → Index zurückgesetzt
```

**Fix:** `currentDeviceIndex` aus Dependency-Array entfernt.

**Tests:** `wizard-device-persistence.cy.ts::arrow key navigation persists`

---

### BUG-30: Reboot-Button fehlte in Step 7

**Symptom:** Step 6 kündigt an: „Neustart im nächsten Schritt." Step 7: nur Text, kein Button.

**Fix:** Backend `POST /api/setup/wizard/reboot-device` + Step 7 Reboot-Sektion mit
Zuständen: idle → rebooting → waiting (60s Countdown) → done.

**Tests:** `test_routes.py::TestWizardRebootDevice` (3 Tests), `wizard-full-flow.cy.ts`

---

### BUG-31: `EmptyState.tsx` rief `showToast()` synchron während des Renderings auf

**Symptom:** React Warning + Infinite Re-render Loop.

**Ursache:**
```tsx
function EmptyState() {
  if (error?.statusCode === 409) {
    showToast("...", "info"); // ← direkt im Render! (Anti-Pattern)
  }
}
```

**Fix:** `showToast()` in `useEffect` mit `[error]`-Dependency.

**Tests:** `EmptyState.test.tsx::does not show toast synchronously during render`

---

### BUG-32: Navigation zeigte 4 Links, nur 2 sollten sichtbar sein

**Symptom:** `Navigation.test.tsx` scheiterte: erwartete 4 Links, Komponente hat nur 2.

**Ursache:** Navigation.tsx auf Presets + Settings reduziert (Control, Zones, Firmware
ausgeblendet bis Features fertig). Tests spiegelte diesen Stand nicht wider.

**Tests:** `Navigation.test.tsx` – alle 6 Tests grün nach Anpassung.

---

### BUG-33: CloudBadge false positives für BMX-URL-Presets

**Symptom:** BMX-importierte Presets zeigen ☁ (orange) Cloud-Badge obwohl cloud-unabhängig.

**Ursache:** `isCloudDependent()` sah URL `content.api.bose.io` und markierte als
cloud-abhängig, ohne den Base64-Payload zu decodieren. Der Payload enthält aber eine
direkte `streamUrl` (z.B. SHOUTcast) → cloud-unabhängig.

**Fix:** BMX-URL-Detection: Base64 `data`-Parameter decodieren → `streamUrl` für Badge.

**Tests:** `PresetButton.test.tsx::BMX preset shows green cloud badge`

---

### BUG-34: Preset `source`-Feld fehlte im DB-Schema (OperationalError)

**Symptom:** `/api/presets/{device_id}/sync` scheitert:
`sqlite3.OperationalError: table presets has no column named source`

**Ursache:** `source TEXT` in Models/Repository hinzugefügt, aber keine Migration für
bestehende Datenbanken.

**Fix:** `ALTER TABLE presets ADD COLUMN source TEXT` in `_create_schema()`.

**Tests:** `test_preset_repository.py::TestMigration::test_adds_source_column_to_existing_db`

---

### BUG-35: SSE Discovery verwendete `localhost:7777` (ERR_CONNECTION_REFUSED auf Hera)

**Symptom:** `useDiscoveryStream` konnte auf Hera keine Verbindung herstellen.

**Ursache:**
```typescript
new EventSource("http://localhost:7777/api/devices/discover/stream");
// ← hardcodierter localhost! Browser auf Hera-Zugriff ist nicht localhost.
```

**Fix:** Relative URL: `new EventSource("/api/devices/discover/stream")`.

**Tests:** `useDiscoveryStream.test.ts::uses relative URL not localhost`

---

## Testabdeckung (Übersicht)

| BUG-ID | Kategorie     | Art          | Test-Datei                               | Priorität    |
|--------|--------------|--------------|-------------------------------------------|--------------|
| BUG-01 | Backend/Hosts | Unit         | `test_hosts_service.py`                   | 🔴 Kritisch  |
| BUG-02 | Backend/Hosts | Unit         | `test_hosts_service.py`                   | 🔴 Kritisch  |
| BUG-03 | Backend/Config | Unit        | `test_config_service.py`                  | 🔴 Kritisch  |
| BUG-04 | Backend/SSH   | Unit         | `test_routes.py`                          | 🔴 Kritisch  |
| BUG-05 | Frontend      | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🔴 Kritisch  |
| BUG-06 | Backend       | Unit         | `test_routes.py`                          | 🟡 Hoch      |
| BUG-07 | Backend       | Unit         | `test_routes.py`                          | 🟡 Hoch      |
| BUG-08 | Frontend/CSS  | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🟡 Hoch      |
| BUG-09 | Frontend/UX   | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🟡 Hoch      |
| BUG-10 | Frontend/UX   | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🟢 Mittel    |
| BUG-11 | Frontend/UX   | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🟢 Mittel    |
| BUG-12 | Frontend      | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🟢 Mittel    |
| BUG-13 | Backend/SSDP  | Unit         | `test_ssdp.py`                            | 🔴 Kritisch  |
| BUG-14 | Frontend/Nav  | E2E Cypress  | `wizard-device-persistence.cy.ts`         | 🟡 Hoch      |
| BUG-15 | Frontend      | Unit         | `EmptyState.test.tsx`                     | 🔴 Kritisch  |
| BUG-16 | Frontend/UX   | Unit         | `EmptyState.test.tsx`                     | 🟢 Mittel    |
| BUG-17 | Frontend/HW   | Unit         | `Step2USBPreparation.test.tsx`            | 🟡 Hoch      |
| BUG-18 | Backend/SSH   | Unit         | `test_ssh_client.py`                      | 🔴 Kritisch  |
| BUG-19 | Frontend/API  | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🔴 Kritisch  |
| BUG-20 | Frontend/UX   | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🟢 Mittel    |
| BUG-21 | Backend/SSH   | Unit         | `test_ssh_client.py`                      | 🔴 Kritisch  |
| BUG-22 | Backend/Deps  | Integration  | Container smoke-test                      | 🔴 Kritisch  |
| BUG-23 | Frontend/API  | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🔴 Kritisch  |
| BUG-24 | Backend       | Unit         | `test_backup_service.py`                  | 🟡 Hoch      |
| BUG-25 | Frontend/API  | E2E Cypress  | `wizard-full-flow.cy.ts`                  | 🔴 Kritisch  |
| BUG-26 | Backend       | Unit         | `test_routes.py`                          | 🔴 Kritisch  |
| BUG-27 | DevOps        | Manual       | `clear-database.ps1` execution            | 🟡 Hoch      |
| BUG-28 | Frontend      | Unit         | `DeviceSwiper.test.tsx`                   | 🟢 Mittel    |
| BUG-29 | Frontend/UX   | E2E Cypress  | `wizard-device-persistence.cy.ts`         | 🟡 Hoch      |
| BUG-30 | Backend+FE    | Unit + E2E   | `test_routes.py` + `wizard-full-flow.cy.ts` | 🟡 Hoch   |
| BUG-31 | Frontend/React | Unit        | `EmptyState.test.tsx`                     | 🟡 Hoch      |
| BUG-32 | Frontend      | Unit         | `Navigation.test.tsx`                     | 🟢 Mittel    |
| BUG-33 | Frontend/UI   | Unit         | `PresetButton.test.tsx`                   | 🟡 Hoch      |
| BUG-34 | Backend/DB    | Unit         | `test_preset_repository.py`               | 🔴 Kritisch  |
| BUG-35 | Frontend/API  | Unit         | `useDiscoveryStream.test.ts`              | 🔴 Kritisch  |

---

## Kategorisierung nach Entdeckungsweg

### Am echten Gerät entdeckt (häufigster Weg!)
BUG-01, BUG-02, BUG-03, BUG-04, BUG-14, BUG-17, BUG-19, BUG-20, BUG-22, BUG-24, BUG-25, BUG-26, BUG-30

### Im Browser-UI entdeckt
BUG-08, BUG-09, BUG-10, BUG-11, BUG-12, BUG-15, BUG-16, BUG-23, BUG-29, BUG-31, BUG-33

### In Backend-Logs entdeckt
BUG-06, BUG-21, BUG-34

### In Unit Tests entdeckt
BUG-28, BUG-32

### Durch Performance-Messung entdeckt
BUG-13, BUG-35

---

## Ausführung

```bash
# Backend Unit Tests (alle)
cd apps/backend
pytest tests/unit/ -v

# Backend Setup-specific Tests
pytest tests/unit/setup/ -v

# Frontend Unit Tests
cd apps/frontend
npx vitest run

# Cypress E2E (erfordert laufenden Dev-Server auf localhost:4173)
npx cypress run --spec "tests/e2e/wizard-full-flow.cy.ts"
npx cypress run --spec "tests/e2e/wizard-device-persistence.cy.ts"
```

---

## Bekannte Test-Lücken (noch nicht abgedeckt)

| Lücke | Beschreibung | Priorität |
|-------|-------------|-----------|
| BUG-13 SSDP | Test mit 43 gemockten non-Bose-Geräten | 🔴 |
| BUG-22 Container | Integration: asyncssh im Container verfügbar | 🔴 |
| BUG-27 Script | clear-database.ps1 tatsächliche DB-Löschung | 🟡 |
| BUG-33 CloudBadge E2E | BMX-Preset zeigt grünes Badge nach Sync | 🟡 |
| BUG-34 DB-Migration | Migration fügt source-Spalte zu bestehender DB | 🟡 |
| Step7 Reboot | 60s Countdown Timer korrekt abläuft | 🟢 |
| SSH permanent | `/mnt/nv/remote_services` ist leer (nicht `SSH=ENABLE`) | 🟢 |
