import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useEnableNativeServer, useNativeServers } from "../../hooks/useDlna";
import { isApiErrorInstance } from "../../api/types";
import DeviceOfflineBanner from "../DeviceOfflineBanner";
import { Icon } from "../Icon";
import DlnaRemoveDialog from "./DlnaRemoveDialog";
import "./DlnaServerList.css";

interface Props {
  deviceId: string;
  onOpenServer: (serverId: string, name: string) => void;
}

const STATE_KEY = {
  ready: "ready",
  not_enabled: "notEnabled",
  unavailable: "unavailable",
} as const;

/** Media servers of one speaker with their live state, enable and remove. */
export default function DlnaServerList({ deviceId, onOpenServer }: Readonly<Props>) {
  const { t } = useTranslation();
  const native = useNativeServers(deviceId);
  const quick = useNativeServers(deviceId, false);
  const enable = useEnableNativeServer(deviceId);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [removing, setRemoving] = useState<{ id: string; name: string } | null>(null);

  // The quick list of known servers shows until the full search answers; an empty one waits.
  const data = native.data ?? (quick.data?.servers.length ? quick.data : undefined);
  if (!data && (native.isLoading || quick.isLoading)) {
    return (
      <div role="status" aria-busy="true" className="dsl-loading">
        <span className="spinner-small" aria-hidden="true" /> {t("dlna.servers.loading")}
      </div>
    );
  }
  if (!data && native.error) {
    if (isApiErrorInstance(native.error) && native.error.code === "device_unreachable") {
      return <DeviceOfflineBanner />;
    }
    return (
      <div className="wz-status wz-status--error" role="alert">
        <span className="wz-icon" aria-hidden="true">
          {Icon.CircleX(22)}
        </span>
        <div className="wz-status-body">
          <span className="wz-status-title">{t("dlna.servers.loadError")}</span>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => void native.refetch()}>
          {t("dlna.servers.retry")}
        </button>
      </div>
    );
  }

  const { servers: listed = [], migration_failed = false, migration_reason = null } = data ?? {};
  // Set-up servers first, otherwise in the backend's order (sort is stable).
  const servers = [...listed].sort(
    (a, b) => Number(b.state === "ready") - Number(a.state === "ready")
  );
  const searching = !native.data && native.isFetching;
  const searchFailed = !native.data && !native.isFetching && native.error !== null;
  if (servers.length === 0) {
    return (
      <div className="dsl-empty">
        <p className="wz-status-title">{t("dlna.servers.empty")}</p>
        <p className="ui-small">{t("dlna.servers.emptyText")}</p>
        <button type="button" className="btn btn-secondary" onClick={() => void native.refetch()}>
          {t("dlna.servers.rescan")}
        </button>
      </div>
    );
  }

  const hosts = servers.flatMap((s) => (s.host ? [s.host] : []));
  const sharedHost = new Set(hosts).size < hosts.length;

  const doEnable = async (id: string, name: string) => {
    setBusyId(id);
    setMessage(null);
    try {
      const result = await enable.mutateAsync(id);
      const ok = result.state !== "unavailable";
      setMessage({
        text: t(ok ? "dlna.servers.enabled" : "dlna.servers.enableUnavailable", { name }),
        error: !ok,
      });
    } catch (err) {
      const noAccount = isApiErrorInstance(err) && err.code === "dlna_speaker_no_account";
      setMessage({
        text: t(noAccount ? "dlna.servers.enableNoAccount" : "dlna.servers.enableFailed", { name }),
        error: true,
      });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="dsl">
      {migration_failed && (
        <div className="wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX(22)}
          </span>
          <div className="wz-status-body">
            <span className="wz-status-title">{t("dlna.servers.migrationFailedTitle")}</span>
            <span className="wz-status-text">
              {t("dlna.servers.migrationFailedText", { reason: migration_reason ?? "" })}
            </span>
          </div>
        </div>
      )}
      <ul className="dsl-list">
        {servers.map((s) => {
          // Registered but not discovered: the speaker's state counts (decision 6), but OCT
          // cannot browse it, so it is not openable and stays removable (decision 32).
          const state = s.discovered || s.state === "ready" ? s.state : "unavailable";
          const openable = state === "ready" && s.discovered;
          return (
            <li key={s.server_id} className="dsl-row" data-state={state}>
              {/* One action per row: the Open button below opens a ready server. */}
              <span className="dsl-name">{s.name}</span>
              <span className="dsl-state ui-small">{t(`dlna.servers.${STATE_KEY[state]}`)}</span>
              {state === "not_enabled" && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={migration_failed || busyId === s.server_id}
                  aria-busy={busyId === s.server_id}
                  aria-label={t("dlna.servers.enableLabel", { name: s.name })}
                  onClick={() => void doEnable(s.server_id, s.name)}
                >
                  {t("dlna.servers.enable")}
                </button>
              )}
              {openable && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  aria-label={t("dlna.servers.openLabel", { name: s.name })}
                  onClick={() => onOpenServer(s.server_id, s.name)}
                >
                  {t("dlna.servers.open")}
                </button>
              )}
              {(state === "unavailable" || !s.discovered) && (
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  aria-label={t("dlna.servers.removeLabel", { name: s.name })}
                  onClick={() => setRemoving({ id: s.server_id, name: s.name })}
                >
                  {t("dlna.servers.remove")}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {searching && (
        <div role="status" aria-live="polite" className="dsl-loading">
          <span className="spinner-small" aria-hidden="true" /> {t("dlna.servers.searching")}
        </div>
      )}
      {searchFailed && (
        <div className="dsl-loading">
          <span className="ui-small">{t("dlna.servers.searchFailed")}</span>
          <button type="button" className="btn btn-secondary" onClick={() => void native.refetch()}>
            {t("dlna.servers.retry")}
          </button>
        </div>
      )}
      <div aria-live="polite">
        {message && !message.error && <p className="ui-small">{message.text}</p>}
      </div>
      {message?.error && (
        <div className="wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX(22)}
          </span>
          <div className="wz-status-body">
            <span className="wz-status-text">{message.text}</span>
          </div>
        </div>
      )}
      {sharedHost && (
        <div className="wz-status wz-status--warning">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Alert(22)}
          </span>
          <div className="wz-status-body">
            <span className="wz-status-title">{t("dlna.servers.sameHostTitle")}</span>
            <span className="wz-status-text">{t("dlna.servers.sameHostText")}</span>
          </div>
        </div>
      )}
      {removing && (
        <DlnaRemoveDialog
          deviceId={deviceId}
          serverId={removing.id}
          serverName={removing.name}
          onClose={() => setRemoving(null)}
        />
      )}
    </div>
  );
}
