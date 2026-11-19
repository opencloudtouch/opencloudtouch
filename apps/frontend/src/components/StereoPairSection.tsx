import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import type { Device } from "./DeviceSwiper";
import type { StereoPair } from "../api/stereoPairs";
import { useStereoPairs } from "../hooks/useStereoPairs";
import { useStereoPairCreate } from "../hooks/useStereoPairCreate";
import { useToast } from "../contexts/ToastContext";
import { userErrorMessage } from "../utils/errorMessages";
import StereoPairCard from "./StereoPairCard";
import StereoPairCreateDialog from "./StereoPairCreateDialog";
import ConfirmDialog from "./ConfirmDialog";
import { Icon } from "./Icon";
import "./StereoPairSection.css";

type EmptyKind = "none" | "one" | "setup" | "ready";

export default function StereoPairSection({
  devices,
  onPairsChanged,
}: Readonly<{ devices: Device[]; onPairsChanged?: () => void }>) {
  const { t } = useTranslation();
  const noteId = useId();
  const { pairs, isLoading, error, reload, busyId, renamePair, dissolvePair, repairPair } =
    useStereoPairs(onPairsChanged);
  const create = useStereoPairCreate();
  const { show: showToast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dissolving, setDissolving] = useState<StereoPair | null>(null);

  // A failed action rejects in the hook: tell the user instead of leaving it unhandled
  const act = (action: () => Promise<void>) => {
    action().catch((e: unknown) => showToast(userErrorMessage(e), "error"));
  };

  const capable = devices.filter((d) => d.stereo_capable);
  const eligible = capable.filter((d) => d.stereo_ineligible_reason === null);
  const running = create.phase === "running";

  // The operation runs in the hook, not in the dialog: closing the dialog shows the pair as "creating" here
  const request = create.request;
  const pendingPair: StereoPair | null =
    running && request
      ? {
          id: -1,
          name: request.name || request.defaultName,
          status: "creating",
          source: "oct",
          members: [
            {
              device_id: request.left_device_id,
              name: request.leftName,
              role: "LEFT",
              reachable: true,
            },
            {
              device_id: request.right_device_id,
              name: request.rightName,
              role: "RIGHT",
              reachable: true,
            },
          ],
          warnings: [],
        }
      : null;
  const listed = pendingPair
    ? pairs.filter((p) => !p.members.some((m) => m.device_id === request?.left_device_id))
    : pairs;
  const total = create.steps.length || 4;
  const done = create.steps.filter((s) => s.state === "done").length;

  // Finished while the dialog is closed: say so, the result is not lost.
  // The failed toast is shown once per failure, not on every re-render of the hook state.
  const failedToastShownRef = useRef(false);
  useEffect(() => {
    if (create.phase !== "failed") failedToastShownRef.current = false;
    if (dialogOpen) return;
    if (create.phase === "succeeded") {
      showToast(t("stereo.toast.created", "Stereopaar erstellt"), "success");
      create.reset();
    } else if (create.phase === "failed" && !failedToastShownRef.current) {
      failedToastShownRef.current = true;
      showToast(
        t("stereo.toast.createFailed", "Das Stereopaar konnte nicht erstellt werden"),
        "error",
        {
          persistent: true,
          action: {
            label: t("stereo.toast.details", "Details"),
            onClick: () => setDialogOpen(true),
          },
        }
      );
    }
  }, [create, dialogOpen, showToast, t]);

  // The pair list must show the result whether or not the dialog is still open
  const finished = create.phase === "succeeded" || create.phase === "failed";
  useEffect(() => {
    if (finished) reload();
  }, [finished, reload]);

  let emptyKind: EmptyKind = "ready";
  if (capable.length === 0) emptyKind = "none";
  else if (capable.length === 1) emptyKind = "one";
  else if (capable.every((d) => !d.oct_provisioned)) emptyKind = "setup";
  const canCreate = eligible.length >= 2 && !running;

  const emptyTitle = {
    none: t("stereo.empty.none.title", "Kein Lautsprecher für Stereopaare"),
    one: t("stereo.empty.one.title", "Ein zweiter SoundTouch 10 fehlt"),
    setup: t("stereo.empty.setup.title", "Lautsprecher noch nicht eingerichtet"),
    ready: t("stereo.empty.ready.title", "Noch kein Stereopaar"),
  }[emptyKind];
  const emptyText = {
    none: t(
      "stereo.empty.none.text",
      "Stereopaare funktionieren nur mit dem SoundTouch 10. Es wurde noch keiner gefunden."
    ),
    one: t(
      "stereo.empty.one.text",
      "Für ein Stereopaar werden zwei SoundTouch 10 benötigt. Gefunden wurde: {{name}}.",
      { name: capable[0]?.name }
    ),
    setup: t(
      "stereo.empty.setup.text",
      "Stereopaare brauchen Lautsprecher, die mit OCT eingerichtet sind. Starte die Einrichtung für deine SoundTouch 10."
    ),
    ready: t(
      "stereo.empty.ready.text",
      "{{count}} SoundTouch 10 können zu einem Stereopaar verbunden werden. Einer spielt links, der andere rechts.",
      { count: capable.length }
    ),
  }[emptyKind];

  return (
    <section className="mr-section sp" aria-labelledby="sp-title" data-test="stereo-section">
      <div className="sp-head">
        <h2 id="sp-title" className="ui-h2">
          {t("stereo.title", "Stereopaare")}
        </h2>
        <button
          type="button"
          className="btn btn-primary sp-create"
          onClick={() => setDialogOpen(true)}
          disabled={!canCreate}
          aria-describedby={canCreate ? undefined : noteId}
        >
          {Icon.Plus(18)}
          <span>{t("stereo.create", "Stereopaar erstellen")}</span>
        </button>
      </div>
      <p className="sp-lead">
        {t(
          "stereo.lead",
          "Zwei SoundTouch 10 spielen als ein Player: einer links, einer rechts. Das Paar bleibt auch nach einem Neustart bestehen."
        )}
      </p>
      {!canCreate && !isLoading && (
        <p id={noteId} className="sp-reason">
          {running
            ? t("stereo.createRunning", "Ein Stereopaar wird gerade erstellt.")
            : t("stereo.createNeedTwo", "Zum Erstellen werden zwei freie SoundTouch 10 benötigt.")}
        </p>
      )}

      {isLoading && listed.length === 0 && !pendingPair && (
        <>
          <output className="ui-card mr-loading">
            <span className="wz-spinner" aria-hidden="true" />
            <span>{t("stereo.loading", "Stereopaare werden geladen")}</span>
          </output>
          <div className="ui-card sp-card sp-skeleton" aria-hidden="true">
            <span className="ui-skeleton sp-sk-line" />
            <span className="ui-skeleton sp-sk-block" />
          </div>
        </>
      )}

      {error && listed.length === 0 && !pendingPair && (
        <div className="wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX(24)}
          </span>
          <div className="wz-status-body">
            <h3 className="wz-status-title">
              {t("stereo.errorLoading", "Stereopaare konnten nicht geladen werden")}
            </h3>
            <p>{error}</p>
            <button type="button" className="btn btn-secondary sp-retry" onClick={reload}>
              {Icon.RefreshCw(18)}
              <span>{t("stereo.retry", "Erneut laden")}</span>
            </button>
          </div>
        </div>
      )}

      {!isLoading && !error && listed.length === 0 && !pendingPair && (
        <div className="wz-status mr-info sp-empty" data-test={`stereo-empty-${emptyKind}`}>
          <span className="wz-icon" aria-hidden="true">
            {Icon.Info(24)}
          </span>
          <div className="wz-status-body">
            <h3 className="mr-info-title">{emptyTitle}</h3>
            <p>{emptyText}</p>
            {(emptyKind === "setup" || (emptyKind === "one" && !capable[0]?.oct_provisioned)) && (
              <Link className="btn btn-secondary sp-wizard" to="/setup">
                {Icon.Wrench(18)}
                <span>{t("stereo.openWizard", "Einrichtung starten")}</span>
              </Link>
            )}
          </div>
        </div>
      )}

      {(listed.length > 0 || pendingPair) && (
        <div className="sp-list">
          {pendingPair && (
            <StereoPairCard
              pair={pendingPair}
              busy={false}
              progress={{ done, total }}
              onRename={() => {}}
              onDissolve={() => {}}
              onRepair={() => {}}
              onShowProgress={() => setDialogOpen(true)}
            />
          )}
          {listed.map((pair) => (
            <StereoPairCard
              key={pair.id}
              pair={pair}
              busy={busyId === pair.id}
              onRename={(name) => act(() => renamePair(pair.id, name))}
              onDissolve={() => setDissolving(pair)}
              onRepair={() => act(() => repairPair(pair.id))}
            />
          ))}
        </div>
      )}

      <StereoPairCreateDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        devices={devices}
        create={create}
        repairing={create.pair ? busyId === create.pair.id : false}
        onRepair={(id) =>
          act(async () => {
            await repairPair(id);
            create.reset();
            setDialogOpen(false);
          })
        }
      />

      <ConfirmDialog
        open={dissolving !== null}
        title={t("stereo.confirmDissolveTitle", "Stereopaar auflösen?")}
        message={t(
          "stereo.confirmDissolveMessage",
          "„{{name}}“ wird aufgelöst. {{left}} und {{right}} spielen danach wieder einzeln.",
          {
            name: dissolving?.name,
            left: dissolving?.members.find((m) => m.role === "LEFT")?.name,
            right: dissolving?.members.find((m) => m.role === "RIGHT")?.name,
          }
        )}
        confirmLabel={t("stereo.dissolve", "Auflösen")}
        cancelLabel={t("common.cancel", "Abbrechen")}
        destructive
        onConfirm={() => {
          const id = dissolving?.id;
          setDissolving(null);
          if (id !== undefined) act(() => dissolvePair(id));
        }}
        onCancel={() => setDissolving(null)}
      />
    </section>
  );
}
