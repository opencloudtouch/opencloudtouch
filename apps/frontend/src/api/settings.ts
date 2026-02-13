/**
 * Settings API Client
 * Centralized API calls for settings management
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export interface ManualIPsResponse {
  ips: string[];
}

/**
 * Get manual IP configuration
 */
export async function getManualIPs(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/settings/manual-ips`);
  if (!response.ok) {
    throw new Error(`Failed to fetch manual IPs: ${response.statusText}`);
  }
  const data: ManualIPsResponse = await response.json();
  return data.ips;
}

/**
 * Set manual IP addresses (replaces all existing IPs)
 */
export async function setManualIPs(ips: string[]): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/settings/manual-ips`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ips }),
  });
  if (!response.ok) {
    throw new Error(`Failed to set manual IPs: ${response.statusText}`);
  }
  const data: ManualIPsResponse = await response.json();
  return data.ips;
}

/**
 * Delete manual IP address
 */
export async function deleteManualIP(ip: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/settings/manual-ips/${ip}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete manual IP: ${response.statusText}`);
  }
}
