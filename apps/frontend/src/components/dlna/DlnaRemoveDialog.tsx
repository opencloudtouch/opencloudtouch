import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import Modal from "../Modal";
import "./DlnaNative.css";
import { errorCode, type DlnaSetupApi, type NativeSlot } from "./dlnaSetupTypes";

type Step = "slots" | "explain" | "run" | "done" | "fail";
const KNOWN = new Set([
  "dlna_native_in_use",
  "dlna_native_remove_failed",
  "dlna_native_setup_failed",
  "device_not_found",
  "device_unreachable",
  "dlna_server_not_found",
  "validation_error",
]);

interface Props {
  api: DlnaSetupApi;
  serverId: string;
  serverName: string;
  onClose: () => void;
  /** true while the removal request runs (also after the dialog was closed), false when it ended */
  onRunning?: (running: boolean) => void;
}

/** Removal of a set-up media server (also used for orphans): load the affected presets, explain, confirm (force), progress, result. */
export default function DlnaRemoveDialog({
  api,
  serverId,
  serverName,
  onClose,
  onRunning,
}: Readonly<Props>) {
  const { t } = useTranslation();
  const listId = useId();
  const titleId = useId();
  const [step, setStep] = useState<Step>("slots");
  const [slots, setSlots] = useState<NativeSlot[]>([]);
  const [changed, setChanged] = useState(false);
  const [code, setCode] = useState("");
  const [live, setLive] = useState("");
  const aliveRef = useRef(true);
  const r = (k: string, v?: Record<string, unknown>) => t(`presets.dlna.remove.${k}`, v);
  const errorText = (c: string) => (KNOWN.has(c) ? t(`errors.api.${c}`) : r("failedGeneric"));

  const fail = (e: unknown) => {
    const c = errorCode(e);
    setCode(c);
    setStep("fail");
    setLive(`${r("failedTitle")}. ${errorText(c)}`);
  };

  useEffect(() => {
    aliveRef.current = true;
    setLive(r("loadingSlots"));
    api
      .slots(serverId)
      .then((s) => {
        if (!aliveRef.current) return;
        setSlots(s);
        setStep("explain");
        setLive("");
      })
      .catch((e) => aliveRef.current && fail(e));
    return () => {
      aliveRef.current = false;
    };
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, []);

  const run = async () => {
    setStep("run");
    setLive(r("progress"));
    onRunning?.(true);
    try {
      await api.remove(serverId, true); // force: the backend switches the listed presets
      if (!aliveRef.current) return;
      setStep("done");
      setLive(r("done"));
    } catch (e) {
      if (!aliveRef.current) return;
      if (errorCode(e) === "dlna_native_in_use") {
        // the presets changed in between: show them again instead of a dead end
        try {
          setSlots(await api.slots(serverId));
          setChanged(true);
          setStep("explain");
          setLive(t("errors.api.dlna_native_in_use"));
        } catch (e2) {
          fail(e2);
        }
      } else fail(e);
    } finally {
      onRunning?.(false);
    }
  };

  const Srv = (
    <p className="nd-srv">
      {Icon.Server(16)}
      <span>{serverName}</span>
    </p>
  );
  const cancel = (
    <button type="button" className="btn btn-secondary" data-autofocus onClick={onClose}>
      {t("common.cancel")}
    </button>
  );
  let body: ReactNode;
  let actions: ReactNode;
  if (step === "slots") {
    body = (
      <>
        {Srv}
        <div className="nd-status">
          <span className="spinner-small" aria-hidden="true" />
          {r("loadingSlots")}
        </div>
      </>
    );
    actions = <>{cancel}</>;
  } else if (step === "explain") {
    body = (
      <>
        {Srv}
        {changed && (
          <div className="wz-status" role="status">
            <span className="wz-icon" aria-hidden="true">
              {Icon.Info(20)}
            </span>
            <div className="wz-status-body">
              <p className="wz-status-text">{t("errors.api.dlna_native_in_use")}</p>
            </div>
          </div>
        )}
        <p className="dlg-text">{r("explain")}</p>
        {slots.length ? (
          <>
            <p className="nd-sub" id={listId}>
              {r("slotsTitle")}
            </p>
            <ul className="nd-slots" aria-labelledby={listId}>
              {slots.map((s) => (
                <li key={s.preset_number}>
                  <span className="nd-slot-num" aria-hidden="true">
                    {s.preset_number}
                  </span>
                  <span>{r("slot", { number: s.preset_number, name: s.name })}</span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="nd-empty">{r("noSlots")}</p>
        )}
      </>
    );
    actions = (
      <>
        {cancel}
        <button
          type="button"
          className="btn btn-danger"
          aria-label={r("confirmLabel", { name: serverName })}
          onClick={() => void run()}
        >
          {r("confirm")}
        </button>
      </>
    );
  } else if (step === "run") {
    body = (
      <>
        {Srv}
        <div className="nd-prog-wrap">
          <progress className="nd-prog" aria-label={r("progress")} />
          <p className="dlg-text">{r("progress")}</p>
        </div>
      </>
    );
    // the request keeps running; the hook reloads the state when it ends
    actions = (
      <button type="button" className="btn btn-secondary" onClick={onClose}>
        {r("leave")}
      </button>
    );
  } else if (step === "done") {
    body = (
      <>
        {Srv}
        <div className="nd-done">
          {Icon.CircleCheck(22)}
          <p className="dlg-text">{r("done")}</p>
        </div>
      </>
    );
    actions = (
      <button type="button" className="btn btn-primary" onClick={onClose}>
        {r("close")}
      </button>
    );
  } else {
    body = (
      <>
        {Srv}
        <div className="wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX(20)}
          </span>
          <div className="wz-status-body">
            <p className="wz-status-title">{r("failedTitle")}</p>
            <p className="wz-status-text">{errorText(code)}</p>
          </div>
        </div>
      </>
    );
    actions = (
      <>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          {t("common.close")}
        </button>
        <button type="button" className="btn btn-primary" onClick={() => void run()}>
          {Icon.RefreshCw(16)} {t("common.retry")}
        </button>
      </>
    );
  }
  // no way out while the presets load or the request runs (except "Close, keeps running")
  const locked = step === "run" || step === "slots";
  return (
    <Modal
      open
      size="sm"
      role={step === "explain" ? "alertdialog" : undefined}
      labelledBy={titleId}
      closeOnEscape={!locked}
      closeOnBackdrop={!locked}
      onClose={onClose}
    >
      <div className="dlg-head">
        <h2 id={titleId} className="dlg-title">
          {r("title")}
        </h2>
      </div>
      <div className="dlg-body nd-body">{body}</div>
      <div className="dlg-actions">{actions}</div>
      <div className="dl-sr" role="status" aria-live="polite">
        {live}
      </div>
    </Modal>
  );
}
