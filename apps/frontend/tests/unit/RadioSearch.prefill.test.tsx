import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RadioSearch from "../../src/components/RadioSearch";
import { loadDlnaSession, storeDlnaSession } from "../../src/components/dlna/session";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const err = (status: number, code: string) =>
  json({ type: "about:blank", title: code, status, detail: code, code }, status);

const NAS = { id: "srv", name: "Living Room NAS", location: "l", control_url: "c" };
const ref = { server_id: "srv", object_id: "t2" };
const PATH = {
  server_id: "srv",
  server_name: "Living Room NAS",
  object_id: "t2",
  title: "Song",
  is_container: false,
  path: [
    { object_id: "a", title: "Albums" },
    { object_id: "b", title: "Best Of" },
  ],
};
const listing = {
  server_id: "srv",
  object_id: "b",
  items: [
    { id: "t1", parent_id: "b", title: "First", is_container: false },
    { id: "t2", parent_id: "b", title: "Song", is_container: false },
  ],
  starting_index: 0,
  number_returned: 2,
  total_matches: null,
  next_index: 2,
  has_more: false,
};

const fetchMock = vi.fn();
const calls = (needle: string) =>
  fetchMock.mock.calls.filter(([u]) => String(u).includes(needle)).length;

type Props = React.ComponentProps<typeof RadioSearch>;
const dlnaPreset = { station_name: "Song", source: "DLNA", dlna: ref };
function ui(props: Partial<Props>) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <RadioSearch isOpen presetNumber={3} onStationSelect={vi.fn()} {...props} />
    </QueryClientProvider>
  );
}
const renderSearch = (props: Partial<Props> = {}) => render(ui(props));

function route(path: () => Response | Promise<Response>) {
  fetchMock.mockImplementation(async (url: string) => {
    const u = String(url);
    if (u.includes("/objects/path")) return path();
    if (u.includes("/browse")) return json(listing);
    if (u.includes("/api/dlna/servers")) return json([NAS]);
    return json({ stations: [], has_more: false });
  });
}

beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  route(() => json(PATH));
});
afterEach(() => vi.unstubAllGlobals());

describe("RadioSearch: pre-filled from the saved preset", () => {
  it("empty slot: default provider, no request", () => {
    renderSearch({ existingPreset: null });
    expect(screen.getByRole("searchbox")).toHaveValue("");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("radio preset: field holds the name, one search runs, searchType is reset to name", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderSearch({
        existingPreset: {
          station_name: " Jazz FM ",
          station_uuid: "123e4567-e89b-12d3-a456-426614174000",
          source: "LOCAL_INTERNET_RADIO",
        },
      });
      expect(screen.getByRole("searchbox")).toHaveValue("Jazz FM");
      expect(screen.getByRole("button", { name: "RadioBrowser" })).toHaveAttribute(
        "aria-pressed",
        "true"
      );
      await waitFor(() => expect(calls("/api/radio/search")).toBe(1));
      expect(String(fetchMock.mock.calls[0][0])).toContain("search_type=name");
      expect(String(fetchMock.mock.calls[0][0])).toContain("provider=radiobrowser");
      expect(calls("/objects/path")).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a name shorter than 2 characters fills the field but sends no search", async () => {
    renderSearch({ existingPreset: { station_name: "A", source: "INTERNET_RADIO" } });
    expect(screen.getByRole("searchbox")).toHaveValue("A");
    await new Promise((r) => setTimeout(r, 600));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("manual preset: fields filled, no request", () => {
    renderSearch({
      existingPreset: {
        station_name: "My",
        station_uuid: "manual-1",
        station_url: "http://x/s",
        station_favicon: "http://x/f.png",
      },
    });
    expect(screen.getByLabelText("Enter stream URL...")).toHaveValue("http://x/s");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not reset the dialog when an equal preset object arrives, but for another slot", async () => {
    const preset = {
      station_name: "Jazz FM",
      station_uuid: "123e4567-e89b-12d3-a456-426614174000",
    };
    const { rerender } = renderSearch({ existingPreset: preset });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "typed" } });
    rerender(ui({ existingPreset: { ...preset } }));
    expect(screen.getByRole("searchbox")).toHaveValue("typed");
    rerender(ui({ existingPreset: { ...preset }, presetNumber: 4 }));
    expect(screen.getByRole("searchbox")).toHaveValue("Jazz FM");
  });
});

describe("RadioSearch: DLNA preset", () => {
  it("writes the resolved path to the session before the pane mounts and focuses the saved row", async () => {
    storeDlnaSession({ serverId: "old", serverName: "Old", stack: [] });
    renderSearch({ existingPreset: dlnaPreset });
    expect(screen.getByText("Loading folder …")).toBeInTheDocument();

    const row = await screen.findByText("Song");
    expect(loadDlnaSession()).toEqual({
      serverId: "srv",
      serverName: "Living Room NAS",
      stack: PATH.path,
    });
    expect(calls("/objects/path")).toBe(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain("object_id=t2");
    await waitFor(() => expect(row.closest("[data-rid]")).toHaveFocus());
    // folder filter is not pre-filled
    expect(screen.queryByDisplayValue("Song")).not.toBeInTheDocument();
  });

  it("sends the path request once per open, also under StrictMode and for an equal preset object", async () => {
    const { rerender } = render(<StrictMode>{ui({ existingPreset: dlnaPreset })}</StrictMode>);
    await screen.findByText("Song");
    rerender(<StrictMode>{ui({ existingPreset: { ...dlnaPreset } })}</StrictMode>);
    expect(calls("/objects/path")).toBe(1 + 1); // StrictMode runs the effect twice, the first is aborted
  });

  it("source DLNA without reference: server list, session cleared, no request, no notice", async () => {
    storeDlnaSession({ serverId: "old", serverName: "Old", stack: [] });
    renderSearch({ existingPreset: { station_name: "x", source: "DLNA", dlna: null } });
    await screen.findByRole("button", { name: "Open server “Living Room NAS”" });
    expect(loadDlnaSession()).toBeNull();
    expect(calls("/objects/path")).toBe(0);
    expect(screen.queryByRole("status", { name: "" })?.textContent ?? "").not.toMatch(/reachable/);
  });

  it("dlna_server_not_found: clears the session and shows the server list with the notice", async () => {
    storeDlnaSession({ serverId: "old", serverName: "Old", stack: [] });
    route(() => err(404, "dlna_server_not_found"));
    renderSearch({ existingPreset: dlnaPreset });
    await screen.findByText(/media server of this preset is not reachable/);
    expect(loadDlnaSession()).toBeNull();
    expect(
      await screen.findByRole("button", { name: "Open server “Living Room NAS”" })
    ).toBeVisible();
  });

  it("network error is treated as not reachable", async () => {
    route(() => Promise.reject(new TypeError("fetch failed")));
    renderSearch({ existingPreset: dlnaPreset });
    await screen.findByText(/media server of this preset is not reachable/);
    expect(loadDlnaSession()).toBeNull();
  });

  it("dlna_object_not_found: server root with the folder notice", async () => {
    route(() => err(404, "dlna_object_not_found"));
    renderSearch({ existingPreset: dlnaPreset });
    await screen.findByText(/item is no longer available. You see the start of “Living Room NAS”/);
    expect(loadDlnaSession()).toEqual({
      serverId: "srv",
      serverName: "Living Room NAS",
      stack: [],
    });
  });

  it.each([
    [502, "dlna_upstream_error"],
    [504, "dlna_server_timeout"],
  ])("%i %s with a listed server: server root with the path-failed notice", async (s, code) => {
    route(() => err(s, code));
    renderSearch({ existingPreset: dlnaPreset });
    await screen.findByText(/could not be read in time. You see the start of “Living Room NAS”/);
    expect(loadDlnaSession()?.stack).toEqual([]);
  });

  it("504 with the server missing from the list: server list with the not-reachable notice", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      String(url).includes("/objects/path")
        ? err(504, "dlna_server_timeout")
        : json([{ ...NAS, id: "other" }])
    );
    renderSearch({ existingPreset: dlnaPreset });
    await screen.findByText(/media server of this preset is not reachable/);
    expect(loadDlnaSession()).toBeNull();
  });

  it("offers Cancel after 5 seconds while the saved location resolves, and Cancel opens the server list", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      fetchMock.mockImplementation(async (url: string) =>
        String(url).includes("/objects/path") ? new Promise<Response>(() => {}) : json([NAS])
      );
      renderSearch({ existingPreset: dlnaPreset });
      expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
      await act(() => vi.advanceTimersByTimeAsync(5000));
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
      expect(
        await screen.findByRole("button", { name: "Open server “Living Room NAS”" })
      ).toBeVisible();
    } finally {
      vi.useRealTimers();
    }
  });

  it("switching mode while resolving aborts the request and a late answer writes nothing", async () => {
    let release!: (r: Response) => void;
    let signal: AbortSignal | undefined;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (!String(url).includes("/objects/path")) return Promise.resolve(json({ stations: [] }));
      signal = init?.signal ?? undefined;
      return new Promise<Response>((r) => (release = r));
    });
    renderSearch({ existingPreset: dlnaPreset });
    await waitFor(() => expect(signal).toBeDefined());
    fireEvent.click(screen.getByRole("button", { name: "RadioBrowser" }));
    expect(signal?.aborted).toBe(true);
    release(json(PATH));
    await new Promise((r) => setTimeout(r, 20));
    expect(loadDlnaSession()).toBeNull();
    expect(screen.getByRole("button", { name: "RadioBrowser" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });
});
