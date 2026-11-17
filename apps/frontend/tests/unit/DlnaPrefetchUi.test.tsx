import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DlnaBrowser from "../../src/components/dlna/DlnaBrowser";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const folder = (id: string) => ({
  id,
  parent_id: "0",
  title: `Folder ${id}`,
  is_container: true,
});
const page = (ids: string[], extra: Record<string, unknown> = {}) => ({
  server_id: "srv",
  object_id: "0",
  items: ids.map(folder),
  starting_index: 0,
  number_returned: ids.length,
  total_matches: null,
  next_index: ids.length,
  has_more: false,
  ...extra,
});

const fetchMock = vi.fn();
const objectIds = () =>
  fetchMock.mock.calls.map((c) => new URL(String(c[0]), "http://x").searchParams.get("object_id"));
const session = { serverId: "srv", serverName: "NAS", stack: [] };
const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
const folderButton = (id: string) =>
  screen.getByRole("button", { name: `Open folder “Folder ${id}”` });

function renderRoot(rootExtra: Record<string, unknown> = {}) {
  fetchMock.mockImplementation(async (url: string) => {
    const id = new URL(url, "http://x").searchParams.get("object_id");
    return json(id === "0" ? page(["a", "b"], rootExtra) : page([], { object_id: id }));
  });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <DlnaBrowser renderRowAction={() => null} initialSession={session} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("DlnaBrowser: prefetch on intent", () => {
  it("prefetches on mouse hover and a click reuses it (one request for the folder)", async () => {
    renderRoot();
    await advance(0);
    fireEvent.pointerEnter(folderButton("a"), { pointerType: "mouse" });
    await advance(200);
    expect(objectIds()).toEqual(["0", "a"]);
    fireEvent.click(folderButton("a"));
    await advance(0);
    expect(objectIds()).toEqual(["0", "a"]);
  });

  it("does nothing for touch hover, a short hover or mere visibility", async () => {
    renderRoot();
    await advance(0);
    fireEvent.pointerEnter(folderButton("a"), { pointerType: "touch" });
    fireEvent.pointerEnter(folderButton("b"), { pointerType: "mouse" });
    await advance(100);
    fireEvent.pointerLeave(folderButton("b"));
    await advance(1000);
    expect(objectIds()).toEqual(["0"]);
  });

  it("prefetches on pointer down at once and keeps keyboard focus below the dwell silent", async () => {
    renderRoot();
    await advance(0);
    fireEvent.focus(folderButton("b"));
    await advance(1000); // jsdom does not match :focus-visible: no speculation
    expect(objectIds()).toEqual(["0"]);
    fireEvent.pointerDown(folderButton("a"));
    await advance(0);
    expect(objectIds()).toEqual(["0", "a"]);
  });

  it("keeps the row elements (and focus) when a follow-up inserts an item above", async () => {
    const stale = { cached: true, stale: true, revalidating: true };
    fetchMock
      .mockResolvedValueOnce(json(page(["a", "b"], stale)))
      .mockResolvedValueOnce(json(page(["x", "a", "b"])));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <DlnaBrowser renderRowAction={() => null} initialSession={session} />
      </QueryClientProvider>
    );
    await advance(0);
    const rowA = folderButton("a");
    rowA.focus();
    await advance(3000);
    expect(folderButton("x")).toBeInTheDocument();
    expect(folderButton("a")).toBe(rowA);
    expect(rowA).toHaveFocus();
  });
});

describe("DlnaBrowser: cached root", () => {
  it("shows the stale root at once with a quiet updating note and an operable refresh", async () => {
    renderRoot({
      cached: true,
      stale: true,
      revalidating: true,
      cached_at: "2026-01-01T00:00:00Z",
    });
    await advance(0);
    expect(folderButton("a")).toBeInTheDocument();
    expect(document.querySelector(".dl-note")).toHaveTextContent("Updating the list …");
    expect(objectIds()).toEqual(["0"]);

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await advance(0);
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain("refresh=true");
    vi.useRealTimers(); // axe uses timers
    const { default: axe } = await import("axe-core");
    const result = await axe.run(document.body, {
      rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });

  it("shows 'may be outdated' when the backend is not revalidating", async () => {
    renderRoot({ cached: true, stale: true, revalidating: false });
    await advance(0);
    expect(document.querySelector(".dl-note")).toHaveTextContent("This list may be outdated.");
  });
});
