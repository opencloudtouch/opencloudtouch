import { useState, useEffect, useRef, FormEvent } from "react";
import { motion } from "framer-motion";
import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useManualIPs, useProbeDevice } from "../hooks/useSettings";
import { useDiscoveryStream } from "../hooks/useDiscoveryStream";
import { useToast } from "../contexts/ToastContext";
import { toUserMessage } from "../utils/errorMessages";
import { getLogEntries, getLogBuffers } from "../utils/logBuffer";
import { syncDebugFromBackendLevel } from "../utils/debug";
import { getDevices, type Device } from "../api/devices";
import "./Settings.css";

export default function Settings() {
  const { t } = useTranslation();
  const [newIP, setNewIP] = useState("");
  const [error, setError] = useState("");

  // React Query hooks
  const { isLoading: loading, error: queryError, refetch } = useManualIPs();
  const probeDevice = useProbeDevice();

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
      syncDebugFromBackendLevel(data.level);
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

  // Snapshot the database before each scan, never after discovery has started.
  const preDiscoveryIdsRef = useRef<Set<string>>(
    new Set((queryClient.getQueryData<Device[]>(["devices"]) ?? []).map((d) => d.device_id))
  );
  const [newDevices, setNewDevices] = useState<Device[]>([]);
  const [showAllDevices, setShowAllDevices] = useState(false);
  const [isPreparingDiscovery, setIsPreparingDiscovery] = useState(false);
  const preparingDiscoveryRef = useRef(false);
  const completedRef = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const handleDiscovery = async () => {
    if (isDiscovering || preparingDiscoveryRef.current) return;

    preparingDiscoveryRef.current = true;
    setIsPreparingDiscovery(true);

    try {
      const existing = await queryClient.fetchQuery({
        queryKey: ["devices"],
        queryFn: getDevices,
        staleTime: 0,
      });
      if (!mountedRef.current) return;
      preDiscoveryIdsRef.current = new Set(existing.map((d) => d.device_id));

      completedRef.current = false;
      setNewDevices([]);
      setShowAllDevices(false);
      startDiscovery();
    } catch (err) {
      if (mountedRef.current) {
        show(toUserMessage(err instanceof Error ? err.message : String(err)), "error");
      }
    } finally {
      preparingDiscoveryRef.current = false;
      if (mountedRef.current) setIsPreparingDiscovery(false);
    }
  };

  useEffect(() => {
    if (!completed) {
      completedRef.current = false;
      return;
    }
    if (completedRef.current) return;
    completedRef.current = true;

    const seen = new Set<string>();
    const newlyAdded = devicesFound.filter((device) => {
      if (preDiscoveryIdsRef.current.has(device.device_id) || seen.has(device.device_id)) {
        return false;
      }
      seen.add(device.device_id);
      return true;
    });
    setNewDevices(newlyAdded);
    show(t("settings.discovery.devicesFound", { count: newlyAdded.length }), "success");
  }, [completed, devicesFound, show, t]);

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

    try {
      const result = await probeDevice.mutateAsync(trimmedIP);
      setNewIP("");
      setError("");
      show(t("settings.manualIps.deviceAdded", { name: result.name, ip: result.ip }), "success");
    } catch (err) {
      console.error("[Settings] Probe failed:", err);
      setError(t("settings.manualIps.probeError", { ip: trimmedIP }));
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
        <button
          className="btn btn-primary"
          onClick={() => {
            refetch();
          }}
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  return (
    <div className="page settings-page">
      <h1 className="page-title">{t("settings.title")}</h1>

      {/* Device Discovery Section */}
      <motion.section
        className="settings-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="section-title">
          <span className="section-icon">🔍</span>
          {t("settings.deviceDiscovery.sectionTitle")}
        </h2>

        <div className="settings-card device-discovery-options">
          {/* Primary: Automatic Discovery */}
          <div className="discovery-method-card primary-method">
            <h3 className="method-title">{t("settings.deviceDiscovery.autoTitle")}</h3>
            <p className="method-description">{t("settings.deviceDiscovery.autoDescription")}</p>

            <div className="discover-action">
              <button
                className="btn btn-primary network-scan-btn"
                onClick={() => void handleDiscovery()}
                disabled={isDiscovering || isPreparingDiscovery}
                aria-label={t("settings.deviceDiscovery.scanButton")}
              >
                {isDiscovering ? (
                  <>
                    <span className="spinner-inline" aria-hidden="true" />
                    {t("settings.deviceDiscovery.scanning")}
                  </>
                ) : (
                  t("settings.deviceDiscovery.scanButton")
                )}
              </button>
            </div>
            {completed && (
              <p role="status" aria-live="polite"
                 data-test="discovery-result-count"
                 data-count={newDevices.length}>
                {t("settings.discovery.devicesFound", { count: newDevices.length })}
              </p>
            )}
            {newDevices.length > 0 && (
              <div className="discovery-results" data-test="newly-discovered-devices">
                <ul className="discovery-device-list">
                  {(showAllDevices ? newDevices : newDevices.slice(0, 5)).map((device) => (
                    <li key={device.device_id}>{device.name}</li>
                  ))}
                </ul>
                {newDevices.length > 5 && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowAllDevices((current) => !current)}
                    aria-expanded={showAllDevices}
                  >
                    {showAllDevices
                      ? t("settings.discovery.showLess")
                      : t("settings.discovery.showMore", { count: newDevices.length - 5 })}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Secondary: Manual IPs */}
          <div className="discovery-method-card secondary-method">
            <h3 className="method-title">{t("settings.deviceDiscovery.manualTitle")}</h3>
            <p className="method-description">{t("settings.deviceDiscovery.manualDescription")}</p>

            {/* Add IP Form */}
            <form onSubmit={handleAddIP} className="ip-add-form">
              <input
                type="text"
                value={newIP}
                onChange={(e) => setNewIP(e.target.value)}
                placeholder={t("settings.manualIps.placeholder")}
                className="ip-input"
                pattern="^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
                disabled={probeDevice.isPending}
              />
              <button type="submit" className="btn btn-primary" disabled={probeDevice.isPending}>
                {probeDevice.isPending ? (
                  <>
                    <span className="spinner-inline" aria-hidden="true" />
                    {t("settings.manualIps.probing")}
                  </>
                ) : (
                  t("settings.manualIps.addButton")
                )}
              </button>
            </form>

            {/* Error Messages */}
            {error && <div className="alert alert-error">{error}</div>}
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
                    body: JSON.stringify({
                      frontend_logs: getLogEntries(),
                      frontend_log_buffers: getLogBuffers(),
                    }),
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
