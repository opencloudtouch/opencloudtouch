/**
 * Device API Client
 * Centralized API calls for device management
 */

// Backend API response structure
interface DeviceAPIResponse {
  device_id: string;
  ip_address: string;
  friendly_name: string;
  model_name?: string;
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
    name: apiDevice.friendly_name,
    model: apiDevice.model_name,
    ip: apiDevice.ip_address,
  };
}

/**
 * Fetch all devices from the backend
 */
export async function getDevices(): Promise<Device[]> {
  const response = await fetch(`${API_BASE_URL}/api/devices`);
  if (!response.ok) {
    throw new Error(`Failed to fetch devices: ${response.statusText}`);
  }
  const data = await response.json();
  const devicesList: DeviceAPIResponse[] = data.devices || [];
  return devicesList.map(mapDeviceFromAPI);
}

/**
 * Sync devices by triggering discovery
 */
export async function syncDevices(): Promise<SyncResult> {
  const response = await fetch(`${API_BASE_URL}/api/devices/sync`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to sync devices: ${response.statusText}`);
  }
  return response.json();
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
