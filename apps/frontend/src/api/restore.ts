/**
 * Restore Wizard API Client
 *
 * Separate from wizard.ts to avoid naming collision with existing
 * RestoreRequest/RestoreResponse (those serve restore-config/restore-hosts).
 */

import { throwIfNotOk } from "./types";

// ---- Request/Response types (manual until OpenAPI types are generated) ----

export interface ScanBackupsRequest {
  device_ip: string;
  device_id: string;
}

export interface BackupFileInfoResponse {
  filename: string;
  volume_type: string;
  file_path: string;
  size_bytes: number;
  device_id: string | null;
  backup_date: string | null;
  is_pre_restore: boolean;
  validation_status: string;
  validation_message: string;
}

export interface BackupSetResponse {
  device_id: string | null;
  backup_date: string | null;
  files: BackupFileInfoResponse[];
  is_legacy: boolean;
  is_match: boolean;
}

export interface ScanBackupsResponse {
  usb_mounted: boolean;
  backup_dir: string;
  selected_set: BackupSetResponse | null;
  all_sets: BackupSetResponse[];
  error: string | null;
}

export interface RestoreWizardFileRef {
  file_path: string;
  volume_type: string;
}

export interface RestoreWizardBackupSet {
  device_id: string | null;
  backup_date: string | null;
  files: RestoreWizardFileRef[];
}

export interface RestoreWizardRequest {
  device_ip: string;
  device_id: string;
  restore_type: "backup" | "clean";
  backup_set: RestoreWizardBackupSet | null;
  skip_snapshot: boolean;
}

export interface RestoreStepResponse {
  name: string;
  status: string;
  message: string;
  error: string | null;
  duration_seconds: number;
}

export interface RestoreWizardResponse {
  success: boolean;
  restore_type: string;
  steps: RestoreStepResponse[];
  pre_restore_snapshot: Record<string, unknown> | null;
  snapshot_skipped: boolean;
  device_rebooted: boolean;
  total_duration_seconds: number;
}

// ---- API Functions ----

export async function scanBackups(request: ScanBackupsRequest): Promise<ScanBackupsResponse> {
  const response = await fetch("/api/setup/wizard/scan-backups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  await throwIfNotOk(response, "Backup scan failed");
  return response.json();
}

export async function executeRestore(
  request: RestoreWizardRequest
): Promise<RestoreWizardResponse> {
  const response = await fetch("/api/setup/wizard/restore-wizard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  await throwIfNotOk(response, "Restore execution failed");
  return response.json();
}
