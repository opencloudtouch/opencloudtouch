/**
 * Setup Wizard API Client
 *
 * Uses generated types from OpenAPI spec for type-safety.
 * Runtime fetch wrappers with error handling.
 */

import type { components } from "./generated/schema";

// Re-export generated DTOs as convenient aliases
export type CheckPortsRequest = components["schemas"]["PortCheckRequest"];
export type CheckPortsResponse = components["schemas"]["PortCheckResponse"];
export type BackupRequest = components["schemas"]["BackupRequest"];
export type BackupResponse = components["schemas"]["BackupResponse"];
export type ModifyConfigRequest = components["schemas"]["ConfigModifyRequest"];
export type ModifyConfigResponse = components["schemas"]["ConfigModifyResponse"];
export type ModifyHostsRequest = components["schemas"]["HostsModifyRequest"];
export type ModifyHostsResponse = components["schemas"]["HostsModifyResponse"];
export type RestoreRequest = components["schemas"]["RestoreRequest"];
export type RestoreResponse = components["schemas"]["RestoreResponse"];
export type VerifyRedirectRequest = components["schemas"]["VerifyRedirectRequest"];
export type VerifyRedirectResponse = components["schemas"]["VerifyRedirectResponse"];
export type RebootDeviceRequest = components["schemas"]["ConnectivityCheckRequest"];
export type EnablePermanentSSHRequest = components["schemas"]["EnablePermanentSSHRequest"];

// Types not in OpenAPI (server-info returns untyped dict)
export interface ServerInfoResponse {
  server_url: string;
  server_ip: string;
  default_port: number;
  supported_protocols: string[];
}

export interface DetectStrategyResponse {
  proxy_available: boolean;
  strategy: "hosts_only" | "bmx_and_hosts";
  message: string;
}

export interface WizardCompleteRequest {
  device_id: string;
}

export interface WizardCompleteResponse {
  success: boolean;
  device_id: string;
  setup_status: string;
  message: string;
}

export interface RebootDeviceResponse {
  success: boolean;
  message: string;
}

export interface EnablePermanentSSHResponse {
  success: boolean;
  permanent_enabled: boolean;
  message: string;
}

// Keep BackupVolume for components that destructure it
export interface BackupVolume {
  volume: string;
  path: string;
  size_mb: number;
  duration_seconds: number;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Get OCT server info for auto-filling wizard forms
 */
export async function getServerInfo(): Promise<ServerInfoResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/server-info`);

  if (!response.ok) {
    throw new Error(`Server info fetch failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Detect setup strategy: hosts-only (proxy on 443) or bmx+hosts
 */
export async function detectStrategy(): Promise<DetectStrategyResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/detect-strategy`);

  if (!response.ok) {
    throw new Error(`Strategy detection failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Check if SSH port is available on device
 */
export async function checkPorts(request: CheckPortsRequest): Promise<CheckPortsResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/check-ports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Port check failed: ${error}`);
  }

  return response.json();
}

/**
 * Create device backups
 */
export async function createBackup(request: BackupRequest): Promise<BackupResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/backup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Backup failed: ${error}`);
  }

  return response.json();
}

/**
 * Modify OverrideSdkPrivateCfg.xml (bmxRegistryUrl HTTPS→HTTP)
 */
export async function modifyConfig(request: ModifyConfigRequest): Promise<ModifyConfigResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/modify-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Config modification failed: ${error}`);
  }

  return response.json();
}

/**
 * Modify /etc/hosts (redirect Bose domains to OCT)
 */
export async function modifyHosts(request: ModifyHostsRequest): Promise<ModifyHostsResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/modify-hosts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Hosts modification failed: ${error}`);
  }

  return response.json();
}

/**
 * Restore config from backup
 */
export async function restoreConfig(request: RestoreRequest): Promise<RestoreResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/restore-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Config restore failed: ${error}`);
  }

  return response.json();
}

/**
 * Restore hosts from backup
 */
export async function restoreHosts(request: RestoreRequest): Promise<RestoreResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/restore-hosts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Hosts restore failed: ${error}`);
  }

  return response.json();
}

/**
 * Send reboot command to device via SSH (Wizard Step 7)
 */
export async function rebootDevice(request: RebootDeviceRequest): Promise<RebootDeviceResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/reboot-device`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Reboot failed: ${error}`);
  }

  return response.json();
}

/**
 * Enable (or skip) permanent SSH on device
 */
export async function enablePermanentSsh(
  request: EnablePermanentSSHRequest
): Promise<EnablePermanentSSHResponse> {
  const response = await fetch(`${API_BASE}/api/setup/ssh/enable-permanent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Enable permanent SSH failed: ${error}`);
  }

  return response.json();
}

/**
 * Mark wizard setup as complete for a device
 */
export async function completeWizard(
  request: WizardCompleteRequest
): Promise<WizardCompleteResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Complete wizard failed: ${error}`);
  }

  return response.json();
}

/**
 * Verify domain redirect
 */
export async function verifyRedirect(
  request: VerifyRedirectRequest
): Promise<VerifyRedirectResponse> {
  const response = await fetch(`${API_BASE}/api/setup/wizard/verify-redirect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Redirect verification failed: ${error}`);
  }

  return response.json();
}
