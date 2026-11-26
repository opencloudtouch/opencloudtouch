import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AlbumViewButton from "../../src/components/dlna/AlbumViewButton";
import DlnaBrowser from "../../src/components/dlna/DlnaBrowser";
import { ApiError } from "../../src/api/types";
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
    render(<AlbumViewButton serverId="s1" onOpen={vi.fn()} />);
    expect(api.getAlbumRoot).not.toHaveBeenCalled();
  });

  it("album button opens the album root", async () => {
    vi.mocked(api.getAlbumRoot).mockResolvedValue("albums");
    const onOpen = vi.fn();
    render(<AlbumViewButton serverId="s1" onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: "Open album view" }));
    expect(onOpen).toHaveBeenCalledWith("albums");
  });

  it("album button hidden when no album root", async () => {
    vi.mocked(api.getAlbumRoot).mockResolvedValue(null);
    const onOpen = vi.fn();
    render(<AlbumViewButton serverId="s1" onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: "Open album view" }));
    expect(onOpen).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Open album view" })).not.toBeInTheDocument();
  });
});

describe("DlnaBrowser folder memory", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
  });

  const setup = () =>
    render(
      <QueryClientProvider client={new QueryClient()}>
        <DlnaBrowser serverId="s1" serverName="Nas" onSelect={vi.fn()} />
      </QueryClientProvider>
    );

  it("opens the remembered folder and remembers navigation", async () => {
    sessionStorage.setItem("oct.dlna.folder.s1", "f9");
    vi.mocked(api.getDlnaObjectPath).mockResolvedValue({
      server_id: "s1",
      server_name: "Nas",
      object_id: "f9",
      title: "Jazz",
      is_container: true,
      path: [],
    });
    vi.mocked(api.browseDlna).mockResolvedValue(emptyPage("f9"));
    setup();
    expect(await screen.findByRole("button", { name: "Jazz" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Nas" }));
    expect(sessionStorage.getItem("oct.dlna.folder.s1")).toBeNull();
  });

  it("vanished remembered folder falls back to root", async () => {
    sessionStorage.setItem("oct.dlna.folder.s1", "f9");
    vi.mocked(api.getDlnaObjectPath).mockRejectedValue(
      new ApiError("x", { status: 404, code: "dlna_object_not_found" })
    );
    vi.mocked(api.browseDlna).mockResolvedValue(emptyPage());
    setup();
    expect(await screen.findByText(/no longer exists/)).toBeInTheDocument();
    expect(sessionStorage.getItem("oct.dlna.folder.s1")).toBeNull();
  });

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
    expect(await screen.findByRole("button", { name: "Albums" })).toBeInTheDocument();
    expect(sessionStorage.getItem("oct.dlna.folder.s1")).toBe("albums");
  });
});
