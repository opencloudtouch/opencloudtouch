/**
 * Setup API Client
 * API calls for device setup wizard
 */

import { throwIfNotOk } from "./types";
import i18next from "i18next";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Setup status enum matching backend
 */
export type SetupStatus =
  | "unconfigured"
  | "pending"
  | "configured"
  | "failed"
  | "outdated"
  | "offline"
  | "unknown";

/**
 * Setup step enum matching backend
 */
export type SetupStep =
  | "usb_insert"
  | "device_reboot"
  | "ssh_connect"
  | "ssh_persist"
  | "config_backup"
  | "config_modify"
  | "verify"
  | "complete";

/**
 * Setup progress response
 */
export interface SetupProgress {
  device_id: string;
  current_step: SetupStep;
  status: SetupStatus;
  message: string;
  error?: string | null;
  started_at: string;
  completed_at?: string | null;
}

/**
 * Model-specific instructions
 */
export interface ModelInstructions {
  model_name: string;
  display_name: string;
  usb_port_type: string;
  usb_port_types: string[];
  usb_port_location: string;
  adapter_needed: boolean;
  adapter_recommendation: string;
  image_url?: string | null;
  notes: string[];
}

/**
 * Connectivity check result
 */
export interface ConnectivityResult {
  ip: string;
  ssh_available: boolean;
  telnet_available: boolean;
  ready_for_setup: boolean;
}

/**
 * Get model-specific setup instructions
 */
export async function getModelInstructions(model: string): Promise<ModelInstructions> {
  const response = await fetch(
    `${API_BASE_URL}/api/setup/instructions/${encodeURIComponent(model)}`
  );
  await throwIfNotOk(response, "Failed to get instructions");
  return response.json();
}

/**
 * Check if device is ready for setup (SSH available)
 */
export async function checkConnectivity(ip: string): Promise<ConnectivityResult> {
  const response = await fetch(`${API_BASE_URL}/api/setup/check-connectivity`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ip }),
  });
  await throwIfNotOk(response, "Connectivity check failed");
  return response.json();
}

/**
 * Get setup status for a device
 */
export async function getSetupStatus(deviceId: string): Promise<SetupProgress | null> {
  const response = await fetch(`${API_BASE_URL}/api/setup/status/${deviceId}`);
  await throwIfNotOk(response, "Failed to get status");
  const data = await response.json();
  if (data.status === "not_found") {
    return null;
  }
  return data as SetupProgress;
}

/**
 * Verify device setup
 */
export async function verifySetup(
  deviceId: string,
  ip: string
): Promise<{
  ip: string;
  ssh_accessible: boolean;
  ssh_persistent: boolean;
  bmx_configured: boolean;
  bmx_url: string | null;
  verified: boolean;
}> {
  const response = await fetch(
    `${API_BASE_URL}/api/setup/verify/${deviceId}?ip=${encodeURIComponent(ip)}`,
    {
      method: "POST",
    }
  );
  await throwIfNotOk(response, "Verification failed");
  return response.json();
}

/**
 * Get all supported models
 */
export async function getSupportedModels(): Promise<ModelInstructions[]> {
  const response = await fetch(`${API_BASE_URL}/api/setup/models`);
  await throwIfNotOk(response, "Failed to get models");
  const data = await response.json();
  return data.models || [];
}

/**
 * Human-readable step labels
 */
export function getStepLabel(step: SetupStep): string {
  const t = i18next.t.bind(i18next);
  const labels: Record<SetupStep, string> = {
    usb_insert: t("setup.stepLabels.usbInsert"),
    device_reboot: t("setup.stepLabels.deviceReboot"),
    ssh_connect: t("setup.stepLabels.sshConnect"),
    ssh_persist: t("setup.stepLabels.sshPersist"),
    config_backup: t("setup.stepLabels.configBackup"),
    config_modify: t("setup.stepLabels.configModify"),
    verify: t("setup.stepLabels.verify"),
    complete: t("setup.stepLabels.complete"),
  };
  return labels[step];
}

/**
 * Step order for progress calculation
 */
export const STEP_ORDER: SetupStep[] = [
  "usb_insert",
  "device_reboot",
  "ssh_connect",
  "ssh_persist",
  "config_backup",
  "config_modify",
  "verify",
  "complete",
];

/**
 * Calculate progress percentage
 */
export function calculateProgress(step: SetupStep): number {
  const index = STEP_ORDER.indexOf(step);
  if (index === -1) return 0;
  return Math.round((index / (STEP_ORDER.length - 1)) * 100);
}
