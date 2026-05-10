/**
 * Bug Report API Client
 */

import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export interface BugReportPayload {
  description: string;
  steps_to_reproduce: string;
  expected_behavior: string;
  installation_type: string;
  hardware: string;
  soundtouch_devices: string[];
  network_config: string;
  additional_info: string;
  other_installation: string;
  other_hardware: string;
  other_device: string;
  screenshot_data_url: string;
  frontend_logs: Array<{ timestamp: string; level: string; message: string }>;
  browser_info: string;
  current_route: string;
  click_timestamp: number;
}

export interface BugReportResponse {
  issue_url: string;
}

export async function submitBugReport(payload: BugReportPayload): Promise<BugReportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/bug-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  await throwIfNotOk(response, "Bug report failed");

  return response.json();
}

export interface DiagnosticsPayload {
  frontend_logs: Array<{ timestamp: string; level: string; message: string }>;
  description: string;
  browser_info: string;
  current_route: string;
  click_timestamp: number;
}

export async function downloadDiagnostics(payload: DiagnosticsPayload): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/bug-report/diagnostics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  await throwIfNotOk(response, "Diagnostics download failed");

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const execResult = /filename="(.+?)"/.exec(disposition);
  const filename = execResult?.[1] || "oct-diagnostics.log.gz";

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
