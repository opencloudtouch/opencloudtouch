import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useDlnaSetup } from "../../../src/hooks/useDlna";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const apiError = (status: number, code: string) =>
  json({ type: "x", title: "x", status, detail: "raw", code }, status);

const LIST = {
  device_id: "dev1",
  servers: [
    {
      server_id: "s1",
      name: "Test NAS",
      state: "not_enabled",
      server_known: true,
      source_id: null,
    },
  ],
};

const fetchMock = vi.fn();
const calls = () => fetchMock.mock.calls.map((c) => `${c[1]?.method ?? "GET"} ${String(c[0])}`);

function wrapper() {
  const client = new QueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("useDlnaSetup", () => {
  it("loads the servers of the speaker", async () => {
    fetchMock.mockResolvedValue(json(LIST));
    const { result } = renderHook(() => useDlnaSetup("dev1"), { wrapper: wrapper() });
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.servers).toHaveLength(1));
    expect(result.current.error).toBeNull();
    expect(calls()).toEqual(["GET /api/dlna/native?device_id=dev1"]);
  });

  it("does nothing without a device id", () => {
    const { result } = renderHook(() => useDlnaSetup(undefined), { wrapper: wrapper() });
    expect(result.current.isLoading).toBe(false);
    expect(result.current.servers).toBeUndefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("503 device_unreachable is 'unreachable', any other failure 'network'", async () => {
    fetchMock.mockResolvedValue(apiError(503, "device_unreachable"));
    const first = renderHook(() => useDlnaSetup("dev1"), { wrapper: wrapper() });
    await waitFor(() => expect(first.result.current.error).toBe("unreachable"));

    fetchMock.mockRejectedValue(new TypeError("offline"));
    const second = renderHook(() => useDlnaSetup("dev1"), { wrapper: wrapper() });
    await waitFor(() => expect(second.result.current.error).toBe("network"));
  });

  it("setup PUTs, returns the state and reloads the list", async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) =>
      init?.method === "PUT" ? json({ server_id: "s1", state: "ready" }) : json(LIST)
    );
    const { result } = renderHook(() => useDlnaSetup("dev1"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.servers).toBeDefined());

    let state;
    await act(async () => {
      state = await result.current.setup("s1");
    });
    expect(state).toBe("ready");
    expect(calls()).toContain("PUT /api/dlna/native/dev1/servers/s1");
    await waitFor(() => expect(calls().filter((c) => c.startsWith("GET")).length).toBe(2));
  });

  it("a failed setup rejects with the API code and still reloads", async () => {
    fetchMock.mockImplementation(async (_url: string, init?: RequestInit) =>
      init?.method === "PUT" ? apiError(502, "dlna_native_setup_failed") : json(LIST)
    );
    const { result } = renderHook(() => useDlnaSetup("dev1"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.servers).toBeDefined());

    await expect(result.current.setup("s1")).rejects.toMatchObject({
      code: "dlna_native_setup_failed",
    });
    await waitFor(() => expect(calls().filter((c) => c.startsWith("GET")).length).toBe(2));
  });

  it("slots reads the affected presets; remove sends force and reloads", async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (init?.method === "DELETE") return json({ affected_slots: [2] });
      if (String(url).endsWith("/presets"))
        return json({ slots: [{ preset_number: 2, name: "Best Of" }] });
      return json(LIST);
    });
    const { result } = renderHook(() => useDlnaSetup("dev1"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.servers).toBeDefined());

    expect(await result.current.slots("s1")).toEqual([{ preset_number: 2, name: "Best Of" }]);
    await act(async () => {
      await result.current.remove("s1", true);
    });
    expect(calls()).toContain("DELETE /api/dlna/native/dev1/servers/s1?force=true");
    await result.current.remove("s1", false).catch(() => undefined);
    expect(calls()).toContain("DELETE /api/dlna/native/dev1/servers/s1");
  });

  it("remove rejects with the code of a 409", async () => {
    fetchMock.mockImplementation(async (_url: string, init?: RequestInit) =>
      init?.method === "DELETE" ? apiError(409, "dlna_native_in_use") : json(LIST)
    );
    const { result } = renderHook(() => useDlnaSetup("dev1"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.servers).toBeDefined());
    await expect(result.current.remove("s1", false)).rejects.toMatchObject({
      code: "dlna_native_in_use",
    });
  });
});
