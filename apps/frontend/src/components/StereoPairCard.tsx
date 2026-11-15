import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { StereoPair, StereoRole } from "../api/stereoPairs";
import { Icon } from "./Icon";
import "./StereoPairCard.css";

/** Square tile with the channel letter. Decorative: the word "Links" / "Rechts" always sits next to it. */
export function SideTile({ role }: Readonly<{ role: StereoRole }>) {
  return (
    <span className={`sp-side sp-side--${role}`} aria-hidden="true">
      {role === "LEFT" ? "L" : "R"}
    </span>
  );
}

/** Badge of the pair card in the device list: the pair is one device playing left and right. */
export function StereoPairBadge() {
  const { t } = useTranslation();
  return (
    <span className="ui-badge ui-badge--info ui-badge--small sp-role" data-test="device-stereo">
      {t("stereo.pairBadge", "L/R Stereo")}
    </span>
  );
}

function StatusChip({ status }: Readonly<{ status: StereoPair["status"] }>) {
  const { t } = useTranslation();
  if (status === "creating") {
    return (
      <span className="ui-badge ui-badge--info ui-badge--small" data-test="stereo-status">
        <span className="spinner-small" aria-hidden="true" />
        {t("stereo.status.creating", "Wird erstellt")}
      </span>
    );
  }
  if (status === "degraded") {
    return (
      <span className="ui-badge ui-badge--warning ui-badge--small" data-test="stereo-status">
        <span className="ui-badge-icon" aria-hidden="true">
          {Icon.Alert(14)}
        </span>
        {t("stereo.status.degraded", "Unterbrochen")}
      </span>
    );
  }
  return (
    <span className="ui-badge ui-badge--success ui-badge--small" data-test="stereo-status">
      <span className="ui-badge-icon" aria-hidden="true">
        {Icon.CircleCheck(14)}
      </span>
      {t("stereo.status.active", "Aktiv")}
    </span>
  );
}

/** Zone-name editing pattern (click the name, Enter saves, Esc cancels). */
function EditablePairName({
  name,
  disabled,
  onSave,
}: Readonly<{ name: string; disabled: boolean; onSave: (name: string) => void }>) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const cancelledRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const handleSave = () => {
    setEditing(false);
    if (cancelledRef.current) {
      cancelledRef.current = false;
      return;
    }
    const next = draft.trim();
    if (next && next !== name) onSave(next);
  };

  if (editing) {
    return (
      <h3 className="zn-title">
        <input
          ref={inputRef}
          className="ui-input zn-name-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={handleSave}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleSave();
            } else if (e.key === "Escape") {
              cancelledRef.current = true;
              setDraft(name);
              setEditing(false);
            }
          }}
          maxLength={40}
          aria-label={t("stereo.renameLabel", "Name des Stereopaars")}
        />
      </h3>
    );
  }

  return (
    <h3 className="zn-title">
      <button
        type="button"
        className="zn-name"
        disabled={disabled}
        onClick={() => {
          cancelledRef.current = false;
          setDraft(name);
          setEditing(true);
        }}
        title={t("stereo.clickToEdit", "Zum Umbenennen anklicken")}
      >
        <span className="zn-name-text">{name}</span>
        <span className="zn-name-icon" aria-hidden="true">
          {Icon.Pencil(16)}
        </span>
      </button>
    </h3>
  );
}

export interface StereoPairCardProps {
  pair: StereoPair;
  /** an action (rename, dissolve, repair) of this pair is running */
  busy: boolean;
  /** only while status is "creating": finished steps / total, from the running operation */
  progress?: { done: number; total: number } | null;
  onRename: (name: string) => void;
  onDissolve: () => void;
  onRepair: () => void;
  /** reopens the create dialog; only passed for the pair this session is creating */
  onShowProgress?: () => void;
}

export default function StereoPairCard({
  pair,
  busy,
  progress,
  onRename,
  onDissolve,
  onRepair,
  onShowProgress,
}: Readonly<StereoPairCardProps>) {
  const { t } = useTranslation();
  const reasonId = useId();
  const left = pair.members.find((m) => m.role === "LEFT");
  const right = pair.members.find((m) => m.role === "RIGHT");
  const members = [left, right].filter((m): m is NonNullable<typeof m> => !!m);
  const offline = members.find((m) => !m.reachable);
  const creating = pair.status === "creating";
  const degraded = pair.status === "degraded";
  const locked = creating || busy;

  return (
    <article className={`ui-card sp-card sp-card--${pair.status}`} data-test="stereo-pair">
      <div className="sp-card-head">
        <span className="zn-icon" aria-hidden="true">
          {Icon.Speaker(22)}
        </span>
        <EditablePairName name={pair.name} disabled={locked || degraded} onSave={onRename} />
      </div>

      <div className="sp-chips">
        <StatusChip status={pair.status} />
        {pair.source === "device" && (
          <span
            className="ui-badge ui-badge--small"
            title={t("stereo.importedTitle", "Außerhalb von OCT erstellt")}
          >
            <span className="ui-badge-icon" aria-hidden="true">
              {Icon.Download(14)}
            </span>
            {t("stereo.imported", "Importiert")}
          </span>
        )}
      </div>

      <ul className="sp-members" aria-label={t("stereo.members", "Lautsprecher des Stereopaars")}>
        {members.map((m) => (
          <li key={m.device_id} className={`sp-member${m.reachable ? "" : " sp-member--offline"}`}>
            <SideTile role={m.role} />
            <div className="sp-member-body">
              <span className="sp-member-role">
                {m.role === "LEFT" ? t("stereo.left", "Links") : t("stereo.right", "Rechts")}
                {m.role === "LEFT" && <> · {t("stereo.master", "Hauptlautsprecher")}</>}
              </span>
              <span className="sp-member-name">{m.name}</span>
            </div>
            {!m.reachable && (
              <span className="ui-badge ui-badge--warning ui-badge--small">
                <span className="ui-badge-icon" aria-hidden="true">
                  {Icon.WifiOff(14)}
                </span>
                {t("stereo.offline", "Offline")}
              </span>
            )}
          </li>
        ))}
      </ul>

      {creating && (
        <div className="sp-creating">
          <progress
            className="sp-bar"
            aria-label={t("stereo.status.creating", "Wird erstellt")}
            max={progress?.total ?? 4}
            value={progress?.done ?? 0}
          />
          <p className="sp-reason">{t("stereo.creatingText", "Wird erstellt.")}</p>
          {onShowProgress && (
            <button type="button" className="btn btn-secondary" onClick={onShowProgress}>
              {t("stereo.showProgress", "Fortschritt anzeigen")}
            </button>
          )}
        </div>
      )}

      {degraded && (
        <div className="wz-status wz-status--warning sp-degraded" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Alert(22)}
          </span>
          <div className="wz-status-body">
            <h4 className="mr-info-title">
              {t("stereo.degradedTitle", "Nur ein Lautsprecher ist gekoppelt")}
            </h4>
            <p>
              {t(
                "stereo.degradedText",
                "Das Paar funktioniert nicht richtig. Beim Reparieren werden beide Lautsprecher auf einen sauberen Zustand zurückgesetzt. Danach kannst du das Stereopaar neu erstellen."
              )}
            </p>
          </div>
        </div>
      )}

      {!creating && (
        <div className="zn-actions">
          {degraded ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onRepair}
              disabled={busy}
              aria-busy={busy || undefined}
            >
              {busy ? <span className="ui-spin">{Icon.Loader(18)}</span> : Icon.Wrench(18)}
              <span>
                {busy ? t("stereo.repairing", "Wird repariert") : t("stereo.repair", "Reparieren")}
              </span>
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-danger-outline"
              onClick={onDissolve}
              disabled={busy || !!offline}
              aria-describedby={offline ? reasonId : undefined}
            >
              {Icon.Unlink(18)}
              <span>{t("stereo.dissolve", "Auflösen")}</span>
            </button>
          )}
        </div>
      )}
      {offline && !degraded && !creating && (
        <p id={reasonId} className="sp-reason">
          {t(
            "stereo.dissolveNeedsBoth",
            "Zum Auflösen müssen beide Lautsprecher erreichbar sein. {{name}} ist offline.",
            { name: offline.name }
          )}
        </p>
      )}
    </article>
  );
}
