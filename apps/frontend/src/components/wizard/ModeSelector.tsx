/**
 * Mode Selector for Setup Wizard
 * Choose between Guided (recommended) or Manual mode
 */
import { motion } from "framer-motion";
import "./ModeSelector.css";

interface ModeSelectorProps {
  onModeSelect: (mode: "guided" | "manual") => void;
}

export default function ModeSelector({ onModeSelect }: ModeSelectorProps) {
  return (
    <div className="mode-selector-container">
      <h2 className="mode-title">Setup-Modus wählen</h2>
      <p className="mode-description">Wählen Sie, wie Sie Ihr Gerät einrichten möchten:</p>

      <div className="mode-options">
        {/* Guided Mode - Recommended */}
        <motion.button
          className="mode-card mode-guided"
          onClick={() => onModeSelect("guided")}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <div className="mode-badge">Empfohlen</div>
          <div className="mode-icon">🧭</div>
          <h3 className="mode-card-title">Geführter Modus</h3>
          <p className="mode-card-description">
            Schritt-für-Schritt Anleitung für Einsteiger. Das Gerät wird automatisch konfiguriert.
          </p>
          <ul className="mode-features">
            <li>✓ USB-Stick Vorbereitung</li>
            <li>✓ Automatische SSH-Aktivierung</li>
            <li>✓ Backup & Konfiguration</li>
            <li>✓ Verifizierung</li>
          </ul>
        </motion.button>

        {/* Manual Mode */}
        <motion.button
          className="mode-card mode-manual"
          onClick={() => onModeSelect("manual")}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <div className="mode-icon">⚙️</div>
          <h3 className="mode-card-title">Manueller Modus</h3>
          <p className="mode-card-description">
            Für erfahrene Nutzer. Volle Kontrolle über jeden Schritt.
          </p>
          <ul className="mode-features">
            <li>• Manuelle SSH-Verbindung</li>
            <li>• Direkter Dateizugriff</li>
            <li>• Erweiterte Optionen</li>
            <li>• Keine Automatisierung</li>
          </ul>
        </motion.button>
      </div>
    </div>
  );
}
