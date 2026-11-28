import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { getFirstChildAudio, type DlnaItem, type DlnaSaveRequest } from "../../api/dlna";
import { dlnaPrefillKey } from "../../hooks/useDlna";
import { Icon } from "../Icon";
import type { Preset } from "../PresetRow";
import DlnaBrowser from "./DlnaBrowser";
import DlnaServerList from "./DlnaServerList";
import { resolveDlnaPrefill, type DlnaPrefill } from "./resolveDlnaPrefill";
import "./DlnaPane.css";

interface Props {
  deviceId: string;
  presetNumber: number;
  existingPreset?: Pick<Preset, "dlna" | "source_account" | "station_url"> | null;
  /** The page saves: the dialog closes at once and the slot shows the progress. */
  onSave: (request: DlnaSaveRequest) => void;
  /** Dialog head slot for the browser's folder navigation. */
  navTarget?: HTMLElement | null;
}

interface Selection {
  item: DlnaItem;
  parentId: string;
  index?: number;
}

interface Warning extends Selection {
  reason: "noAudioFirst" | "hiResFlac";
}

/** Measured on a SoundTouch 10: FLAC above 48 kHz fails with a decoder error. */
const isHiResFlac = (item: DlnaItem) =>
  // MiniDLNA/ReadyMedia report audio/x-flac, Gerbera audio/flac.
  ["audio/flac", "audio/x-flac"].includes(
    (item.protocol_info?.split(":")[2] ?? "").toLowerCase()
  ) && (item.sample_frequency ?? 0) > 48000;

/** DLNA tab of the preset dialog: server list -> browser -> hand the selected item to the page. */
export default function DlnaPane({
  deviceId,
  presetNumber,
  existingPreset,
  onSave,
  navTarget,
}: Readonly<Props>) {
  const { t } = useTranslation();
  const editing = !!existingPreset?.dlna;
  const account = existingPreset?.source_account;
  const url = existingPreset?.station_url;
  const queryClient = useQueryClient();
  // A reopen starts at the location resolved last time; the fresh answer only refreshes the cache.
  const [cached] = useState(() =>
    editing
      ? queryClient.getQueryData<DlnaPrefill>(dlnaPrefillKey(deviceId, account, url))
      : undefined
  );
  // null = the saved location is still being resolved
  const [prefill, setPrefill] = useState<DlnaPrefill | null>(
    cached ?? (editing ? null : { server: null })
  );
  const [server, setServer] = useState(cached?.server ?? null);
  const [warn, setWarn] = useState<Warning | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!editing) return;
    const controller = new AbortController();
    resolveDlnaPrefill(deviceId, { source_account: account, station_url: url }, controller.signal)
      .then((p) => {
        if (controller.signal.aborted) return;
        const key = dlnaPrefillKey(deviceId, account, url);
        // Failures and notices are never cached: the next open asks again.
        if (p.server && !p.notice) {
          queryClient.setQueryDefaults(key, { gcTime: Infinity });
          queryClient.setQueryData(key, p);
        } else queryClient.removeQueries({ queryKey: key, exact: true });
        if (cached) return;
        setPrefill(p);
        setServer(p.server);
      })
      .catch(() => {
        if (!controller.signal.aborted && !cached) setPrefill({ server: null });
      });
    return () => controller.abort();
  }, [editing, deviceId, account, url, queryClient, cached]);

  if (!prefill) {
    return (
      <div className="dlp-loading" role="status" aria-busy="true">
        <span className="spinner-small" aria-hidden="true" /> {t("dlna.pane.loading")}
      </div>
    );
  }

  // index and cover let the backend skip its own lookups; confirm skips its audio-first check.
  const save = (sel: Selection, confirm = false) => {
    if (!server) return;
    setWarn(null);
    onSave({
      device_id: deviceId,
      preset_number: presetNumber,
      server_id: server.id,
      parent_id: sel.parentId,
      object_id: sel.item.id,
      ...(sel.index !== undefined && { index: sel.index }),
      ...(sel.item.album_art_url && { artwork_url: sel.item.album_art_url }),
      ...(sel.item.artist && { artist: sel.item.artist }),
      ...(confirm && { confirm }),
    });
  };

  const select = async (item: DlnaItem, parentId: string, index?: number) => {
    const sel = { item, parentId, index };
    if (item.is_container && server) {
      setBusy(true);
      // A failed check (null) saves without confirm: the backend then checks the folder itself.
      const audioFirst = await getFirstChildAudio(server.id, item.id)
        .catch(() => null)
        .finally(() => setBusy(false));
      if (audioFirst === false) {
        setWarn({ ...sel, reason: "noAudioFirst" });
        return;
      }
      save(sel, audioFirst === true);
    } else if (isHiResFlac(item)) {
      setWarn({ ...sel, reason: "hiResFlac" });
    } else save(sel);
  };

  const resumeHere = server !== null && server.id === prefill.server?.id;

  return (
    <div className="dlp">
      {prefill.notice && (
        <div className="wz-status" role="status">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Info(18)}
          </span>
          <div className="wz-status-body">
            <p className="wz-status-text">{t(`dlna.pane.${prefill.notice}`)}</p>
          </div>
        </div>
      )}
      {server ? (
        <DlnaBrowser
          key={server.id}
          serverId={server.id}
          serverName={server.name}
          startObjectId={resumeHere ? prefill.startObjectId : undefined}
          focusObjectId={resumeHere ? prefill.focusId : undefined}
          onSelect={(item, parentId, index) => void select(item, parentId, index)}
          busy={busy}
          onAllServers={() => {
            setServer(null);
            setWarn(null);
          }}
          navTarget={navTarget}
        />
      ) : (
        <DlnaServerList deviceId={deviceId} onOpenServer={(id, name) => setServer({ id, name })} />
      )}
      {busy && (
        <div className="dlp-loading" role="status" aria-live="polite">
          <span className="spinner-small" aria-hidden="true" />{" "}
          {t("dlna.save.saving", { number: presetNumber })}
        </div>
      )}
      {warn && (
        <div className="wz-status wz-status--warning" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Alert(22)}
          </span>
          <div className="wz-status-body">
            <p className="wz-status-text">
              {t(`dlna.save.${warn.reason}`, { khz: (warn.item.sample_frequency ?? 0) / 1000 })}
            </p>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => save(warn, warn.reason === "noAudioFirst")}
          >
            {t("dlna.save.saveAnyway")}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => setWarn(null)}>
            {t("dlna.save.chooseAnother")}
          </button>
        </div>
      )}
    </div>
  );
}
