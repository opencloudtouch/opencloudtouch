import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { createQueryWrapper, createTestQueryClient } from "../../utils/reactQueryTestUtils";
import {
  useDisableNativeServer,
  useDlnaFolder,
  useDlnaObjectPath,
  useDlnaServers,
  useEnableNativeServer,
  useNativeServers,
} from "../../../src/hooks/useDlna";
import * as api from "../../../src/api/dlna";

vi.mock("../../../src/api/dlna");

const server: api.NativeServer = {
  server_id: "s",
  name: "N",
  state: "ready",
  discovered: true,
  host: null,
};
const list: api.NativeServerList = {
  servers: [],
  migration_failed: false,
  migration_reason: null,
};

describe("useDlna", () => {
  beforeEach(() => vi.resetAllMocks());

  it("useNativeServers refetches on enable", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list);
    vi.mocked(api.enableNativeServer).mockResolvedValue(server);
    const wrapper = createQueryWrapper(createTestQueryClient());
    const native = renderHook(() => useNativeServers("d"), { wrapper });
    await waitFor(() => expect(native.result.current.isSuccess).toBe(true));
    expect(api.getNativeServers).toHaveBeenCalledTimes(1);

    const enable = renderHook(() => useEnableNativeServer("d"), { wrapper });
    await act(() => enable.result.current.mutateAsync("s"));
    await waitFor(() => expect(api.getNativeServers).toHaveBeenCalledTimes(2));
    expect(api.enableNativeServer).toHaveBeenCalledWith("d", "s");
  });

  it("useDisableNativeServer passes force and refetches", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list);
    vi.mocked(api.disableNativeServer).mockResolvedValue(undefined);
    const wrapper = createQueryWrapper(createTestQueryClient());
    const native = renderHook(() => useNativeServers("d"), { wrapper });
    await waitFor(() => expect(native.result.current.isSuccess).toBe(true));

    const disable = renderHook(() => useDisableNativeServer("d"), { wrapper });
    await act(() => disable.result.current.mutateAsync({ serverId: "s", force: true }));
    expect(api.disableNativeServer).toHaveBeenCalledWith("d", "s", true);
    await waitFor(() => expect(api.getNativeServers).toHaveBeenCalledTimes(2));
  });

  it("useDlnaServers and useDlnaObjectPath load live; the root path is skipped", async () => {
    vi.mocked(api.getDlnaServers).mockResolvedValue([{ id: "s" }]);
    vi.mocked(api.getDlnaObjectPath).mockResolvedValue({
      server_id: "s",
      server_name: "N",
      object_id: "o",
      title: "T",
      is_container: true,
      path: [],
    });
    const wrapper = createQueryWrapper(createTestQueryClient());
    const servers = renderHook(() => useDlnaServers(), { wrapper });
    const path = renderHook(() => useDlnaObjectPath("s", "o"), { wrapper });
    renderHook(() => useDlnaObjectPath("s", "0"), { wrapper });
    await waitFor(() => expect(servers.result.current.data).toEqual([{ id: "s" }]));
    await waitFor(() => expect(path.result.current.isSuccess).toBe(true));
    expect(api.getDlnaObjectPath).toHaveBeenCalledTimes(1);
  });

  it("useDlnaFolder pages by has_more", async () => {
    vi.mocked(api.browseDlna).mockResolvedValueOnce({
      server_id: "s",
      object_id: "0",
      items: [],
      starting_index: 0,
      number_returned: 50,
      total_matches: null,
      next_index: 50,
      has_more: true,
    });
    const wrapper = createQueryWrapper(createTestQueryClient());
    const folder = renderHook(() => useDlnaFolder("s", "0"), { wrapper });
    await waitFor(() => expect(folder.result.current.isSuccess).toBe(true));
    expect(folder.result.current.hasNextPage).toBe(true);
    expect(api.browseDlna).toHaveBeenCalledWith("s", "0", 0, undefined, expect.anything());
  });
});
