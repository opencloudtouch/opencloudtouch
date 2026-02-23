/**
 * Guided Mode - Backup Progress Step
 */
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import "../GuidedSteps.css";

interface BackupProgressProps {
  onNext: () => void;
  onPrevious: () => void;
}

export default function BackupProgress({ onNext, onPrevious }: BackupProgressProps) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<"running" | "success" | "error">("running");

  useEffect(() => {
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer);
          setStatus("success");
          return 100;
        }
        return prev + 5;
      });
    }, 200);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="guided-step-container">
      <div className="demo-banner">
        ⚠️ <strong>DEMO MODUS</strong> - Simuliertes Backup. Backend folgt in Phase 3.
      </div>

      <div className="step-header">
        <h2 className="step-title">💾 Backup wird erstellt...</h2>
        <p className="step-description">
          Konfigurationsdateien werden gesichert bevor Änderungen vorgenommen werden.
        </p>
      </div>

      <div className="progress-container">
        <div className="progress-bar-wrapper">
          <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-status">
          {status === "running" && `${progress}% - Dateien werden kopiert...`}
          {status === "success" && "Backup erfolgreich erstellt ✓"}
          {status === "error" && "Backup fehlgeschlagen ✗"}
        </div>
      </div>

      {status === "success" && (
        <motion.div
          className="success-box"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="success-icon">✓</div>
          <div>
            <strong>Backup abgeschlossen</strong>
            <br />
            Alle Konfigurationsdateien wurden gesichert.
          </div>
        </motion.div>
      )}

      <div className="step-actions">
        <button className="btn btn-secondary" onClick={onPrevious}>
          ← Zurück
        </button>
        <button className="btn btn-primary" onClick={onNext} disabled={status !== "success"}>
          Weiter →
        </button>
      </div>
    </div>
  );
}
