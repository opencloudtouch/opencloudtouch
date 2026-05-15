/**
 * API service for preset management.
 *
 * Provides methods to interact with the backend preset endpoints.
 */

import { throwIfNotOk } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export interface PresetSetRequest {
  device_id: string;
  preset_number: number;
  station_uuid: string;
  station_name: string;
  station_url: string;
  station_homepage?: string;
  station_favicon?: string;
}

export interface PresetResponse {
  id: number;
  device_id: string;
  preset_number: number;
  station_uuid: string;
  station_name: string;
  station_url: string;
  source?: string;
  station_homepage?: string;
  station_favicon?: string;
  created_at: string;
  updated_at: string;
}

export interface MessageResponse {
  message: string;
}

/**
 * Set a preset for a device.
 */
export async function setPreset(request: PresetSetRequest): Promise<PresetResponse> {
  const response = await fetch(`${API_BASE_URL}/api/presets/set`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  await throwIfNotOk(response, "Failed to set preset");

  return response.json();
}

/**
 * Get all presets for a device.
 */
export async function getDevicePresets(deviceId: string): Promise<PresetResponse[]> {
  const response = await fetch(`${API_BASE_URL}/api/presets/${deviceId}`);

  await throwIfNotOk(response, "Failed to get presets");

  return response.json();
}

/**
 * Get a specific preset for a device.
 */
export async function getPreset(deviceId: string, presetNumber: number): Promise<PresetResponse> {
  const response = await fetch(`${API_BASE_URL}/api/presets/${deviceId}/${presetNumber}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Preset not found");
    }
    await throwIfNotOk(response, "Failed to get preset");
  }

  return response.json();
}

/**
 * Clear a specific preset for a device.
 */
export async function clearPreset(
  deviceId: string,
  presetNumber: number
): Promise<MessageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/presets/${deviceId}/${presetNumber}`, {
    method: "DELETE",
  });

  await throwIfNotOk(response, "Failed to clear preset");

  return response.json();
}

/**
 * Clear all presets for a device.
 */
export async function clearAllPresets(deviceId: string): Promise<MessageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/presets/${deviceId}`, {
    method: "DELETE",
  });

  await throwIfNotOk(response, "Failed to clear all presets");

  return response.json();
}

/**
 * Sync presets from device to OCT database.
 *
 * Fetches presets from the physical device and imports them.
 * Useful when device was configured by another OCT instance or manually.
 */
export async function syncPresetsFromDevice(deviceId: string): Promise<MessageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/presets/${deviceId}/sync`, {
    method: "POST",
  });

  await throwIfNotOk(response, "Failed to sync presets from device");

  return response.json();
}
