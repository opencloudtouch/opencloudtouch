import { useEffect, useId, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import type { Device } from "./DeviceSwiper";
import type { IneligibleReason, OperationStepKey } from "../api/stereoPairs";
import type { StereoPairCreate } from "../hooks/useStereoPairCreate";
import Modal from "./Modal";
import { SideTile } from "./StereoPairCard";
import { Icon } from "./Icon";
import "./StereoPairCreateDialog.css";

const STEP_KEYS: OperationStepKey[] = ["preflight", "create_left", "create_right", "verify"];
const STEP_DEFAULTS: Record<OperationStepKey, string> = {
  preflight: "Lautsprecher prüfen",
  create_left: "Auf dem linken Lautsprecher einrichten",
  create_right: "Auf dem rechten Lautsprecher einrichten",
  verify: "Ergebnis prüfen",
};
const REASON_DEFAULTS: Record<Exclude<IneligibleReason, null | "not_capable">, string> = {
  not_provisioned: "Nicht mit OCT eingerichtet",
  offline: "Offline",
  in_zone: "In einer Zone",
  in_pair: "In einem Stereopaar",
};
const ERROR_DEFAULTS: Record<string, string> = {
  stereo_pair_device_not_capable:
    "Ein Lautsprecher unterstützt keine Stereopaare. Nur der SoundTouch 10 kann ein Paar bilden.",
  stereo_pair_device_not_provisioned:
    "Mindestens ein Lautsprecher ist nicht mit OCT eingerichtet. Starte zuerst die Einrichtung.",
  stereo_pair_device_in_zone:
    "Mindestens ein Lautsprecher ist Teil einer Zone. Löse die Zone zuerst auf.",
  stereo_pair_device_in_pair: "Mindestens ein Lautsprecher ist schon in einem Stereopaar.",
  stereo_pair_device_unreachable:
    "Ein Lautsprecher antwortet nicht. Prüfe Strom und WLAN und versuche es erneut.",
  stereo_pair_marge_failed:
    "Die Lautsprecher haben die Kopplung nicht angenommen. Prüfe, ob beide mit OCT eingerichtet sind.",
  stereo_pair_verification_failed:
    "Die Kopplung konnte nicht bestätigt werden. Es wurde nichts geändert oder der Vorgang wurde zurückgenommen.",
};

type Selection = string[]; // [left, right]

function toggleSelection(s: Selection, id: string): Selection {
  if (s.includes(id)) return s.filter((x) => x !== id);
  return s.length < 2 ? [...s, id] : s;
}

function swapSelection(s: Selection): Selection {
  const [first, second] = s;
  return first !== undefined && second !== undefined ? [second, first] : s;
}

function pairDefaultName(t: TFunction, left?: Device, right?: Device): string {
  if (!left || !right) return "";
  return t("stereo.defaultName", "{{left}} + {{right}}", { left: left.name, right: right.name });
}

function firmwareMismatch(left?: Device, right?: Device): boolean {
  return !!left?.firmware && !!right?.firmware && left.firmware !== right.firmware;
}

interface Props {
  open: boolean;
  /** hides the dialog; a running operation keeps running (the section shows the pair as "creating") */
  onClose: () => void;
  devices: Device[];
  create: StereoPairCreate;
  repairing: boolean;
  onRepair: (pairId: number) => void;
}

function PickStep({
  candidates,
  selected,
  onToggle,
  descId,
  countId,
}: Readonly<{
  candidates: Device[];
  selected: Selection;
  onToggle: (id: string) => void;
  descId: string;
  countId: string;
}>) {
  const { t } = useTranslation();
  return (
    <fieldset className="sp-pick">
      <legend className="sp-pick-legend">
        {t("stereo.dlg.pickLegend", "Wähle zwei Lautsprecher")}
      </legend>
      <p className="sp-reason">
        {t(
          "stereo.dlg.pickHint",
          "Nur SoundTouch 10, die mit OCT eingerichtet sind, können ein Paar bilden."
        )}
      </p>
      <div className="sp-pick-list">
        {candidates.map((d) => {
          const reason = d.stereo_ineligible_reason;
          const isSel = selected.includes(d.device_id);
          const full = selected.length >= 2 && !isSel;
          const blocked = reason !== null || full;
          const checkId = `${descId}-pick-${d.device_id}`;
          const reasonKey = reason && reason !== "not_capable" ? reason : null;
          return (
            <div
              key={d.device_id}
              className={`mr-dev${isSel ? " mr-dev--selected" : ""}${blocked ? " mr-dev--zone" : ""}`}
            >
              <input
                id={checkId}
                className="mr-dev-check"
                type="checkbox"
                checked={isSel}
                disabled={blocked}
                onChange={() => onToggle(d.device_id)}
                aria-describedby={`${checkId}-info ${countId}`}
              />
              <div className="mr-dev-main">
                <label className="mr-dev-name" htmlFor={checkId}>
                  {d.name}
                </label>
                <span className="mr-dev-model">{d.model}</span>
                <div className="mr-dev-badges" id={`${checkId}-info`}>
                  {reasonKey && (
                    <span className="ui-badge ui-badge--warning ui-badge--small">
                      <span className="ui-badge-icon" aria-hidden="true">
                        {reasonKey === "offline" ? Icon.WifiOff(14) : Icon.Alert(14)}
                      </span>
                      {t(`stereo.reason.${reasonKey}`, REASON_DEFAULTS[reasonKey])}
                    </span>
                  )}
                </div>
              </div>
              {reason === "not_provisioned" && (
                <Link className="btn btn-ghost mr-star sp-wizard-link" to="/setup">
                  {t("stereo.openWizard", "Einrichtung starten")}
                </Link>
              )}
            </div>
          );
        })}
      </div>
      <output id={countId} className="sp-count">
        {t("stereo.dlg.pickCount", "{{count}} von 2 ausgewählt", { count: selected.length })}
      </output>
    </fieldset>
  );
}

function SidesStep({
  left,
  right,
  name,
  onNameChange,
  defaultName,
  onSwap,
  nameId,
}: Readonly<{
  left: Device;
  right: Device;
  name: string;
  onNameChange: (name: string) => void;
  defaultName: string;
  onSwap: () => void;
  nameId: string;
}>) {
  const { t } = useTranslation();
  const mismatch = firmwareMismatch(left, right);
  return (
    <>
      <div className="sp-sides">
        <h3 className="ui-h3">{t("stereo.dlg.sidesTitle", "Welcher Lautsprecher steht wo?")}</h3>
        <p className="sp-reason">
          {t("stereo.dlg.sidesHint", "Links und rechts, wie du vor den Lautsprechern stehst.")}
        </p>
      </div>
      <div className="sp-slots">
        {[
          { role: "LEFT" as const, dev: left },
          { role: "RIGHT" as const, dev: right },
        ].map(({ role, dev }, i) => (
          <div key={role} className={`sp-slot${i === 1 ? " sp-slot--right" : ""}`}>
            <div className="sp-slot-head">
              <SideTile role={role} />
              <span className="sp-slot-label">
                {role === "LEFT" ? t("stereo.left", "Links") : t("stereo.right", "Rechts")}
              </span>
            </div>
            <span className="sp-slot-name">{dev.name}</span>
            <span className="mr-dev-model">{dev.model}</span>
            {role === "LEFT" && (
              <span className="ui-badge ui-badge--info ui-badge--small">
                <span className="ui-badge-icon mr-fill" aria-hidden="true">
                  {Icon.Star(14)}
                </span>
                {t("stereo.master", "Hauptlautsprecher")}
              </span>
            )}
          </div>
        ))}
        <button type="button" className="btn btn-secondary sp-swap" onClick={onSwap}>
          <span className="sp-swap-icon" aria-hidden="true">
            {Icon.ArrowLeftRight(18)}
          </span>
          <span>{t("stereo.dlg.swap", "Seiten tauschen")}</span>
        </button>
      </div>
      <div className="wz-status mr-info">
        <span className="wz-icon" aria-hidden="true">
          {Icon.Info(22)}
        </span>
        <div className="wz-status-body">
          <p>
            {t(
              "stereo.dlg.masterHint",
              "Der linke Lautsprecher ist immer der Hauptlautsprecher. Wiedergabe, Quelle und Voreinstellungen laufen darüber."
            )}
          </p>
        </div>
      </div>
      {mismatch && (
        <output className="wz-status wz-status--warning">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Alert(22)}
          </span>
          <div className="wz-status-body">
            <p>
              {t(
                "stereo.dlg.firmwareWarn",
                "Die Firmware-Versionen unterscheiden sich ({{left}} und {{right}}). Du kannst das Stereopaar trotzdem erstellen.",
                { left: left.firmware, right: right.firmware }
              )}
            </p>
          </div>
        </output>
      )}
      <div className="ui-field">
        <label htmlFor={nameId} className="ui-label">
          {t("stereo.dlg.nameLabel", "Name (optional)")}
        </label>
        <input
          id={nameId}
          className="ui-input"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder={defaultName}
          maxLength={40}
          autoComplete="off"
        />
        <p className="ui-field-hint">
          {t("stereo.dlg.nameHint", "Ohne Eingabe: {{name}}", { name: defaultName })}
        </p>
      </div>
    </>
  );
}

function RunningPanel({ create }: Readonly<{ create: StereoPairCreate }>) {
  const { t } = useTranslation();
  const doneCount = create.steps.filter((s) => s.state === "done").length;
  const current = create.steps.find((s) => s.state === "running");
  return (
    <>
      <>
        <div className="sp-run-head">
          <h3 className="ui-h3">{t("stereo.dlg.runningTitle", "Stereopaar wird erstellt")}</h3>
          <p className="sp-reason">
            {t("stereo.dlg.runningHint", "Lass beide Lautsprecher eingeschaltet.")}
          </p>
        </div>
        <progress
          className="sp-bar"
          aria-label={t("stereo.dlg.runningTitle", "Stereopaar wird erstellt")}
          max={STEP_KEYS.length}
          value={doneCount}
        />
        <output className="visually-hidden">
          {current
            ? t("stereo.dlg.stepAnn", "Schritt {{n}} von 4: {{label}}", {
                n: STEP_KEYS.indexOf(current.key) + 1,
                label: t(`stereo.step.${current.key}`, STEP_DEFAULTS[current.key]),
              })
            : ""}
        </output>
      </>
    </>
  );
}

function SucceededPanel({ create }: Readonly<{ create: StereoPairCreate }>) {
  const { t } = useTranslation();
  return (
    <output className="wz-status wz-status--success">
      <span className="wz-icon" aria-hidden="true">
        {Icon.CircleCheck(24)}
      </span>
      <div className="wz-status-body">
        <h3 className="wz-status-title">
          {t("stereo.dlg.successTitle", "Stereopaar „{{name}}“ ist aktiv", {
            name: create.pair?.name ?? create.request?.defaultName,
          })}
        </h3>
        <p>
          {t(
            "stereo.dlg.successText",
            "{{left}} spielt links, {{right}} rechts. Steuere die Wiedergabe über {{left}}.",
            { left: create.request?.leftName, right: create.request?.rightName }
          )}
        </p>
      </div>
    </output>
  );
}

function FailedPanel({
  create,
  degraded,
}: Readonly<{ create: StereoPairCreate; degraded: boolean }>) {
  const { t } = useTranslation();
  const errorText = create.error
    ? t(
        `stereo.err.${create.error.code}`,
        ERROR_DEFAULTS[create.error.code] ?? create.error.message
      )
    : "";
  return (
    <div
      className={`wz-status ${degraded ? "wz-status--warning" : "wz-status--error"}`}
      role="alert"
    >
      <span className="wz-icon" aria-hidden="true">
        {degraded ? Icon.Alert(24) : Icon.CircleX(24)}
      </span>
      <div className="wz-status-body">
        <h3 className="wz-status-title">
          {degraded
            ? t("stereo.degradedTitle", "Nur ein Lautsprecher ist gekoppelt")
            : t("stereo.dlg.failedTitle", "Das Stereopaar wurde nicht erstellt")}
        </h3>
        <p>{errorText}</p>
        <p>
          {degraded
            ? t(
                "stereo.dlg.degradedText",
                "Repariere das Paar, damit beide Lautsprecher wieder einzeln nutzbar sind."
              )
            : t("stereo.dlg.failedNothing", "Es wurde nichts geändert.")}
        </p>
        {create.error && (
          <p className="sp-code">
            {t("stereo.dlg.failedCode", "Fehlercode: {{code}}", {
              code: create.error.code,
            })}
          </p>
        )}
      </div>
    </div>
  );
}

function RunStep({ create, degraded }: Readonly<{ create: StereoPairCreate; degraded: boolean }>) {
  const { t } = useTranslation();
  return (
    <div className="sp-run">
      {create.phase === "running" && <RunningPanel create={create} />}
      {create.phase === "succeeded" && <SucceededPanel create={create} />}
      {create.phase === "failed" && <FailedPanel create={create} degraded={degraded} />}

      <ol className="sp-ops" aria-label={t("stereo.dlg.stepsLabel", "Schritte")}>
        {create.steps.map((s) => (
          <li key={s.key} className={`sp-op sp-op--${s.state}`}>
            <span className="sp-op-icon" aria-hidden="true">
              {s.state === "running" && <span className="wz-spinner" />}
              {s.state === "done" && Icon.CircleCheck(22)}
              {s.state === "failed" && Icon.CircleX(22)}
              {s.state === "waiting" && <span className="sp-ring" />}
            </span>
            <span className="sp-op-label">{t(`stereo.step.${s.key}`, STEP_DEFAULTS[s.key])}</span>
            <span className="sp-op-state">{t(`stereo.stepState.${s.state}`, s.state)}</span>
          </li>
        ))}
      </ol>

      {create.phase === "running" && (
        <p className="sp-reason">
          {t(
            "stereo.dlg.backgroundHint",
            "Du kannst das Fenster schließen. Das Paar erscheint dann mit dem Status „Wird erstellt“."
          )}
        </p>
      )}
    </div>
  );
}

function FailedActions({
  create,
  degraded,
  repairing,
  onRepair,
  onStart,
  onBackToSides,
  onCloseAndRestart,
}: Readonly<{
  create: StereoPairCreate;
  degraded: boolean;
  repairing: boolean;
  onRepair: (pairId: number) => void;
  onStart: () => void;
  onBackToSides: () => void;
  onCloseAndRestart: () => void;
}>) {
  const { t } = useTranslation();
  const pair = create.pair;
  return (
    <>
      <button type="button" className="btn btn-secondary" onClick={onCloseAndRestart}>
        {t("common.close", "Schließen")}
      </button>
      {degraded && pair ? (
        <button
          type="button"
          className="btn btn-primary"
          disabled={repairing}
          aria-busy={repairing || undefined}
          onClick={() => onRepair(pair.id)}
          data-autofocus
        >
          {repairing ? <span className="ui-spin">{Icon.Loader(18)}</span> : Icon.Wrench(18)}
          <span>
            {repairing ? t("stereo.repairing", "Wird repariert") : t("stereo.repair", "Reparieren")}
          </span>
        </button>
      ) : (
        <>
          <button type="button" className="btn btn-secondary" onClick={onBackToSides}>
            {t("stereo.dlg.back", "Zurück")}
          </button>
          <button type="button" className="btn btn-primary" onClick={onStart} data-autofocus>
            {Icon.RefreshCw(18)}
            <span>{t("stereo.dlg.retry", "Erneut versuchen")}</span>
          </button>
        </>
      )}
    </>
  );
}

function StepLine({ step, descId }: Readonly<{ step: 1 | 2 | 3; descId: string }>) {
  const { t } = useTranslation();
  const stepLabels = {
    1: t("stereo.dlg.step1", "Lautsprecher wählen"),
    2: t("stereo.dlg.step2", "Seiten zuweisen"),
    3: t("stereo.dlg.step3", "Erstellen"),
  };
  return (
    <div className="sp-stepline">
      <p id={descId} className="sp-stepline-text">
        <span className="sp-stepline-num">
          {t("stereo.dlg.stepOf", "Schritt {{current}} von 3", { current: step })}
        </span>
        <span aria-hidden="true"> · </span>
        <span>{stepLabels[step]}</span>
      </p>
      <div className="sp-stepline-bar" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span
            key={n}
            className={n <= step ? "sp-stepline-seg sp-stepline-seg--on" : "sp-stepline-seg"}
          />
        ))}
      </div>
    </div>
  );
}

export default function StereoPairCreateDialog({
  open,
  onClose,
  devices,
  create,
  repairing,
  onRepair,
}: Readonly<Props>) {
  const { t } = useTranslation();
  const titleId = useId();
  const descId = useId();
  const nameId = useId();
  const countId = useId();
  const [localStep, setLocalStep] = useState<1 | 2>(1);
  const [selected, setSelected] = useState<Selection>([]);
  const [name, setName] = useState("");
  const bodyRef = useRef<HTMLDivElement>(null);

  const candidates = devices.filter((d) => d.stereo_capable);
  const byId = (id: string) => devices.find((d) => d.device_id === id);
  const left = byId(selected[0] ?? "");
  const right = byId(selected[1] ?? "");
  const defaultName = pairDefaultName(t, left, right);

  const running = create.phase !== "idle";
  const step: 1 | 2 | 3 = running ? 3 : localStep;

  // The buttons of the old step are gone after a step change: move focus to the primary action of the new one
  // (Modal only focuses [data-autofocus] when it opens). Step 1 has none enabled, focus then stays on the close button.
  useEffect(() => {
    if (!open) return;
    bodyRef.current
      ?.closest("dialog")
      ?.querySelector<HTMLElement>("[data-autofocus]:not([disabled])")
      ?.focus();
  }, [open, step, create.phase]);

  const toggle = (id: string) => setSelected((s) => toggleSelection(s, id));
  const start = () => {
    if (!left || !right) return;
    create.start({
      left_device_id: left.device_id,
      right_device_id: right.device_id,
      name: name.trim() || undefined,
      leftName: left.name,
      rightName: right.name,
      defaultName,
    });
  };
  const restart = () => {
    create.reset();
    setLocalStep(1);
    setSelected([]);
    setName("");
  };
  const closeAndRestart = () => {
    onClose();
    restart();
  };
  const backToSides = () => {
    create.reset();
    setLocalStep(2);
  };
  const degraded = create.phase === "failed" && create.pair?.status === "degraded";

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      labelledBy={titleId}
      describedBy={descId}
      closeOnBackdrop={false}
    >
      <div className="dlg-head">
        <h2 id={titleId} className="dlg-title">
          {t("stereo.create", "Stereopaar erstellen")}
        </h2>
        <button
          type="button"
          className="btn btn-ghost btn-icon dlg-close"
          onClick={onClose}
          aria-label={
            running && create.phase === "running"
              ? t("stereo.background", "Im Hintergrund fortsetzen")
              : t("common.close", "Schließen")
          }
        >
          {Icon.X(22)}
        </button>
      </div>

      <StepLine step={step} descId={descId} />

      <div className="dlg-body sp-body" ref={bodyRef}>
        {step === 1 && (
          <PickStep
            candidates={candidates}
            selected={selected}
            onToggle={toggle}
            descId={descId}
            countId={countId}
          />
        )}
        {step === 2 && left && right && (
          <SidesStep
            left={left}
            right={right}
            name={name}
            onNameChange={setName}
            defaultName={defaultName}
            onSwap={() => setSelected(swapSelection)}
            nameId={nameId}
          />
        )}
        {step === 3 && <RunStep create={create} degraded={degraded} />}
      </div>

      <div className="dlg-actions">
        {step === 1 && (
          <>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              {t("common.cancel", "Abbrechen")}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={selected.length < 2}
              onClick={() => setLocalStep(2)}
            >
              {t("stereo.dlg.next", "Weiter")}
            </button>
          </>
        )}
        {step === 2 && (
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setLocalStep(1)}>
              {t("stereo.dlg.back", "Zurück")}
            </button>
            <button type="button" className="btn btn-primary" onClick={start} data-autofocus>
              {Icon.Plus(18)}
              <span>{t("stereo.create", "Stereopaar erstellen")}</span>
            </button>
          </>
        )}
        {step === 3 && create.phase === "running" && (
          <button type="button" className="btn btn-secondary" onClick={onClose} data-autofocus>
            {t("stereo.background", "Im Hintergrund fortsetzen")}
          </button>
        )}
        {step === 3 && create.phase === "succeeded" && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={closeAndRestart}
            data-autofocus
          >
            {t("stereo.dlg.done", "Fertig")}
          </button>
        )}
        {step === 3 && create.phase === "failed" && (
          <FailedActions
            create={create}
            degraded={degraded}
            repairing={repairing}
            onRepair={onRepair}
            onStart={start}
            onBackToSides={backToSides}
            onCloseAndRestart={closeAndRestart}
          />
        )}
      </div>
    </Modal>
  );
}
