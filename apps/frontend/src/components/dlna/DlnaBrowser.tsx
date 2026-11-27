import { Fragment, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import { isApiErrorInstance } from "../../api/types";
import type { DlnaItem } from "../../api/dlna";
import { useDlnaFolder, useDlnaObjectPath } from "../../hooks/useDlna";
import AlbumViewButton from "./AlbumViewButton";
import "./DlnaBrowser.css";

interface Props {
  serverId: string;
  serverName: string;
  startObjectId?: string;
  /** Row that gets keyboard focus and is centred on arrival (the saved object when editing). */
  focusObjectId?: string;
  /** index: the item's 0-based position in the folder; absent for the open folder itself. */
  onSelect: (item: DlnaItem, parentId: string, index?: number) => void;
  onPathChange?: (objectId: string) => void;
  /** Disables the select buttons while the parent saves a selection. */
  busy?: boolean;
}

interface Crumb {
  object_id: string;
  title: string;
}

const ERROR_KEY: Record<string, string> = {
  dlna_server_not_found: "serverNotFound",
  dlna_server_timeout: "serverTimeout",
};

function Cover({ url }: Readonly<{ url?: string | null }>) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) return <span className="dlb-cover dlb-cover--icon">{Icon.Music(20)}</span>;
  return (
    <img className="dlb-cover" src={url} alt="" loading="lazy" onError={() => setFailed(true)} />
  );
}

/** Folder-by-folder browser of one media server; the parent decides what "select" means. */
export default function DlnaBrowser({
  serverId,
  serverName,
  startObjectId,
  focusObjectId,
  onSelect,
  onPathChange,
  busy = false,
}: Readonly<Props>) {
  const { t } = useTranslation();
  // Opens at startObjectId (editing a saved preset), else at the root.
  const [start, setStart] = useState(startObjectId ?? "0");
  // null = the start folder's ancestors are still being resolved
  const [stack, setStack] = useState<Crumb[] | null>(start === "0" ? [] : null);
  const [notice, setNotice] = useState(false);
  // A pending album lookup is the latest action: the folder's loading state hides meanwhile.
  const [albumBusy, setAlbumBusy] = useState(false);
  // The saved object on arrival, after going up the folder the user came from.
  const [focusId, setFocusId] = useState(focusObjectId);
  const startPath = useDlnaObjectPath(serverId, stack === null ? start : undefined);
  // The API path lists the ancestors only; the start folder itself is the last crumb.
  const path =
    stack ??
    (startPath.data
      ? [
          ...startPath.data.path,
          { object_id: startPath.data.object_id, title: startPath.data.title },
        ]
      : []);
  // The start folder is browsed while its ancestors resolve: the root never shows in between.
  const objectId = stack ? (stack.at(-1)?.object_id ?? "0") : start;
  const folder = useDlnaFolder(serverId, objectId);
  // The previous folder stays visible but inert until the new one answers.
  const stale = folder.isPlaceholderData;
  const hasNextPage = folder.hasNextPage && !stale;
  const { isFetchingNextPage, fetchNextPage } = folder;
  // A failed next page stops the auto-load: the button below retries it on demand.
  const pageFailed = folder.isFetchNextPageError;
  const [filter, setFilter] = useState("");
  const [filterFolder, setFilterFolder] = useState(objectId);
  // Cleared once the next folder shows: the dimmed previous list keeps its filter meanwhile.
  if (!stale && filterFolder !== objectId) {
    setFilterFolder(objectId);
    setFilter("");
  }
  const needle = filter.trim().toLowerCase();
  // The filter covers the whole folder: every remaining page loads; a failed one stops it.
  useEffect(() => {
    if (needle && hasNextPage && !isFetchingNextPage && !pageFailed) void fetchNextPage();
  }, [needle, hasNextPage, isFetchingNextPage, pageFailed, fetchNextPage]);
  const sentinelRef = useRef<HTMLDivElement>(null);
  // Old browsers and jsdom lack the observer: they keep the "Load more" button.
  const canObserve = typeof IntersectionObserver !== "undefined";
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !canObserve || !hasNextPage || isFetchingNextPage || pageFailed) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) void fetchNextPage();
      },
      { rootMargin: "200px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [canObserve, hasNextPage, isFetchingNextPage, pageFailed, fetchNextPage]);

  const rootRef = useRef<HTMLDivElement>(null);
  // Going down starts the next folder at the top, once its first page replaces the dimmed list.
  const toTopRef = useRef(false);
  useLayoutEffect(() => {
    if (stale || !folder.data || !toTopRef.current) return;
    toTopRef.current = false;
    let el = rootRef.current?.parentElement;
    while (el && !/auto|scroll/.test(getComputedStyle(el).overflowY)) el = el.parentElement;
    if (el) el.scrollTop = 0;
  }, [stale, folder.data]);

  // Going up focuses the folder the way back started from; going down focuses nothing.
  const go = (next: Crumb[]) => {
    const back = path[next.length]?.object_id;
    setStack(next);
    setNotice(false);
    setFocusId(back);
    toTopRef.current = !back;
    onPathChange?.(next.at(-1)?.object_id ?? "0");
  };

  // A folder with an unknown breadcrumb (the album view): its ancestors are resolved.
  const openFolder = (id: string) => {
    setStart(id);
    setStack(null);
    setNotice(false);
    setFocusId(undefined);
    toTopRef.current = true;
    onPathChange?.(id);
  };

  // Stable, so it runs once when the row mounts, not on every render.
  const focusRow = useCallback((el: HTMLButtonElement | null) => {
    el?.focus({ preventScroll: true });
    el?.scrollIntoView({ block: "center" });
  }, []);

  const code = isApiErrorInstance(folder.error) ? folder.error.code : undefined;
  const pathGone =
    isApiErrorInstance(startPath.error) && startPath.error.code === "dlna_object_not_found";
  const gone = pathGone || (code === "dlna_object_not_found" && objectId !== "0");
  useEffect(() => {
    if (!gone) return;
    setStack([]);
    setNotice(true);
    onPathChange?.("0");
  }, [gone, onPathChange]);

  // A library change between pages can repeat an item; the id keeps it once.
  const items = new Map<string, DlnaItem>();
  for (const page of folder.data?.pages ?? []) for (const it of page.items) items.set(it.id, it);
  const list = [...items.values()];
  const shown = needle
    ? list.filter((it) => [it.title, it.artist].some((v) => v?.toLowerCase().includes(needle)))
    : list;

  const crumbs = [{ object_id: "0", title: serverName }, ...path];
  // A folder with tracks can be saved itself, without going back up to its parent.
  const current = path.at(-1);
  const wholeFolder =
    current && current.object_id === objectId && !stale && !needle
      ? list.find((it) => !it.is_container)
      : undefined;
  const contentsId = useId();
  return (
    <div className="dlb" ref={rootRef}>
      <nav className="dlb-crumbs" aria-label={t("dlna.browser.breadcrumb")}>
        {path.length > 0 && (
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            aria-label={t("dlna.browser.up")}
            onClick={() => go(path.slice(0, -1))}
          >
            {Icon.ArrowLeft(18)}
          </button>
        )}
        {crumbs.map((c, i) => (
          <Fragment
            key={crumbs
              .slice(0, i + 1)
              .map((x) => x.object_id)
              .join("/")}
          >
            {i > 0 && (
              <span className="dlb-sep" aria-hidden="true">
                {Icon.ChevronRight(14)}
              </span>
            )}
            {i === crumbs.length - 1 ? (
              <span className="dlb-crumb dlb-crumb--current" aria-current="location">
                {c.title}
              </span>
            ) : (
              <button type="button" className="dlb-crumb" onClick={() => go(path.slice(0, i))}>
                {c.title}
              </button>
            )}
          </Fragment>
        ))}
      </nav>
      <AlbumViewButton
        serverId={serverId}
        onOpen={openFolder}
        folderId={objectId}
        onBusyChange={setAlbumBusy}
      />
      {notice && (
        <div className="wz-status wz-status--warning" role="status">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Info(18)}
          </span>
          <div className="wz-status-body">
            <p className="wz-status-text">{t("dlna.browser.objectGone")}</p>
          </div>
        </div>
      )}
      {(folder.isLoading || startPath.isLoading) && !albumBusy && (
        <div className="dlb-loading" role="status" aria-busy="true">
          <span className="spinner-small" aria-hidden="true" /> {t("dlna.browser.loading")}
        </div>
      )}
      {folder.isError && !folder.data && !gone && (
        <div className="wz-status wz-status--error" role="alert">
          <div className="wz-status-body">
            <span className="wz-status-title">
              {t(`dlna.browser.${(code && ERROR_KEY[code]) || "error"}`)}
            </span>
          </div>
          <button type="button" className="btn btn-secondary" onClick={() => void folder.refetch()}>
            {t("dlna.browser.retry")}
          </button>
        </div>
      )}
      {folder.data && list.length === 0 && <p className="dlb-empty">{t("dlna.browser.empty")}</p>}
      {list.length > 0 && (
        <input
          type="search"
          className="ui-input"
          placeholder={t("dlna.browser.filterLabel")}
          aria-label={t("dlna.browser.filterLabel")}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      )}
      {current && wholeFolder && (
        <div className="dlb-row dlb-row--folder">
          <Cover url={wholeFolder.album_art_url} />
          <span className="dlb-title">
            <span className="dlb-line">{current.title}</span>
            <small className="dlb-line dlb-artist">{t("dlna.browser.wholeFolder")}</small>
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            aria-label={t("dlna.browser.selectFolderLabel", { title: current.title })}
            disabled={busy}
            onClick={() =>
              onSelect(
                {
                  id: current.object_id,
                  parent_id: path.at(-2)?.object_id ?? "0",
                  title: current.title,
                  is_container: true,
                  album_art_url: wholeFolder.album_art_url,
                },
                path.at(-2)?.object_id ?? "0"
              )
            }
          >
            {t("dlna.browser.select")}
          </button>
        </div>
      )}
      {current && wholeFolder && (
        <span id={contentsId} className="dlb-section">
          {t("dlna.browser.folderContents")}
        </span>
      )}
      {list.length > 0 && shown.length === 0 && (!hasNextPage || pageFailed) && (
        <p className="dlb-empty" role="status">
          {t("dlna.browser.noMatches")}
        </p>
      )}
      {stale && !albumBusy && (
        <div className="dlb-loading" role="status" aria-live="polite">
          <span className="spinner-small" aria-hidden="true" /> {t("dlna.browser.loading")}
        </div>
      )}
      {shown.length > 0 && (
        <ul
          className={`dlb-list${stale ? " dlb-list--stale" : ""}`}
          inert={stale}
          aria-labelledby={wholeFolder ? contentsId : undefined}
        >
          {shown.map((item) => (
            <li key={item.id} className="dlb-row">
              <Cover url={item.album_art_url} />
              {item.is_container ? (
                <button
                  type="button"
                  className="btn btn-ghost dlb-title"
                  aria-label={t("dlna.browser.openLabel", { title: item.title })}
                  onClick={() => go([...path, { object_id: item.id, title: item.title }])}
                >
                  {Icon.Folder(18)} {item.title}
                </button>
              ) : (
                <span className="dlb-title">
                  <span className="dlb-line">{item.title}</span>
                  {item.artist && <small className="dlb-line dlb-artist">{item.artist}</small>}
                </span>
              )}
              <button
                type="button"
                className="btn btn-secondary"
                aria-label={t("dlna.browser.selectLabel", { title: item.title })}
                ref={item.id === focusId ? focusRow : undefined}
                disabled={busy}
                onClick={() => onSelect(item, objectId, list.indexOf(item))}
              >
                {t("dlna.browser.select")}
              </button>
            </li>
          ))}
        </ul>
      )}
      {isFetchingNextPage && (
        <div className="dlb-loading" role="status" aria-live="polite">
          <span className="spinner-small" aria-hidden="true" /> {t("dlna.browser.loading")}
        </div>
      )}
      {pageFailed && (
        <p className="ui-small" role="alert">
          {t(`dlna.browser.${(code && ERROR_KEY[code]) || "error"}`)}
        </p>
      )}
      {hasNextPage &&
        (canObserve && !pageFailed ? (
          <div ref={sentinelRef} aria-hidden="true" />
        ) : (
          <button
            type="button"
            className="btn btn-secondary"
            disabled={isFetchingNextPage}
            onClick={() => void fetchNextPage()}
          >
            {t("dlna.browser.loadMore")}
          </button>
        ))}
    </div>
  );
}
