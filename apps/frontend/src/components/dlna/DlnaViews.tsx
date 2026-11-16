import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import { useDlnaBrowse, useDlnaServers } from "../../hooks/useDlna";
import type { DlnaItem } from "../../api/dlna";
import { coverBlocked } from "./cover";
import "./DlnaBrowser.css";

export interface DlnaCrumb {
  object_id: string;
  title: string;
}

/** Where the browser is: a server and the folders below its root (empty stack = the root). */
export interface DlnaSession {
  serverId: string;
  serverName: string;
  stack: DlnaCrumb[];
}

export interface RowActionContext {
  disabled: boolean;
  busy: boolean;
}

/** Which element gets focus after a navigation: the heading, or the row that was left. */
export type FocusTarget = "heading" | string | null;

type Translate = ReturnType<typeof useTranslation>["t"];
const T = (t: Translate, key: string, vars?: Record<string, unknown>) =>
  t(`presets.dlna.${key}`, vars);

function Cover({ item }: Readonly<{ item: DlnaItem }>) {
  const [failed, setFailed] = useState(false);
  const url = item.album_art_url;
  if (!url || coverBlocked(url) || failed) {
    return (
      <span className="dl-cover dl-cover--ph" aria-hidden="true">
        {item.is_container ? Icon.Folder(22) : Icon.Music(22)}
      </span>
    );
  }
  return (
    <span className="dl-cover" aria-hidden="true">
      <img
        src={url}
        alt=""
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
      />
    </span>
  );
}

function Skeleton({ rows }: Readonly<{ rows: number }>) {
  return (
    <ul className="dl-list" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <li key={i} className="dl-skel">
          <span className="dl-skel-cover" />
          <span className="dl-skel-lines">
            <span className="dl-skel-line" />
            <span className="dl-skel-line" />
          </span>
        </li>
      ))}
    </ul>
  );
}

function Loading({ text }: Readonly<{ text: string }>) {
  return (
    <div className="dl-status">
      <span className="spinner-small" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}

interface StateBlockProps {
  readonly icon: ReactNode;
  readonly title: string;
  readonly text?: string;
  readonly children: ReactNode;
}

function StateBlock({ icon, title, text, children }: StateBlockProps) {
  return (
    <div className="dl-state">
      <span className="dl-state-icon" aria-hidden="true">
        {icon}
      </span>
      <h4 className="dl-state-title">{title}</h4>
      {text && <p className="dl-state-text">{text}</p>}
      <div className="dl-state-actions">{children}</div>
    </div>
  );
}

interface SlowBoxProps {
  readonly text: string;
  readonly onCancel: () => void;
  readonly onBack?: () => void;
}

/** Hint after 5 s of waiting: keep waiting (do nothing), cancel the request, or go back. */
function SlowBox({ text, onCancel, onBack }: SlowBoxProps) {
  const { t } = useTranslation();
  return (
    <div className="dl-slow">
      <div className="wz-status wz-status--warning" role="status">
        <span className="wz-icon" aria-hidden="true">
          {Icon.Clock(20)}
        </span>
        <div className="wz-status-body">
          <p className="wz-status-title">{T(t, "slowTitle")}</p>
          <p className="wz-status-text">{text}</p>
          <div className="dl-banner-actions">
            <button type="button" className="btn btn-outline btn-sm" onClick={onCancel}>
              {t("common.cancel")}
            </button>
            {onBack && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>
                {Icon.ArrowLeft(16)} {T(t, "back")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function RetryButton({ onClick }: Readonly<{ onClick: () => void }>) {
  const { t } = useTranslation();
  return (
    <button type="button" className="btn btn-outline" onClick={onClick}>
      {Icon.RefreshCw(18)} {t("common.retry")}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Server list
// ---------------------------------------------------------------------------

interface ServersViewProps {
  readonly banner?: ReactNode;
  readonly focus: FocusTarget;
  readonly onOpen: (id: string, name: string) => void;
  readonly onLive: (message: string) => void;
}

export function ServersView({ banner, focus, onOpen, onLive }: ServersViewProps) {
  const { t } = useTranslation();
  const uniqueId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const scrollRef = useRef<HTMLElement>(null);
  const { status, servers, refresh, cancel } = useDlnaServers();
  const loading = status === "loading" || status === "slow";

  useEffect(() => {
    if (focus === "heading") headingRef.current?.focus();
  }, [focus]);
  const returnedRef = useRef(focus !== "heading" ? focus : null);
  useEffect(() => {
    if (status !== "ready" || !returnedRef.current) return;
    const row = scrollRef.current?.querySelector<HTMLElement>(
      `[data-rid="${CSS.escape(returnedRef.current)}"]`
    );
    (row ?? headingRef.current)?.focus();
    returnedRef.current = null;
  }, [status, servers]);

  useEffect(() => {
    if (loading) onLive(T(t, "serversLoading"));
    else if (status === "error") onLive(T(t, "netTitle"));
    else
      onLive(
        servers.length ? T(t, "serversFound", { count: servers.length }) : T(t, "serversEmptyTitle")
      );
  }, [loading, status, servers.length, t, onLive]);

  const refreshButton = (cls: string, size: number) => (
    <button type="button" className={`btn ${cls}`} onClick={refresh}>
      {Icon.RefreshCw(size)} {T(t, "refresh")}
    </button>
  );

  let body: ReactNode;
  if (loading) {
    body = (
      <>
        <Skeleton rows={3} />
        <Loading text={T(t, "serversLoading")} />
        {status === "slow" && <SlowBox text={T(t, "serversSlow")} onCancel={cancel} />}
      </>
    );
  } else if (status === "error") {
    body = (
      <StateBlock icon={Icon.CircleX(32)} title={T(t, "netTitle")} text={T(t, "netText")}>
        {refreshButton("btn-primary", 18)}
      </StateBlock>
    );
  } else if (servers.length === 0) {
    body = (
      <StateBlock
        icon={Icon.Server(32)}
        title={T(t, "serversEmptyTitle")}
        text={T(t, "serversEmptyHint")}
      >
        {refreshButton("btn-primary", 18)}
      </StateBlock>
    );
  } else {
    body = (
      <>
        <p className="dl-count">{T(t, "serversFound", { count: servers.length })}</p>
        <ul className="dl-list" aria-label={T(t, "serversList")}>
          {servers.map((s) => (
            <li key={s.id} className="dl-row dl-row--server">
              <button
                type="button"
                className="dl-open"
                data-rid={s.id}
                aria-label={T(t, "openServer", { name: s.name })}
                onClick={() => onOpen(s.id, s.name)}
              >
                <span className="dl-srv-ico" aria-hidden="true">
                  {Icon.Server(22)}
                </span>
                <span className="dl-info">
                  <span className="dl-title" title={s.name}>
                    {s.name}
                  </span>
                </span>
                <span className="dl-chev" aria-hidden="true">
                  {Icon.ChevronRight(20)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </>
    );
  }

  return (
    <>
      <div className="dl-top">{banner}</div>
      <section
        ref={scrollRef}
        className="dl-scroll"
        tabIndex={0} // NOSONAR(S6845): scrollable region must be keyboard-focusable (WCAG 2.1.1)
        aria-labelledby={`${uniqueId}-title`}
        aria-busy={loading || undefined}
      >
        <div className="dl-head">
          <h3 className="dl-h" id={`${uniqueId}-title`} tabIndex={-1} ref={headingRef}>
            {T(t, "serversTitle")}
          </h3>
          {!loading && servers.length > 0 && refreshButton("btn-ghost btn-sm", 16)}
        </div>
        {body}
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// Folder
// ---------------------------------------------------------------------------

function Crumbs({
  session,
  onCrumb,
}: Readonly<{ session: DlnaSession; onCrumb: (index: number) => void }>) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);
  const all: { title: string }[] = [{ title: session.serverName }, ...session.stack];
  const last = all.length - 1;
  const collapsed = all.length > 3 && !open;

  useEffect(() => {
    if (open) navRef.current?.querySelector<HTMLElement>("button.dl-crumb")?.focus();
  }, [open]);

  const crumb = (i: number) => {
    const title = all[i]?.title ?? "";
    return i === last ? (
      <span className="dl-crumb dl-crumb--current" aria-current="page">
        <span title={title}>{title}</span>
      </span>
    ) : (
      <button type="button" className="dl-crumb" onClick={() => onCrumb(i)}>
        <span title={title}>{title}</span>
      </button>
    );
  };
  const sep = (
    <span className="dl-sep" aria-hidden="true">
      {Icon.ChevronRight(16)}
    </span>
  );

  // [className, crumb index | "ellipsis"]
  const items: [string, number | "ellipsis"][] = collapsed
    ? [
        ["", 0],
        ["dl-li--fixed", "ellipsis"],
        ["dl-li--parent", last - 1],
        ["", last],
      ]
    : all.map((_, i) => ["", i]);

  return (
    <nav className="dl-crumbs" aria-label={T(t, "crumbs")} ref={navRef}>
      <ol>
        {items.map(([cls, what], k) => (
          <li key={what} className={cls || undefined}>
            {k > 0 && sep}
            {what === "ellipsis" ? (
              <button
                type="button"
                className="dl-crumb dl-crumb--ellipsis"
                aria-label={T(t, "crumbsHidden", { count: all.length - 3 })}
                onClick={() => setOpen(true)}
              >
                {Icon.Ellipsis(20)}
              </button>
            ) : (
              crumb(what)
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export interface FolderViewProps {
  readonly session: DlnaSession;
  readonly restoring: boolean;
  readonly focus: FocusTarget;
  readonly banner?: ReactNode;
  readonly notice?: ReactNode;
  readonly busyItemId: string | null;
  readonly busyLabel?: string;
  readonly renderRowAction: (item: DlnaItem, ctx: RowActionContext) => ReactNode;
  readonly onUp: () => void;
  readonly onServers: () => void;
  readonly onCrumb: (index: number) => void;
  readonly onOpenFolder: (item: DlnaItem) => void;
  /** The folder answered `gone` (or, while restoring a session, `offline`). */
  readonly onFail: (status: "gone" | "offline") => void;
  readonly onResolved: () => void;
  readonly onLive: (message: string) => void;
}

export function FolderView(p: FolderViewProps) {
  const { t } = useTranslation();
  const uniqueId = useId();
  const objectId = p.session.stack.at(-1)?.object_id ?? "0";
  const title = p.session.stack.at(-1)?.title ?? p.session.serverName;
  const { status, items, hasMore, loadingMore, loadMore, retry, cancel } = useDlnaBrowse(
    p.session.serverId,
    objectId
  );
  const [filter, setFilter] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const scrollRef = useRef<HTMLElement>(null);
  const moreRef = useRef<HTMLButtonElement>(null);
  const loading = status === "loading" || status === "slow";
  const { onFail, onResolved, onLive } = p;

  const findRow = (id: string) =>
    scrollRef.current?.querySelector<HTMLElement>(`[data-rid="${CSS.escape(id)}"]`);

  // Focus: heading after entering a folder, the left row after going up.
  const returnedRef = useRef(p.focus !== "heading" ? p.focus : null);
  useEffect(() => {
    if (p.focus === "heading") headingRef.current?.focus();
  }, [p.focus]);
  useEffect(() => {
    if (status !== "ready" || !returnedRef.current) return;
    (findRow(returnedRef.current) ?? headingRef.current)?.focus();
    returnedRef.current = null;
  }, [status, items]);

  // Focus after the user pressed "load more": the first new row, or the button when the page was empty.
  const focusFromRef = useRef<number | null>(null);
  useEffect(() => {
    if (loadingMore || focusFromRef.current === null) return;
    const first = items[focusFromRef.current];
    (first ? findRow(first.id) : moreRef.current)?.focus();
    focusFromRef.current = null;
  }, [loadingMore, items]);
  const onMore = () => {
    focusFromRef.current = items.length;
    loadMore();
  };

  useEffect(() => {
    if (status === "gone" || status === "offline") onFail(status);
    if (status === "ready") onResolved();
  }, [status, onFail, onResolved]);

  // Load the next page when the button scrolls into view (the button stays as the fallback).
  const canAutoLoad = status === "ready" && hasMore && !loadingMore;
  useEffect(() => {
    const el = moreRef.current;
    if (!canAutoLoad || !el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) loadMore();
      },
      { root: scrollRef.current, rootMargin: "0px 0px 80px 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [canAutoLoad, items.length, loadMore]);

  // Live region: loading, counts, new rows, errors.
  const lastCountRef = useRef(0);
  useEffect(() => {
    let message = "";
    if (loading) message = T(t, "loadingFolder");
    else if (status === "offline") message = T(t, "offlineTitle");
    else if (status === "timeout") message = T(t, "timeoutTitle");
    else if (status === "error") message = T(t, "netTitle");
    else if (loadingMore) message = T(t, "loadingMore");
    else if (status === "ready") {
      const added = items.length - lastCountRef.current;
      message =
        lastCountRef.current > 0 && added > 0
          ? T(t, "newRows", { count: added })
          : T(t, hasMore ? "loadedMore" : "loaded", { count: items.length });
      lastCountRef.current = items.length;
    }
    onLive(message);
  }, [loading, status, loadingMore, items.length, hasMore, t, onLive]);

  const needle = filter.trim().toLowerCase();
  const visible = needle ? items.filter((i) => i.title.toLowerCase().includes(needle)) : items;
  const ready = status === "ready";

  const filterBox = ready && (items.length > 0 || filter) && (
    <div>
      <div className="dl-filter">
        <input
          type="search"
          className="ui-input"
          placeholder={T(t, "filterPlaceholder")}
          aria-label={T(t, "filterLabel")}
          aria-describedby={`${uniqueId}-note`}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {filter && (
          <button
            type="button"
            className="btn btn-ghost btn-icon dl-filter-clear"
            aria-label={T(t, "filterClear")}
            onClick={() => setFilter("")}
          >
            {Icon.X(18)}
          </button>
        )}
      </div>
      <p className="dl-filter-note" id={`${uniqueId}-note`}>
        <span>
          {needle
            ? `${T(t, "filterCount", { shown: visible.length, loaded: items.length })}. `
            : ""}
          {T(t, hasMore ? "filterHintMore" : "filterHint")}
        </span>
        {hasMore && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={loadingMore}
            onClick={onMore}
          >
            {T(t, "loadMore")}
          </button>
        )}
      </p>
    </div>
  );

  const row = (item: DlnaItem, index: number) => {
    const busy = p.busyItemId === item.id;
    const meta = [item.artist, item.album, item.duration].filter(Boolean).join(" · ");
    const sub = busy ? p.busyLabel : item.is_container ? T(t, "folderHint") : meta;
    const info = (
      <span className="dl-info">
        <span className="dl-title" title={item.title}>
          {item.title}
        </span>
        {sub && (
          <span className="dl-sub" id={`${uniqueId}-h${index}`}>
            {sub}
          </span>
        )}
      </span>
    );
    const action = p.renderRowAction(item, { disabled: p.busyItemId !== null, busy });
    const cls = `dl-row${item.is_container ? "" : " dl-row--track"}${busy ? " dl-row--saving" : ""}`;
    if (item.is_container) {
      return (
        <li key={item.id} className={cls}>
          <button
            type="button"
            className="dl-open"
            data-rid={item.id}
            disabled={p.busyItemId !== null}
            aria-label={T(t, "openFolder", { title: item.title })}
            aria-describedby={`${uniqueId}-h${index}`}
            onClick={() => p.onOpenFolder(item)}
          >
            <Cover item={item} />
            {info}
            <span className="dl-chev" aria-hidden="true">
              {Icon.ChevronRight(20)}
            </span>
          </button>
          {action}
        </li>
      );
    }
    return (
      <li key={item.id} className={cls} data-rid={item.id} tabIndex={-1}>
        <div className="dl-open">
          <Cover item={item} />
          {info}
        </div>
        {action}
      </li>
    );
  };

  let body: ReactNode;
  if (loading) {
    body = (
      <>
        <Skeleton rows={6} />
        <Loading text={T(t, "loadingFolder")} />
        {status === "slow" && (
          <SlowBox
            text={T(t, "slowText")}
            onCancel={() => {
              cancel();
              p.onUp();
            }}
            onBack={p.onUp}
          />
        )}
      </>
    );
  } else if (status === "offline") {
    body = (
      <StateBlock
        icon={Icon.WifiOff(32)}
        title={T(t, "offlineTitle")}
        text={T(t, "offlineText", { name: p.session.serverName })}
      >
        <RetryButton onClick={retry} />
        <button type="button" className="btn btn-ghost" onClick={p.onServers}>
          {T(t, "backToServers")}
        </button>
      </StateBlock>
    );
  } else if (status === "timeout" || status === "error") {
    const timeout = status === "timeout";
    body = (
      <StateBlock
        icon={timeout ? Icon.Clock(32) : Icon.CircleX(32)}
        title={T(t, timeout ? "timeoutTitle" : "netTitle")}
        text={timeout ? T(t, "timeoutText", { name: p.session.serverName }) : T(t, "netText")}
      >
        <RetryButton onClick={retry} />
        <button type="button" className="btn btn-ghost" onClick={p.onUp}>
          {T(t, "back")}
        </button>
      </StateBlock>
    );
  } else if (status === "gone") {
    body = <Skeleton rows={6} />; // the parent moves up
  } else if (items.length === 0 && !hasMore) {
    body = (
      <StateBlock icon={Icon.Folder(32)} title={T(t, "emptyFolder")}>
        <button type="button" className="btn btn-outline" onClick={p.onUp}>
          {Icon.ArrowLeft(18)} {T(t, "back")}
        </button>
      </StateBlock>
    );
  } else {
    body = (
      <>
        <p className="dl-count">
          {T(t, hasMore ? "loadedMore" : "loaded", { count: items.length })}
        </p>
        {items.length === 0 && (
          <div className="dl-status">
            <span>{T(t, "shortPage")}</span>
          </div>
        )}
        {items.length > 0 && visible.length === 0 && (
          <div className="dl-status" role="status">
            <span>{T(t, "filterNone")}</span>
          </div>
        )}
        {visible.length > 0 && (
          <ul className="dl-list" aria-label={T(t, "folderList", { name: title })}>
            {visible.map(row)}
          </ul>
        )}
        {loadingMore && (
          <>
            <Skeleton rows={2} />
            <Loading text={T(t, "loadingMore")} />
          </>
        )}
        {!loadingMore && hasMore && (
          <div className="dl-more">
            <button type="button" className="btn btn-outline" ref={moreRef} onClick={onMore}>
              {T(t, "loadMore")}
            </button>
          </div>
        )}
        {!hasMore && <p className="dl-end">{T(t, "endOfList")}</p>}
      </>
    );
  }

  return (
    <>
      <div className="dl-top">
        <div className="dl-nav">
          <button
            type="button"
            className="btn btn-ghost btn-sm dl-back"
            title={T(t, "backTitle")}
            onClick={p.onUp}
          >
            {Icon.ArrowLeft(18)}
            <span>{T(t, "back")}</span>
          </button>
          <Crumbs session={p.session} onCrumb={p.onCrumb} />
        </div>
        {p.banner}
        {p.notice}
        {filterBox}
      </div>
      <section
        ref={scrollRef}
        className="dl-scroll"
        tabIndex={0} // NOSONAR(S6845): scrollable region must be keyboard-focusable (WCAG 2.1.1)
        aria-labelledby={`${uniqueId}-title`}
        aria-busy={loading || loadingMore || p.busyItemId !== null || undefined}
      >
        <div className="dl-head">
          <h3 className="dl-h" id={`${uniqueId}-title`} tabIndex={-1} ref={headingRef}>
            {title}
          </h3>
        </div>
        {body}
      </section>
    </>
  );
}
