/**
 * Diagnostics API Client
 */

import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export interface DiagnosticsDevice {
  device_id: string;
  name: string;
  model: string;
  ip: string;
  firmware_version: string;
  setup_status: string;
  last_seen: string | null;
  setup_completed_at: string | null;
  ssh_permanent: boolean;
}

export interface DiagnosticsServer {
  version: string;
  python_version: string;
  platform: string;
  discovery_enabled: boolean;
  mock_mode: boolean;
  log_level: string;
  manual_device_ips: number;
  timestamp: string;
}

export interface DiagnosticsResponse {
  server: DiagnosticsServer;
  devices: DiagnosticsDevice[];
  db_stats: { devices: number; presets: number };
}

export async function getDiagnostics(): Promise<DiagnosticsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/diagnostics`);
  await throwIfNotOk(response, "Failed to fetch diagnostics");
  return response.json();
}
