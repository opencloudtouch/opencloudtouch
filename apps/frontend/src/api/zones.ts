/**
 * Zone API Client (STORY-1005)
 * API calls for multi-room zone management
 */

import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

// ---- Types ----

export interface ZoneMemberInfo {
  device_id: string;
  ip_address: string;
  role: "master" | "slave";
  name?: string;
  model?: string;
}

export interface ZoneInfo {
  master_id: string;
  master_ip: string;
  is_master: boolean;
  members: ZoneMemberInfo[];
}

// ---- API Functions ----

export async function getZones(): Promise<ZoneInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/zones`);
  await throwIfNotOk(response, "Failed to fetch zones");
  return response.json();
}

export async function getDeviceZone(deviceId: string): Promise<ZoneInfo | null> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${encodeURIComponent(deviceId)}/zone`);
  await throwIfNotOk(response, "Failed to fetch device zone");
  return response.json();
}

export async function createZone(masterId: string, slaveIds: string[]): Promise<ZoneInfo> {
  const response = await fetch(`${API_BASE_URL}/api/zones`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ master_id: masterId, slave_ids: slaveIds }),
  });
  await throwIfNotOk(response, "Failed to create zone");
  return response.json();
}

export async function dissolveZone(masterId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/zones/${encodeURIComponent(masterId)}`, {
    method: "DELETE",
  });
  await throwIfNotOk(response, "Failed to dissolve zone");
}

export async function addZoneMembers(masterId: string, deviceIds: string[]): Promise<ZoneInfo> {
  const response = await fetch(
    `${API_BASE_URL}/api/zones/${encodeURIComponent(masterId)}/members`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_ids: deviceIds }),
    }
  );
  await throwIfNotOk(response, "Failed to add members");
  return response.json();
}

export async function removeZoneMembers(masterId: string, deviceIds: string[]): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/zones/${encodeURIComponent(masterId)}/members`,
    {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_ids: deviceIds }),
    }
  );
  await throwIfNotOk(response, "Failed to remove members");
}

export async function changeMaster(
  currentMasterId: string,
  newMasterId: string
): Promise<ZoneInfo> {
  const response = await fetch(
    `${API_BASE_URL}/api/zones/${encodeURIComponent(currentMasterId)}/master`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_master_id: newMasterId }),
    }
  );
  await throwIfNotOk(response, "Failed to change master");
  return response.json();
}
