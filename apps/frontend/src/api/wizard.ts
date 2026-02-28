/**
 * Setup Wizard API Client
 *
 * Provides type-safe API calls for device modification wizard.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export interface CheckPortsRequest {
  device_ip: string;
  timeout?: number;
}

export interface CheckPortsResponse {
  success: boolean;
  has_ssh: boolean;
  has_telnet: boolean;
  message: string;
}

export interface BackupVolume {
  volume: string;
  path: string;
  size_mb: number;
  duration_seconds: number;
}

export interface BackupRequest {
  device_ip: string;
}

export interface BackupResponse {
  success: boolean;
  message: string;
  volumes: BackupVolume[];
  total_size_mb: number;
  total_duration_seconds: number;
}

export interface ModifyConfigRequest {
  device_ip: string;
  oct_ip: string;
}

export interface ModifyConfigResponse {
  success: boolean;
  action: string;
  old_url?: string;
  new_url?: string;
  backup_path?: string;
  diff?: string;
  message: string;
}

export interface ModifyHostsRequest {
  device_ip: string;
  oct_ip: string;
  include_optional?: boolean;
}

export interface ModifyHostsResponse {
  success: boolean;
  action: string;
  added_entries: number;
  backup_path?: string;
  diff?: string;
  message: string;
}

export interface RestoreRequest {
  device_ip: string;
  backup_path?: string;
}

export interface RestoreResponse {
  success: boolean;
  restored_from: string;
  message: string;
}

export interface VerifyRedirectRequest {
  device_ip: string;
  domain: string;
  expected_ip: string;
}

export interface VerifyRedirectResponse {
  success: boolean;
  domain: string;
  resolved_ip: string;
  matches_expected: boolean;
  message: string;
}

/**
 * Check if SSH/Telnet ports are available on device
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

export interface RebootDeviceRequest {
  ip: string;
}

export interface RebootDeviceResponse {
  success: boolean;
  message: string;
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

export interface EnablePermanentSSHRequest {
  device_id: string;
  ip: string;
  make_permanent: boolean;
}

export interface EnablePermanentSSHResponse {
  success: boolean;
  permanent_enabled: boolean;
  message: string;
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
