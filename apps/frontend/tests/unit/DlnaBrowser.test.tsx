import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { Profiler } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DlnaBrowser from "../../src/components/dlna/DlnaBrowser";
import { ApiError } from "../../src/api/types";
import * as api from "../../src/api/dlna";

vi.mock("../../src/api/dlna");

const folderItem = (id: string, title: string): api.DlnaItem => ({
  id,
  parent_id: "0",
  title,
  is_container: true,
});
const track = (id: string, title: string): api.DlnaItem => ({
  id,
  parent_id: "0",
  title,
  is_container: false,
});
const page = (
  items: api.DlnaItem[],
  has_more = false,
  next_index = items.length
): api.DlnaBrowsePage => ({
  server_id: "s1",
  object_id: "0",
  items,
  starting_index: 0,
  number_returned: items.length,
  total_matches: null,
  next_index,
  has_more,
});

/** Every committed list state, deduplicated: the row titles, "empty" or "none" (no list). */
let lists: string[] = [];
function recordList() {
  const ul = document.querySelector(".dlb-list");
  const titles = [...(ul?.querySelectorAll(".dlb-title") ?? [])].map((e) => e.textContent?.trim());
  let state = titles.join("|");
  if (!ul) state = document.querySelector(".dlb-empty") ? "empty" : "none";
  if (lists.at(-1) !== state) lists.push(state);
}

function setupWithContainer(props: Partial<React.ComponentProps<typeof DlnaBrowser>> = {}) {
  const onSelect = vi.fn();
  const client = new QueryClient();
  lists = [];
  const view = render(
    <QueryClientProvider client={client}>
      <Profiler id="browser" onRender={recordList}>
        <DlnaBrowser serverId="s1" serverName="Nas" onSelect={onSelect} {...props} />
      </Profiler>
    </QueryClientProvider>
  );
  return { onSelect, container: view.container };
}

const setup = (props: Partial<React.ComponentProps<typeof DlnaBrowser>> = {}) =>
  setupWithContainer(props).onSelect;

describe("DlnaBrowser", () => {
  afterEach(() => vi.unstubAllGlobals());

  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
  });

  it("opens root and shows folders and tracks", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(
      page([folderItem("f1", "Rock"), track("t1", "Song")])
    );
    setup();
    expect(await screen.findByRole("button", { name: "Open folder Rock" })).toBeInTheDocument();
    expect(screen.getByText("Song")).toBeInTheDocument();
    expect(api.browseDlna).toHaveBeenCalledWith("s1", "0", 0, undefined, expect.anything());
  });

  it("load more appends using has_more", async () => {
    vi.mocked(api.browseDlna)
      .mockResolvedValueOnce(page([track("t1", "One")], true, 1))
      .mockResolvedValueOnce(page([track("t1", "One"), track("t2", "Two")]));
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Load more" }));
    expect(await screen.findByText("Two")).toBeInTheDocument();
    expect(screen.getAllByText("One")).toHaveLength(1);
    expect(api.browseDlna).toHaveBeenLastCalledWith("s1", "0", 1, undefined, expect.anything());
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("loads the next page when the list end scrolls into view", async () => {
    let fire: () => void = () => {};
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb: IntersectionObserverCallback) {
          fire = () => cb([{ isIntersecting: true } as IntersectionObserverEntry], this as never);
        }
        observe() {}
        disconnect() {}
      }
    );
    let resolveNext: (p: api.DlnaBrowsePage) => void = () => {};
    vi.mocked(api.browseDlna)
      .mockResolvedValueOnce(page([track("t1", "One")], true, 1))
      .mockReturnValueOnce(new Promise((r) => (resolveNext = r)));
    setup();
    expect(await screen.findByText("One")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
    fire();
    expect(await screen.findByText("Loading folder")).toBeInTheDocument();
    resolveNext(page([track("t2", "Two")]));
    expect(await screen.findByText("Two")).toBeInTheDocument();
    expect(api.browseDlna).toHaveBeenLastCalledWith("s1", "0", 1, undefined, expect.anything());
  });

  it("stops loading on scroll after a failed page and offers the button instead", async () => {
    // Like a real observer: every observe() of a visible sentinel reports it at once.
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(private cb: IntersectionObserverCallback) {}
        observe() {
          this.cb([{ isIntersecting: true } as IntersectionObserverEntry], this as never);
        }
        disconnect() {}
      }
    );
    vi.mocked(api.browseDlna)
      .mockResolvedValueOnce(page([track("t1", "One")], true, 1))
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(page([track("t2", "Two")]));
    setup();
    expect(await screen.findByText("The folder could not be loaded.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load more" })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(api.browseDlna).toHaveBeenCalledTimes(2);
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("Two")).toBeInTheDocument();
    expect(screen.queryByText("The folder could not be loaded.")).not.toBeInTheDocument();
  });

  const twoLevels = () =>
    vi
      .mocked(api.browseDlna)
      .mockImplementation(async (_s, objectId) =>
        objectId === "f1" ? page([track("t1", "Inside")]) : page([folderItem("f1", "Rock")])
      );

  it("folder click requests the folder", async () => {
    twoLevels();
    const onPathChange = vi.fn();
    setup({ onPathChange });
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    expect(await screen.findByText("Inside")).toBeInTheDocument();
    expect(api.browseDlna).toHaveBeenCalledWith("s1", "f1", 0, undefined, expect.anything());
    expect(onPathChange).toHaveBeenLastCalledWith("f1");
  });

  it("opening a folder keeps the old list until the new one renders, without a path request", async () => {
    let resolveFolder: (p: api.DlnaBrowsePage) => void = () => {};
    vi.mocked(api.browseDlna).mockImplementation((_s, objectId) =>
      objectId === "f1"
        ? new Promise((r) => (resolveFolder = r))
        : Promise.resolve(page([folderItem("f1", "Rock")]))
    );
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    expect(screen.getByText("Rock", { selector: "[aria-current]" })).toHaveAttribute(
      "aria-current",
      "location"
    );
    resolveFolder(page([track("t1", "Inside")]));
    expect(await screen.findByText("Inside")).toBeInTheDocument();
    expect(lists).toEqual(["none", "Rock", "Inside"]);
    expect(api.getDlnaObjectPath).not.toHaveBeenCalled();
  });

  it("a start folder is browsed directly: the root list never shows", async () => {
    vi.mocked(api.getDlnaObjectPath).mockResolvedValue({
      server_id: "s1",
      server_name: "Nas",
      object_id: "p1",
      title: "Parent",
      is_container: true,
      path: [],
    });
    vi.mocked(api.browseDlna).mockImplementation(async (_s, objectId) =>
      objectId === "p1" ? page([track("t1", "Song")]) : page([folderItem("f1", "Rock")])
    );
    setup({ startObjectId: "p1", focusObjectId: "t1" });
    expect(await screen.findByText("Parent", { selector: "[aria-current]" })).toHaveAttribute(
      "aria-current",
      "location"
    );
    expect(screen.getByRole("button", { name: "Select Song" })).toHaveFocus();
    expect(lists).toEqual(["none", "Song"]);
    expect(api.browseDlna).not.toHaveBeenCalledWith("s1", "0", 0, undefined, expect.anything());
  });

  it("a new browser opens at the root and ignores a folder left in the session", async () => {
    sessionStorage.setItem("oct.dlna.folder.s1", "f9");
    twoLevels();
    setup();
    expect(await screen.findByRole("button", { name: "Open folder Rock" })).toBeInTheDocument();
    expect(api.getDlnaObjectPath).not.toHaveBeenCalled();
    expect(api.browseDlna).toHaveBeenCalledTimes(1);
  });

  it("going up focuses and centres the folder the user came from", async () => {
    vi.mocked(api.browseDlna).mockImplementation(async (_s, objectId) => {
      if (objectId === "f1") return page([folderItem("f2", "Deep")]);
      if (objectId === "f2") return page([track("t1", "Inside")]);
      return page([folderItem("f0", "Jazz"), folderItem("f1", "Rock")]);
    });
    const scroll = vi.mocked(Element.prototype.scrollIntoView);
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Deep" }));
    expect(await screen.findByText("Inside")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Up" }));
    const deep = await screen.findByRole("button", { name: "Select Deep" });
    await waitFor(() => expect(deep).toHaveFocus());
    expect(scroll.mock.contexts.at(-1)).toBe(deep);
    expect(scroll).toHaveBeenLastCalledWith({ block: "center" });

    // A breadcrumb two levels up focuses the top folder of the way back.
    await userEvent.click(screen.getByRole("button", { name: "Open folder Deep" }));
    expect(await screen.findByText("Inside")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Nas" }));
    const rock = await screen.findByRole("button", { name: "Select Rock" });
    await waitFor(() => expect(rock).toHaveFocus());
    expect(scroll.mock.contexts.at(-1)).toBe(rock);
  });

  it("opening a folder scrolls to the top once it shows; going up keeps the position", async () => {
    let resolveFolder: (p: api.DlnaBrowsePage) => void = () => {};
    vi.mocked(api.browseDlna).mockImplementation((_s, objectId) =>
      objectId === "f1"
        ? new Promise((r) => (resolveFolder = r))
        : Promise.resolve(page([folderItem("f1", "Rock")]))
    );
    const { container } = setupWithContainer();
    let top = 500;
    container.style.overflowY = "auto";
    Object.defineProperty(container, "scrollTop", {
      configurable: true,
      get: () => top,
      set: (v: number) => (top = v),
    });
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    // The dimmed previous list does not jump while the next folder loads.
    expect(top).toBe(500);
    resolveFolder(page([track("t1", "Inside")]));
    expect(await screen.findByText("Inside")).toBeInTheDocument();
    expect(top).toBe(0);

    top = 300;
    await userEvent.click(screen.getByRole("button", { name: "Up" }));
    const rock = await screen.findByRole("button", { name: "Select Rock" });
    await waitFor(() => expect(rock).toHaveFocus());
    expect(top).toBe(300);
  });

  describe("filter", () => {
    const filterBox = () => screen.getByRole("searchbox", { name: "Filter this folder" });

    it("filters the folder by title and artist, case-insensitive, and says when nothing matches", async () => {
      vi.mocked(api.browseDlna).mockResolvedValue(
        page([
          folderItem("f1", "Rock Classics"),
          { ...track("t1", "Song"), artist: "The ROCKers" },
          track("t2", "Ballad"),
        ])
      );
      setup();
      await screen.findByText("Ballad");
      await userEvent.type(filterBox(), "rock");
      expect(screen.getByRole("button", { name: "Open folder Rock Classics" })).toBeInTheDocument();
      expect(screen.getByText("Song")).toBeInTheDocument();
      expect(screen.queryByText("Ballad")).not.toBeInTheDocument();

      await userEvent.clear(filterBox());
      await userEvent.type(filterBox(), "jazz");
      expect(screen.getByText("No items match the filter.")).toBeInTheDocument();
      expect(screen.queryByRole("list")).not.toBeInTheDocument();
    });

    it("shows the artist on its own line under the title", async () => {
      vi.mocked(api.browseDlna).mockResolvedValue(
        page([{ ...track("t1", "Song"), artist: "The Band" }])
      );
      setup();
      const title = await screen.findByText("Song");
      const artist = screen.getByText("The Band");
      expect(title).toHaveClass("dlb-line");
      expect(artist).toHaveClass("dlb-line", "dlb-artist");
      expect(artist.previousElementSibling).toBe(title);
    });

    it("loads every remaining page while the filter is set", async () => {
      vi.mocked(api.browseDlna)
        .mockResolvedValueOnce(page([track("t1", "One")], true, 1))
        .mockResolvedValueOnce(page([track("t2", "Two")], true, 2))
        .mockResolvedValueOnce(page([track("t3", "Three")]));
      setup();
      await screen.findByText("One");
      expect(api.browseDlna).toHaveBeenCalledTimes(1);
      await userEvent.type(filterBox(), "three");
      expect(await screen.findByText("Three")).toBeInTheDocument();
      expect(screen.queryByText("One")).not.toBeInTheDocument();
      expect(api.browseDlna).toHaveBeenCalledTimes(3);
      expect(api.browseDlna).toHaveBeenLastCalledWith("s1", "0", 2, undefined, expect.anything());
    });

    it("stops loading pages after a failed page", async () => {
      vi.mocked(api.browseDlna)
        .mockResolvedValueOnce(page([track("t1", "One")], true, 1))
        .mockRejectedValueOnce(new Error("boom"))
        .mockResolvedValue(page([track("t2", "Two")]));
      setup();
      await screen.findByText("One");
      await userEvent.type(filterBox(), "two");
      expect(await screen.findByText("The folder could not be loaded.")).toBeInTheDocument();
      await new Promise((r) => setTimeout(r, 50));
      expect(api.browseDlna).toHaveBeenCalledTimes(2);
      expect(screen.getByText("No items match the filter.")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Load more" }));
      expect(await screen.findByText("Two")).toBeInTheDocument();
    });

    it("is cleared when the folder changes", async () => {
      twoLevels();
      setup();
      await screen.findByRole("button", { name: "Open folder Rock" });
      await userEvent.type(filterBox(), "ro");
      await userEvent.click(screen.getByRole("button", { name: "Open folder Rock" }));
      expect(await screen.findByText("Inside")).toBeInTheDocument();
      expect(filterBox()).toHaveValue("");
    });
  });

  it("breadcrumb navigates up", async () => {
    twoLevels();
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    expect(await screen.findByText("Inside")).toBeInTheDocument();
    expect(screen.getByText("Rock", { selector: "[aria-current]" })).toHaveAttribute(
      "aria-current",
      "location"
    );
    await userEvent.click(screen.getByRole("button", { name: "Nas" }));
    expect(await screen.findByRole("button", { name: "Open folder Rock" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open folder Rock" }));
    await userEvent.click(await screen.findByRole("button", { name: "Up" }));
    expect(await screen.findByRole("button", { name: "Open folder Rock" })).toBeInTheDocument();
  });

  it("separates the crumbs and shows the current one as plain text", async () => {
    twoLevels();
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    const nav = await screen.findByRole("navigation");
    const current = within(nav).getByText("Rock");
    expect(current.tagName).not.toBe("BUTTON");
    expect(within(nav).queryByRole("button", { name: "Rock" })).toBeNull();
    expect(within(nav).getByRole("button", { name: "Nas" })).toBeInTheDocument();
    expect(nav.querySelectorAll(".dlb-sep[aria-hidden='true']")).toHaveLength(1);
  });

  it("keeps the path on one line: full names in titles, middle crumbs marked for narrow screens", async () => {
    vi.mocked(api.browseDlna).mockImplementation(async (_s, objectId) => {
      if (objectId === "f1") return page([folderItem("f2", "Jazz")]);
      if (objectId === "f2") return page([track("t1", "Inside")]);
      return page([folderItem("f1", "Rock")]);
    });
    setup({ onAllServers: vi.fn() });
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Jazz" }));
    expect(await screen.findByText("Inside")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Folder path" });
    // server icon > Nas > Rock > Jazz: only the icon, the last parent and the current folder stay
    const server = within(nav).getByRole("button", { name: "All media servers" });
    expect(server).toHaveAttribute("title", "All media servers");
    expect(within(nav).getByRole("button", { name: "Nas" })).toHaveClass("rs-mid");
    const parent = within(nav).getByRole("button", { name: "Rock" });
    expect(parent).not.toHaveClass("rs-mid");
    expect(parent).toHaveAttribute("title", "Rock");
    expect(within(nav).getByText("Jazz")).toHaveAttribute("title", "Jazz");
    const seps = nav.querySelectorAll(".dlb-sep");
    expect(seps).toHaveLength(3);
    expect([...seps].map((s) => s.classList.contains("rs-mid"))).toEqual([true, false, false]);
  });

  it("the server icon leads back to all media servers", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(page([track("t1", "Song")]));
    const onAllServers = vi.fn();
    setup({ onAllServers });
    await userEvent.click(await screen.findByRole("button", { name: "All media servers" }));
    expect(onAllServers).toHaveBeenCalledTimes(1);
  });

  it("renders the navigation into the given head slot and heads the list with the filter", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(page([track("t1", "Song")]));
    const slot = document.createElement("div");
    document.body.append(slot);
    const { container } = setupWithContainer({ navTarget: slot });
    expect(await screen.findByText("Song")).toBeInTheDocument();
    const nav = within(slot).getByRole("navigation", { name: "Folder path" });
    expect(within(nav).getByRole("button", { name: "Open album view" })).toHaveClass("rs-album");
    expect(container.querySelector("nav")).toBeNull();
    const filter = container.querySelector(".dlb")!.firstElementChild!;
    expect(filter).toHaveClass("dlb-filter");
    expect(within(filter as HTMLElement).getByRole("searchbox")).toBeInTheDocument();
    slot.remove();
  });

  it("shows the fallback icon when a cover fails to load", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(
      page([{ ...track("t1", "Song"), album_art_url: "http://nas/a.jpg" }])
    );
    const { container } = setupWithContainer();
    const img = await waitFor(() => {
      const el = container.querySelector("img.dlb-cover");
      if (!el) throw new Error("cover not rendered yet");
      return el;
    });
    fireEvent.error(img);
    expect(container.querySelector("img.dlb-cover")).toBeNull();
    expect(container.querySelector(".dlb-cover--icon")).not.toBeNull();
  });

  it("selects an item with its parent id and its position across the loaded pages", async () => {
    vi.mocked(api.browseDlna)
      .mockResolvedValueOnce(page([track("t1", "One")], true, 1))
      .mockResolvedValueOnce(page([track("t2", "Two")]));
    const onSelect = setup();
    await userEvent.click(await screen.findByRole("button", { name: "Load more" }));
    await userEvent.click(await screen.findByRole("button", { name: "Select Two" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "t2" }), "0", 1);
  });

  it("says the next folder is loading while the previous one is shown dimmed", async () => {
    let resolveRock: (p: api.DlnaBrowsePage) => void = () => {};
    vi.mocked(api.browseDlna)
      .mockResolvedValueOnce(page([folderItem("f1", "Rock")]))
      .mockReturnValueOnce(new Promise((r) => (resolveRock = r)));
    const { container } = setupWithContainer();
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Loading folder");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(container.querySelector(".dlb-list--stale")).not.toBeNull();
    resolveRock(page([track("t1", "Song")]));
    expect(await screen.findByText("Song")).toBeInTheDocument();
    expect(screen.queryByText("Loading folder")).not.toBeInTheDocument();
  });

  it("empty folder message", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(page([]));
    setup();
    expect(await screen.findByText("This folder is empty")).toBeInTheDocument();
  });

  it("timeout error shows retry", async () => {
    vi.mocked(api.browseDlna)
      .mockRejectedValueOnce(new ApiError("x", { status: 504, code: "dlna_server_timeout" }))
      .mockResolvedValueOnce(page([track("t1", "Song")]));
    setup();
    expect(await screen.findByText("The server did not answer. Try again.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Song")).toBeInTheDocument();
  });

  it("object not found shows calm notice and goes to root", async () => {
    vi.mocked(api.getDlnaObjectPath).mockResolvedValue({
      server_id: "s1",
      server_name: "Nas",
      object_id: "gone",
      title: "Gone",
      is_container: true,
      path: [],
    });
    vi.mocked(api.browseDlna).mockImplementation(async (_s, objectId) => {
      if (objectId === "gone")
        throw new ApiError("x", { status: 404, code: "dlna_object_not_found" });
      return page([folderItem("f1", "Rock")]);
    });
    setup({ startObjectId: "gone" });
    expect(await screen.findByText(/no longer exists/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Open folder Rock" })).toBeInTheDocument();
  });

  it("no request is made on hover", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(page([folderItem("f1", "Rock")]));
    setup();
    await userEvent.hover(await screen.findByRole("button", { name: "Open folder Rock" }));
    expect(api.browseDlna).toHaveBeenCalledTimes(1);
  });

  describe("whole folder entry", () => {
    const entry = (title: string) =>
      screen.queryByRole("button", { name: `Select whole folder ${title}` });
    const nested = () =>
      vi.mocked(api.browseDlna).mockImplementation(async (_s, objectId) => {
        if (objectId === "f1") return page([folderItem("f2", "Album")]);
        if (objectId === "f2")
          return page([
            folderItem("f3", "Bonus"),
            { ...track("t1", "Song"), album_art_url: "http://nas.example/a.jpg" },
          ]);
        return page([folderItem("f1", "Rock"), track("t0", "Loose")]);
      });

    it("shows only in a folder with tracks below the root and selects that folder", async () => {
      nested();
      const onSelect = setup();
      await screen.findByText("Loose");
      expect(entry("Nas")).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Open folder Rock" }));
      await screen.findByRole("button", { name: "Open folder Album" });
      expect(entry("Rock")).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Open folder Album" }));
      await screen.findByText("Song");
      expect(screen.getByText("Whole folder as preset")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Select whole folder Album" }));
      expect(onSelect).toHaveBeenCalledWith(
        {
          id: "f2",
          parent_id: "f1",
          title: "Album",
          is_container: true,
          album_art_url: "http://nas.example/a.jpg",
        },
        "f1"
      );
    });

    it("hides while a filter text is entered and is disabled while busy", async () => {
      nested();
      vi.mocked(api.getDlnaObjectPath).mockResolvedValue({
        server_id: "s1",
        server_name: "Nas",
        object_id: "f2",
        title: "Album",
        is_container: true,
        path: [],
      });
      setup({ startObjectId: "f2", busy: true });
      await screen.findByText("Song");
      await waitFor(() => expect(entry("Album")).toBeDisabled());
      await userEvent.type(screen.getByRole("searchbox"), "so");
      expect(entry("Album")).not.toBeInTheDocument();
    });

    it("labels the list below it as the folder's contents and hides the label with it", async () => {
      nested();
      setup();
      await screen.findByText("Loose");
      expect(screen.queryByText("Contents")).not.toBeInTheDocument();
      expect(screen.getByRole("list")).not.toHaveAccessibleName();
      await userEvent.click(screen.getByRole("button", { name: "Open folder Rock" }));
      await userEvent.click(await screen.findByRole("button", { name: "Open folder Album" }));
      await screen.findByText("Song");
      expect(entry("Album")).toBeInTheDocument();
      expect(screen.getByRole("list", { name: "Contents" })).toBeInTheDocument();
      await userEvent.type(screen.getByRole("searchbox"), "so");
      expect(entry("Album")).not.toBeInTheDocument();
      expect(screen.queryByText("Contents")).not.toBeInTheDocument();
      expect(screen.getByRole("list")).not.toHaveAccessibleName();
    });
  });
});
