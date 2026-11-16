import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import type { DlnaItem } from "../../api/dlna";
import { isApiErrorInstance } from "../../api/types";
import { useDlnaSetup } from "../../hooks/useDlna";
import DlnaBanner from "./DlnaBanner";
import DlnaBrowser, { type DlnaSession } from "./DlnaBrowser";
import DlnaOrphanList from "./DlnaOrphanList";
import DlnaSetupPanel from "./DlnaSetupPanel";
import type { SetupBusy } from "./dlnaSetupTypes";
import { loadDlnaSession, storeDlnaSession } from "./session";

/** After this long a running setup shows the "this takes a moment" text. */
const LONG_AFTER_MS = 4000;
const SETUP_FAILED = "dlna_native_setup_failed";

interface DlnaPaneProps {
  readonly presetNumber: number | null | undefined;
  /** Speaker the preset is for; without it no setup state is loaded and servers are not set up. */
  readonly deviceId?: string;
  readonly onDlnaSelect?: (ref: { server_id: string; object_id: string }) => Promise<void>;
  readonly onClose?: () => void;
}

/** The DLNA mode of the preset dialog: browser, setup panel, removal and the save order (set up first, then save). */
export default function DlnaPane({ presetNumber, deviceId, onDlnaSelect, onClose }: DlnaPaneProps) {
  const { t } = useTranslation();
  const setupApi = useDlnaSetup(deviceId);
  const [session, setSession] = useState<DlnaSession | null>(loadDlnaSession);
  const [savingItemId, setSavingItemId] = useState<string | null>(null);
  // `code` is undefined for a failure without a backend code (generic message)
  const [error, setError] = useState<{ code?: string } | null>(null);
  const [busy, setBusy] = useState<SetupBusy>(null);
  const [long, setLong] = useState(false);
  const [failedIds, setFailedIds] = useState<string[]>([]);
  const lastItemRef = useRef<DlnaItem | null>(null);

  useEffect(() => {
    if (busy !== "setup") return setLong(false);
    const timer = setTimeout(() => setLong(true), LONG_AFTER_MS);
    return () => clearTimeout(timer);
  }, [busy]);

  // a server whose setup failed is shown as "not available" until a later setup works
  const api = {
    ...setupApi,
    servers: setupApi.servers?.map((s) =>
      failedIds.includes(s.server_id) ? { ...s, state: "unavailable" as const } : s
    ),
  };

  /** Sets the server up when its state is known and not `ready`; an unknown state skips it (saving stays possible). */
  const ensureSetup = async (serverId: string) => {
    const server = setupApi.servers?.find((s) => s.server_id === serverId);
    if (!server || (server.state === "ready" && !failedIds.includes(serverId))) return;
    setBusy("setup");
    try {
      const state = await setupApi.setup(serverId);
      if (state !== "ready")
        throw Object.assign(new Error("setup did not finish"), { code: SETUP_FAILED });
      setFailedIds((ids) => ids.filter((id) => id !== serverId));
    } catch (err) {
      // 422: the server id is not a UUID and can never be set up; the save falls back to the plain preset
      if (isApiErrorInstance(err) && err.code === "validation_error") return;
      if (!isApiErrorInstance(err) || err.code === SETUP_FAILED) {
        setFailedIds((ids) => [...ids.filter((id) => id !== serverId), serverId]);
      }
      throw err;
    } finally {
      setBusy(null);
    }
  };

  const fail = (err: unknown) => {
    const code = (err as { code?: string } | null)?.code;
    setError({ code });
    console.error("Failed to save DLNA preset:", err);
  };

  const saveDlna = async (item: DlnaItem) => {
    if (!session || !onDlnaSelect) return;
    lastItemRef.current = item;
    setError(null);
    setSavingItemId(item.id);
    try {
      await ensureSetup(session.serverId);
      await onDlnaSelect({ server_id: session.serverId, object_id: item.id });
      onClose?.();
    } catch (err) {
      fail(err);
    } finally {
      setSavingItemId(null);
    }
  };

  const retrySetup = async () => {
    if (!session) return;
    setError(null);
    try {
      await ensureSetup(session.serverId);
    } catch (err) {
      fail(err);
    }
  };

  const changeSession = (next: DlnaSession | null) => {
    setSession(next);
    storeDlnaSession(next);
    setError(null);
  };

  let busyLabel = t("presets.dlna.saving", { number: presetNumber });
  if (busy === "setup")
    busyLabel = t(`presets.dlna.setup.${long ? "rowSettingUpLong" : "rowSettingUp"}`);

  return (
    <div className="rs-dlna">
      <DlnaBrowser
        initialSession={session}
        onSessionChange={changeSession}
        busyItemId={savingItemId}
        busyLabel={busyLabel}
        liveMessage={savingItemId ? busyLabel : undefined}
        folderHeader={
          deviceId &&
          session && (
            <DlnaSetupPanel
              api={api}
              serverId={session.serverId}
              serverName={session.serverName}
              busy={busy}
              long={long}
              onRetrySetup={() => void retrySetup()}
              onRemoving={(running) => setBusy(running ? "remove" : null)}
            />
          )
        }
        serversFooter={deviceId && <DlnaOrphanList api={api} />}
        banner={
          error && (
            <DlnaBanner
              code={error.code}
              onRetry={() => lastItemRef.current && saveDlna(lastItemRef.current)}
              onDismiss={() => setError(null)}
            />
          )
        }
        renderRowAction={(item, { disabled, busy: rowBusy }) => (
          <button
            type="button"
            className="btn btn-outline btn-sm dl-slot"
            disabled={disabled}
            aria-busy={rowBusy || undefined}
            aria-label={t("presets.dlna.useFor", { number: presetNumber, title: item.title })}
            onClick={() => saveDlna(item)}
          >
            {rowBusy ? <span className="spinner-small" aria-hidden="true" /> : Icon.Plus(18)}
            <span className="dl-slot-num" aria-hidden="true">
              {presetNumber}
            </span>
            <span className="dl-slot-text" aria-hidden="true">
              {t("presets.dlna.forPreset", { number: presetNumber })}
            </span>
          </button>
        )}
      />
    </div>
  );
}
