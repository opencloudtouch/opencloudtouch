import { useState, FormEvent } from "react";
import { motion } from "framer-motion";
import { useManualIPs, useAddManualIP, useDeleteManualIP } from "../hooks/useSettings";
import { toUserMessage } from "../utils/errorMessages";
import "./Settings.css";

export default function Settings() {
  const [newIP, setNewIP] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // React Query hooks
  const { data: manualIPs = [], isLoading: loading, error: queryError, refetch } = useManualIPs();
  const addIP = useAddManualIP();
  const deleteIP = useDeleteManualIP();

  const validateIP = (ip: string): boolean => {
    const parts = ip.split(".");
    if (parts.length !== 4) return false;
    return parts.every((part) => {
      const num = parseInt(part, 10);
      return num >= 0 && num <= 255 && part === num.toString();
    });
  };

  const handleAddIP = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmedIP = newIP.trim();

    if (!trimmedIP) {
      setError("Bitte geben Sie eine IP-Adresse ein");
      return;
    }

    if (!validateIP(trimmedIP)) {
      setError("Ungültige IP-Adresse (Format: 192.168.1.10)");
      return;
    }

    if (manualIPs.includes(trimmedIP)) {
      setError("Diese IP-Adresse existiert bereits");
      return;
    }

    try {
      await addIP.mutateAsync(trimmedIP);
      setNewIP("");
      setSuccess(`IP ${trimmedIP} hinzugefügt`);
      setError("");
      // Auto-clear success message after 3s
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      console.error("[Settings] Failed to add IP:", err);
      setError(toUserMessage(err));
    }
  };

  const handleDeleteIP = async (ipToDelete: string) => {
    try {
      await deleteIP.mutateAsync(ipToDelete);
      setSuccess(`IP ${ipToDelete} entfernt`);
      setError("");
      // Auto-clear success message after 3s
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      console.error("[Settings] Failed to delete IP:", err);
      setError(toUserMessage(err));
    }
  };

  if (loading) {
    return (
      <div className="loading-container" role="status" aria-live="polite" aria-label="Ladevorgang">
        <div className="spinner" aria-hidden="true" />
        <p className="loading-message">Einstellungen werden geladen...</p>
      </div>
    );
  }

  if (queryError) {
    return (
      <div className="error-container">
        <div className="error-icon">⚠️</div>
        <h2 className="error-title">Fehler beim Laden</h2>
        <p className="error-message">{toUserMessage(queryError.message)}</p>
        <button className="btn btn-primary" onClick={() => void refetch()}>
          Erneut versuchen
        </button>
      </div>
    );
  }

  return (
    <div className="page settings-page">
      <h1 className="page-title">Einstellungen</h1>

      {/* Manual IPs Section */}
      <motion.section
        className="settings-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="section-title">
          <span className="section-icon">🌐</span>
          Manuelle Geräte-IPs
        </h2>

        <div className="settings-card">
          <p className="section-description">
            Fügen Sie IP-Adressen von Geräten manuell hinzu, falls die automatische Erkennung nicht
            funktioniert.
          </p>

          {/* Add IP Form */}
          <form onSubmit={handleAddIP} className="ip-add-form">
            <input
              type="text"
              value={newIP}
              onChange={(e) => setNewIP(e.target.value)}
              placeholder="192.168.1.10"
              className="ip-input"
              pattern="^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
            />
            <button type="submit" className="btn btn-primary">
              + Hinzufügen
            </button>
          </form>

          {/* Error/Success Messages */}
          {error && <div className="alert alert-error">{error}</div>}
          {success && <div className="alert alert-success">{success}</div>}

          {/* IP List */}
          <div className="ip-list">
            {manualIPs.length === 0 ? (
              <p className="empty-message">Keine manuellen IPs konfiguriert</p>
            ) : (
              <ul className="ip-items">
                {manualIPs.map((ip) => (
                  <motion.li
                    key={ip}
                    className="ip-item"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                  >
                    <span className="ip-address">{ip}</span>
                    <button
                      onClick={() => handleDeleteIP(ip)}
                      className="btn btn-delete"
                      title="IP entfernen"
                    >
                      ×
                    </button>
                  </motion.li>
                ))}
              </ul>
            )}
          </div>

          {/* Info Box */}
          <div className="info-box">
            <strong>ℹ️ Hinweis:</strong>
            <p>
              Nach dem Hinzufügen oder Entfernen von IPs wird die Geräteerkennung automatisch neu
              gestartet. Die Geräte erscheinen dann auf der Startseite.
            </p>
          </div>
        </div>
      </motion.section>
    </div>
  );
}
