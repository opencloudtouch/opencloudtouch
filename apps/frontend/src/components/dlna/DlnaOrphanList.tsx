import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";
import DlnaRemoveDialog from "./DlnaRemoveDialog";
import type { DlnaSetupApi } from "./dlnaSetupTypes";

/** Registrations whose media server is no longer found (server_known = false). An empty list renders nothing. */
export default function DlnaOrphanList({ api }: Readonly<{ api: DlnaSetupApi }>) {
  const { t } = useTranslation();
  const [sel, setSel] = useState<{ id: string; name: string } | null>(null);
  const orphans = (api.servers ?? []).filter((s) => !s.server_known);
  if (!orphans.length) return null;
  return (
    <section className="nd-orph" aria-labelledby="nd-orph-h">
      <h4 className="nd-orph-title" id="nd-orph-h">
        {t("presets.dlna.remove.orphanTitle")}
      </h4>
      <p className="nd-orph-text">{t("presets.dlna.remove.orphanText")}</p>
      <ul className="dl-list" aria-label={t("presets.dlna.remove.orphanList")}>
        {orphans.map((o) => (
          <li key={o.server_id} className="nd-orph-row">
            <span className="nd-orph-name">
              <span className="dl-srv-ico" aria-hidden="true">
                {Icon.Server(22)}
              </span>
              <span>{o.name}</span>
            </span>
            <button
              type="button"
              className="btn btn-outline"
              aria-label={t("presets.dlna.remove.actionLabel", { name: o.name })}
              onClick={() => setSel({ id: o.server_id, name: o.name })}
            >
              {t("presets.dlna.remove.action")}
            </button>
          </li>
        ))}
      </ul>
      {sel && (
        <DlnaRemoveDialog
          api={api}
          serverId={sel.id}
          serverName={sel.name}
          onClose={() => setSel(null)}
        />
      )}
    </section>
  );
}
