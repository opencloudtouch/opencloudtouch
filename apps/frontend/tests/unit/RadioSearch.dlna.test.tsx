import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RadioSearch from "../../src/components/RadioSearch";
import { ApiError } from "../../src/api/types";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const NAS = {
  id: "srv",
  name: "Living Room NAS",
  location: "http://10.0.0.5/d.xml",
  control_url: "c",
};
const page = (items: unknown[]) => ({
  server_id: "srv",
  object_id: "0",
  items,
  starting_index: 0,
  number_returned: items.length,
  total_matches: null,
  next_index: items.length,
  has_more: false,
});
const ROOT = [
  { id: "t1", parent_id: "0", title: "First Song", is_container: false },
  { id: "f1", parent_id: "0", title: "Best Of", is_container: true },
];

const fetchMock = vi.fn();
const onDlnaSelect = vi.fn();
const onClose = vi.fn();

function renderSearch(props: Partial<React.ComponentProps<typeof RadioSearch>> = {}) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <RadioSearch
        isOpen
        presetNumber={3}
        onStationSelect={vi.fn()}
        onDlnaSelect={onDlnaSelect}
        onClose={onClose}
        {...props}
      />
    </QueryClientProvider>
  );
}

const enterDlna = () => fireEvent.click(document.querySelector('[data-test="dlna-mode"]')!);
const openRoot = async () => {
  enterDlna();
  fireEvent.click(await screen.findByRole("button", { name: "Open server “Living Room NAS”" }));
  await screen.findByText("First Song");
};

beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  onDlnaSelect.mockReset();
  onClose.mockReset();
  fetchMock.mockImplementation(async (url: string) =>
    String(url).includes("/browse") ? json(page(ROOT)) : json([NAS])
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("RadioSearch: DLNA mode", () => {
  it("offers a DLNA chip between the providers and the stream URL chip, and switches the panel", async () => {
    const { container } = renderSearch();
    const chips = Array.from(
      container.querySelectorAll("fieldset")[1].querySelectorAll("button")
    ).map((b) => b.textContent);
    expect(chips).toEqual(["TuneIn", "RadioBrowser", "DLNA", "Stream URL"]);

    enterDlna();
    expect(document.querySelector('[data-test="dlna-mode"]')).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(container.querySelector(".rs-chips--dlna")).not.toBeNull();
    expect(container.querySelector(".rs-field")).toBeNull();
    screen
      .getAllByRole("button", { name: /Name|Country|Genre/ })
      .forEach((b) => expect(b).toBeDisabled());
    expect(await screen.findByText("Living Room NAS")).toBeInTheDocument();
  });

  it("keeps the radio query when switching to DLNA and back", () => {
    renderSearch();
    fireEvent.change(screen.getByPlaceholderText("e.g. SWR3, BBC Radio…"), {
      target: { value: "rock" },
    });
    enterDlna();
    fireEvent.click(screen.getByText("RadioBrowser"));
    expect(screen.getByPlaceholderText("e.g. SWR3, BBC Radio…")).toHaveValue("rock");
  });

  it("keeps the folder when switching away and back, and in a new dialog of the same browser session", async () => {
    const { unmount } = renderSearch();
    await openRoot();
    fireEvent.click(screen.getByText("RadioBrowser"));
    enterDlna();
    expect(await screen.findByText("First Song")).toBeInTheDocument();
    expect(sessionStorage.getItem("oct.dlna.session")).toContain('"serverId":"srv"');

    unmount();
    renderSearch();
    enterDlna();
    expect(await screen.findByRole("heading", { name: "Living Room NAS" })).toBeInTheDocument();
    expect(await screen.findByText("First Song")).toBeInTheDocument();
  });

  it("ignores a broken stored session", () => {
    sessionStorage.setItem("oct.dlna.session", "{not json");
    renderSearch();
    enterDlna();
    expect(screen.getByRole("heading", { name: "Media servers" })).toBeInTheDocument();
  });

  it("saves a track for the dialog's preset, closes on success and disables actions while saving", async () => {
    let resolve!: () => void;
    onDlnaSelect.mockImplementation(() => new Promise<void>((r) => (resolve = r)));
    renderSearch();
    await openRoot();

    expect(
      screen.getByRole("button", { name: "Use for preset 3: First Song" })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: First Song" }));

    await waitFor(() =>
      expect(onDlnaSelect).toHaveBeenCalledWith({ server_id: "srv", object_id: "t1" })
    );
    expect(screen.getByRole("button", { name: "Use for preset 3: First Song" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Use for preset 3: Best Of" })).toBeDisabled();
    expect(screen.getAllByText("Saving preset 3 …")).not.toHaveLength(0);

    resolve();
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("saves a folder with its object id", async () => {
    onDlnaSelect.mockResolvedValue(undefined);
    renderSearch();
    await openRoot();
    fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: Best Of" }));
    await waitFor(() =>
      expect(onDlnaSelect).toHaveBeenCalledWith({ server_id: "srv", object_id: "f1" })
    );
  });

  const rejectWith = (code: string) => new ApiError("raw backend detail", { status: 502, code });

  it.each([
    ["dlna_server_not_found", "The media server was not found."],
    ["dlna_object_not_found", "The item no longer exists, the library may have been rescanned."],
    ["dlna_upstream_error", "The media server did not answer properly."],
    ["dlna_server_timeout", "The media server answered too slowly."],
    ["dlna_not_playable", "The speaker cannot play this item."],
    ["dlna_reference_too_long", "The item's address is too long."],
    ["device_not_found", "The device was not found."],
    ["device_unreachable", "The device is not reachable"],
    ["validation_error", "The request contains invalid data."],
  ])(
    "shows a distinct message for the save error %s and lets the user retry",
    async (code, text) => {
      onDlnaSelect.mockRejectedValueOnce(rejectWith(code)).mockResolvedValueOnce(undefined);
      vi.spyOn(console, "error").mockImplementation(() => {});
      renderSearch();
      await openRoot();
      fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: First Song" }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent("Preset not saved");
      expect(alert).toHaveTextContent(text);
      expect(alert).not.toHaveTextContent("raw backend detail");
      expect(onClose).not.toHaveBeenCalled();
      await waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toHaveFocus());
      // the list stays usable
      await waitFor(() =>
        expect(screen.getByRole("button", { name: "Use for preset 3: Best Of" })).toBeEnabled()
      );

      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
      await waitFor(() => expect(onClose).toHaveBeenCalled());
      expect(onDlnaSelect).toHaveBeenCalledTimes(2);
      expect(onDlnaSelect).toHaveBeenLastCalledWith({ server_id: "srv", object_id: "t1" });
    }
  );

  it.each([
    ["an unknown code", rejectWith("something_new")],
    ["a network failure", new TypeError("Failed to fetch")],
  ])("shows the generic message for %s, never raw text", async (_name, error) => {
    onDlnaSelect.mockRejectedValueOnce(error);
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderSearch();
    await openRoot();
    fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: First Song" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The preset could not be saved. Try again.");
    expect(alert).not.toHaveTextContent("raw backend detail");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("clears the save error when the user navigates on", async () => {
    onDlnaSelect.mockRejectedValueOnce(rejectWith("dlna_not_playable"));
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderSearch();
    await openRoot();
    fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: First Song" }));
    await screen.findByRole("alert");

    fireEvent.click(screen.getByRole("button", { name: "Open folder “Best Of”" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
});

describe("RadioSearch: media server setup before saving", () => {
  const native = (state: string) => ({
    device_id: "dev1",
    servers: [{ server_id: "srv", name: NAS.name, state, server_known: true, source_id: null }],
  });
  let put: () => Response | Promise<Response>;
  let nativeList: () => Response | Promise<Response>;

  beforeEach(() => {
    put = () => json({ server_id: "srv", state: "ready" });
    nativeList = () => json(native("not_enabled"));
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes("/api/dlna/native")) return init?.method === "PUT" ? put() : nativeList();
      return u.includes("/browse") ? json(page(ROOT)) : json([NAS]);
    });
  });

  const save = async () => {
    renderSearch({ deviceId: "dev1" });
    await openRoot();
    await screen.findByText("Not set up");
    fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: Best Of" }));
  };

  it("sets a server that is not set up up first, then saves", async () => {
    onDlnaSelect.mockResolvedValue(undefined);
    await save();
    await waitFor(() =>
      expect(onDlnaSelect).toHaveBeenCalledWith({ server_id: "srv", object_id: "f1" })
    );
    const methods = fetchMock.mock.calls.map((c) => c[1]?.method);
    expect(methods).toContain("PUT");
    expect(onClose).toHaveBeenCalled();
  });

  it("shows 'Setting up …' on the row while the setup runs, then 'Saving …'", async () => {
    let finish!: () => void;
    put = () =>
      new Promise<Response>((r) => (finish = () => r(json({ server_id: "srv", state: "ready" }))));
    onDlnaSelect.mockImplementation(() => new Promise<void>(() => undefined));
    await save();
    expect(await screen.findAllByText("Setting up …")).not.toHaveLength(0);
    expect(onDlnaSelect).not.toHaveBeenCalled();
    finish();
    expect(await screen.findAllByText("Saving preset 3 …")).not.toHaveLength(0);
  });

  it("after 4 s of setup the row says that this takes a moment", async () => {
    put = () => new Promise<Response>(() => undefined);
    renderSearch({ deviceId: "dev1" });
    await openRoot();
    await screen.findByText("Not set up");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: Best Of" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4100);
      });
      expect(screen.getAllByText("Setting up, this takes a moment …")).not.toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("skips the setup for a server that is ready", async () => {
    nativeList = () => json(native("ready"));
    onDlnaSelect.mockResolvedValue(undefined);
    renderSearch({ deviceId: "dev1" });
    await openRoot();
    await screen.findByText("Ready");
    fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: Best Of" }));
    await waitFor(() => expect(onDlnaSelect).toHaveBeenCalled());
    expect(fetchMock.mock.calls.some((c) => c[1]?.method === "PUT")).toBe(false);
  });

  it("a failed setup marks the server 'Not available', shows the banner and retries", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    put = () =>
      json(
        { type: "x", title: "x", status: 502, detail: "raw", code: "dlna_native_setup_failed" },
        502
      );
    await save();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The speaker did not accept the media server.");
    expect(onDlnaSelect).not.toHaveBeenCalled();
    expect(screen.getByText("Not available")).toBeInTheDocument();

    put = () => json({ server_id: "srv", state: "ready" });
    onDlnaSelect.mockResolvedValue(undefined);
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(onDlnaSelect).toHaveBeenCalled());
  });

  it("a server that can never be set up (422) is saved as a plain preset", async () => {
    put = () =>
      json({ type: "x", title: "x", status: 422, detail: "raw", code: "validation_error" }, 422);
    onDlnaSelect.mockResolvedValue(undefined);
    await save();
    await waitFor(() => expect(onDlnaSelect).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("a setup that does not end ready counts as failed", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    put = () => json({ server_id: "srv", state: "not_enabled" });
    await save();
    expect(await screen.findByRole("alert")).toHaveTextContent("did not accept the media server");
    expect(onDlnaSelect).not.toHaveBeenCalled();
  });

  it("an unreadable speaker shows 'State unknown' and saving stays possible", async () => {
    nativeList = () =>
      json({ type: "x", title: "x", status: 503, detail: "raw", code: "device_unreachable" }, 503);
    onDlnaSelect.mockResolvedValue(undefined);
    renderSearch({ deviceId: "dev1" });
    await openRoot();
    await screen.findByText("State unknown");
    fireEvent.click(screen.getByRole("button", { name: "Use for preset 3: Best Of" }));
    await waitFor(() => expect(onDlnaSelect).toHaveBeenCalled());
    expect(fetchMock.mock.calls.some((c) => c[1]?.method === "PUT")).toBe(false);
  });

  it("shows servers that are no longer found below the server list", async () => {
    nativeList = () =>
      json({
        device_id: "dev1",
        servers: [
          { server_id: "old", name: "Old NAS", state: "ready", server_known: false, source_id: 3 },
        ],
      });
    renderSearch({ deviceId: "dev1" });
    enterDlna();
    expect(await screen.findByRole("button", { name: "Remove: Old NAS" })).toBeInTheDocument();
  });
});
