import type { DlnaSession } from "./DlnaViews";

const KEY = "oct.dlna.session";

function isSession(value: unknown): value is DlnaSession {
  const s = value as DlnaSession | null;
  return (
    typeof s?.serverId === "string" &&
    typeof s.serverName === "string" &&
    Array.isArray(s.stack) &&
    s.stack.every((c) => typeof c?.object_id === "string" && typeof c.title === "string")
  );
}

/** The browser location of this browser session (nothing persists beyond it), or null. */
export function loadDlnaSession(): DlnaSession | null {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? "null");
    return isSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function storeDlnaSession(session: DlnaSession | null): void {
  try {
    if (session) sessionStorage.setItem(KEY, JSON.stringify(session));
    else sessionStorage.removeItem(KEY);
  } catch {
    // storage unavailable: the location is simply not remembered
  }
}
