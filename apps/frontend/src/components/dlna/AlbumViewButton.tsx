import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import { getAlbumRoot } from "../../api/dlna";

interface Props {
  serverId: string;
  onOpen: (objectId: string) => void;
}

/** Jumps to the server's album folder; looked up on click only, hidden when the server has none. */
export default function AlbumViewButton({ serverId, onOpen }: Readonly<Props>) {
  const { t } = useTranslation();
  const [none, setNone] = useState(false);
  const [busy, setBusy] = useState(false);
  if (none) return null;

  const press = async () => {
    setBusy(true);
    try {
      const id = await getAlbumRoot(serverId);
      if (id === null) setNone(true);
      else onOpen(id);
    } catch {
      // lookup failed: the button stays, the user can press it again
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      className="btn btn-ghost"
      disabled={busy}
      aria-busy={busy}
      onClick={() => void press()}
    >
      {busy ? <span className="spinner-small" aria-hidden="true" /> : Icon.Folder(18)}{" "}
      {t("dlna.album.open")}
    </button>
  );
}
