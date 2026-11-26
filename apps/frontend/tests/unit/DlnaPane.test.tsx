import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DlnaPane from "../../src/components/dlna/DlnaPane";
import { ApiError } from "../../src/api/types";
import * as api from "../../src/api/dlna";

vi.mock("../../src/api/dlna");

const item = (id: string, title: string, is_container: boolean): api.DlnaItem => ({
  id,
  parent_id: "0",
  title,
  is_container,
});
const page = (items: api.DlnaItem[]): api.DlnaBrowsePage => ({
  server_id: "s1",
  object_id: "0",
  items,
  starting_index: 0,
  number_returned: items.length,
  total_matches: null,
  next_index: items.length,
  has_more: false,
});
const nas: api.NativeServer = {
  server_id: "s1",
  name: "Nas",
  state: "ready",
  discovered: true,
  host: null,
};
const saved: api.PresetResponse = {
  id: 1,
  device_id: "dev1",
  preset_number: 2,
  station_uuid: "f1",
  station_name: "Album",
  station_url: "f1",
  station_homepage: null,
  station_favicon: null,
  source: "STORED_MUSIC",
  source_account: "s1/0",
  dlna: true,
  created_at: "",
  updated_at: "",
};
const notFound = (code: string) => new ApiError("nope", { status: 404, code });
const warning =
  "The first item in this folder is not a song (for example a cover image). The speaker may not be able to play it. Save anyway?";

function setup(existingPreset?: React.ComponentProps<typeof DlnaPane>["existingPreset"]) {
  const onSaved = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DlnaPane
        deviceId="dev1"
        presetNumber={2}
        existingPreset={existingPreset}
        onSaved={onSaved}
      />
    </QueryClientProvider>
  );
  return onSaved;
}

describe("DlnaPane", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
    vi.mocked(api.getNativeServers).mockResolvedValue({
      servers: [nas],
      migration_failed: false,
      migration_reason: null,
    });
    vi.mocked(api.browseDlna).mockResolvedValue(
      page([item("f1", "Album", true), item("t1", "Song", false)])
    );
    vi.mocked(api.saveDlnaPreset).mockResolvedValue(saved);
  });

  async function openAndSelect(title: string) {
    await userEvent.click(await screen.findByRole("button", { name: "Open Nas" }));
    await userEvent.click(await screen.findByRole("button", { name: `Select ${title}` }));
  }

  it("dlna tab saves a folder with audio first without a warning", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(true);
    const onSaved = setup();
    await openAndSelect("Album");
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.getFirstChildAudio).toHaveBeenCalledWith("s1", "f1");
    expect(api.saveDlnaPreset).toHaveBeenCalledWith({
      device_id: "dev1",
      preset_number: 2,
      server_id: "s1",
      parent_id: "0",
      object_id: "f1",
    });
    expect(screen.queryByText(warning)).not.toBeInTheDocument();
  });

  it("folder without audio first shows the pre-save warning and saves with confirm", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(false);
    const onSaved = setup();
    await openAndSelect("Album");
    expect(await screen.findByRole("alert")).toHaveTextContent(warning);
    expect(api.saveDlnaPreset).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Save anyway" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.saveDlnaPreset).toHaveBeenCalledWith(expect.objectContaining({ confirm: true }));
  });

  it("choose another folder closes the warning without saving", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(false);
    const onSaved = setup();
    await openAndSelect("Album");
    await userEvent.click(await screen.findByRole("button", { name: "Choose another folder" }));
    expect(screen.queryByText(warning)).not.toBeInTheDocument();
    expect(api.saveDlnaPreset).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("409 from the server shows the same warning", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(true);
    vi.mocked(api.saveDlnaPreset).mockRejectedValueOnce(
      new ApiError("conflict", { status: 409, code: "dlna_folder_no_audio_first" })
    );
    const onSaved = setup();
    await openAndSelect("Album");
    expect(await screen.findByText(warning)).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("track saves directly", async () => {
    const onSaved = setup();
    await openAndSelect("Song");
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.getFirstChildAudio).not.toHaveBeenCalled();
  });

  it("a speaker error on save shows the inline error", async () => {
    vi.mocked(api.saveDlnaPreset).mockRejectedValueOnce(
      new ApiError("Speaker refused the preset", { status: 502, code: "device_error" })
    );
    const onSaved = setup();
    await openAndSelect("Song");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("editing a dlna preset opens the dlna tab at the parent folder with the row focused", async () => {
    // The API path lists ancestors only: the song's parent p1, then p1's own (empty) ancestry.
    vi.mocked(api.getDlnaObjectPath).mockImplementation(async (_s, objectId) =>
      objectId === "t1"
        ? {
            server_id: "s1",
            server_name: "Nas",
            object_id: "t1",
            title: "Song",
            is_container: false,
            path: [{ object_id: "p1", title: "Parent" }],
          }
        : {
            server_id: "s1",
            server_name: "Nas",
            object_id: "p1",
            title: "Parent",
            is_container: true,
            path: [],
          }
    );
    setup({ dlna: true, source_account: "s1/0", station_url: "t1 TRACK" });
    const select = await screen.findByRole("button", { name: "Select Song" });
    expect(api.getDlnaObjectPath).toHaveBeenCalledWith("s1", "t1", expect.anything());
    expect(api.browseDlna).toHaveBeenCalledWith("s1", "p1", 0, undefined, expect.anything());
    // The start folder is the last breadcrumb (prefill breadcrumb fix).
    expect(await screen.findByRole("button", { name: "Parent" })).toHaveAttribute(
      "aria-current",
      "location"
    );
    expect(select).toHaveFocus();
  });

  it("vanished saved object shows calm notice and root", async () => {
    vi.mocked(api.getDlnaObjectPath).mockRejectedValue(notFound("dlna_object_not_found"));
    setup({ dlna: true, source_account: "s1/0", station_url: "gone" });
    expect(await screen.findByText(/no longer exists on the server/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Select Album" })).toBeInTheDocument();
    expect(api.browseDlna).toHaveBeenCalledWith("s1", "0", 0, undefined, expect.anything());
  });

  it("vanished server shows the server list", async () => {
    vi.mocked(api.getDlnaObjectPath).mockRejectedValue(notFound("dlna_server_not_found"));
    setup({ dlna: true, source_account: "s1/0", station_url: "f1" });
    expect(await screen.findByText(/no longer available/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Open Nas" })).toBeInTheDocument();
  });

  it("vanished object on a server the speaker no longer lists shows the server list", async () => {
    vi.mocked(api.getDlnaObjectPath).mockRejectedValue(notFound("dlna_object_not_found"));
    setup({ dlna: true, source_account: "other/0", station_url: "f1" });
    expect(await screen.findByRole("button", { name: "Open Nas" })).toBeInTheDocument();
    expect(api.browseDlna).not.toHaveBeenCalled();
  });
});
