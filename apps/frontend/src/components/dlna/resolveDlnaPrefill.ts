import { getDlnaObjectPath, getNativeServers } from "../../api/dlna";
import { isApiErrorInstance } from "../../api/types";

export interface DlnaPrefill {
  server: { id: string; name: string } | null;
  /** Folder the browser opens at: the PARENT of the saved object. */
  startObjectId?: string;
  focusId?: string;
  notice?: "serverGone" | "objectGone";
}

/** Where the DLNA tab opens for a saved preset; never a dead end (server root or server list). */
export async function resolveDlnaPrefill(
  deviceId: string,
  preset: { source_account?: string | null; station_url?: string },
  signal: AbortSignal
): Promise<DlnaPrefill> {
  // Speaker location: "<objectId>" for folders, "<objectId> TRACK" for tracks; account "<serverId>/0".
  const serverId = (preset.source_account ?? "").replace(/\/0$/, "");
  const objectId = (preset.station_url ?? "").replace(/ TRACK$/, "");
  try {
    const path = await getDlnaObjectPath(serverId, objectId, signal);
    return {
      server: { id: serverId, name: path.server_name },
      startObjectId: path.path.at(-1)?.object_id ?? "0",
      focusId: objectId,
    };
  } catch (err) {
    const code = isApiErrorInstance(err) ? err.code : undefined;
    if (code === "dlna_object_not_found") {
      const list = await getNativeServers(deviceId, signal).catch(() => null);
      const server = list?.servers.find((s) => s.server_id === serverId);
      if (server) {
        return {
          server: { id: serverId, name: server.name },
          startObjectId: "0",
          notice: "objectGone",
        };
      }
    }
    return {
      server: null,
      notice:
        code === "dlna_server_not_found" || code === "dlna_object_not_found"
          ? "serverGone"
          : undefined,
    };
  }
}
