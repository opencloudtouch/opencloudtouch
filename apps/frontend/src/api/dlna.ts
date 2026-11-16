/**
 * API service for DLNA media servers: discovery and paged browsing.
 * The preset call lives in presets.ts (`setDlnaPreset`).
 */

import type { components } from "./generated/schema";
import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export type DlnaItem = components["schemas"]["DlnaItem"];
export type DlnaBrowsePage = components["schemas"]["DlnaBrowseResponse"];
export type NativeServer = components["schemas"]["NativeServer"];
export type NativeSlot = components["schemas"]["NativeSlot"];
export type NativeState = components["schemas"]["NativeState"];

/** Setting up lists the server and may re-pair the speaker once: allow well over the usual 15 s. */
const NATIVE_SETUP_TIMEOUT_MS = 30000;

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

const nativeUrl = (deviceId: string, serverId: string) =>
  `${API_BASE_URL}/api/dlna/native/${encodeURIComponent(deviceId)}/servers/${encodeURIComponent(serverId)}`;

/** Media servers with their setup state on one speaker (503 `device_unreachable` = speaker unreadable). */
export async function getNativeServers(
  deviceId: string,
  signal?: AbortSignal
): Promise<NativeServer[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/dlna/native?${new URLSearchParams({ device_id: deviceId })}`,
    { signal }
  );
  await throwIfNotOk(response, "Failed to load media server state");
  return ((await response.json()) as components["schemas"]["NativeServerList"]).servers;
}

/** Set a server up on the speaker; the answer carries the state that must be evaluated. */
export async function enableNativeServer(deviceId: string, serverId: string): Promise<NativeState> {
  const response = await fetch(nativeUrl(deviceId, serverId), {
    method: "PUT",
    signal: AbortSignal.timeout(NATIVE_SETUP_TIMEOUT_MS),
  });
  await throwIfNotOk(response, "Failed to set up media server");
  return ((await response.json()) as components["schemas"]["NativeEnableResponse"]).state;
}

/** Presets that a forced removal of this server would switch. */
export async function getNativeSlots(deviceId: string, serverId: string): Promise<NativeSlot[]> {
  const response = await fetch(`${nativeUrl(deviceId, serverId)}/presets`);
  await throwIfNotOk(response, "Failed to load affected presets");
  return ((await response.json()) as components["schemas"]["NativeSlotList"]).slots;
}

/** Remove the server from the speaker; without `force` presets in use answer 409 `dlna_native_in_use`. */
export async function disableNativeServer(
  deviceId: string,
  serverId: string,
  force: boolean
): Promise<void> {
  const response = await fetch(`${nativeUrl(deviceId, serverId)}${force ? "?force=true" : ""}`, {
    method: "DELETE",
  });
  await throwIfNotOk(response, "Failed to remove media server");
}
