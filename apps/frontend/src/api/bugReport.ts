/**
 * Bug Report API Client
 */

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

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Bug report failed (${response.status}): ${text}`);
  }

  return response.json();
}
