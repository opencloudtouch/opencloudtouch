import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { getDiagnostics, DiagnosticsResponse } from "../api/diagnostics";
import { downloadDiagnostics } from "../api/bugReport";
import { getLogEntries } from "../utils/logBuffer";
import { useToast } from "../contexts/ToastContext";
import "./Diagnostics.css";

function StatusDot({ status }: { readonly status: "green" | "yellow" | "red" }) {
  return <span className={`status-dot status-${status}`} aria-label={status} />;
}

function getDeviceStatus(lastSeen: string | null): "green" | "yellow" | "red" {
  if (!lastSeen) return "red";
  const diff = Date.now() - new Date(lastSeen).getTime();
  if (diff < 5 * 60 * 1000) return "green"; // < 5 min
  if (diff < 30 * 60 * 1000) return "yellow"; // < 30 min
  return "red";
}

export default function Diagnostics() {
  const { t } = useTranslation();
  const { show: showToast } = useToast();
  const [data, setData] = useState<DiagnosticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getDiagnostics()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadDiagnostics({
        frontend_logs: getLogEntries(),
        description: "Diagnostics page export",
        browser_info: `${navigator.userAgent} | ${window.innerWidth}x${window.innerHeight}`,
        current_route: "/diagnostics",
        click_timestamp: Date.now() / 1000,
      });
      showToast(t("bugReport.diagnosticsSuccess"), "success", 8000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : t("errors.unknown");
      showToast(t("bugReport.diagnosticsFailed", { error: msg }), "error", 8000);
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="page diagnostics-page">
        <h1>{t("diagnostics.title")}</h1>
        <div className="diagnostics-loading">{t("common.loading")}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page diagnostics-page">
        <h1>{t("diagnostics.title")}</h1>
        <div className="diagnostics-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="page diagnostics-page" data-test="diagnostics-page">
      <h1>{t("diagnostics.title")}</h1>

      {/* Server Info */}
      <section className="diagnostics-section" data-test="diagnostics-server">
        <h2>{t("diagnostics.serverInfo")}</h2>
        <table className="diagnostics-table">
          <tbody>
            <tr>
              <th scope="row">{t("diagnostics.version")}</th>
              <td>{data?.server.version}</td>
            </tr>
            <tr>
              <th scope="row">{t("diagnostics.python")}</th>
              <td>{data?.server.python_version}</td>
            </tr>
            <tr>
              <th scope="row">{t("diagnostics.platform")}</th>
              <td>{data?.server.platform}</td>
            </tr>
            <tr>
              <th scope="row">{t("diagnostics.discovery")}</th>
              <td>
                <StatusDot status={data?.server.discovery_enabled ? "green" : "yellow"} />
                {data?.server.discovery_enabled ? t("common.enabled") : t("common.disabled")}
              </td>
            </tr>
            <tr>
              <th scope="row">{t("diagnostics.logLevel")}</th>
              <td>{data?.server.log_level}</td>
            </tr>
            <tr>
              <th scope="row">{t("diagnostics.manualIPs")}</th>
              <td>{data?.server.manual_device_ips}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* DB Stats */}
      <section className="diagnostics-section" data-test="diagnostics-db">
        <h2>{t("diagnostics.database")}</h2>
        <table className="diagnostics-table">
          <tbody>
            <tr>
              <th scope="row">{t("diagnostics.devicesCount")}</th>
              <td>{data?.db_stats.devices}</td>
            </tr>
            <tr>
              <th scope="row">{t("diagnostics.presetsCount")}</th>
              <td>{data?.db_stats.presets}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* Devices */}
      <section className="diagnostics-section" data-test="diagnostics-devices">
        <h2>{t("diagnostics.devices")}</h2>
        {data?.devices.length === 0 ? (
          <p className="diagnostics-empty">{t("diagnostics.noDevices")}</p>
        ) : (
          <div className="diagnostics-device-list">
            {data?.devices.map((device) => (
              <div key={device.device_id} className="diagnostics-device-card">
                <div className="device-card-header">
                  <StatusDot status={getDeviceStatus(device.last_seen)} />
                  <strong>{device.name}</strong>
                  <span className="device-card-model">{device.model}</span>
                </div>
                <table className="diagnostics-table diagnostics-table-compact">
                  <tbody>
                    <tr>
                      <th scope="row">IP</th>
                      <td>{device.ip}</td>
                    </tr>
                    <tr>
                      <th scope="row">{t("diagnostics.firmware")}</th>
                      <td>{device.firmware_version}</td>
                    </tr>
                    <tr>
                      <th scope="row">{t("diagnostics.setupStatus")}</th>
                      <td>{device.setup_status}</td>
                    </tr>
                    <tr>
                      <th scope="row">{t("diagnostics.lastSeen")}</th>
                      <td>
                        {device.last_seen ? new Date(device.last_seen).toLocaleString() : "—"}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">SSH</th>
                      <td>{device.ssh_permanent ? "✅" : "❌"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Download Bundle */}
      <section className="diagnostics-section" data-test="diagnostics-download">
        <button
          className="diagnostics-download-btn"
          onClick={handleDownload}
          disabled={downloading}
        >
          {downloading ? t("bugReport.downloading") : t("diagnostics.downloadBundle")}
        </button>
      </section>
    </div>
  );
}
