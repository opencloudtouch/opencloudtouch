import { describe, it, expect, vi, afterEach } from "vitest";
import {
  browseDlna,
  disableNativeServer,
  enableNativeServer,
  getAlbumRoot,
  getDlnaObjectPath,
  getDlnaServers,
  getFirstChildAudio,
  getNativeServers,
  saveDlnaPreset,
} from "../../../src/api/dlna";
import { ApiError } from "../../../src/api/types";

const json = (status: number, body: unknown) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const errorBody = (code: string, extra: Record<string, unknown>) => ({
  type: "conflict",
  title: "Conflict",
  status: 409,
  detail: "conflict",
  code,
  extra,
});

function stubFetch(status: number, body: unknown) {
  const f = vi.fn().mockResolvedValue(json(status, body));
  vi.stubGlobal("fetch", f);
  return f;
}

const calledUrl = (f: ReturnType<typeof vi.fn>) => String(f.mock.calls[0][0]);

async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (e) {
    if (e instanceof ApiError) return e;
  }
  throw new Error("expected an ApiError");
}

afterEach(() => vi.unstubAllGlobals());

describe("dlna api", () => {
  it("browseDlna builds the query and parses has_more", async () => {
    const f = stubFetch(200, { items: [], has_more: true, next_index: 50 });
    const result = await browseDlna("srv/1", "0", 50, 50);
    const url = calledUrl(f);
    expect(url).toContain("/api/dlna/servers/srv%2F1/browse?");
    expect(url).toContain("object_id=0");
    expect(url).toContain("starting_index=50");
    expect(url).toContain("requested_count=50");
    expect(url).not.toContain("refresh");
    expect(result.has_more).toBe(true);
  });

  it("saveDlnaPreset posts the request and surfaces 409 code and extra", async () => {
    const f = stubFetch(409, errorBody("dlna_folder_no_audio_first", { title: "Album" }));
    const err = await rejection(
      saveDlnaPreset({
        device_id: "d",
        preset_number: 1,
        server_id: "s",
        parent_id: "0",
        object_id: "o",
      })
    );
    expect(err.code).toBe("dlna_folder_no_audio_first");
    expect(err.extra).toEqual({ title: "Album" });
    expect(calledUrl(f)).toContain("/api/presets/dlna");
    expect(f.mock.calls[0][1]).toMatchObject({ method: "POST" });
  });

  it("disableNativeServer surfaces slots", async () => {
    const f = stubFetch(409, errorBody("dlna_native_slots_affected", { slots: [1, 3] }));
    const err = await rejection(disableNativeServer("d", "s", false));
    expect(err.code).toBe("dlna_native_slots_affected");
    expect(err.extra?.slots).toEqual([1, 3]);
    expect(calledUrl(f)).toContain("/api/dlna/native/d/servers/s?force=false");
    expect(f.mock.calls[0][1]).toMatchObject({ method: "DELETE" });
  });

  it("disableNativeServer sends force=true", async () => {
    const f = stubFetch(204, null);
    await disableNativeServer("d", "s", true);
    expect(calledUrl(f)).toContain("force=true");
  });

  it("getNativeServers returns the list with the migration state", async () => {
    const body = {
      servers: [{ server_id: "s", name: "N", state: "ready", discovered: true, host: "h" }],
      migration_failed: true,
      migration_reason: "step failed",
    };
    const f = stubFetch(200, body);
    expect(await getNativeServers("d")).toEqual(body);
    expect(calledUrl(f)).toContain("/api/dlna/native?device_id=d");
  });

  it("enableNativeServer puts and returns the server state", async () => {
    const server = {
      server_id: "s",
      name: "N",
      state: "unavailable",
      discovered: true,
      host: null,
    };
    const f = stubFetch(200, server);
    expect(await enableNativeServer("d", "s")).toEqual(server);
    expect(f.mock.calls[0][1]).toMatchObject({ method: "PUT" });
  });

  it("small getters unwrap their bodies", async () => {
    stubFetch(200, [{ id: "s" }]);
    expect(await getDlnaServers()).toEqual([{ id: "s" }]);
    stubFetch(200, { object_id: "7" });
    expect(await getAlbumRoot("s")).toBe("7");
    let f = stubFetch(200, { first_child_is_audio: false });
    expect(await getFirstChildAudio("s", "o")).toBe(false);
    expect(calledUrl(f)).toContain("/first-child-audio?object_id=o");
    f = stubFetch(200, { path: [] });
    expect(await getDlnaObjectPath("s", "o")).toEqual({ path: [] });
    expect(calledUrl(f)).toContain("/objects/path?object_id=o");
  });

  it("non-2xx keeps the status", async () => {
    stubFetch(500, { detail: "x" });
    expect((await rejection(getDlnaServers())).status).toBe(500);
  });
});
