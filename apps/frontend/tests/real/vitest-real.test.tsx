/**
 * Real Device Unit Tests (Frontend)
 * Tests that interact with real backend/devices
 *
 * NOTE: These tests are NOT run by default (not in standard test suite)
 * Run with: npm run test:real
 */
import { describe, it, expect, beforeAll } from "vitest";

// Mark as real device tests (will be skipped in CI)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const REAL_DEVICES_AVAILABLE = (import.meta as any).env?.OCT_HAS_DEVICES === "true";
const skipIfNoDevices = REAL_DEVICES_AVAILABLE ? it : it.skip;

describe("Real Device API Integration", () => {
  const API_BASE_URL = "http://localhost:7778/api";

  beforeAll(() => {
    if (!REAL_DEVICES_AVAILABLE) {
      console.warn("⚠️  Skipping real device tests (OCT_HAS_DEVICES not set)");
    }
  });

  skipIfNoDevices("should fetch real devices from backend", async () => {
    // Trigger sync first
    const syncResponse = await fetch(`${API_BASE_URL}/devices/sync`, {
      method: "POST",
    });

    expect(syncResponse.ok).toBe(true);

    // Wait for sync to complete
    await new Promise((resolve) => setTimeout(resolve, 15000));

    // Fetch devices
    const response = await fetch(`${API_BASE_URL}/devices`);
    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data.count).toBeGreaterThan(0);
    expect(Array.isArray(data.devices)).toBe(true);

    // Verify real device data (NOT mock)
    const device = data.devices[0];
    expect(device.device_id).toBeTruthy();
    expect(device.device_id).not.toMatch(/^AABBCC|^DDEEFF/); // Not mock IDs
    expect(device.ip).toMatch(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/);
  });

  skipIfNoDevices("should fetch device capabilities from real hardware", async () => {
    // Get devices first
    const devicesResponse = await fetch(`${API_BASE_URL}/devices`);
    const devicesData = await devicesResponse.json();

    expect(devicesData.count).toBeGreaterThan(0);

    const deviceId = devicesData.devices[0].device_id;

    // Fetch capabilities
    const capResponse = await fetch(`${API_BASE_URL}/devices/${deviceId}/capabilities`);
    const capabilities = await capResponse.json();

    expect(capResponse.ok).toBe(true);
    expect(capabilities).toHaveProperty("hdmi_control");
    expect(capabilities).toHaveProperty("supports_bluetooth");
    expect(capabilities).toHaveProperty("supports_airplay");
  });
});

describe("Real RadioBrowser API Integration", () => {
  const API_BASE_URL = "http://localhost:7778/api";

  skipIfNoDevices("should search real radio stations from RadioBrowser", async () => {
    const response = await fetch(`${API_BASE_URL}/radio/search?query=BBC&search_type=name&limit=5`);
    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data.count).toBeGreaterThan(0);
    expect(Array.isArray(data.stations)).toBe(true);

    // Verify real station data
    const station = data.stations[0];
    expect(station.name).toBeTruthy();
    expect(station.uuid).toBeTruthy();
    expect(station.url).toMatch(/^https?:\/\//);
  });

  skipIfNoDevices("should fetch station details from RadioBrowser", async () => {
    // Search first
    const searchResponse = await fetch(
      `${API_BASE_URL}/radio/search?query=Radio&search_type=name&limit=1`
    );
    const searchData = await searchResponse.json();

    expect(searchData.count).toBeGreaterThan(0);

    const stationUuid = searchData.stations[0].uuid;

    // Fetch details
    const detailResponse = await fetch(`${API_BASE_URL}/radio/stations/${stationUuid}`);
    const station = await detailResponse.json();

    expect(detailResponse.ok).toBe(true);
    expect(station.uuid).toBe(stationUuid);
    expect(station.name).toBeTruthy();
  });
});
