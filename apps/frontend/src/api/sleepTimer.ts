/**
 * Sleep timer API client (per device)
 */

import type { components } from "./generated/schema";
import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export type SleepTimerStatus = components["schemas"]["SleepTimerStatus"];
export type SleepTimerInput = components["schemas"]["SleepTimerRequest"];
export type EndAction = SleepTimerInput["end_action"];

const url = (deviceId: string) =>
  `${API_BASE_URL}/api/devices/${encodeURIComponent(deviceId)}/sleep-timer`;

export async function getSleepTimer(deviceId: string): Promise<SleepTimerStatus> {
  const response = await fetch(url(deviceId));
  await throwIfNotOk(response, "Failed to load the sleep timer");
  return response.json() as Promise<SleepTimerStatus>;
}

export async function startSleepTimer(
  deviceId: string,
  input: SleepTimerInput
): Promise<SleepTimerStatus> {
  const response = await fetch(url(deviceId), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  await throwIfNotOk(response, "Failed to start the sleep timer");
  return response.json() as Promise<SleepTimerStatus>;
}

export async function cancelSleepTimer(deviceId: string): Promise<void> {
  const response = await fetch(url(deviceId), { method: "DELETE" });
  await throwIfNotOk(response, "Failed to cancel the sleep timer");
}
