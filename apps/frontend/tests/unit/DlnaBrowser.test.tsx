import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DlnaBrowser, { type DlnaSession } from "../../src/components/dlna/DlnaBrowser";
import { coverBlocked } from "../../src/components/dlna/cover";
import type { DlnaItem } from "../../src/api/dlna";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const apiError = (status: number, code: string) =>
  json({ type: "dlna", title: "x", status, detail: "raw backend text", code }, status);

const track = (id: string, extra: Partial<DlnaItem> = {}): DlnaItem => ({
  id,
  parent_id: "0",
  title: `Track ${id}`,
  is_container: false,
  ...extra,
});
const folder = (id: string, title = `Folder ${id}`): DlnaItem => ({
  id,
  parent_id: "0",
  title,
  is_container: true,
});

/** Answers the browse endpoint from a map of object id -> all entries (paged by starting_index / requested_count). */
function tree(entries: Record<string, DlnaItem[]>, shortPages = false) {
  return (url: string) => {
    const u = new URL(url, "http://x");
    const all = entries[u.searchParams.get("object_id") ?? "0"];
    if (!all) return apiError(404, "dlna_object_not_found");
    const start = Number(u.searchParams.get("starting_index"));
    const count = shortPages ? 3 : Number(u.searchParams.get("requested_count"));
    const items = all.slice(start, start + count);
    return json({
      server_id: "srv",
      object_id: u.searchParams.get("object_id"),
      items,
      starting_index: start,
      number_returned: items.length,
      total_matches: null,
      next_index: start + items.length,
      has_more: start + items.length < all.length,
    });
  };
}

type Handler = (url: string) => Response | Promise<Response>;
const fetchMock = vi.fn();
const NAS = {
  id: "srv",
  name: "Living Room NAS",
  location: "http://10.0.0.5/d.xml",
  control_url: "c",
};

/** Routes /servers to `servers` and everything else to the browse handler. */
function serve(browse: Handler, servers: unknown[] = [NAS]) {
  fetchMock.mockImplementation(async (url: string) =>
    String(url).includes("/browse") ? browse(String(url)) : json(servers)
  );
}
const moreButton = () => document.querySelector<HTMLElement>(".dl-more button")!;
const browseCalls = () =>
  fetchMock.mock.calls.map((c) => String(c[0])).filter((u) => u.includes("/browse"));

const slot = (item: DlnaItem, { disabled, busy }: { disabled: boolean; busy: boolean }) => (
  <button type="button" disabled={disabled} aria-busy={busy || undefined}>
    {`Use ${item.title}`}
  </button>
);

function renderBrowser(props: Partial<React.ComponentProps<typeof DlnaBrowser>> = {}) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <DlnaBrowser renderRowAction={slot} {...props} />
    </QueryClientProvider>
  );
}

const openServer = async () => {
  fireEvent.click(await screen.findByRole("button", { name: "Open server “Living Room NAS”" }));
  await screen.findByRole("heading", { name: "Living Room NAS" });
};

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("DlnaBrowser: server list", () => {
  it("announces the scan and lists the servers by name only", async () => {
    serve(tree({ "0": [] }), [
      NAS,
      { id: "b", name: "Garage", location: "http://10.0.0.6/", control_url: "c" },
    ]);
    renderBrowser();

    expect(screen.getAllByText("Looking for media servers …").length).toBeGreaterThan(0);
    const list = await screen.findByRole("list", { name: "Media servers found" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("Living Room NAS")).toBeInTheDocument();
    expect(screen.getByText("Garage")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("10.0.0");
    expect(document.querySelector(".dl-sr")).toHaveTextContent("2 media servers found");
  });

  it("shows an empty state and repeats the scan on refresh", async () => {
    serve(tree({ "0": [] }), []);
    renderBrowser();

    expect(
      await screen.findByText("No media servers found", { selector: "h4" })
    ).toBeInTheDocument();
    serve(tree({ "0": [] }), [NAS]);
    fireEvent.click(screen.getByRole("button", { name: /Search again/ }));
    expect(await screen.findByText("Living Room NAS")).toBeInTheDocument();
  });

  it("lists a single server (no auto-skip)", async () => {
    serve(tree({ "0": [] }));
    renderBrowser();
    expect(await screen.findByText("Living Room NAS")).toBeInTheDocument();
    expect(browseCalls()).toHaveLength(0);
  });

  it("offers a retry when the scan fails and shows no raw backend text", async () => {
    fetchMock.mockResolvedValue(apiError(500, "boom"));
    renderBrowser();
    expect(await screen.findByText("Could not load", { selector: "h4" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("raw backend text");
  });

  it("cancelling a slow scan aborts it", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | null | undefined;
    fetchMock.mockImplementation((_u: string, init?: RequestInit) => {
      signal = init?.signal;
      return new Promise((_, reject) =>
        signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))
      );
    });
    renderBrowser();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5100);
    });
    expect(screen.getByText(/taking longer than usual/)).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    });
    expect(signal?.aborted).toBe(true);
    expect(screen.getByText("No media servers found", { selector: "h4" })).toBeInTheDocument();
  });
});

describe("DlnaBrowser: folders and breadcrumb", () => {
  const root = [folder("a", "Albums"), track("t1")];
  const entries = { "0": root, a: [folder("b", "Rock"), track("t2")], b: [track("t3")] };

  it("navigates with breadcrumb, back and crumbs, browsing only the target folder", async () => {
    serve(tree(entries));
    const onSessionChange = vi.fn();
    renderBrowser({ onSessionChange });
    await openServer();

    fireEvent.click(await screen.findByRole("button", { name: "Open folder “Albums”" }));
    await screen.findByRole("heading", { name: "Albums" });
    const nav = screen.getByRole("navigation", { name: "Path" });
    expect(within(nav).getByText("Albums").closest("[aria-current]")).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(within(nav).getByRole("button", { name: "Living Room NAS" })).toBeInTheDocument();
    expect(onSessionChange).toHaveBeenLastCalledWith({
      serverId: "srv",
      serverName: "Living Room NAS",
      stack: [{ object_id: "a", title: "Albums" }],
    });

    fireEvent.click(await screen.findByRole("button", { name: "Open folder “Rock”" }));
    await screen.findByRole("heading", { name: "Rock" });
    const before = browseCalls().length;

    fireEvent.click(screen.getByRole("button", { name: /^Back$/ }));
    await screen.findByRole("heading", { name: "Albums" });
    // the listing is younger than the 45 s stale time: answered by the query cache
    expect(browseCalls().length).toBe(before);
    // focus returns to the row that was opened
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Open folder “Rock”" })).toHaveFocus()
    );

    fireEvent.click(
      within(screen.getByRole("navigation", { name: "Path" })).getByRole("button", {
        name: "Living Room NAS",
      })
    );
    await screen.findByRole("heading", { name: "Living Room NAS" });
    expect(onSessionChange).toHaveBeenLastCalledWith({
      serverId: "srv",
      serverName: "Living Room NAS",
      stack: [],
    });

    fireEvent.click(screen.getByRole("button", { name: /^Back$/ })); // from the root to the server list
    expect(await screen.findByRole("heading", { name: "Media servers" })).toBeInTheDocument();
    expect(onSessionChange).toHaveBeenLastCalledWith(null);
  });

  it("collapses a long path and expands it in place", async () => {
    const session: DlnaSession = {
      serverId: "srv",
      serverName: "NAS",
      stack: ["a", "b", "c", "d"].map((id) => ({ object_id: id, title: `F${id}` })),
    };
    serve(tree({ d: [track("t")] }));
    renderBrowser({ initialSession: session });
    await screen.findByRole("heading", { name: "Fd" });

    fireEvent.click(screen.getByRole("button", { name: "Show 2 folders in between" }));
    const nav = screen.getByRole("navigation", { name: "Path" });
    expect(within(nav).getAllByRole("listitem")).toHaveLength(5);
    expect(within(nav).getByRole("button", { name: "NAS" })).toHaveFocus();
  });

  it("moves focus to the heading after entering a folder", async () => {
    serve(tree(entries));
    renderBrowser();
    await openServer();
    expect(screen.getByRole("heading", { name: "Living Room NAS" })).toHaveFocus();
  });

  it("shows covers, a placeholder without cover or after a load error, never a broken image", async () => {
    serve(
      tree({
        "0": [
          track("c1", { album_art_url: "http://nas.local/c1.jpg" }),
          track("c2"),
          track("c3", { album_art_url: "http://nas.local/c3.jpg" }),
        ],
      })
    );
    const { container } = renderBrowser({
      initialSession: { serverId: "srv", serverName: "NAS", stack: [] },
    });
    await screen.findByText("Track c1");
    expect(container.querySelectorAll("img")).toHaveLength(2);
    expect(container.querySelectorAll(".dl-cover--ph")).toHaveLength(1);

    fireEvent.error(container.querySelectorAll("img")[0]);
    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(container.querySelectorAll(".dl-cover--ph")).toHaveLength(2);
  });

  it("renders titles as text, never as HTML, and shows artist, album and duration", async () => {
    serve(
      tree({
        "0": [
          track("x", {
            title: "<b>bold</b> &lt;script&gt;",
            artist: "Ann",
            album: "LP",
            duration: "0:03:10",
          }),
        ],
      })
    );
    const { container } = renderBrowser({
      initialSession: { serverId: "srv", serverName: "NAS", stack: [] },
    });
    expect(await screen.findByText("<b>bold</b> &lt;script&gt;")).toBeInTheDocument();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText("Ann · LP · 0:03:10")).toBeInTheDocument();
  });
});

describe("DlnaBrowser: rows and actions", () => {
  const session: DlnaSession = { serverId: "srv", serverName: "NAS", stack: [] };

  it("folder rows offer open, the action and the folder note; track rows have no open action", async () => {
    serve(tree({ "0": [folder("a", "Albums"), track("t1")] }));
    renderBrowser({ initialSession: session });

    expect(
      await screen.findByRole("button", { name: "Open folder “Albums”" })
    ).toHaveAccessibleDescription("Plays as a folder");
    expect(screen.getByRole("button", { name: "Use Albums" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use Track t1" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Open folder “Track/ })).toBeNull();
  });

  it("disables every action while one runs and shows the busy row", async () => {
    serve(tree({ "0": [folder("a", "Albums"), track("t1")] }));
    renderBrowser({ initialSession: session, busyItemId: "t1", busyLabel: "Saving preset 2 …" });

    expect(await screen.findByRole("button", { name: "Use Track t1" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Use Track t1" })).toHaveAttribute(
      "aria-busy",
      "true"
    );
    expect(screen.getByRole("button", { name: "Use Albums" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Open folder “Albums”" })).toBeDisabled();
    expect(screen.getByText("Saving preset 2 …")).toBeInTheDocument();
  });

  it("works outside the preset dialog with its own action and banner", async () => {
    serve(tree({ "0": [track("t1")] }));
    const onPick = vi.fn();
    renderBrowser({
      initialSession: session,
      banner: <p>custom banner</p>,
      renderRowAction: (item) => (
        <button type="button" onClick={() => onPick(item.id)}>
          Queue
        </button>
      ),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Queue" }));
    expect(onPick).toHaveBeenCalledWith("t1");
    expect(screen.getByText("custom banner")).toBeInTheDocument();
  });
});

describe("DlnaBrowser: paging and filter", () => {
  const session: DlnaSession = { serverId: "srv", serverName: "NAS", stack: [] };
  const tracks = (n: number) => Array.from({ length: n }, (_, i) => track(`t${i}`));

  it("loads 120 tracks in three pages, focuses the first new row and ends by has_more", async () => {
    serve(tree({ "0": tracks(120) }));
    renderBrowser({ initialSession: session });

    expect(
      await screen.findByText("50 entries loaded, more available", { selector: ".dl-count" })
    ).toBeInTheDocument();
    fireEvent.click(moreButton());
    expect(
      await screen.findByText("100 entries loaded, more available", { selector: ".dl-count" })
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Track t50").closest("li")).toHaveFocus());

    fireEvent.click(moreButton());
    expect(
      await screen.findByText("120 entries loaded", { selector: ".dl-count" })
    ).toBeInTheDocument();
    expect(document.querySelector(".dl-more")).toBeNull();
    expect(screen.getByText("End of list. All entries are loaded.")).toBeInTheDocument();
    expect(browseCalls()[2]).toContain("starting_index=100");
  });

  it("does not claim completeness after short pages with has_more: loads 3 more by itself, then offers the button", async () => {
    serve(tree({ "0": tracks(30) }, true)); // pages of 3
    renderBrowser({ initialSession: session });

    await waitFor(() => expect(browseCalls()).toHaveLength(4));
    expect(
      await screen.findByText("12 entries loaded, more available", { selector: ".dl-count" })
    ).toBeInTheDocument();
    expect(moreButton()).toBeInTheDocument();
    expect(screen.queryByText(/End of list/)).toBeNull();
    await new Promise((r) => setTimeout(r, 30));
    expect(browseCalls()).toHaveLength(4);
  });

  it("explains an empty page that still has more", async () => {
    serve(() =>
      json({
        server_id: "srv",
        object_id: "0",
        items: [],
        starting_index: 0,
        number_returned: 0,
        total_matches: null,
        next_index: 0,
        has_more: true,
      })
    );
    renderBrowser({ initialSession: session });
    await waitFor(() => expect(moreButton()).toBeInTheDocument());
    expect(
      screen.getByText("This section had no entries, but more are available.")
    ).toBeInTheDocument();
  });

  it("shows an empty folder", async () => {
    serve(tree({ "0": [] }));
    renderBrowser({ initialSession: session });
    expect(await screen.findByText("This folder is empty.")).toBeInTheDocument();
  });

  it("filters the loaded entries by title, says so, and restores them when cleared", async () => {
    serve(
      tree({
        "0": [
          track("1", { title: "Blue Sky" }),
          track("2", { title: "red moon" }),
          ...tracks(60).slice(3),
        ],
      })
    );
    renderBrowser({ initialSession: session });
    await screen.findByText("Blue Sky");

    const input = screen.getByRole("searchbox", { name: "Filter loaded entries" });
    expect(input).toHaveAccessibleDescription(/more are available/);
    fireEvent.change(input, { target: { value: "MOON" } });
    expect(screen.getByText("red moon")).toBeInTheDocument();
    expect(screen.queryByText("Blue Sky")).toBeNull();
    expect(screen.getByText(/1 of 50 loaded entries/)).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "zzz" } });
    expect(screen.getByText("No matches among the loaded entries.")).toBeInTheDocument();
    expect(moreButton()).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear filter" }));
    expect(screen.getByText("Blue Sky")).toBeInTheDocument();
    expect(screen.getByText("red moon")).toBeInTheDocument();
  });
});

describe("DlnaBrowser: error and slow states", () => {
  const session: DlnaSession = {
    serverId: "srv",
    serverName: "NAS",
    stack: [{ object_id: "a", title: "Albums" }],
  };

  it.each([
    [404, "dlna_server_not_found"],
    [502, "dlna_upstream_error"],
  ])(
    "falls back to the server list while restoring when browse says %i %s",
    async (status, code) => {
      serve(() => apiError(status, code));
      renderBrowser({ initialSession: { ...session, stack: [] } });
      expect(
        await screen.findByText(/The media server you used last is no longer reachable/)
      ).toBeInTheDocument();
      expect(document.body.textContent).not.toContain("raw backend text");
    }
  );

  it("says the folder is missing, not the server, when the saved folder is gone and the path is empty", async () => {
    serve(() => apiError(404, "dlna_object_not_found"));
    const onSessionChange = vi.fn();
    renderBrowser({ initialSession: { ...session, stack: [] }, onSessionChange });

    expect(
      await screen.findByText(
        "The folder you opened last is no longer available. Pick a server from the list."
      )
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("no longer reachable");
    expect(onSessionChange).toHaveBeenLastCalledWith(null);
  });

  it("shows offline with retry and back to servers when it happens after navigating", async () => {
    let fail = false;
    serve((url) =>
      fail
        ? apiError(502, "dlna_upstream_error")
        : tree({ "0": [folder("a", "Albums")], a: [] })(url)
    );
    renderBrowser();
    await openServer();
    fail = true;
    fireEvent.click(await screen.findByRole("button", { name: "Open folder “Albums”" }));

    expect(await screen.findByText("Server not reachable", { selector: "h4" })).toBeInTheDocument();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(await screen.findByText("This folder is empty.")).toBeInTheDocument();
  });

  it("shows the slow-server state for a timeout and the generic state for a network failure", async () => {
    let next: Handler = () => apiError(504, "dlna_server_timeout");
    serve((u) => next(u));
    renderBrowser({ initialSession: session });
    expect(
      await screen.findByText("The server did not answer in time", { selector: "h4" })
    ).toBeInTheDocument();

    next = () => {
      throw new TypeError("Failed to fetch");
    };
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(await screen.findByText("Could not load", { selector: "h4" })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Back" }).at(-1)!);
    expect(await screen.findByRole("heading", { name: "NAS" })).toBeInTheDocument();
  });

  it("moves one level up with a notice when a folder is gone", async () => {
    serve((u) =>
      u.includes("object_id=b")
        ? apiError(404, "dlna_object_not_found")
        : tree({ "0": [folder("a")], a: [folder("b")] })(u)
    );
    renderBrowser();
    await openServer();
    fireEvent.click(await screen.findByRole("button", { name: "Open folder “Folder a”" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open folder “Folder b”" }));

    expect(await screen.findByText(/You now see the level above/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Folder a" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notice" }));
    expect(screen.queryByText(/You now see the level above/)).toBeNull();
  });

  it("shows the slow hint after 5 s and cancel leaves the folder and aborts the request", async () => {
    vi.useFakeTimers();
    const signals: (AbortSignal | null | undefined)[] = [];
    fetchMock.mockImplementation((_u: string, init?: RequestInit) => {
      signals.push(init?.signal);
      return new Promise((_, reject) =>
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError"))
        )
      );
    });
    renderBrowser({ initialSession: session });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5100);
    });
    expect(screen.getByText("The server is slow to answer")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    });
    expect(signals[0]?.aborted).toBe(true);
    expect(screen.getByRole("heading", { name: "NAS" })).toBeInTheDocument();
  });
});

describe("DlnaBrowser: session restore", () => {
  const session: DlnaSession = {
    serverId: "srv",
    serverName: "NAS",
    stack: [
      { object_id: "a", title: "Albums" },
      { object_id: "b", title: "Rock" },
    ],
  };

  it("browses only the stored top folder and shows the stored breadcrumb", async () => {
    serve(tree({ b: [track("t")] }));
    renderBrowser({ initialSession: session });

    expect(await screen.findByRole("heading", { name: "Rock" })).toBeInTheDocument();
    expect(browseCalls()).toHaveLength(1);
    expect(browseCalls()[0]).toContain("object_id=b");
    expect(
      within(screen.getByRole("navigation", { name: "Path" })).getByText("Albums")
    ).toBeInTheDocument();
  });

  it("falls back to the server root with a notice when the folder is gone", async () => {
    serve(tree({ "0": [track("r")] }));
    const onSessionChange = vi.fn();
    renderBrowser({ initialSession: session, onSessionChange });

    expect(
      await screen.findByText(
        "The folder you opened last is no longer available. You see the start of “NAS”."
      )
    ).toBeInTheDocument();
    expect(await screen.findByText("Track r")).toBeInTheDocument();
    expect(onSessionChange).toHaveBeenLastCalledWith({ ...session, stack: [] });
  });

  it("falls back to the server list with a notice when the server is gone", async () => {
    serve(() => apiError(404, "dlna_server_not_found"));
    const onSessionChange = vi.fn();
    renderBrowser({ initialSession: session, onSessionChange });

    expect(
      await screen.findByText(/The media server you used last is no longer reachable/)
    ).toBeInTheDocument();
    expect(await screen.findByText("Living Room NAS")).toBeInTheDocument();
    expect(onSessionChange).toHaveBeenLastCalledWith(null);
  });
});

describe("cover URLs", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("blocks missing covers and http covers on an https page only", () => {
    expect(coverBlocked(null)).toBe(true);
    expect(coverBlocked("http://nas/c.jpg")).toBe(false); // the test page is http:
    vi.stubGlobal("location", { protocol: "https:" });
    expect(coverBlocked("http://nas/c.jpg")).toBe(true);
    expect(coverBlocked("https://nas/c.jpg")).toBe(false);
  });
});

describe("DlnaBrowser: initialFocus and initialNotice", () => {
  const session: DlnaSession = {
    serverId: "srv",
    serverName: "Living Room NAS",
    stack: [{ object_id: "f1", title: "Folder f1" }],
  };

  it("focuses the given row once the first folder is listed", async () => {
    serve(tree({ f1: [track("a"), track("b")] }));
    renderBrowser({ initialSession: session, initialFocus: "b" });
    await screen.findByText("Track b");
    await waitFor(() => expect(document.querySelector('[data-rid="b"]')).toHaveFocus());
  });

  it("falls back to the heading when the row is not in the listing", async () => {
    serve(tree({ f1: [track("a")] }));
    renderBrowser({ initialSession: session, initialFocus: "missing" });
    await screen.findByText("Track a");
    await waitFor(() => expect(screen.getByRole("heading", { level: 3 })).toHaveFocus());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the initial notice on the first render", async () => {
    serve(tree({ "0": [track("a")] }));
    renderBrowser({
      initialSession: { ...session, stack: [] },
      initialNotice: { key: "editFolderGone", vars: { server: "Living Room NAS" } },
    });
    expect(screen.getByText(/item is no longer available/)).toBeInTheDocument();
    await screen.findByText("Track a");
    expect(screen.getByText(/item is no longer available/)).toBeInTheDocument();
  });
});
