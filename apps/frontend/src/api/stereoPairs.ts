/**
 * Stereo Pair API Client
 * Contract: /api/stereo-pairs (see apps/backend/openapi.yaml)
 */

import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

// ---- Types ----

export type StereoRole = "LEFT" | "RIGHT";
export type IneligibleReason =
  | "not_capable"
  | "not_provisioned"
  | "offline"
  | "in_zone"
  | "in_pair"
  | null;

/** Additions to the device list entry (`api/devices.ts`, interface Device). */
export interface DeviceStereoInfo {
  stereo_capable: boolean;
  oct_provisioned: boolean;
  stereo_ineligible_reason: IneligibleReason;
  stereo_pair_id: number | null;
  stereo_role: StereoRole | null;
  stereo_master: boolean;
  /** name of the other speaker of the pair, null outside a pair */
  stereo_partner_name: string | null;
  /** name of the LEFT (main) speaker of the pair, null outside a pair */
  stereo_master_name: string | null;
  /** name of the pair, null outside a pair */
  stereo_pair_name: string | null;
  /** firmware of the speaker, needed for the mismatch warning before the pair exists */
  firmware?: string;
}

export interface StereoPairMember {
  device_id: string;
  name: string;
  role: StereoRole;
  reachable: boolean;
}

export interface StereoPair {
  id: number;
  name: string;
  status: "creating" | "active" | "degraded";
  source: "oct" | "device";
  members: StereoPairMember[];
  warnings: string[];
}

export type OperationStepKey = "preflight" | "create_left" | "create_right" | "verify";
export interface OperationStep {
  key: OperationStepKey;
  state: "waiting" | "running" | "done" | "failed";
}

export interface StereoPairOperation {
  state: "running" | "succeeded" | "failed";
  steps: OperationStep[];
  pair: StereoPair | null;
  warnings: string[];
  error: { code: string; message: string } | null;
}

// ---- API Functions ----

export async function getStereoPairs(): Promise<StereoPair[]> {
  const response = await fetch(`${API_BASE_URL}/api/stereo-pairs`);
  await throwIfNotOk(response, "Failed to fetch stereo pairs");
  const body: unknown = await response.json();
  return Array.isArray(body) ? (body as StereoPair[]) : [];
}

/** Starts the asynchronous create operation and returns its id. */
export async function startStereoPairCreate(request: {
  left_device_id: string;
  right_device_id: string;
  name?: string;
}): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/stereo-pairs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  await throwIfNotOk(response, "Failed to create stereo pair");
  const body: { operation_id: string } = await response.json();
  return body.operation_id;
}

export async function getStereoPairOperation(operationId: string): Promise<StereoPairOperation> {
  const response = await fetch(
    `${API_BASE_URL}/api/stereo-pairs/operations/${encodeURIComponent(operationId)}`
  );
  await throwIfNotOk(response, "Failed to fetch stereo pair operation");
  return response.json();
}

export async function renameStereoPair(id: number, name: string): Promise<StereoPair> {
  const response = await fetch(`${API_BASE_URL}/api/stereo-pairs/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await throwIfNotOk(response, "Failed to rename stereo pair");
  return response.json();
}

export async function dissolveStereoPair(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/stereo-pairs/${id}`, { method: "DELETE" });
  await throwIfNotOk(response, "Failed to dissolve stereo pair");
}

export async function repairStereoPair(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/stereo-pairs/${id}/repair`, {
    method: "POST",
  });
  await throwIfNotOk(response, "Failed to repair stereo pair");
}
