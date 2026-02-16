/**
 * Device API Client
 * Centralized API calls for device management
 */

import { getErrorMessage } from "./types";

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
}

// Frontend Device interface (matches DeviceSwiper.tsx)
export interface Device {
  device_id: string;
  name: string;
  model?: string;
  firmware?: string;
  ip?: string;
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
    name: apiDevice.name, // Backend already returns 'name'
    model: apiDevice.model, // Backend already returns 'model'
    ip: apiDevice.ip, // Backend already returns 'ip'
    firmware: apiDevice.firmware_version,
  };
}

/**
 * Fetch all devices from the backend
 */
export async function getDevices(): Promise<Device[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/devices`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(
        getErrorMessage(errorData) || `Failed to fetch devices: ${response.statusText}`
      );
    }
    const data = await response.json();
    const devicesList: DeviceAPIResponse[] = data.devices || [];
    return devicesList.map(mapDeviceFromAPI);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
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
      throw new Error(
        getErrorMessage(errorData) || `Failed to sync devices: ${response.statusText}`
      );
    }
    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get device capabilities
 */
export async function getDeviceCapabilities(deviceId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/devices/${deviceId}/capabilities`);
  if (!response.ok) {
    throw new Error(`Failed to fetch device capabilities: ${response.statusText}`);
  }
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

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(getErrorMessage(errorData) || `Failed to play preset: ${response.statusText}`);
  }
}
