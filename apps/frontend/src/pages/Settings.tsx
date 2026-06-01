import { useState, useEffect, useRef, FormEvent } from "react";
import { motion } from "framer-motion";
import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useManualIPs, useAddManualIP, useDeleteManualIP } from "../hooks/useSettings";
import { useDiscoveryStream } from "../hooks/useDiscoveryStream";
import { useToast } from "../contexts/ToastContext";
import { toUserMessage } from "../utils/errorMessages";
import { getLogEntries } from "../utils/logBuffer";
import type { Device } from "../api/devices";
import "./Settings.css";

export default function Settings() {
  const { t } = useTranslation();
  const [newIP, setNewIP] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // React Query hooks
  const { data: manualIPs = [], isLoading: loading, error: queryError, refetch } = useManualIPs();
  const addIP = useAddManualIP();
  const deleteIP = useDeleteManualIP();

  // Log level query + mutation
  const { data: logLevelData } = useQuery<{ level: string }>({
    queryKey: ["log-level"],
    queryFn: async () => {
      const res = await fetch("/api/logs/level");
      if (!res.ok) throw new Error("Failed to fetch log level");
      return res.json() as Promise<{ level: string }>;
    },
    staleTime: 60_000,
  });

  const setLogLevel = useMutation<{ level: string }, Error, string>({
    mutationFn: async (level: string) => {
      const res = await fetch("/api/logs/level", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level }),
      });
      if (!res.ok) throw new Error("Failed to set log level");
      return res.json() as Promise<{ level: string }>;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["log-level"], data);
      show(t("settings.logging.levelChanged", { level: data.level }), "success");
    },
    onError: () => {
      show(t("settings.logging.levelError"), "error");
    },
  });

  // Discovery
  const { isDiscovering, devicesFound, completed, startDiscovery } = useDiscoveryStream();
  const queryClient = useQueryClient();
  const { show } = useToast();

  // Capture device IDs that existed before this component was mounted.
  // Used to determine how many NEW devices were found by the discovery.
  const [preDiscoveryDeviceIds] = useState<Set<string>>(() => {
    const existing = queryClient.getQueryData<Device[]>(["devices"]) ?? [];
    return new Set(existing.map((d) => d.device_id));
  });

  const completedRef = useRef(false);

  // Show toast when discovery completes
  useEffect(() => {
    if (completed && !completedRef.current) {
      completedRef.current = true;
      const newDeviceCount = devicesFound.filter(
        (d) => !preDiscoveryDeviceIds.has(d.device_id)
      ).length;
      const message = t("settings.discovery.devicesFound", { count: newDeviceCount });
      show(message, "success");
    }
  }, [completed, devicesFound, preDiscoveryDeviceIds, show, t]);

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
      setError(t("settings.manualIps.enterIp"));
      return;
    }

    if (!validateIP(trimmedIP)) {
      setError(t("settings.manualIps.invalidFormat"));
      return;
    }

    if (manualIPs.includes(trimmedIP)) {
      setError(t("settings.manualIps.alreadyExists"));
      return;
    }

    try {
      await addIP.mutateAsync(trimmedIP);
      setNewIP("");
      setSuccess(t("settings.manualIps.ipAdded", { ip: trimmedIP }));
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
      setSuccess(t("settings.manualIps.ipRemoved", { ip: ipToDelete }));
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
        <p className="loading-message">{t("settings.loading")}</p>
      </div>
    );
  }

  if (queryError) {
    return (
      <div className="error-container">
        <div className="error-icon">⚠️</div>
        <h2 className="error-title">{t("settings.errorTitle")}</h2>
        <p className="error-message">{toUserMessage(queryError.message)}</p>
        <button className="btn btn-primary" onClick={() => void refetch()}>
          {t("common.retry")}
        </button>
      </div>
    );
  }

  return (
    <div className="page settings-page">
      <h1 className="page-title">{t("settings.title")}</h1>

      {/* Manual IPs Section */}
      <motion.section
        className="settings-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="section-title">
          <span className="section-icon">🌐</span>
          {t("settings.manualIps.sectionTitle")}
        </h2>

        <div className="settings-card">
          <p className="section-description">{t("settings.manualIps.description")}</p>

          {/* Add IP Form */}
          <form onSubmit={handleAddIP} className="ip-add-form">
            <input
              type="text"
              value={newIP}
              onChange={(e) => setNewIP(e.target.value)}
              placeholder={t("settings.manualIps.placeholder")}
              className="ip-input"
              pattern="^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
            />
            <button type="submit" className="btn btn-primary">
              {t("settings.manualIps.addButton")}
            </button>
          </form>

          {/* Error/Success Messages */}
          {error && <div className="alert alert-error">{error}</div>}
          {success && <div className="alert alert-success">{success}</div>}

          {/* IP List */}
          <div className="ip-list">
            {manualIPs.length === 0 ? (
              <p className="empty-message">{t("settings.manualIps.emptyList")}</p>
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
                      title={t("settings.manualIps.removeIp")}
                    >
                      ×
                    </button>
                  </motion.li>
                ))}
              </ul>
            )}
          </div>

          {/* Discover Button */}
          {manualIPs.length > 0 && (
            <div className="discover-action">
              <button
                className="btn btn-primary"
                onClick={() => void startDiscovery()}
                disabled={isDiscovering}
                aria-label={t("settings.manualIps.discoverButton")}
              >
                {isDiscovering
                  ? t("settings.manualIps.discovering")
                  : t("settings.manualIps.discoverButton")}
              </button>
            </div>
          )}

          {/* Info Box */}
          <div className="info-box">
            <strong>ℹ️</strong>
            <p>{t("settings.manualIps.infoHint")}</p>
          </div>
        </div>
      </motion.section>

      {/* Logging Section */}
      <motion.section
        className="settings-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h2 className="section-title">
          <span className="section-icon">📋</span>
          {t("settings.logging.sectionTitle")}
        </h2>

        <div className="settings-card">
          <p className="section-description">{t("settings.logging.description")}</p>

          {/* Log Level Dropdown */}
          <div className="log-level-row">
            <label htmlFor="log-level-select" className="log-level-label">
              {t("settings.logging.logLevel")}
            </label>
            <select
              id="log-level-select"
              className="log-level-select"
              value={
                logLevelData?.level === "CRITICAL" ? "CRITICAL" : (logLevelData?.level ?? "INFO")
              }
              onChange={(e) => setLogLevel.mutate(e.target.value)}
              disabled={setLogLevel.isPending}
            >
              <option value="CRITICAL">{t("settings.logging.levelOff")}</option>
              <option value="INFO">{t("settings.logging.levelInfo")}</option>
              <option value="DEBUG">{t("settings.logging.levelDebug")}</option>
            </select>
          </div>

          {/* Download Logs */}
          <div className="log-download-row">
            <p className="section-description">{t("settings.logging.downloadDescription")}</p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={async () => {
                try {
                  const resp = await fetch("/api/logs/backend", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ frontend_logs: getLogEntries() }),
                  });
                  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                  const blob = await resp.blob();
                  const disposition = resp.headers.get("Content-Disposition") || "";
                  const execResult = /filename="(.+?)"/.exec(disposition);
                  const filename = execResult?.[1] || "oct-backend.log";
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = filename;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  URL.revokeObjectURL(url);
                } catch (err) {
                  console.error("Log download failed:", err);
                }
              }}
            >
              {t("settings.logging.downloadLogs")}
            </button>
          </div>
        </div>
      </motion.section>
    </div>
  );
}
