/**
 * Step 2: USB Preparation
 */
import { useState, useEffect } from "react";
import WizardStep from "./WizardStep";
import "./Step2USBPreparation.css";

interface Step2Props {
  deviceModel: string;
  onNext: () => void;
  onPrevious: () => void;
}

type Platform = "windows" | "macos" | "linux" | "unknown";

export default function Step2USBPreparation({ deviceModel, onNext, onPrevious }: Step2Props) {
  const [platform, setPlatform] = useState<Platform>("unknown");
  const [usbReady, setUsbReady] = useState(false);

  useEffect(() => {
    // Detect platform
    const userAgent = navigator.userAgent.toLowerCase();
    const plat = navigator.platform?.toLowerCase();

    if (plat?.includes("win") || userAgent.includes("windows")) {
      setPlatform("windows");
    } else if (plat?.includes("mac") || userAgent.includes("mac")) {
      setPlatform("macos");
    } else if (plat?.includes("linux") || userAgent.includes("linux")) {
      setPlatform("linux");
    } else {
      setPlatform("unknown");
    }
  }, []);

  const usbPort = deviceModel.includes("30") || deviceModel.includes("300") ? "USB-A" : "Micro-USB";

  const getFormatInstructions = (): { title: string; steps: string[] } => {
    switch (platform) {
      case "windows":
        return {
          title: "Windows - USB-Stick formatieren",
          steps: [
            "USB-Stick einstecken",
            "Rechtsklick auf USB-Laufwerk im Explorer → Formatieren",
            "Dateisystem: FAT32 auswählen",
            "Volumebezeichnung: USB_SOUNDTOUCH",
            "Schnellformatierung: aktiviert",
            "Klick auf 'Starten'",
          ],
        };
      case "macos":
        return {
          title: "macOS - USB-Stick formatieren",
          steps: [
            "USB-Stick einstecken",
            "Festplattendienstprogramm öffnen",
            "USB-Stick links auswählen",
            "Klick auf 'Löschen'",
            "Format: MS-DOS (FAT) auswählen",
            "Name: USB_SOUNDTOUCH",
            "Klick auf 'Löschen'",
          ],
        };
      case "linux":
        return {
          title: "Linux - USB-Stick formatieren",
          steps: [
            "USB-Stick einstecken",
            "Terminal öffnen",
            "Gerät identifizieren: lsblk",
            "Formatieren: sudo mkfs.vfat -F 32 -n USB_SOUNDTOUCH /dev/sdX1",
            "(Ersetze sdX1 mit deinem USB-Gerät)",
          ],
        };
      default:
        return {
          title: "USB-Stick formatieren",
          steps: ["USB-Stick mit FAT32 formatieren", "Volumebezeichnung: USB_SOUNDTOUCH"],
        };
    }
  };

  const formatInstructions = getFormatInstructions();

  return (
    <WizardStep
      stepNumber={2}
      title="USB-Stick vorbereiten"
      description="Formatieren Sie einen USB-Stick und erstellen Sie die Konfigurationsdatei."
      warning="Der USB-Stick wird vollständig gelöscht! Sichern Sie vorher alle Daten."
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!usbReady}
      nextDisabledReason="Bitte alle Schritte oben abhaken, um fortzufahren."
    >
      <div className="usb-preparation">
        {/* Device Info */}
        <div className="usb-device-info">
          <div className="usb-icon">🔌</div>
          <div className="usb-device-details">
            <strong>Ihr Gerät benötigt:</strong> {usbPort}
            <br />
            <small>Modell: {deviceModel}</small>
          </div>
        </div>

        {/* Format Instructions */}
        <div className="usb-section">
          <div className="usb-section-header">
            <h3 className="usb-section-title">
              <span className="usb-section-number">1</span>
              {formatInstructions.title}
            </h3>
            <label htmlFor="usb-platform-select" className="usb-platform-label">
              Betriebssystem:
            </label>
            <select
              id="usb-platform-select"
              className="usb-platform-select"
              value={platform}
              onChange={(e) => setPlatform(e.target.value as Platform)}
              aria-label="Betriebssystem auswählen"
            >
              <option value="windows">Windows</option>
              <option value="macos">macOS</option>
              <option value="linux">Linux</option>
            </select>
          </div>
          <ol className="usb-instruction-list">
            {formatInstructions.steps.map((step, index) => (
              <li key={index} className="usb-instruction-item">
                {step}
              </li>
            ))}
          </ol>
        </div>

        {/* Create File */}
        <div className="usb-section">
          <h3 className="usb-section-title">
            <span className="usb-section-number">2</span>
            Datei &quot;remote_services&quot; erstellen
          </h3>
          <p className="usb-section-description">
            Erstellen Sie eine Datei namens <code>remote_services</code> (ohne Dateiendung) im
            Root-Verzeichnis des USB-Sticks. Die Datei muss <strong>leer</strong> sein (kein
            Inhalt).
          </p>
        </div>

        {/* Verification */}
        <div className="usb-section">
          <h3 className="usb-section-title">
            <span className="usb-section-number">3</span>
            Überprüfung
          </h3>
          <div className="usb-checklist">
            <label className="usb-checklist-item">
              <input type="checkbox" />
              <span>USB-Stick ist mit FAT32 formatiert</span>
            </label>
            <label className="usb-checklist-item">
              <input type="checkbox" />
              <span>Datei &quot;remote_services&quot; ist im Root-Verzeichnis und leer</span>
            </label>
            <label className="usb-checklist-item">
              <input
                type="checkbox"
                checked={usbReady}
                onChange={(e) => setUsbReady(e.target.checked)}
              />
              <span>
                <strong>USB-Stick ist bereit zum Einstecken in das Gerät</strong>
              </span>
            </label>
          </div>
        </div>
      </div>
    </WizardStep>
  );
}
