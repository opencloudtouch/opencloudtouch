/**
 * Tests for zones.ts API client.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getZones,
  getDeviceZone,
  createZone,
  dissolveZone,
  addZoneMembers,
  removeZoneMembers,
  changeMaster,
} from "../../../src/api/zones";

const MOCK_ZONE = {
  master_id: "ST10-001",
  master_ip: "192.168.1.10",
  is_master: true,
  members: [{ device_id: "ST10-001", ip_address: "192.168.1.10", role: "master" as const }],
};

describe("Zones API Client", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  it("getZones fetches the zone list", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([MOCK_ZONE]) });

    const result = await getZones();

    expect(mockFetch).toHaveBeenCalledWith("/api/zones");
    expect(result).toEqual([MOCK_ZONE]);
  });

  it("getDeviceZone fetches and URL-encodes the device id", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(MOCK_ZONE) });

    const result = await getDeviceZone("ST10 001");

    expect(mockFetch).toHaveBeenCalledWith("/api/devices/ST10%20001/zone");
    expect(result).toEqual(MOCK_ZONE);
  });

  it("createZone POSTs master_id and slave_ids", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(MOCK_ZONE) });

    const result = await createZone("ST10-001", ["ST30-002"]);

    expect(mockFetch).toHaveBeenCalledWith("/api/zones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ master_id: "ST10-001", slave_ids: ["ST30-002"] }),
    });
    expect(result).toEqual(MOCK_ZONE);
  });

  it("dissolveZone DELETEs the zone by master id", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

    await dissolveZone("ST10-001");

    expect(mockFetch).toHaveBeenCalledWith("/api/zones/ST10-001", { method: "DELETE" });
  });

  it("addZoneMembers POSTs device_ids to the members endpoint", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(MOCK_ZONE) });

    const result = await addZoneMembers("ST10-001", ["ST30-002"]);

    expect(mockFetch).toHaveBeenCalledWith("/api/zones/ST10-001/members", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_ids: ["ST30-002"] }),
    });
    expect(result).toEqual(MOCK_ZONE);
  });

  it("removeZoneMembers DELETEs with device_ids in the body", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

    await removeZoneMembers("ST10-001", ["ST30-002"]);

    expect(mockFetch).toHaveBeenCalledWith("/api/zones/ST10-001/members", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_ids: ["ST30-002"] }),
    });
  });

  it("changeMaster PUTs new_master_id to the master endpoint", async () => {
    const newMasterZone = { ...MOCK_ZONE, master_id: "ST30-002" };
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(newMasterZone) });

    const result = await changeMaster("ST10-001", "ST30-002");

    expect(mockFetch).toHaveBeenCalledWith("/api/zones/ST10-001/master", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_master_id: "ST30-002" }),
    });
    expect(result).toEqual(newMasterZone);
  });

  it("throws on a failed request", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      statusText: "Conflict",
      json: () => Promise.resolve({ detail: "Zone already exists" }),
    });

    await expect(createZone("ST10-001", ["ST30-002"])).rejects.toThrow("Zone already exists");
  });
});
