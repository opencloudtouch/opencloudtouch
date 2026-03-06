/**
 * Guided Mode - USB Detection Step
 * Uses File System Access API to detect and prepare USB stick
 */
import { useState } from "react";
import { motion } from "framer-motion";
import "../GuidedSteps.css";

interface USBDevice {
  name: string;
  dirHandle: FileSystemDirectoryHandle;
  isEmpty: boolean;
  isWritable: boolean;
  fileCount: number;
}

interface USBDetectionProps {
  onNext: () => void;
  onCancel: () => void;
}

export default function USBDetection({ onNext, onCancel }: USBDetectionProps) {
  const [devices, setDevices] = useState<USBDevice[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<USBDevice | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [remoteServicesCreated, setRemoteServicesCreated] = useState(false);

  const detectUSB = async () => {
    setScanning(true);
    setError(null);
    setRemoteServicesCreated(false);

    try {
      // Request directory access with write permission
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const dirHandle = await (window as any).showDirectoryPicker({
        mode: "readwrite",
      });

      // Count files in directory
      let fileCount = 0;
      for await (const entry of dirHandle.values()) {
        void entry; // Mark as intentionally unused
        fileCount++;
      }

      // Test write access
      const isWritable = await testWriteAccess(dirHandle);

      const device: USBDevice = {
        name: dirHandle.name,
        dirHandle,
        isEmpty: fileCount === 0,
        isWritable,
        fileCount,
      };

      setDevices([device]);
      setSelectedDevice(device);

      // Auto-create remote_services if writable
      if (isWritable) {
        await createRemoteServicesFile(dirHandle);
      }
    } catch (err: unknown) {
      const error = err as Error;
      if (error.name === "AbortError") {
        // User cancelled - not an error
        setError(null);
      } else {
        setError(`Fehler beim Zugriff: ${error.message}`);
      }
    } finally {
      setScanning(false);
    }
  };

  const testWriteAccess = async (dirHandle: FileSystemDirectoryHandle): Promise<boolean> => {
    try {
      const testFile = await dirHandle.getFileHandle(".oct-write-test", {
        create: true,
      });
      const writable = await testFile.createWritable();
      await writable.write("test");
      await writable.close();
      await dirHandle.removeEntry(".oct-write-test");
      return true;
    } catch {
      return false;
    }
  };

  const createRemoteServicesFile = async (dirHandle: FileSystemDirectoryHandle) => {
    try {
      const fileHandle = await dirHandle.getFileHandle("remote_services", {
        create: true,
      });
      const writable = await fileHandle.createWritable();
      await writable.write(""); // Empty file
      await writable.close();
      setRemoteServicesCreated(true);
    } catch (err: unknown) {
      const error = err as Error;
      setError(`Fehler beim Erstellen: ${error.message}`);
    }
  };

  const isReady = selectedDevice !== null && remoteServicesCreated;

  return (
    <div className="guided-step-container">
      <div className="demo-banner">
        ℹ️ <strong>INFO</strong> - USB File System Access API (nur Chromium-Browser)
      </div>

      <div className="step-header">
        <h2 className="step-title">💾 USB-Stick vorbereiten</h2>
        <p className="step-description">
          Wählen Sie einen USB-Stick aus, um die remote_services Datei zu erstellen. Diese Datei
          aktiviert den SSH-Zugang am SoundTouch-Gerät.
        </p>
      </div>

      <motion.div
        className="info-box-info"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="info-icon">ℹ️</div>
        <div className="info-text">
          <strong>SSH-Aktivierung via USB-Stick:</strong>
          <br />
          Die Datei <code>remote_services</code> (leer, ohne Endung) aktiviert den SSH-Server am
          Bose SoundTouch Gerät beim Boot.
          <br />
          <br />
          <strong>Empfohlen:</strong> FAT32 formatierter USB-Stick. Andere Formate (exFAT, NTFS)
          können ebenfalls funktionieren - Browser kann Format nicht erkennen.
        </div>
      </motion.div>

      <div className="usb-scan-section">
        <button className="btn btn-primary" onClick={detectUSB} disabled={scanning}>
          {scanning ? "Zugriff wird angefordert..." : "📂 USB-Stick auswählen"}
        </button>
      </div>

      {error && (
        <motion.div className="warning-box" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="warning-icon" aria-hidden="true">
            ⚠️
          </div>
          <div className="warning-text">{error}</div>
        </motion.div>
      )}

      {devices.length > 0 && (
        <div className="usb-devices-list">
          {devices.map((device, idx) => (
            <motion.div
              key={idx}
              className={`usb-device-card ${selectedDevice === device ? "selected" : ""}`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              onClick={() => setSelectedDevice(device)}
            >
              <div className="device-name">📁 {device.name}</div>
              <div className="device-meta">
                {device.fileCount} Dateien • {device.isWritable ? "✓" : "✗"} Beschreibbar
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {selectedDevice && remoteServicesCreated && selectedDevice.isEmpty && (
        <motion.div
          className="success-box"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="success-icon">✓</div>
          <div>
            <strong>USB-Stick bereit!</strong>
            <br />
            Die Datei <code>remote_services</code> wurde erstellt. Sie können mit dem nächsten
            Schritt fortfahren.
          </div>
        </motion.div>
      )}

      {selectedDevice && remoteServicesCreated && !selectedDevice.isEmpty && (
        <motion.div
          className="warning-box"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="warning-icon" aria-hidden="true">
            ⚠️
          </div>
          <div className="warning-text">
            <strong>USB-Stick nicht leer ({selectedDevice.fileCount} Dateien)</strong>
            <br />
            Daten bleiben erhalten. Nur <code>remote_services</code> wurde hinzugefügt.
          </div>
        </motion.div>
      )}

      <div className="step-actions">
        <button className="btn btn-secondary" onClick={onCancel}>
          Abbrechen
        </button>
        <button className="btn btn-primary" onClick={onNext} disabled={!isReady}>
          Weiter →
        </button>
      </div>
    </div>
  );
}
