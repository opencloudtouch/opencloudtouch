import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DlnaServerList from "../../src/components/dlna/DlnaServerList";
import { ApiError } from "../../src/api/types";
import * as api from "../../src/api/dlna";

vi.mock("../../src/api/dlna");

const native = (
  server_id: string,
  name: string,
  state: api.NativeServer["state"],
  host: string | null = "10.0.0.5",
  discovered = true
): api.NativeServer => ({ server_id, name, state, discovered, host });

const list = (
  servers: api.NativeServer[],
  migration_reason: string | null = null
): api.NativeServerList => ({
  servers,
  migration_failed: migration_reason !== null,
  migration_reason,
});

function setup(onOpenServer = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DlnaServerList deviceId="dev1" onOpenServer={onOpenServer} />
    </QueryClientProvider>
  );
  return onOpenServer;
}

describe("DlnaServerList", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders ready, not-set-up and not-available states", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(
      list([
        native("a", "Alpha", "ready", "10.0.0.1"),
        native("b", "Beta", "not_enabled", "10.0.0.2"),
        native("c", "Gamma", "unavailable", "10.0.0.3"),
      ])
    );
    const onOpen = setup();
    expect(await screen.findByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Not set up")).toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set up Beta" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Remove Gamma" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open Alpha" }));
    expect(onOpen).toHaveBeenCalledWith("a", "Alpha");
  });

  it("registered but undiscovered server is listed as not available and removable", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(
      list([native("uuid:x", "uuid:x", "unavailable", null, false)])
    );
    setup();
    expect(await screen.findByText("uuid:x")).toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open uuid:x" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove uuid:x" })).toBeInTheDocument();
  });

  it("undiscovered but speaker-ready server shows Ready and stays removable", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(
      list([native("uuid:y", "uuid:y", "ready", null, false)])
    );
    setup();
    expect(await screen.findByText("Ready")).toBeInTheDocument();
    expect(screen.queryByText("Not available")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open uuid:y" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove uuid:y" })).toBeInTheDocument();
  });

  it("enable calls the API and refreshes the list", async () => {
    let enabled = false;
    vi.mocked(api.getNativeServers).mockImplementation(async () =>
      list([native("b", "Beta", enabled ? "ready" : "not_enabled")])
    );
    vi.mocked(api.enableNativeServer).mockImplementation(async () => {
      enabled = true;
      return native("b", "Beta", "ready");
    });
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Set up Beta" }));
    expect(api.enableNativeServer).toHaveBeenCalledWith("dev1", "b");
    expect(await screen.findByText("Ready")).toBeInTheDocument();
    expect(
      screen.getByText("Beta is set up. Open the server to choose a folder or title.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Beta" })).toHaveTextContent("Open");
  });

  it("enable that ends unavailable shows the not-available hint", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list([native("b", "Beta", "not_enabled")]));
    vi.mocked(api.enableNativeServer).mockResolvedValue(native("b", "Beta", "unavailable"));
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Set up Beta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Beta is not available");
  });

  it("failed enable shows an alert", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list([native("b", "Beta", "not_enabled")]));
    vi.mocked(api.enableNativeServer).mockRejectedValue(new Error("boom"));
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Set up Beta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Beta could not be set up");
  });

  it("enable without a speaker account explains the missing setup", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list([native("b", "Beta", "not_enabled")]));
    vi.mocked(api.enableNativeServer).mockRejectedValue(
      new ApiError("x", { status: 409, code: "dlna_speaker_no_account" })
    );
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Set up Beta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Beta could not be set up: the speaker has no OpenCloudTouch account yet."
    );
  });

  it("migration failure shows the reason and disables enable", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(
      list([native("b", "Beta", "not_enabled")], "step 1 failed")
    );
    setup();
    expect(await screen.findByRole("alert")).toHaveTextContent("step 1 failed");
    expect(screen.getByRole("button", { name: "Set up Beta" })).toBeDisabled();
  });

  it("two servers on one host show the hint", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(
      list([native("a", "Alpha", "ready"), native("b", "Beta", "ready")])
    );
    setup();
    expect(await screen.findByText(/one server per IP/i)).toBeInTheDocument();
  });

  it("no hint for servers on different hosts", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(
      list([
        native("a", "Alpha", "ready", "10.0.0.5"),
        native("b", "Beta", "ready", "10.0.0.6"),
        native("c", "Gone", "unavailable", null, false),
        native("d", "Gone2", "unavailable", null, false),
      ])
    );
    setup();
    await screen.findByText("Alpha");
    expect(screen.queryByText(/one server per IP/i)).not.toBeInTheDocument();
  });

  it("empty state offers a rescan", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list([]));
    setup();
    expect(await screen.findByText("No media servers found")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Rescan" }));
    // Quick and full list on mount, then the rescan of the full list.
    await waitFor(() => expect(api.getNativeServers).toHaveBeenCalledTimes(3));
  });

  it("error state shows an alert with retry", async () => {
    let fail = true;
    vi.mocked(api.getNativeServers).mockImplementation(async () => {
      if (fail) throw new Error("x");
      return list([]);
    });
    setup();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No media servers found")).toBeInTheDocument();
  });

  it("shows the known servers at once, ready first, while the search runs", async () => {
    let finish: (value: api.NativeServerList) => void = () => {};
    vi.mocked(api.getNativeServers).mockImplementation((_id, _signal, discover) =>
      discover === false
        ? Promise.resolve(
            list([native("b", "Beta", "not_enabled", "10.0.0.2"), native("a", "Alpha", "ready")])
          )
        : new Promise((resolve) => (finish = resolve))
    );
    setup();
    expect(await screen.findByText(/Searching for more media servers/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      expect.stringContaining("Alpha"),
      expect.stringContaining("Beta"),
    ]);

    finish(list([native("a", "Alpha", "ready"), native("n", "New", "not_enabled", "10.0.0.9")]));
    expect(await screen.findByText("New")).toBeInTheDocument();
    expect(screen.queryByText("Beta")).not.toBeInTheDocument();
    expect(screen.queryByText("Searching for more media servers …")).not.toBeInTheDocument();
  });

  it("a failed search keeps the known servers and offers a retry", async () => {
    let fail = true;
    vi.mocked(api.getNativeServers).mockImplementation(async (_id, _signal, discover) => {
      if (discover !== false && fail) throw new Error("x");
      return list([
        native(discover === false ? "a" : "n", discover === false ? "Alpha" : "New", "ready"),
      ]);
    });
    setup();
    expect(await screen.findByText("Alpha")).toBeInTheDocument();
    expect(
      await screen.findByText("The search for more media servers failed.")
    ).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("New")).toBeInTheDocument();
  });

  it("offline speaker shows the offline banner", async () => {
    vi.mocked(api.getNativeServers).mockRejectedValue(
      new ApiError("x", { status: 503, code: "device_unreachable" })
    );
    setup();
    expect(await screen.findByTestId("device-offline-banner")).toBeInTheDocument();
  });

  it("rows are keyboard operable with accessible names", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list([native("b", "Beta", "not_enabled")]));
    vi.mocked(api.enableNativeServer).mockResolvedValue(native("b", "Beta", "ready"));
    setup();
    const btn = await screen.findByRole("button", { name: "Set up Beta" });
    btn.focus();
    await userEvent.keyboard("{Enter}");
    expect(api.enableNativeServer).toHaveBeenCalled();
    expect(screen.getByRole("list")).toBeInTheDocument();
  });

  it("remove opens the confirm dialog", async () => {
    vi.mocked(api.getNativeServers).mockResolvedValue(list([native("c", "Gamma", "unavailable")]));
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Remove Gamma" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Remove Gamma?");
  });
});
