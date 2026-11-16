/**
 * DLNA media browser: server list, folder navigation with breadcrumb, paging and a filter over the
 * loaded entries. Reusable: it knows nothing about presets; the per-row action comes in as a render prop.
 */
import { useCallback, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import type { DlnaItem } from "../../api/dlna";
import {
  FolderView,
  ServersView,
  type DlnaSession,
  type FocusTarget,
  type RowActionContext,
} from "./DlnaViews";
import "./DlnaBrowser.css";

export type { DlnaSession, DlnaCrumb, RowActionContext } from "./DlnaViews";

interface DlnaBrowserProps {
  /** Per-row action (use for a preset, queue, ...). */
  readonly renderRowAction: (item: DlnaItem, ctx: RowActionContext) => ReactNode;
  /** Id of the item whose action is running: all actions are disabled and that row shows the saving state. */
  readonly busyItemId?: string | null;
  /** Text of the busy row ("Saving preset 3 ..."). */
  readonly busyLabel?: string;
  /** Banner above the list owned by the parent (for example a save error). */
  readonly banner?: ReactNode;
  /** Where to start; only the top folder is browsed, a missing folder or server falls back with a notice. */
  readonly initialSession?: DlnaSession | null;
  readonly onSessionChange?: (session: DlnaSession | null) => void;
}

interface Notice {
  key: string;
  vars?: Record<string, string>;
}

export default function DlnaBrowser({
  renderRowAction,
  busyItemId = null,
  busyLabel,
  banner,
  initialSession = null,
  onSessionChange,
}: DlnaBrowserProps) {
  const { t } = useTranslation();
  const [session, setSession] = useState<DlnaSession | null>(initialSession);
  // True until the restored top folder answered; only then a gone folder or an offline server means "fall back".
  const [restoring, setRestoring] = useState(initialSession !== null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [focus, setFocus] = useState<FocusTarget>(null);
  const [live, setLive] = useState("");

  const go = (next: DlnaSession | null, to: FocusTarget, message: Notice | null = null) => {
    setSession(next);
    setFocus(to);
    setNotice(message);
    setRestoring(false);
    onSessionChange?.(next);
  };

  const stack = session?.stack ?? [];
  const up = () => {
    if (!session) return;
    if (stack.length === 0) go(null, session.serverId);
    else go({ ...session, stack: stack.slice(0, -1) }, stack.at(-1)?.object_id ?? null);
  };
  const toCrumb = (index: number) => {
    if (session) go({ ...session, stack: stack.slice(0, index) }, stack[index]?.object_id ?? null);
  };

  const onFail = useCallback(
    (status: "gone" | "offline") => {
      if (!session || (status === "offline" && !restoring)) return;
      const fallback = (next: DlnaSession | null, message: Notice) => {
        setSession(next);
        setFocus(null);
        setNotice(message);
        onSessionChange?.(next);
      };
      const serverGone = { key: "sessionServerGone" };
      if (status === "offline" || session.stack.length === 0) return fallback(null, serverGone);
      if (restoring) {
        return fallback(
          { ...session, stack: [] },
          { key: "sessionFolderGone", vars: { server: session.serverName } }
        );
      }
      const parent = session.stack.length > 1;
      fallback(
        { ...session, stack: session.stack.slice(0, -1) },
        { key: parent ? "goneParent" : "goneRoot" }
      );
    },
    [session, restoring, onSessionChange]
  );
  const onResolved = useCallback(() => setRestoring(false), []);

  const noticeBox = notice && (
    <div className="dl-banner">
      <div className="wz-status" role="status">
        <span className="wz-icon" aria-hidden="true">
          {Icon.Info(20)}
        </span>
        <div className="wz-status-body">
          <p className="wz-status-text">{t(`presets.dlna.${notice.key}`, notice.vars)}</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-icon"
          aria-label={t("presets.dlna.noticeClose")}
          onClick={() => setNotice(null)}
        >
          {Icon.X(18)}
        </button>
      </div>
    </div>
  );

  return (
    <div className="dl">
      {session ? (
        <FolderView
          key={`${session.serverId}/${stack.at(-1)?.object_id ?? "0"}`}
          session={session}
          restoring={restoring}
          focus={focus}
          banner={banner}
          notice={noticeBox}
          busyItemId={busyItemId}
          busyLabel={busyLabel}
          renderRowAction={renderRowAction}
          onUp={up}
          onServers={() => go(null, session.serverId)}
          onCrumb={toCrumb}
          onOpenFolder={(item) =>
            go(
              { ...session, stack: [...stack, { object_id: item.id, title: item.title }] },
              "heading"
            )
          }
          onFail={onFail}
          onResolved={onResolved}
          onLive={setLive}
        />
      ) : (
        <ServersView
          banner={
            <>
              {banner}
              {noticeBox}
            </>
          }
          focus={focus}
          onOpen={(id, name) => go({ serverId: id, serverName: name, stack: [] }, "heading")}
          onLive={setLive}
        />
      )}
      <div className="dl-sr" role="status" aria-live="polite">
        {live}
      </div>
    </div>
  );
}
