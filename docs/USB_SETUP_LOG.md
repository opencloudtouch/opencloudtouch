# SoundTouch USB Setup - Protokoll

**Datum:** 2026-02-15  
**Gerät:** Bose SoundTouch 20 (Küche)  
**Ziel:** BMX Server URL via USB-Direktverbindung ändern

---

## Übersicht: Was wir machen

1. USB-Kabel an "Setup" Port (Micro-USB hinten am Gerät)
2. PC erkennt Netzwerk-Interface (203.0.113.1)
3. Telnet → SSH aktivieren
4. SSH → Config ändern (`bmxRegistryUrl`)
5. Reboot → Gerät nutzt OCT Server

---

## Schritt 1: USB-Verbindung testen

**Status:** ✅ ERFOLGREICH

**Aktion:**
```
Browser: http://203.0.113.1:17008/update.html
```

**Ergebnis:** Firmware-Upload-Seite wird angezeigt!

**Erkenntnis:** 
- USB-Kabel muss Daten-fähig sein (nicht nur Ladekabel)
- Windows erkennt automatisch USB-Netzwerk-Interface
- IP ist fest: `203.0.113.1`

---

## Schritt 2: Telnet-Verbindung herstellen

**Status:** 🔄 IN ARBEIT

**Problem #1:** Telnet nicht installiert
```
telnet 203.0.113.1 17000
telnet : Die Benennung "telnet" wurde nicht als Name eines Cmdlet...
```

**Ursache:** Windows hat Telnet-Client standardmäßig deaktiviert.

**Lösung:** Admin-PowerShell:
```powershell
dism /online /Enable-Feature /FeatureName:TelnetClient
```

**Ergebnis:** ✅ ERFOLGREICH
```
Features werden aktiviert
[==========================100.0%==========================]
Der Vorgang wurde erfolgreich beendet.
```

---

### Schritt 2b: Telnet-Verbindung aufbauen

**Status:** ✅ ERFOLGREICH

**Aktion:**
```powershell
telnet 203.0.113.1 17000
```

**Ergebnis:** `->` Prompt erscheint sofort!

---

## Schritt 3: Firmware-Version prüfen

**Status:** ✅ ERFOLGREICH

**Aktion:**
```
sys ver
```

**Ergebnis:**
```
BoseApp version: 27.0.6.46330.5043500 epdbuild.trunk.hepdswbld04.2022-08-04T11:20:29
```

**Erkenntnis:** 
- Firmware 27.0.6 ist die "Bluetooth Version" (gut für Modding!)
- Build-Datum: 2022-08-04
- Diese Version sollte `remote_services` unterstützen

---

## Schritt 4: SSH/Telnet dauerhaft aktivieren

**Status:** 🔄 IN ARBEIT

**Versuch 1:** `remote_services on`
```
->remote_services on
Command not found
```

**Versuch 2:** `local_services on`
```
->local_services on
Command not found
```

**Versuch 3:** `help`
```
->help
Command not found
```

**Erkenntnis:** Firmware 27.0.6 hat die meisten Befehle entfernt/versteckt!

Auch in PuTTY getestet - gleiches Ergebnis (kein PowerShell-Problem).

---

### Alternative: USB-Stick Methode

**Laut Internet-Research funktioniert:**
1. USB-Stick (FAT32 formatiert)
2. Leere Datei `remote_services` erstellen (ohne Endung!)
3. USB-Stick in SoundTouch einstecken
4. SoundTouch neustarten (Strom aus/ein)
5. SSH/Telnet sollte dann aktiv sein

---

## Schritt 3: SSH aktivieren

**Status:** ⏳ AUSSTEHEND

**Erwartete Befehle (im Telnet-Prompt `->`):**
```
sys ver
# Zeigt Firmware-Version

remote_services on
# ODER (bei neuerer Firmware):
# Leere Datei "remote_services" auf USB-Stick → einstecken → reboot
```

---

## Schritt 4: SSH-Verbindung und Config ändern

**Status:** ⏳ AUSSTEHEND

**Erwartete Befehle:**
```bash
ssh root@203.0.113.1
# (kein Passwort)

# Config bearbeiten:
vi /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml

# Ändern:
# <bmxRegistryUrl>https://content.api.bose.io/bmx/registry/v1/services</bmxRegistryUrl>
# zu:
# <bmxRegistryUrl>http://192.168.178.11:7777/bmx/registry/v1/services</bmxRegistryUrl>

# Speichern und Reboot:
reboot
```

---

## Schritt 5: Verifizieren

**Status:** ⏳ AUSSTEHEND

**Test:**
- SoundTouch App öffnen
- Preset drücken
- Gerät sollte Stream von OCT Server fetchen

---

## Hardware-Anforderungen

| Teil | Beschreibung | Status |
|------|--------------|--------|
| USB-Kabel (Micro-USB) | Daten-fähig, nicht nur Ladekabel | ✅ Vorhanden |
| PC mit Windows | Für Telnet/SSH | ✅ Vorhanden |
| Telnet-Client | Windows-Feature oder PuTTY | 🔄 Setup |

---

## Erkenntnisse & Learnings

### Was funktioniert
- ✅ USB-Verbindung wird automatisch als Netzwerk erkannt
- ✅ IP ist immer `203.0.113.1`
- ✅ Browser-Zugriff auf Firmware-Upload funktioniert

### Schwierigkeiten
- ❌ Telnet muss auf Windows erst aktiviert werden
- [weitere folgen...]

### Offene Fragen
- Funktioniert `remote_services on` auf aktueller Firmware?
- Ist Root-Filesystem beschreibbar?
- Persistiert Config-Änderung nach Reboot?

---

## Für End-User Dokumentation

**Minimale Hardware-Kosten:** ~3€ (USB-Kabel)

**Technisches Niveau:** Mittel (Telnet/SSH Befehle)

**Alternative für Nicht-Techniker:** Windows-Tool das alles automatisch macht (TODO: implementieren)
