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
const notFound = (code: string) => new ApiError("nope", { status: 404, code });
const warning =
  "The first item in this folder is not a song (for example a cover image). The speaker may not be able to play it. Save anyway?";

function setup(existingPreset?: React.ComponentProps<typeof DlnaPane>["existingPreset"]) {
  const onSave = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DlnaPane deviceId="dev1" presetNumber={2} existingPreset={existingPreset} onSave={onSave} />
    </QueryClientProvider>
  );
  return onSave;
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
  });

  async function openAndSelect(title: string) {
    await userEvent.click(await screen.findByRole("button", { name: "Open Nas" }));
    await userEvent.click(await screen.findByRole("button", { name: `Select ${title}` }));
  }

  it("a folder whose check found audio first is handed over with index and confirm", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(true);
    const onSave = setup();
    await openAndSelect("Album");
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(api.getFirstChildAudio).toHaveBeenCalledWith("s1", "f1");
    expect(onSave).toHaveBeenCalledWith({
      device_id: "dev1",
      preset_number: 2,
      server_id: "s1",
      parent_id: "0",
      object_id: "f1",
      index: 0,
      confirm: true,
    });
    expect(screen.queryByText(warning)).not.toBeInTheDocument();
    expect(api.saveDlnaPreset).not.toHaveBeenCalled();
  });

  it("a failed audio-first check hands the folder over without confirm", async () => {
    vi.mocked(api.getFirstChildAudio).mockRejectedValue(new Error("timeout"));
    const onSave = setup();
    await openAndSelect("Album");
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0]?.[0]).not.toHaveProperty("confirm");
  });

  it("folder without audio first shows the pre-save warning and saves with confirm", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(false);
    const onSave = setup();
    await openAndSelect("Album");
    expect(await screen.findByRole("alert")).toHaveTextContent(warning);
    expect(onSave).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Save anyway" }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ confirm: true }));
  });

  it("choose another folder closes the warning without saving", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(false);
    const onSave = setup();
    await openAndSelect("Album");
    await userEvent.click(await screen.findByRole("button", { name: "Choose something else" }));
    expect(screen.queryByText(warning)).not.toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("track is handed over directly with its position and without confirm or cover", async () => {
    const onSave = setup();
    await openAndSelect("Song");
    expect(onSave).toHaveBeenCalledWith({
      device_id: "dev1",
      preset_number: 2,
      server_id: "s1",
      parent_id: "0",
      object_id: "t1",
      index: 1,
    });
    expect(api.getFirstChildAudio).not.toHaveBeenCalled();
  });

  it("sends the artist of an item that has one", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(
      page([{ ...item("t1", "Song", false), artist: "Some Artist" }])
    );
    const onSave = setup();
    await openAndSelect("Song");
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ artist: "Some Artist" }));
  });

  it("sends the cover of an item that has one", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(
      page([{ ...item("t1", "Song", false), album_art_url: "http://nas.example/art.jpg" }])
    );
    const onSave = setup();
    await openAndSelect("Song");
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ index: 0, artwork_url: "http://nas.example/art.jpg" })
    );
  });

  it.each([
    [96000, "96", "audio/flac"],
    [88200, "88.2", "audio/flac"],
    [96000, "96", "audio/x-flac"],
  ])(
    "hi-res FLAC track (%i Hz = %s kHz, %s) warns first and saves without confirm",
    async (hz, khz, mime) => {
      vi.mocked(api.browseDlna).mockResolvedValue(
        page([
          {
            ...item("t1", "Song", false),
            protocol_info: `http-get:*:${mime}:DLNA.ORG_PN=FLAC`,
            sample_frequency: hz,
          },
        ])
      );
      const onSave = setup();
      await openAndSelect("Song");
      expect(await screen.findByRole("alert")).toHaveTextContent(
        `This track is a high-resolution FLAC (${khz} kHz).`
      );
      expect(onSave).not.toHaveBeenCalled();
      await userEvent.click(screen.getByRole("button", { name: "Save anyway" }));
      expect(onSave).toHaveBeenCalledWith(expect.not.objectContaining({ confirm: true }));
    }
  );

  it("FLAC track at 48 kHz saves directly", async () => {
    vi.mocked(api.browseDlna).mockResolvedValue(
      page([
        {
          ...item("t1", "Song", false),
          protocol_info: "http-get:*:audio/flac:*",
          sample_frequency: 48000,
        },
      ])
    );
    const onSave = setup();
    await openAndSelect("Song");
    expect(onSave).toHaveBeenCalled();
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
    expect(await screen.findByText("Parent", { selector: "[aria-current]" })).toHaveAttribute(
      "aria-current",
      "location"
    );
    expect(select).toHaveFocus();
  });

  it("a server the first scan missed is restored once the full search finds it", async () => {
    let finish: (value: api.NativeServerList) => void = () => {};
    vi.mocked(api.getNativeServers).mockImplementation(
      () => new Promise((resolve) => (finish = resolve))
    );
    vi.mocked(api.getDlnaObjectPath)
      .mockRejectedValueOnce(notFound("dlna_server_not_found"))
      .mockResolvedValue({
        server_id: "s1",
        server_name: "Nas",
        object_id: "t1",
        title: "Song",
        is_container: false,
        path: [{ object_id: "p1", title: "Parent" }],
      });
    setup({ dlna: true, source_account: "s1/0", station_url: "t1 TRACK" });
    await waitFor(() =>
      expect(api.getNativeServers).toHaveBeenCalledWith("dev1", expect.anything())
    );
    // The pane waits for the full search instead of declaring the server gone.
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText(/no longer available/)).not.toBeInTheDocument();

    finish({ servers: [nas], migration_failed: false, migration_reason: null });
    expect(await screen.findByRole("button", { name: "Select Song" })).toBeInTheDocument();
    expect(api.browseDlna).toHaveBeenCalledWith("s1", "p1", 0, undefined, expect.anything());
    expect(screen.queryByText(/no longer available/)).not.toBeInTheDocument();
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

  it("shows a busy status and disables select buttons while the folder is checked", async () => {
    let resolve!: (v: boolean) => void;
    vi.mocked(api.getFirstChildAudio).mockReturnValue(new Promise((r) => (resolve = r)));
    const onSave = setup();
    await openAndSelect("Album");
    expect(await screen.findByText("Saving to preset 2 …")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select Song" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Select Album" })).toBeDisabled();
    resolve(true);
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(screen.queryByText("Saving to preset 2 …")).not.toBeInTheDocument();
  });

  it("saves the open folder from its whole-folder entry without an index", async () => {
    vi.mocked(api.getFirstChildAudio).mockResolvedValue(true);
    vi.mocked(api.browseDlna).mockImplementation(async (_s, objectId) =>
      objectId === "f1"
        ? page([item("t1", "Song", false)])
        : page([item("f1", "Album", true), item("t0", "Loose", false)])
    );
    const onSave = setup();
    await userEvent.click(await screen.findByRole("button", { name: "Open Nas" }));
    await userEvent.click(await screen.findByRole("button", { name: "Open folder Album" }));
    await userEvent.click(await screen.findByRole("button", { name: "Select whole folder Album" }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(api.getFirstChildAudio).toHaveBeenCalledWith("s1", "f1");
    expect(onSave).toHaveBeenCalledWith({
      device_id: "dev1",
      preset_number: 2,
      server_id: "s1",
      parent_id: "0",
      object_id: "f1",
      confirm: true,
    });
  });
});
