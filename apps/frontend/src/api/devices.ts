/**
 * Device API Client
 * Centralized API calls for device management
 */

import { getErrorMessage, throwIfNotOk } from "./types";
import { SetupStatus } from "./setup";

// Backend API response structure (matches Device.to_dict() from repository.py)
interface DeviceAPIResponse {
  id?: number;
  device_id: string;
  ip: string; // Backend uses 'ip', not 'ip_address'
  name: string; // Backend uses 'name', not 'friendly_name'
  model: string; // Backend uses 'model', not 'model_name'
  mac_address: string;
  firmware_version: string;
  schema_version?: string;
  last_seen: string;
  setup_status: string;
  ssh_permanent: boolean;
  setup_completed_at: string | null;
}

// Frontend Device interface (matches DeviceSwiper.tsx)
export interface Device {
  device_id: string;
  name: string;
  model?: string;
  firmware?: string;
  ip?: string;
  setup_status?: SetupStatus;
  ssh_permanent?: boolean;
  setup_completed_at?: string | null;
  last_seen?: string;
  capabilities?: {
    airplay?: boolean;
  };
}

export interface SyncResult {
  discovered: number;
  synced: number;
  failed: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Map backend API response to frontend Device format
 */
function mapDeviceFromAPI(apiDevice: DeviceAPIResponse): Device {
  return {
    device_id: apiDevice.device_id,
    name: apiDevice.name,
    model: apiDevice.model,
    ip: apiDevice.ip,
    firmware: apiDevice.firmware_version,
    setup_status: apiDevice.setup_status as SetupStatus,
    ssh_permanent: apiDevice.ssh_permanent,
    setup_completed_at: apiDevice.setup_completed_at,
    last_seen: apiDevice.last_seen,
  };
}

/**
 * Fetch all devices from the backend
 */
export async function getDevices(): Promise<Device[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/devices`);
    await throwIfNotOk(response, "Failed to fetch devices");
    const data = await response.json();
    const devicesList: DeviceAPIResponse[] = data.devices || [];
    return devicesList.map(mapDeviceFromAPI);
  } catch (error) {
    throw new Error(getErrorMessage(error), { cause: error });
  }
}

/**
 * Custom error class with HTTP status code
 */
export class APIError extends Error {
  statusCode?: number;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "APIError";
    this.statusCode = statusCode;
  }
}

/** Check if an error indicates the device is offline (503 Service Unavailable or 500 from device endpoint) */
export function isDeviceOfflineError(error: unknown): boolean {
  return error instanceof APIError && (error.statusCode === 503 || error.statusCode === 500);
}

/**
 * Sync devices by triggering discovery
 */
export async function syncDevices(): Promise<SyncResult> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/devices/sync`, {
      method: "POST",
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const message =
        getErrorMessage(errorData) || `Failed to sync devices: ${response.statusText}`;
      throw new APIError(message, response.status);
    }
    return response.json();
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    throw new Error(getErrorMessage(error), { cause: error });
  }
}

/**
 * Get device capabilities
 */
export async function getDeviceCapabilities(deviceId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/capabilities`);
  await throwIfNotOk(response, "Failed to fetch device capabilities");
  return response.json();
}

/**
 * Play a preset on a device by simulating key press
 *
 * @param deviceId - Device ID
 * @param presetNumber - Preset number (1-6)
 */
export async function playPreset(deviceId: string, presetNumber: number): Promise<void> {
  if (presetNumber < 1 || presetNumber > 6) {
    throw new Error(`Invalid preset number: ${presetNumber}. Must be 1-6`);
  }

  const key = `PRESET_${presetNumber}`;
  const response = await fetch(
    `${API_BASE_URL}/api/devices/${deviceId}/key?key=${key}&state=both`,
    {
      method: "POST",
    }
  );

  await throwIfNotOk(response, "Failed to play preset");
}

/**
 * Delete a device by id
 * @param deviceId - Id of the device you wish to delete
 */
export async function deleteDeviceById(deviceId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}`, {
    method: "DELETE",
  });

  await throwIfNotOk(response, "Failed to delete device");
}

// ---- Device Rename API ----

export interface RenameDeviceResponse {
  device_id: string;
  name: string;
  previous_name: string;
}

export async function renameDevice(deviceId: string, name: string): Promise<RenameDeviceResponse> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/name`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  await throwIfNotOk(response, "Failed to rename device");
  return response.json();
}

// ---- Volume API ----

export interface VolumeState {
  actual: number;
  target: number;
  muted: boolean;
}

export async function getVolume(deviceId: string): Promise<VolumeState> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/volume`);
  if (!response.ok) {
    throw new APIError(`Failed to get volume: ${response.statusText}`, response.status);
  }
  return response.json();
}

export async function setVolume(deviceId: string, level: number): Promise<VolumeState> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/volume`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level }),
  });
  await throwIfNotOk(response, "Failed to set volume");
  return response.json();
}

export async function setMute(deviceId: string, muted: boolean): Promise<VolumeState> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/mute`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ muted }),
  });
  await throwIfNotOk(response, "Failed to set mute");
  return response.json();
}

// ---- Now Playing API ----

export interface NowPlayingState {
  source: string;
  state: string;
  station_name?: string;
  artist?: string;
  track?: string;
  album?: string;
  artwork_url?: string;
}

export async function getNowPlaying(deviceId: string): Promise<NowPlayingState> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/now-playing`);
  if (!response.ok) {
    throw new APIError(`Failed to get now playing: ${response.statusText}`, response.status);
  }
  return response.json();
}

export async function togglePlayPause(deviceId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/devices/${deviceId}/key?key=PLAY_PAUSE&state=both`,
    { method: "POST" }
  );
  await throwIfNotOk(response, "Failed to toggle play/pause");
}

export async function sendKey(deviceId: string, key: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/devices/${deviceId}/key?key=${encodeURIComponent(key)}&state=both`,
    { method: "POST" }
  );
  await throwIfNotOk(response, `Failed to send key ${key}`);
}

export async function nextTrack(deviceId: string): Promise<void> {
  return sendKey(deviceId, "NEXT_TRACK");
}

export async function prevTrack(deviceId: string): Promise<void> {
  return sendKey(deviceId, "PREV_TRACK");
}

export async function power(deviceId: string): Promise<void> {
  return sendKey(deviceId, "POWER");
}
