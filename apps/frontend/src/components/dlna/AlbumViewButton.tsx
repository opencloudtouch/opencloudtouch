import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import { getAlbumRoot } from "../../api/dlna";

interface Props {
  serverId: string;
  onOpen: (objectId: string) => void;
  /** The browser's current folder: a navigation to another one cancels a pending lookup. */
  folderId: string;
  onBusyChange?: (busy: boolean) => void;
}

/** Jumps to the server's album folder; looked up on click only, hidden when the server has none. */
export default function AlbumViewButton({
  serverId,
  onOpen,
  folderId,
  onBusyChange,
}: Readonly<Props>) {
  const { t } = useTranslation();
  const [none, setNone] = useState(false);
  const [pending, setPending] = useState<AbortController | null>(null);
  const busy = pending !== null;
  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange]);
  // The last action wins: another navigation (or unmount) aborts the lookup.
  useEffect(() => () => pending?.abort(), [pending, folderId]);
  if (none) return null;

  const press = async () => {
    const lookup = new AbortController();
    const done = () => setPending((p) => (p === lookup ? null : p));
    lookup.signal.addEventListener("abort", done);
    setPending(lookup);
    try {
      const id = await getAlbumRoot(serverId, lookup.signal);
      if (lookup.signal.aborted) return;
      if (id === null) setNone(true);
      else onOpen(id);
    } catch {
      // lookup failed or was cancelled: the button stays, the user can press it again
    } finally {
      done();
    }
  };

  return (
    <button
      type="button"
      className="btn btn-ghost rs-album"
      disabled={busy}
      aria-busy={busy}
      onClick={() => void press()}
    >
      {busy ? <span className="spinner-small" aria-hidden="true" /> : Icon.Folder(18)}
      <span className="dlb-lbl">{t("dlna.album.open")}</span>
    </button>
  );
}
