/**
 * Setup API Client
 * API calls for device setup wizard
 */

import { getErrorMessage } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Setup status enum matching backend
 */
export type SetupStatus = "unconfigured" | "pending" | "configured" | "failed";

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
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(
      getErrorMessage(errorData) || `Failed to get instructions: ${response.statusText}`
    );
  }
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
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(
      getErrorMessage(errorData) || `Connectivity check failed: ${response.statusText}`
    );
  }
  return response.json();
}

/**
 * Start device setup process
 */
export async function startSetup(
  deviceId: string,
  ip: string,
  model: string
): Promise<{ device_id: string; status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/setup/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, ip, model }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(getErrorMessage(errorData) || `Failed to start setup: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get setup status for a device
 */
export async function getSetupStatus(deviceId: string): Promise<SetupProgress | null> {
  const response = await fetch(`${API_BASE_URL}/api/setup/status/${deviceId}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(getErrorMessage(errorData) || `Failed to get status: ${response.statusText}`);
  }
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
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(getErrorMessage(errorData) || `Verification failed: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get all supported models
 */
export async function getSupportedModels(): Promise<ModelInstructions[]> {
  const response = await fetch(`${API_BASE_URL}/api/setup/models`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(getErrorMessage(errorData) || `Failed to get models: ${response.statusText}`);
  }
  const data = await response.json();
  return data.models || [];
}

/**
 * Human-readable step labels (German)
 */
export const STEP_LABELS: Record<SetupStep, string> = {
  usb_insert: "USB-Stick einstecken",
  device_reboot: "Gerät neu starten",
  ssh_connect: "SSH-Verbindung herstellen",
  ssh_persist: "SSH dauerhaft aktivieren",
  config_backup: "Backup erstellen",
  config_modify: "Konfiguration anpassen",
  verify: "Verifizieren",
  complete: "Abgeschlossen",
};

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
