import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

    expect(onDlnaSelect).toHaveBeenCalledWith({ server_id: "srv", object_id: "t1" });
    expect(screen.getByRole("button", { name: "Use for preset 3: First Song" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Use for preset 3: Best Of" })).toBeDisabled();
    expect(screen.getByText("Saving preset 3 …")).toBeInTheDocument();

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
