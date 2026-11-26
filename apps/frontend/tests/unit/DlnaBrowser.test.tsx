import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function setupWithContainer(props: Partial<React.ComponentProps<typeof DlnaBrowser>> = {}) {
  const onSelect = vi.fn();
  const client = new QueryClient();
  const view = render(
    <QueryClientProvider client={client}>
      <DlnaBrowser serverId="s1" serverName="Nas" onSelect={onSelect} {...props} />
    </QueryClientProvider>
  );
  return { onSelect, container: view.container };
}

const setup = (props: Partial<React.ComponentProps<typeof DlnaBrowser>> = {}) =>
  setupWithContainer(props).onSelect;

describe("DlnaBrowser", () => {
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

  it("breadcrumb navigates up", async () => {
    twoLevels();
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Rock" }));
    expect(await screen.findByText("Inside")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rock" })).toHaveAttribute(
      "aria-current",
      "location"
    );
    await userEvent.click(screen.getByRole("button", { name: "Nas" }));
    expect(await screen.findByRole("button", { name: "Open folder Rock" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open folder Rock" }));
    await userEvent.click(await screen.findByRole("button", { name: "Up" }));
    expect(await screen.findByRole("button", { name: "Open folder Rock" })).toBeInTheDocument();
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

  it("selects an item with its parent id", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(page([track("t1", "Song")]));
    const onSelect = setup();
    await userEvent.click(await screen.findByRole("button", { name: "Select Song" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "t1" }), "0");
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
});
