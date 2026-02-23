/**
 * Setup Wizard API Client
 *
 * Provides type-safe API calls for device modification wizard.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface CheckPortsRequest {
  device_id: string;
}

export interface CheckPortsResponse {
  ssh_available: boolean;
  telnet_available: boolean;
  message: string;
}

export interface BackupRequest {
  device_id: string;
  backup_types: ("rootfs" | "persistent" | "update")[];
}

export interface BackupResponse {
  success: boolean;
  backup_dir: string;
  backups: {
    rootfs?: string;
    persistent?: string;
    update?: string;
  };
  sizes: {
    rootfs?: number;
    persistent?: number;
    update?: number;
  };
  message: string;
}

export interface ModifyConfigRequest {
  device_id: string;
  oct_url: string;
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
  device_id: string;
  oct_ip: string;
  domains: string[];
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
  device_id: string;
  backup_path?: string;
}

export interface RestoreResponse {
  success: boolean;
  restored_from: string;
  message: string;
}

export interface VerifyRedirectRequest {
  device_id: string;
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
