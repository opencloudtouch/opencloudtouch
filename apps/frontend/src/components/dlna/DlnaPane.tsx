import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getFirstChildAudio, saveDlnaPreset, type DlnaItem } from "../../api/dlna";
import { isApiErrorInstance } from "../../api/types";
import { userErrorMessage } from "../../utils/errorMessages";
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
  onSaved: () => void;
}

interface Selection {
  item: DlnaItem;
  parentId: string;
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

/** DLNA tab of the preset dialog: server list -> browser -> save the selected item to the slot. */
export default function DlnaPane({
  deviceId,
  presetNumber,
  existingPreset,
  onSaved,
}: Readonly<Props>) {
  const { t } = useTranslation();
  const editing = !!existingPreset?.dlna;
  const account = existingPreset?.source_account;
  const url = existingPreset?.station_url;
  // null = the saved location is still being resolved
  const [prefill, setPrefill] = useState<DlnaPrefill | null>(editing ? null : { server: null });
  const [server, setServer] = useState<{ id: string; name: string } | null>(null);
  const [warn, setWarn] = useState<Warning | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!editing) return;
    const controller = new AbortController();
    resolveDlnaPrefill(deviceId, { source_account: account, station_url: url }, controller.signal)
      .then((p) => {
        setPrefill(p);
        setServer(p.server);
      })
      .catch(() => {
        if (!controller.signal.aborted) setPrefill({ server: null });
      });
    return () => controller.abort();
  }, [editing, deviceId, account, url]);

  if (!prefill) {
    return (
      <div className="dlp-loading" role="status" aria-busy="true">
        <span className="spinner-small" aria-hidden="true" /> {t("dlna.pane.loading")}
      </div>
    );
  }

  const save = async (sel: Selection, confirm = false) => {
    if (!server) return;
    setSaveError(null);
    setWarn(null);
    setBusy(true);
    try {
      await saveDlnaPreset({
        device_id: deviceId,
        preset_number: presetNumber,
        server_id: server.id,
        parent_id: sel.parentId,
        object_id: sel.item.id,
        ...(confirm && { confirm }),
      });
      onSaved();
    } catch (err) {
      if (isApiErrorInstance(err) && err.code === "dlna_folder_no_audio_first")
        setWarn({ ...sel, reason: "noAudioFirst" });
      else setSaveError(userErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const select = async (item: DlnaItem, parentId: string) => {
    const sel = { item, parentId };
    if (item.is_container && server) {
      setBusy(true);
      // A failed check falls through: the backend answers 409 for such a folder anyway.
      const audioFirst = await getFirstChildAudio(server.id, item.id)
        .catch(() => true)
        .finally(() => setBusy(false));
      if (!audioFirst) {
        setSaveError(null);
        setWarn({ ...sel, reason: "noAudioFirst" });
        return;
      }
    } else if (isHiResFlac(item)) {
      setSaveError(null);
      setWarn({ ...sel, reason: "hiResFlac" });
      return;
    }
    await save(sel);
  };

  const resumeHere = server !== null && server.id === prefill.server?.id;

  return (
    <div className="dlp">
      <p className="ui-small">{t("dlna.pane.hint", { number: presetNumber })}</p>
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
        <>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setServer(null);
              setWarn(null);
            }}
          >
            {t("dlna.pane.allServers")}
          </button>
          <DlnaBrowser
            key={server.id}
            serverId={server.id}
            serverName={server.name}
            startObjectId={resumeHere ? prefill.startObjectId : undefined}
            focusObjectId={resumeHere ? prefill.focusId : undefined}
            onSelect={(item, parentId) => void select(item, parentId)}
            busy={busy}
          />
        </>
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
            onClick={() => void save(warn, warn.reason === "noAudioFirst")}
          >
            {t("dlna.save.saveAnyway")}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => setWarn(null)}>
            {t("dlna.save.chooseAnother")}
          </button>
        </div>
      )}
      {saveError && (
        <div className="wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX(22)}
          </span>
          <div className="wz-status-body">
            <p className="wz-status-text">{saveError}</p>
          </div>
        </div>
      )}
    </div>
  );
}
