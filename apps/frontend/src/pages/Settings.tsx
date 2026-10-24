import { useState, useEffect, useRef, useId, FormEvent } from "react";
import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useManualIPs, useProbeDevice } from "../hooks/useSettings";
import { useDiscoveryStream } from "../hooks/useDiscoveryStream";
import { useToast } from "../contexts/ToastContext";
import { toUserMessage } from "../utils/errorMessages";
import { getLogEntries, getLogBuffers } from "../utils/logBuffer";
import { syncDebugFromBackendLevel } from "../utils/debug";
import type { Device } from "../api/devices";
import { Icon } from "../components/Icon";
import "./Settings.css";

export default function Settings() {
  const { t } = useTranslation();
  const [newIP, setNewIP] = useState("");
  const [error, setError] = useState("");
  const ipId = useId();
  const ipHintId = `${ipId}-hint`;
  const ipErrorId = `${ipId}-error`;
  // state of the log download (a failed download used to be silent)
  const [downloadState, setDownloadState] = useState<"idle" | "busy" | "error">("idle");
  const [downloadError, setDownloadError] = useState("");

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

  // Device IDs that were known when the current scan started (initially: when this page was mounted, because a scan
  // can already be running after a reload). Used to determine how many NEW devices the scan found.
  const knownDeviceIdsRef = useRef<Set<string> | null>(null);
  knownDeviceIdsRef.current ??= new Set(
    (queryClient.getQueryData<Device[]>(["devices"]) ?? []).map((d) => d.device_id)
  );

  const completedRef = useRef(false);

  // A new scan resets the "toast shown" flag, otherwise only the first scan per page visit would show its result
  useEffect(() => {
    if (!completed) completedRef.current = false;
  }, [completed]);

  // Show toast when discovery completes: the count and the names of the new devices (like the manual search by IP)
  useEffect(() => {
    if (completed && !completedRef.current) {
      completedRef.current = true;
      const known = knownDeviceIdsRef.current ?? new Set<string>();
      const newDevices = devicesFound.filter(
        (d, index) =>
          !known.has(d.device_id) &&
          devicesFound.findIndex((o) => o.device_id === d.device_id) === index
      );
      const summary = t("settings.discovery.devicesFound", { count: newDevices.length });
      const names = newDevices.map((d) => `${d.name} (${d.ip})`).join(", "); // same form as "{{name}} ({{ip}}) added"
      show(newDevices.length > 0 ? `${summary}: ${names}` : summary, "success");
    }
  }, [completed, devicesFound, show, t]);

  const handleScan = () => {
    knownDeviceIdsRef.current = new Set(
      (queryClient.getQueryData<Device[]>(["devices"]) ?? []).map((d) => d.device_id)
    );
    completedRef.current = false;
    void startDiscovery();
  };

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

  const handleDownloadLogs = async () => {
    setDownloadState("busy");
    setDownloadError("");
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
      setDownloadState("idle");
    } catch (err) {
      console.error("Log download failed:", err);
      setDownloadError(err instanceof Error ? err.message : t("errors.unknown"));
      setDownloadState("error");
    }
  };

  if (loading) {
    return (
      <div className="st st--state">
        <h1 className="visually-hidden">{t("settings.title")}</h1>
        <div className="ui-state" role="status" aria-live="polite" aria-label={t("common.loading")}>
          <div className="spinner" aria-hidden="true" />
          <p>{t("settings.loading")}</p>
        </div>
      </div>
    );
  }

  if (queryError) {
    return (
      <div className="st st--state">
        <h1 className="visually-hidden">{t("settings.title")}</h1>
        <div className="ui-state ui-state--error" role="alert">
          <div className="ui-state-icon" aria-hidden="true">
            {Icon.Alert(32)}
          </div>
          <h2>{t("settings.errorTitle")}</h2>
          <p>{toUserMessage(queryError.message)}</p>
          <button
            className="btn btn-primary"
            onClick={() => {
              refetch();
            }}
          >
            {t("common.retry")}
          </button>
        </div>
      </div>
    );
  }

  const downloading = downloadState === "busy";

  return (
    <div className="st">
      <h1 className="ui-h1">{t("settings.title")}</h1>

      {/* Device Discovery Section */}
      <section className="st-section" aria-labelledby="st-discovery-title">
        <h2 id="st-discovery-title" className="ui-h2 st-h2">
          <span className="st-h2-icon" aria-hidden="true">
            {Icon.Search(22)}
          </span>
          {t("settings.deviceDiscovery.sectionTitle")}
        </h2>

        <div className="ui-card st-card">
          {/* Primary: Automatic Discovery */}
          <div className="st-method">
            <h3 className="ui-h3">{t("settings.deviceDiscovery.autoTitle")}</h3>
            <p className="st-text">{t("settings.deviceDiscovery.autoDescription")}</p>
            <button
              type="button"
              className="btn btn-primary st-scan"
              onClick={handleScan}
              disabled={isDiscovering}
              aria-busy={isDiscovering}
            >
              {isDiscovering ? (
                <>
                  <span className="spinner-small" aria-hidden="true" />
                  {t("settings.deviceDiscovery.scanning")}
                </>
              ) : (
                <>
                  {Icon.Search(18)}
                  {t("settings.deviceDiscovery.scanButton")}
                </>
              )}
            </button>
            <span className="visually-hidden" role="status">
              {isDiscovering ? t("settings.deviceDiscovery.scanningStatus") : ""}
            </span>
          </div>

          {/* Secondary: Manual IPs */}
          <div className="st-method">
            <h3 className="ui-h3">{t("settings.deviceDiscovery.manualTitle")}</h3>
            <p className="st-text">{t("settings.deviceDiscovery.manualDescription")}</p>

            {/* noValidate: our own messages appear instead of the browser bubble */}
            <form onSubmit={handleAddIP} className="ui-field st-ip" noValidate>
              <label htmlFor={ipId} className="ui-label">
                {t("settings.manualIps.label")}
              </label>
              <div className="st-ip-row">
                <input
                  id={ipId}
                  type="text"
                  value={newIP}
                  onChange={(e) => setNewIP(e.target.value)}
                  placeholder={t("settings.manualIps.placeholder")}
                  className="ui-input"
                  pattern="^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
                  autoComplete="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? ipErrorId : ipHintId}
                  disabled={probeDevice.isPending}
                />
                <button
                  type="submit"
                  className="btn btn-primary st-add"
                  disabled={probeDevice.isPending}
                  aria-busy={probeDevice.isPending}
                >
                  {probeDevice.isPending ? (
                    <>
                      <span className="spinner-small" aria-hidden="true" />
                      {t("settings.manualIps.probing")}
                    </>
                  ) : (
                    t("settings.manualIps.addButton")
                  )}
                </button>
              </div>
              {/* one reserved slot: hint, or the error in its place */}
              <div className="st-ip-msg">
                {error ? (
                  <div id={ipErrorId} className="ui-field-error" role="alert">
                    {Icon.CircleX(16)}
                    <span>{error}</span>
                  </div>
                ) : (
                  <p id={ipHintId} className="ui-field-hint">
                    {t("settings.manualIps.hint")}
                  </p>
                )}
              </div>
            </form>
          </div>
        </div>
      </section>

      {/* Logging Section */}
      <section className="st-section" aria-labelledby="st-logging-title">
        <h2 id="st-logging-title" className="ui-h2 st-h2">
          <span className="st-h2-icon" aria-hidden="true">
            {Icon.FileText(22)}
          </span>
          {t("settings.logging.sectionTitle")}
        </h2>

        <div className="ui-card st-card">
          <p className="st-text">{t("settings.logging.description")}</p>

          {/* Log Level Dropdown */}
          <div className="ui-field st-level">
            <label htmlFor="log-level-select" className="ui-label">
              {t("settings.logging.logLevel")}
            </label>
            <div className="st-select">
              <select
                id="log-level-select"
                className="ui-select"
                value={
                  logLevelData?.level === "CRITICAL" ? "CRITICAL" : (logLevelData?.level ?? "INFO")
                }
                onChange={(e) => setLogLevel.mutate(e.target.value)}
                disabled={setLogLevel.isPending}
                aria-busy={setLogLevel.isPending}
              >
                <option value="CRITICAL">{t("settings.logging.levelOff")}</option>
                <option value="INFO">{t("settings.logging.levelInfo")}</option>
                <option value="DEBUG">{t("settings.logging.levelDebug")}</option>
              </select>
              <span className="st-select-icon" aria-hidden="true">
                {setLogLevel.isPending ? (
                  <span className="ui-spin">{Icon.Loader(18)}</span>
                ) : (
                  Icon.ChevronDown(18)
                )}
              </span>
            </div>
            <span className="visually-hidden" role="status">
              {setLogLevel.isPending ? t("settings.logging.levelSaving") : ""}
            </span>
          </div>

          {/* Download Logs */}
          <div className="st-download">
            <p className="st-text">{t("settings.logging.downloadDescription")}</p>
            <button
              type="button"
              className="btn btn-secondary st-download-btn"
              onClick={() => void handleDownloadLogs()}
              disabled={downloading}
              aria-busy={downloading}
            >
              {downloading ? (
                <>
                  <span className="spinner-small" aria-hidden="true" />
                  {t("settings.logging.downloading")}
                </>
              ) : (
                <>
                  {Icon.Download(18)}
                  {t("settings.logging.downloadLogs")}
                </>
              )}
            </button>
            {downloadState === "error" && (
              <div className="wz-status wz-status--error st-download-error" role="alert">
                <span className="wz-icon" aria-hidden="true">
                  {Icon.CircleX(20)}
                </span>
                <div className="wz-status-body">
                  <p>{t("settings.logging.downloadFailed", { error: downloadError })}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
