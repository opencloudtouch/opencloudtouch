/**
 * DLNA media server API client.
 * Contract: /api/dlna/* and /api/presets/dlna (see apps/backend/openapi.yaml)
 */

import type { components } from "./generated/schema";
import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

type Schemas = components["schemas"];
export type DlnaItem = Schemas["DlnaItem"];
export type DlnaBrowsePage = Schemas["DlnaBrowseResponse"];
export type DlnaObjectPath = Schemas["DlnaObjectPath"];
export type NativeServer = Schemas["NativeServer"];
export type NativeServerList = Schemas["NativeServerList"];
export type DlnaPresetRequest = Schemas["PresetDlnaRequest"];
export type PresetResponse = Schemas["PresetResponse"];

export const DLNA_PAGE_SIZE = 50;

const serverUrl = (serverId: string) =>
  `${API_BASE_URL}/api/dlna/servers/${encodeURIComponent(serverId)}`;
const nativeUrl = (deviceId: string, serverId: string) =>
  `${API_BASE_URL}/api/dlna/native/${encodeURIComponent(deviceId)}/servers/${encodeURIComponent(serverId)}`;

export async function getDlnaServers(signal?: AbortSignal): Promise<Record<string, unknown>[]> {
  const response = await fetch(`${API_BASE_URL}/api/dlna/servers`, { signal });
  await throwIfNotOk(response, "Failed to list media servers");
  return response.json();
}

/** One page of a folder (objectId "0" is the root); has_more drives paging. */
export async function browseDlna(
  serverId: string,
  objectId: string,
  startingIndex: number,
  requestedCount = DLNA_PAGE_SIZE,
  signal?: AbortSignal
): Promise<DlnaBrowsePage> {
  const query = new URLSearchParams({
    object_id: objectId,
    starting_index: String(startingIndex),
    requested_count: String(requestedCount),
  });
  const response = await fetch(`${serverUrl(serverId)}/browse?${query}`, { signal });
  await throwIfNotOk(response, "Failed to browse media server");
  return response.json();
}

export async function getDlnaObjectPath(
  serverId: string,
  objectId: string,
  signal?: AbortSignal
): Promise<DlnaObjectPath> {
  const response = await fetch(
    `${serverUrl(serverId)}/objects/path?${new URLSearchParams({ object_id: objectId })}`,
    { signal }
  );
  await throwIfNotOk(response, "Failed to resolve media server path");
  return response.json();
}

export async function getAlbumRoot(serverId: string, signal?: AbortSignal): Promise<string | null> {
  const response = await fetch(`${serverUrl(serverId)}/album-root`, { signal });
  await throwIfNotOk(response, "Failed to load album root");
  const body: Schemas["DlnaAlbumRoot"] = await response.json();
  return body.object_id;
}

export async function getFirstChildAudio(
  serverId: string,
  objectId: string,
  signal?: AbortSignal
): Promise<boolean> {
  const response = await fetch(
    `${serverUrl(serverId)}/first-child-audio?${new URLSearchParams({ object_id: objectId })}`,
    { signal }
  );
  await throwIfNotOk(response, "Failed to check folder content");
  const body: Schemas["FirstChildAudio"] = await response.json();
  return body.first_child_is_audio;
}

/** Live server states plus the speaker's migration state (migration_failed disables enable). */
export async function getNativeServers(
  deviceId: string,
  signal?: AbortSignal
): Promise<NativeServerList> {
  const response = await fetch(
    `${API_BASE_URL}/api/dlna/native?${new URLSearchParams({ device_id: deviceId })}`,
    { signal }
  );
  await throwIfNotOk(response, "Failed to load media server state");
  return response.json();
}

export async function enableNativeServer(
  deviceId: string,
  serverId: string
): Promise<NativeServer> {
  const response = await fetch(nativeUrl(deviceId, serverId), { method: "PUT" });
  await throwIfNotOk(response, "Failed to set up media server");
  return response.json();
}

/** Without force, 409 dlna_native_slots_affected carries extra.slots; force removes anyway. */
export async function disableNativeServer(
  deviceId: string,
  serverId: string,
  force: boolean
): Promise<void> {
  const response = await fetch(`${nativeUrl(deviceId, serverId)}?force=${force}`, {
    method: "DELETE",
  });
  await throwIfNotOk(response, "Failed to remove media server");
}

/** 409 dlna_folder_no_audio_first carries extra.title; resend with confirm: true to save anyway. */
export async function saveDlnaPreset(
  request: Omit<DlnaPresetRequest, "confirm"> & { confirm?: boolean }
): Promise<PresetResponse> {
  const response = await fetch(`${API_BASE_URL}/api/presets/dlna`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  await throwIfNotOk(response, "Failed to save media preset");
  return response.json();
}
