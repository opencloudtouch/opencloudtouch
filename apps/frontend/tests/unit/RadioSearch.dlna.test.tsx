import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RadioSearch from "../../src/components/RadioSearch";
import * as api from "../../src/api/dlna";

vi.mock("../../src/api/dlna");

function setup(props: Partial<React.ComponentProps<typeof RadioSearch>> = {}) {
  const onClose = vi.fn();
  const onDlnaSave = vi.fn();
  const view = render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RadioSearch
        isOpen
        onClose={onClose}
        onStationSelect={vi.fn()}
        presetNumber={3}
        deviceId="dev1"
        onDlnaSave={onDlnaSave}
        {...props}
      />
    </QueryClientProvider>
  );
  return { onClose, onDlnaSave, rerender: view.rerender };
}

const dlnaPreset = {
  station_name: "Album",
  dlna: true,
  source_account: "s1/0",
  station_url: "f1",
};

describe("RadioSearch DLNA tab", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
    vi.mocked(api.getNativeServers).mockResolvedValue({
      servers: [],
      migration_failed: false,
      migration_reason: null,
    });
  });

  it("offers the DLNA tab and hides the search field in it", async () => {
    setup();
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "DLNA" }));
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Search by" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "DLNA" })).toHaveAttribute("aria-pressed", "true");
    const hint = await screen.findByText(/Choose a folder or song for preset 3/);
    // The pane scrolls inside the dialog like the other modes.
    const region = screen.getByRole("region", { name: "DLNA" });
    expect(region).toHaveClass("rs-scroll");
    expect(region).toContainElement(hint);
  });

  it("loads the quick media server list as soon as the dialog opens", async () => {
    setup();
    await waitFor(() =>
      expect(api.getNativeServers).toHaveBeenCalledWith("dev1", expect.anything(), false)
    );
    expect(api.getNativeServers).toHaveBeenCalledTimes(1);
  });

  it("does not load media servers while the dialog is closed", () => {
    setup({ isOpen: false });
    expect(api.getNativeServers).not.toHaveBeenCalled();
  });

  it("has no DLNA tab without a device", () => {
    setup({ deviceId: undefined });
    expect(screen.queryByRole("button", { name: "DLNA" })).not.toBeInTheDocument();
  });

  it("opens an existing DLNA preset in the DLNA tab", async () => {
    vi.mocked(api.getDlnaObjectPath).mockRejectedValue(new Error("offline"));
    setup({ existingPreset: dlnaPreset });
    expect(screen.getByRole("button", { name: "DLNA" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByText(/Choose a folder or song for preset 3/)).toBeInTheDocument();
  });

  it("search filters are not restored", async () => {
    vi.mocked(api.getDlnaObjectPath).mockRejectedValue(new Error("offline"));
    setup({ existingPreset: dlnaPreset });
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    // Switching to a provider shows a fresh, empty search (no restored query or type).
    await userEvent.click(screen.getByRole("button", { name: "RadioBrowser" }));
    expect(screen.getByRole("searchbox")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Name" })).toHaveAttribute("aria-pressed", "true");
  });

  it("cancel changes nothing", async () => {
    const { onClose, onDlnaSave } = setup();
    await userEvent.click(screen.getByRole("button", { name: "DLNA" }));
    await userEvent.click(screen.getAllByRole("button", { name: /close/i })[0]);
    expect(onClose).toHaveBeenCalled();
    expect(api.saveDlnaPreset).not.toHaveBeenCalled();
    expect(onDlnaSave).not.toHaveBeenCalled();
  });

  it("a DLNA save notifies the page and closes the dialog", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue({
      servers: [{ server_id: "s1", name: "Nas", state: "ready", discovered: true, host: null }],
      migration_failed: false,
      migration_reason: null,
    });
    vi.mocked(api.browseDlna).mockResolvedValue({
      server_id: "s1",
      object_id: "0",
      items: [{ id: "t1", parent_id: "0", title: "Song", is_container: false }],
      starting_index: 0,
      number_returned: 1,
      total_matches: null,
      next_index: 1,
      has_more: false,
    });
    const { onClose, onDlnaSave } = setup();
    await userEvent.click(screen.getByRole("button", { name: "DLNA" }));
    await userEvent.click(await screen.findByRole("button", { name: "Open Nas" }));
    await userEvent.click(await screen.findByRole("button", { name: "Select Song" }));
    expect(onDlnaSave).toHaveBeenCalledWith(expect.objectContaining({ object_id: "t1", index: 0 }));
    expect(onClose).toHaveBeenCalled();
  });
});
