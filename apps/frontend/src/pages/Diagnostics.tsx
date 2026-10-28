import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { getDiagnostics, DiagnosticsResponse } from "../api/diagnostics";
import { downloadDiagnostics } from "../api/bugReport";
import { getLogEntries } from "../utils/logBuffer";
import { useToast } from "../contexts/ToastContext";
import StatusBadge from "../components/StatusBadge";
import type { SetupStatus } from "../api/setup";
import { Icon } from "../components/Icon";
import "./Diagnostics.css";

type Presence = "green" | "yellow" | "red";

/** Colour is never the only cue: every state has an icon and a text. */
const PRESENCE_CONFIG = {
  green: { variant: "success", icon: Icon.CircleCheck, labelKey: "diagnostics.statusOnline" },
  yellow: { variant: "warning", icon: Icon.Clock, labelKey: "diagnostics.statusStale" },
  red: { variant: "danger", icon: Icon.WifiOff, labelKey: "diagnostics.statusOffline" },
} as const;

function PresenceBadge({ status }: Readonly<{ status: Presence }>) {
  const { t } = useTranslation();
  const config = PRESENCE_CONFIG[status];
  return (
    <span className={`ui-badge ui-badge--${config.variant}`}>
      <span className="ui-badge-icon" aria-hidden="true">
        {config.icon(14)}
      </span>
      <span>{t(config.labelKey)}</span>
    </span>
  );
}

/** On / off with icon and text (replaces the emoji marks and the coloured dot). */
function OnOffBadge({ on, label }: Readonly<{ on: boolean; label: string }>) {
  return (
    <span className={`ui-badge ${on ? "ui-badge--success" : ""}`}>
      <span className="ui-badge-icon" aria-hidden="true">
        {on ? Icon.Check(14) : Icon.Minus(14)}
      </span>
      <span>{label}</span>
    </span>
  );
}

function getDeviceStatus(lastSeen: string | null): Presence {
  if (!lastSeen) return "red";
  const diff = Date.now() - new Date(lastSeen).getTime();
  if (diff < 5 * 60 * 1000) return "green"; // < 5 min
  if (diff < 30 * 60 * 1000) return "yellow"; // < 30 min
  return "red";
}

const SETUP_STATUSES: ReadonlySet<string> = new Set([
  "unconfigured",
  "pending",
  "configured",
  "failed",
  "outdated",
  "offline",
  "unknown",
]);

/** The API sends a raw string; values outside the enum are shown as "unknown" instead of crashing StatusBadge. */
function toSetupStatus(value: string): SetupStatus {
  return (SETUP_STATUSES.has(value) ? value : "unknown") as SetupStatus;
}

function Row({
  label,
  children,
  mono,
}: Readonly<{ label: string; children: React.ReactNode; mono?: boolean }>) {
  return (
    <div className="dg-row">
      <dt>{label}</dt>
      <dd className={mono ? "ui-mono" : undefined}>{children}</dd>
    </div>
  );
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
    if (downloading) return; // aria-disabled instead of disabled, so the button keeps focus and <main> keeps a focusable element
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
      <div className="dg">
        <h1 className="ui-h1">{t("diagnostics.title")}</h1>
        <div className="ui-state" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p>{t("common.loading")}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dg">
        <h1 className="ui-h1">{t("diagnostics.title")}</h1>
        <div className="ui-state ui-state--error" role="alert">
          <div className="ui-state-icon" aria-hidden="true">
            {Icon.CircleX(32)}
          </div>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  const server = data?.server;

  return (
    <div className="dg" data-test="diagnostics-page">
      {/* the download sits next to the title (first focusable element, reachable without scrolling a long list) */}
      <div className="dg-head">
        <h1 className="ui-h1">{t("diagnostics.title")}</h1>
        <div data-test="diagnostics-download">
          <button
            type="button"
            className="btn btn-primary dg-download-btn"
            onClick={handleDownload}
            aria-disabled={downloading}
            aria-busy={downloading}
          >
            {downloading ? (
              <>
                <span className="spinner-small" aria-hidden="true" />
                {t("bugReport.downloading")}
              </>
            ) : (
              <>
                {Icon.Download(18)}
                {t("diagnostics.downloadBundle")}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Server Info */}
      <section
        className="dg-section"
        data-test="diagnostics-server"
        aria-labelledby="dg-server-title"
      >
        <h2 id="dg-server-title" className="ui-h2">
          {t("diagnostics.serverInfo")}
        </h2>
        <dl className="ui-card dg-kv">
          <Row label={t("diagnostics.version")} mono>
            {server?.version}
          </Row>
          <Row label={t("diagnostics.python")} mono>
            {server?.python_version}
          </Row>
          <Row label={t("diagnostics.platform")} mono>
            {server?.platform}
          </Row>
          <Row label={t("diagnostics.discovery")}>
            <OnOffBadge
              on={!!server?.discovery_enabled}
              label={server?.discovery_enabled ? t("common.enabled") : t("common.disabled")}
            />
          </Row>
          <Row label={t("diagnostics.logLevel")} mono>
            {server?.log_level}
          </Row>
          <Row label={t("diagnostics.manualIPs")}>{server?.manual_device_ips}</Row>
        </dl>
      </section>

      {/* DB Stats */}
      <section className="dg-section" data-test="diagnostics-db" aria-labelledby="dg-db-title">
        <h2 id="dg-db-title" className="ui-h2">
          {t("diagnostics.database")}
        </h2>
        <dl className="ui-card dg-kv">
          <Row label={t("diagnostics.devicesCount")}>{data?.db_stats.devices}</Row>
          <Row label={t("diagnostics.presetsCount")}>{data?.db_stats.presets}</Row>
        </dl>
      </section>

      {/* Devices */}
      <section
        className="dg-section"
        data-test="diagnostics-devices"
        aria-labelledby="dg-devices-title"
      >
        <h2 id="dg-devices-title" className="ui-h2">
          {t("diagnostics.devices")}
        </h2>
        {data?.devices.length === 0 ? (
          <p className="ui-card dg-empty">
            <span aria-hidden="true">{Icon.Speaker(22)}</span>
            {t("diagnostics.noDevices")}
          </p>
        ) : (
          <div className="dg-devices">
            {data?.devices.map((device) => (
              <article key={device.device_id} className="ui-card dg-device">
                <div className="dg-device-head">
                  <div className="dg-device-title">
                    <h3 className="ui-h3">{device.name}</h3>
                    <span className="ui-small">{device.model}</span>
                  </div>
                  <PresenceBadge status={getDeviceStatus(device.last_seen)} />
                </div>
                <dl className="dg-kv dg-kv--compact">
                  <Row label={t("diagnostics.ip")} mono>
                    {device.ip}
                  </Row>
                  <Row label={t("diagnostics.firmware")} mono>
                    {device.firmware_version}
                  </Row>
                  <Row label={t("diagnostics.setupStatus")}>
                    <StatusBadge
                      status={toSetupStatus(device.setup_status)}
                      size="small"
                      showLabel
                    />
                  </Row>
                  <Row label={t("diagnostics.lastSeen")}>
                    {device.last_seen ? (
                      new Date(device.last_seen).toLocaleString()
                    ) : (
                      <>
                        <span aria-hidden="true">—</span>
                        <span className="visually-hidden">{t("diagnostics.unknownValue")}</span>
                      </>
                    )}
                  </Row>
                  <Row label={t("diagnostics.ssh")}>
                    <OnOffBadge
                      on={device.ssh_permanent}
                      label={
                        device.ssh_permanent ? t("diagnostics.sshOn") : t("diagnostics.sshOff")
                      }
                    />
                  </Row>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
