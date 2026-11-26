import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import { isApiErrorInstance } from "../../api/types";
import type { DlnaItem } from "../../api/dlna";
import { useDlnaFolder, useDlnaObjectPath } from "../../hooks/useDlna";
import AlbumViewButton from "./AlbumViewButton";
import { getLastFolder, setLastFolder } from "./session";
import "./DlnaBrowser.css";

interface Props {
  serverId: string;
  serverName: string;
  startObjectId?: string;
  onSelect: (item: DlnaItem, parentId: string) => void;
  onPathChange?: (objectId: string) => void;
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
  onSelect,
  onPathChange,
}: Readonly<Props>) {
  const { t } = useTranslation();
  // Opens at startObjectId, else the folder remembered for this server, else the root.
  const [start, setStart] = useState(() => startObjectId ?? getLastFolder(serverId) ?? "0");
  // null = the start folder's ancestors are still being resolved
  const [stack, setStack] = useState<Crumb[] | null>(start === "0" ? [] : null);
  const [notice, setNotice] = useState(false);
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
  const objectId = path.at(-1)?.object_id ?? "0";
  const folder = useDlnaFolder(serverId, objectId);

  const go = (next: Crumb[]) => {
    setStack(next);
    setNotice(false);
    const id = next.at(-1)?.object_id ?? "0";
    setLastFolder(serverId, id);
    onPathChange?.(id);
  };

  const openFolder = (id: string) => {
    setStart(id);
    setStack(null);
    setNotice(false);
    setLastFolder(serverId, id);
    onPathChange?.(id);
  };

  const code = isApiErrorInstance(folder.error) ? folder.error.code : undefined;
  const pathGone =
    isApiErrorInstance(startPath.error) && startPath.error.code === "dlna_object_not_found";
  const gone = pathGone || (code === "dlna_object_not_found" && objectId !== "0");
  useEffect(() => {
    if (!gone) return;
    setStack([]);
    setNotice(true);
    setLastFolder(serverId, "0");
    onPathChange?.("0");
  }, [gone, serverId, onPathChange]);

  // A library change between pages can repeat an item; the id keeps it once.
  const items = new Map<string, DlnaItem>();
  for (const page of folder.data?.pages ?? []) for (const it of page.items) items.set(it.id, it);
  const list = [...items.values()];

  const crumbs = [{ object_id: "0", title: serverName }, ...path];
  return (
    <div className="dlb">
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
          <button
            key={crumbs
              .slice(0, i + 1)
              .map((x) => x.object_id)
              .join("/")}
            type="button"
            className="btn btn-ghost"
            aria-current={i === crumbs.length - 1 ? "location" : undefined}
            disabled={i === crumbs.length - 1}
            onClick={() => go(path.slice(0, i))}
          >
            {c.title}
          </button>
        ))}
      </nav>
      <AlbumViewButton serverId={serverId} onOpen={openFolder} />
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
      {(folder.isLoading || startPath.isLoading) && (
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
        <ul className="dlb-list">
          {list.map((item) => (
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
                  {item.title}
                  {item.artist && <small> {item.artist}</small>}
                </span>
              )}
              <button
                type="button"
                className="btn btn-secondary"
                aria-label={t("dlna.browser.selectLabel", { title: item.title })}
                onClick={() => onSelect(item, objectId)}
              >
                {t("dlna.browser.select")}
              </button>
            </li>
          ))}
        </ul>
      )}
      {folder.hasNextPage && (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={folder.isFetchingNextPage}
          onClick={() => void folder.fetchNextPage()}
        >
          {t("dlna.browser.loadMore")}
        </button>
      )}
    </div>
  );
}
