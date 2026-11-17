import { getDlnaObjectPath, getDlnaServers } from "../../api/dlna";
import { ApiError } from "../../api/types";
import type { DlnaNotice, DlnaSession } from "./DlnaBrowser";
import { storeDlnaSession } from "./session";

export interface DlnaPrefill {
  focus: string | null;
  notice: DlnaNotice | null;
}

const SERVER_GONE: DlnaPrefill = { focus: null, notice: { key: "editServerGone" } };

/**
 * Resolves where the DLNA browser opens for a saved preset and writes that location to the browser
 * session (the only persistence); the pane must be mounted afterwards because it reads it once.
 * A late answer after `signal` aborted writes nothing (rejects with the abort error).
 */
export async function resolveDlnaPrefill(
  ref: { server_id: string; object_id: string } | null,
  signal: AbortSignal
): Promise<DlnaPrefill> {
  if (!ref) {
    storeDlnaSession(null);
    return { focus: null, notice: null };
  }
  const done = (session: DlnaSession | null, prefill: DlnaPrefill) => {
    signal.throwIfAborted();
    storeDlnaSession(session);
    return prefill;
  };

  try {
    const path = await getDlnaObjectPath(ref.server_id, ref.object_id, signal);
    return done(
      { serverId: ref.server_id, serverName: path.server_name, stack: path.path },
      { focus: ref.object_id, notice: null }
    );
  } catch (err) {
    signal.throwIfAborted();
    // not an API answer (network) or an unknown server: nothing to show but the server list
    if (!(err instanceof ApiError) || err.code === "dlna_server_not_found") {
      return done(null, SERVER_GONE);
    }
    const servers = await getDlnaServers(signal).catch(() => []);
    const server = servers.find((s) => s.id === ref.server_id);
    if (!server) return done(null, SERVER_GONE);
    const key = err.code === "dlna_object_not_found" ? "editFolderGone" : "editPathFailed";
    return done(
      { serverId: server.id, serverName: server.name, stack: [] },
      { focus: null, notice: { key, vars: { server: server.name } } }
    );
  }
}
