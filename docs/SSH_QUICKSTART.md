# SoundTouch SSH Aktivierung - Quick Start

## Vorbereitung (HEUTE)

### 1. USB-Stick vorbereiten

```powershell
# PowerShell als Admin ausführen

# USB-Stick Laufwerksbuchstabe ermitteln (z.B. E:)
Get-Volume

# FAT32 formatieren (ACHTUNG: Löscht alle Daten!)
# Ersetze E: mit deinem Laufwerksbuchstaben
Format-Volume -DriveLetter E -FileSystem FAT32 -NewFileSystemLabel "BOSE"

# Leere remote_services Datei erstellen (OHNE Extension!)
New-Item -Path "E:\remote_services" -ItemType File
```

**WICHTIG:** Die Datei heißt `remote_services` - NICHT `remote_services.txt`!

### 2. Prüfen ob Datei korrekt erstellt wurde

```powershell
# Muss "remote_services" anzeigen (ohne .txt)
Get-ChildItem E:\ -Force
```

---

## Durchführung (MORGEN ABEND)

### Schritt 1: USB-Stick anschließen

```
1. SoundTouch AUSSCHALTEN (Power-Taste lang drücken, Orange blinkt)
2. USB-C Adapter an USB-Stick stecken
3. Micro-USB Ende in SoundTouch "Setup-B" Port (hinten)
4. SoundTouch EINSCHALTEN
5. 60 Sekunden warten
```

### Schritt 2: SSH verbinden

```powershell
# SoundTouch IP ermitteln (aus deinem Router oder SoundTouch App)
# Deine SoundTouch IP: 192.168.178.79

ssh root@192.168.178.79
# Bei "Are you sure you want to continue connecting?" -> yes
# KEIN Passwort - einfach Enter drücken
```

### Schritt 3: SSH persistent machen

```bash
# Auf dem SoundTouch (nach SSH-Login):

# SSH dauerhaft aktivieren (auch ohne USB-Stick)
touch /mnt/nv/remote_services

# Prüfen ob erfolgreich
ls -la /mnt/nv/remote_services
```

### Schritt 4: System erkunden

```bash
# Firmware-Version
cat /opt/Bose/etc/version.txt

# Aktuelle BMX Config anzeigen
cat /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml | grep -i bmx

# Netzwerk-Info
ifconfig

# Hostname
hostname
```

### Schritt 5: Config-Backup erstellen

```bash
# Backup der originalen Config
cp /opt/Bose/etc/SoundTouchSdkPrivateCfg.xml /mnt/nv/SoundTouchSdkPrivateCfg.xml.backup

# Prüfen
ls -la /mnt/nv/*.backup
```

### Schritt 6: BMX Registry URL ändern

```bash
# Prüfe ob Override-Verzeichnis existiert
ls -la /mnt/nv/

# Config in beschreibbares Verzeichnis kopieren
# (Details folgen nach System-Erkundung)
```

---

## Troubleshooting

### SSH: "Connection refused"
- USB-Stick noch drin?
- SoundTouch nach USB-Stick-Einstecken neu gestartet?
- Richtige IP?

### SSH: "Permission denied"
- User muss `root` sein, nicht `pi` oder anderer Name
- Kein Passwort eingeben, nur Enter

### USB-Stick wird nicht erkannt
- FAT32 formatiert?
- Datei heißt `remote_services` (nicht .txt)?
- Setup-B Port verwendet (nicht USB-A)?

---

## Nach erfolgreichem SSH-Zugang

Sobald SSH funktioniert, können wir:

1. **Filesystem analysieren** - Wo genau liegt die BMX Config?
2. **Override testen** - Gibt es /mnt/nv Override-Mechanismus?
3. **BMX URL ändern** - Auf unseren Server zeigen
4. **Stream-Proxy testen** - Preset mit umgeleitetem Stream
