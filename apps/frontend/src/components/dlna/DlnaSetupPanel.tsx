import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import DlnaRemoveDialog from "./DlnaRemoveDialog";
import "./DlnaNative.css";
import { SETUP_BADGE, type DlnaSetupApi, type SetupBusy, type SetupView } from "./dlnaSetupTypes";

interface Props {
  api: DlnaSetupApi;
  serverId: string;
  serverName: string;
  /** set while a setup (started by saving a folder) or a removal runs: the panel shows "busy" */
  busy?: SetupBusy;
  /** true after 4 s of a running setup: swaps in the reassurance text */
  long?: boolean;
  /** explicit retry after "not available" (the same setup the save runs) */
  onRetrySetup: () => void;
  /** a removal started from the dialog begins or ends */
  onRemoving?: (running: boolean) => void;
}

const ICONS: Record<string, (size: number) => ReactNode> = {
  Clock: Icon.Clock,
  CircleMinus: Icon.CircleMinus,
  CircleCheck: Icon.CircleCheck,
  Alert: Icon.Alert,
  CircleHelp: Icon.CircleHelp,
};

/** Setup state of ONE media server on the target speaker, with a reserved height so the state never shifts the list. */
export default function DlnaSetupPanel({
  api,
  serverId,
  serverName,
  busy = null,
  long = false,
  onRetrySetup,
  onRemoving,
}: Readonly<Props>) {
  const { t } = useTranslation();
  const [removing, setRemoving] = useState(false);
  const server = api.servers?.find((s) => s.server_id === serverId);
  let view: SetupView;
  if (busy) view = "busy";
  else if (api.isLoading) view = "loading";
  else if (api.error === "unreachable") view = "unknown";
  else if (api.error) view = "net";
  else view = server?.state ?? "not_enabled";

  const k = (s: string, v?: Record<string, unknown>) => t(`presets.dlna.setup.${s}`, v);
  const text: Record<SetupView, string> = {
    loading: k("loading"),
    busy:
      busy === "remove"
        ? t("presets.dlna.remove.progress")
        : k(long ? "settingUpLong" : "settingUp"),
    not_enabled: k("notSetUp"),
    ready: k("ready"),
    unavailable: k("unavailableReason"),
    unknown: k("unknownText"),
    net: k("net"),
  };
  const recheck = (
    <button
      type="button"
      className="btn btn-outline"
      aria-label={k("recheckLabel", { name: serverName })}
      onClick={() => void api.refetch()}
    >
      {Icon.RefreshCw(18)}
      {k("recheck")}
    </button>
  );
  const actions: Partial<Record<SetupView, ReactNode>> = {
    ready: (
      <button
        type="button"
        className="btn btn-ghost"
        data-opener="remove"
        aria-label={t("presets.dlna.remove.actionLabel", { name: serverName })}
        onClick={() => setRemoving(true)}
      >
        {t("presets.dlna.remove.action")}
      </button>
    ),
    unavailable: (
      <button
        type="button"
        className="btn btn-secondary"
        aria-label={k("retryLabel", { name: serverName })}
        onClick={onRetrySetup}
      >
        {Icon.RefreshCw(18)}
        {k("retry")}
      </button>
    ),
    unknown: recheck,
    net: recheck,
  };
  const b = SETUP_BADGE[view];
  const spinning = view === "loading" || view === "busy";
  const label = busy === "remove" ? k("state.removing") : k(`state.${b.label}`);
  return (
    <section className="nd" aria-label={k("panelLabel", { name: serverName })} data-nd={view}>
      <div className="nd-head">
        <h4 className="nd-title">
          {Icon.Server(20)}
          <span>{k("title")}</span>
        </h4>
        <div className={`ui-badge ui-badge--${b.variant} ui-badge--small nd-badge`}>
          <span className="ui-badge-icon" aria-hidden="true">
            {spinning ? <span className="spinner-small" /> : ICONS[b.icon]?.(14)}
          </span>
          <span>{label}</span>
        </div>
      </div>
      <p className="nd-text">{text[view]}</p>
      <div className="nd-actions">{actions[view]}</div>
      {removing && (
        <DlnaRemoveDialog
          api={api}
          serverId={serverId}
          serverName={serverName}
          onRunning={onRemoving}
          onClose={() => {
            setRemoving(false);
            // the opener is gone after a successful removal: the folder heading takes the focus
            requestAnimationFrame(() =>
              (
                document.querySelector<HTMLElement>('[data-opener="remove"]') ??
                document.querySelector<HTMLElement>(".dl-h")
              )?.focus()
            );
          }}
        />
      )}
    </section>
  );
}
