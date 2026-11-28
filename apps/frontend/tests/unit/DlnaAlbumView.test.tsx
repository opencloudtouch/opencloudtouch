import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AlbumViewButton from "../../src/components/dlna/AlbumViewButton";
import DlnaBrowser from "../../src/components/dlna/DlnaBrowser";
import * as api from "../../src/api/dlna";

vi.mock("../../src/api/dlna");

const emptyPage = (objectId = "0"): api.DlnaBrowsePage => ({
  server_id: "s1",
  object_id: objectId,
  items: [],
  starting_index: 0,
  number_returned: 0,
  total_matches: null,
  next_index: 0,
  has_more: false,
});

describe("AlbumViewButton", () => {
  beforeEach(() => vi.resetAllMocks());

  it("does not call the endpoint on mount", () => {
    render(<AlbumViewButton serverId="s1" folderId="0" onOpen={vi.fn()} />);
    expect(api.getAlbumRoot).not.toHaveBeenCalled();
  });

  it("album button opens the album root", async () => {
    vi.mocked(api.getAlbumRoot).mockResolvedValue("albums");
    const onOpen = vi.fn();
    render(<AlbumViewButton serverId="s1" folderId="0" onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: "Open album view" }));
    expect(onOpen).toHaveBeenCalledWith("albums");
  });

  it("album button shows a busy state during the lookup", async () => {
    let resolve: (id: string | null) => void = () => {};
    vi.mocked(api.getAlbumRoot).mockReturnValue(new Promise((r) => (resolve = r)));
    const onOpen = vi.fn();
    const { container } = render(<AlbumViewButton serverId="s1" folderId="0" onOpen={onOpen} />);
    const button = screen.getByRole("button", { name: "Open album view" });
    await userEvent.click(button);
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector(".spinner-small")).not.toBeNull();
    resolve("albums");
    await vi.waitFor(() => expect(onOpen).toHaveBeenCalledWith("albums"));
    expect(button).not.toBeDisabled();
  });

  it("album button hidden when no album root", async () => {
    vi.mocked(api.getAlbumRoot).mockResolvedValue(null);
    const onOpen = vi.fn();
    render(<AlbumViewButton serverId="s1" folderId="0" onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: "Open album view" }));
    expect(onOpen).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Open album view" })).not.toBeInTheDocument();
  });
});

describe("DlnaBrowser album view", () => {
  beforeEach(() => vi.resetAllMocks());

  const setup = () =>
    render(
      <QueryClientProvider client={new QueryClient()}>
        <DlnaBrowser serverId="s1" serverName="Nas" onSelect={vi.fn()} />
      </QueryClientProvider>
    );

  it("album view button jumps to the album folder", async () => {
    vi.mocked(api.getAlbumRoot).mockResolvedValue("albums");
    vi.mocked(api.getDlnaObjectPath).mockResolvedValue({
      server_id: "s1",
      server_name: "Nas",
      object_id: "albums",
      title: "Albums",
      is_container: true,
      path: [],
    });
    vi.mocked(api.browseDlna).mockResolvedValue(emptyPage());
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open album view" }));
    expect(await screen.findByText("Albums", { selector: "[aria-current]" })).toBeInTheDocument();
    // The album folder is browsed directly, not the root again.
    expect(api.browseDlna).toHaveBeenLastCalledWith(
      "s1",
      "albums",
      0,
      undefined,
      expect.anything()
    );
    expect(api.browseDlna).toHaveBeenCalledTimes(2);
  });

  it("folder loading, then album view: only the album lookup shows as loading", async () => {
    vi.mocked(api.browseDlna).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getAlbumRoot).mockReturnValue(new Promise(() => {}));
    setup();
    expect(await screen.findByText("Loading folder")).toBeInTheDocument();
    const album = screen.getByRole("button", { name: "Open album view" });
    expect(album).not.toBeDisabled();

    await userEvent.click(album);

    expect(album).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText("Loading folder")).not.toBeInTheDocument();
  });

  it("album view loading, then a breadcrumb: the album lookup is cancelled", async () => {
    const folder: api.DlnaItem = { id: "a", parent_id: "0", title: "A", is_container: true };
    vi.mocked(api.browseDlna).mockImplementation(async (_s, objectId) =>
      objectId === "0" ? { ...emptyPage(), items: [folder], number_returned: 1 } : emptyPage("a")
    );
    vi.mocked(api.getAlbumRoot).mockReturnValue(new Promise(() => {}));
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open folder A" }));
    const album = screen.getByRole("button", { name: "Open album view" });
    await userEvent.click(album);
    expect(album).toHaveAttribute("aria-busy", "true");

    await userEvent.click(screen.getByRole("button", { name: "Nas" }));

    const signal = vi.mocked(api.getAlbumRoot).mock.calls[0][1];
    expect(signal?.aborted).toBe(true);
    await waitFor(() => expect(album).toHaveAttribute("aria-busy", "false"));
    expect(album).not.toBeDisabled();
  });
});
