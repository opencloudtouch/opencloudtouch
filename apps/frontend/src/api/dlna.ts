/**
 * API service for DLNA media servers: discovery and paged browsing.
 * The preset call lives in presets.ts (`setDlnaPreset`).
 */

import type { components } from "./generated/schema";
import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export type DlnaItem = components["schemas"]["DlnaItem"];
export type DlnaBrowsePage = components["schemas"]["DlnaBrowseResponse"];

/** The part of a discovered server the UI needs; addresses (location, control URL) are never exposed. */
export interface DlnaServer {
  id: string;
  name: string;
}

/** Page size requested from the backend; a shorter page does not mean the end of the list. */
export const DLNA_PAGE_SIZE = 50;

/**
 * List DLNA media servers. Known servers come back at once while the backend rescans; with
 * `refresh` the answer waits for a fresh network scan (can take seconds).
 */
export async function getDlnaServers(signal?: AbortSignal, refresh = false): Promise<DlnaServer[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/dlna/servers${refresh ? "?refresh=true" : ""}`,
    {
      signal,
    }
  );
  await throwIfNotOk(response, "Failed to discover media servers");

  const data: Record<string, unknown>[] = await response.json();
  return data.flatMap((s) =>
    typeof s.id === "string" && typeof s.name === "string" ? [{ id: s.id, name: s.name }] : []
  );
}

/** Browse one page of a folder (`objectId` "0" is the server root). */
export async function browseDlna(
  serverId: string,
  objectId: string,
  startingIndex: number,
  signal?: AbortSignal
): Promise<DlnaBrowsePage> {
  const query = new URLSearchParams({
    object_id: objectId,
    starting_index: String(startingIndex),
    requested_count: String(DLNA_PAGE_SIZE),
  });
  const response = await fetch(
    `${API_BASE_URL}/api/dlna/servers/${encodeURIComponent(serverId)}/browse?${query}`,
    { signal }
  );
  await throwIfNotOk(response, "Failed to browse media server");

  return response.json();
}
