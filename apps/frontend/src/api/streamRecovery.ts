/**
 * Stream recovery API client: watchdog settings and activity log
 */

import type { components } from "./generated/schema";
import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export type StreamRecoveryConfig = components["schemas"]["StreamRecoveryConfigResponse"];
export type StreamRecoveryEvent = components["schemas"]["StreamRecoveryEventItem"];

/** Body of the full-replacement PUT. */
export interface StreamRecoveryConfigInput {
  enabled: boolean;
  min_play_seconds: number;
  max_attempts_per_hour: number;
}

export async function getStreamRecovery(): Promise<StreamRecoveryConfig> {
  const response = await fetch(`${API_BASE_URL}/api/stream-recovery`);
  await throwIfNotOk(response, "Failed to load stream recovery settings");
  return response.json() as Promise<StreamRecoveryConfig>;
}

export async function putStreamRecovery(
  input: StreamRecoveryConfigInput
): Promise<StreamRecoveryConfig> {
  const response = await fetch(`${API_BASE_URL}/api/stream-recovery`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  await throwIfNotOk(response, "Failed to save stream recovery settings");
  return response.json() as Promise<StreamRecoveryConfig>;
}

export async function getStreamRecoveryEvents(limit = 20): Promise<StreamRecoveryEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/stream-recovery/events?limit=${limit}`);
  await throwIfNotOk(response, "Failed to load stream recovery activity");
  const data = (await response.json()) as components["schemas"]["StreamRecoveryEventsResponse"];
  return data.events;
}
