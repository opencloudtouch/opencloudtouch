/**
 * Settings API Client
 * Centralized API calls for settings management
 */

import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export interface ManualIPsResponse {
  ips: string[];
}

/**
 * Get manual IP configuration
 */
export async function getManualIPs(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/settings/manual-ips`);
  await throwIfNotOk(response, "Failed to fetch manual IPs");
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
  await throwIfNotOk(response, "Failed to set manual IPs");
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
  await throwIfNotOk(response, "Failed to delete manual IP");
}

export interface ProbeResult {
  device_id: string;
  ip: string;
  name: string;
  model: string;
}

/**
 * Probe a single device by IP address.
 * Contacts the device, fetches info, upserts to DB, and adds to manual IPs.
 */
export async function probeDevice(ip: string): Promise<ProbeResult> {
  const response = await fetch(`${API_BASE_URL}/api/devices/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ip }),
  });
  await throwIfNotOk(response, "Device not reachable");
  return response.json();
}
