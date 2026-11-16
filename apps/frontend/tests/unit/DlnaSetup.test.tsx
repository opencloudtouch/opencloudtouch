import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import DlnaSetupPanel from "../../src/components/dlna/DlnaSetupPanel";
import DlnaOrphanList from "../../src/components/dlna/DlnaOrphanList";
import type { DlnaSetupApi, NativeServer } from "../../src/components/dlna/dlnaSetupTypes";

const srv = (over: Partial<NativeServer> = {}): NativeServer => ({
  server_id: "s1",
  name: "Test NAS",
  state: "ready",
  server_known: true,
  source_id: 1,
  ...over,
});

const mkApi = (over: Partial<DlnaSetupApi> = {}): DlnaSetupApi => ({
  servers: [srv()],
  isLoading: false,
  error: null,
  refetch: vi.fn().mockResolvedValue(undefined),
  setup: vi.fn(),
  slots: vi.fn().mockResolvedValue([]),
  remove: vi.fn().mockResolvedValue(undefined),
  ...over,
});

const panel = (
  api: DlnaSetupApi,
  props: Partial<React.ComponentProps<typeof DlnaSetupPanel>> = {}
) =>
  render(
    <DlnaSetupPanel
      api={api}
      serverId="s1"
      serverName="Test NAS"
      onRetrySetup={vi.fn()}
      {...props}
    />
  );

const codeError = (code: string) => Object.assign(new Error("x"), { code });

describe("DlnaSetupPanel states", () => {
  it("ready: badge, sentence and a Remove action, no track/folder distinction", () => {
    panel(mkApi());
    expect(
      screen.getByRole("region", { name: "Media server on this speaker: Test NAS" })
    ).toHaveAttribute("data-nd", "ready");
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText(/folders and tracks/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove: Test NAS" })).toBeInTheDocument();
    expect(screen.queryByText(/single item/i)).toBeNull();
  });

  it("not set up: explains the automatic setup and offers no action", () => {
    panel(mkApi({ servers: [srv({ state: "not_enabled" })] }));
    expect(screen.getByText("Not set up")).toBeInTheDocument();
    expect(screen.getByText(/happens automatically when you save/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("setting up: busy badge, then the reassurance text when long", () => {
    const { rerender } = panel(mkApi(), { busy: "setup" });
    expect(screen.getByText("Setting up")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    rerender(
      <DlnaSetupPanel
        api={mkApi()}
        serverId="s1"
        serverName="Test NAS"
        busy="setup"
        long
        onRetrySetup={vi.fn()}
      />
    );
    expect(screen.getByText(/up to 15 seconds/)).toBeInTheDocument();
  });

  it("removing: badge and progress text", () => {
    panel(mkApi(), { busy: "remove" });
    expect(screen.getByText("Removing")).toBeInTheDocument();
    expect(screen.getByText("Removing …")).toBeInTheDocument();
  });

  it("unavailable: Not available with Try again that calls onRetrySetup", () => {
    const onRetrySetup = vi.fn();
    panel(mkApi({ servers: [srv({ state: "unavailable" })] }), { onRetrySetup });
    expect(screen.getByText("Not available")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again: set up for Test NAS" }));
    expect(onRetrySetup).toHaveBeenCalledTimes(1);
  });

  it("loading: checking text, no action", () => {
    panel(mkApi({ isLoading: true, servers: undefined }));
    expect(screen.getByText("Checking")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it.each([
    ["unreachable", /speaker could not be reached/],
    ["network", /did not return the state/],
  ] as const)("%s: State unknown with Check again that reloads", (error, text) => {
    const api = mkApi({ error, servers: undefined });
    panel(api);
    expect(screen.getByText("State unknown")).toBeInTheDocument();
    expect(screen.getByText(text)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check again: state of Test NAS" }));
    expect(api.refetch).toHaveBeenCalledTimes(1);
  });
});

describe("removal dialog", () => {
  const open = async (api: DlnaSetupApi) => {
    panel(api);
    fireEvent.click(screen.getByRole("button", { name: "Remove: Test NAS" }));
    await screen.findByText("Remove the media server for this speaker?");
  };

  it("lists the presets that will be switched, confirms with force and shows the result", async () => {
    const api = mkApi({
      slots: vi.fn().mockResolvedValue([{ preset_number: 2, name: "Best Of" }]),
    });
    await open(api);
    expect(await screen.findByText("These presets will be switched:")).toBeInTheDocument();
    expect(screen.getByText("Preset 2: Best Of")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Confirm removal: Test NAS" }));
    expect(await screen.findAllByText("Removed.")).not.toHaveLength(0);
    expect(api.remove).toHaveBeenCalledWith("s1", true);

    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByText("Removed.")).toBeNull());
  });

  it("shows the empty state when no preset uses the server", async () => {
    await open(mkApi());
    expect(await screen.findByText("No preset uses this media server.")).toBeInTheDocument();
    expect(screen.queryByText("These presets will be switched:")).toBeNull();
  });

  it("409 in use: reloads the list and shows it again, then removes", async () => {
    const slots = vi
      .fn()
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ preset_number: 4, name: "Late Preset" }]);
    const remove = vi
      .fn()
      .mockRejectedValueOnce(codeError("dlna_native_in_use"))
      .mockResolvedValueOnce(undefined);
    await open(mkApi({ slots, remove }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm removal: Test NAS" }));

    expect(await screen.findByText("Preset 4: Late Preset")).toBeInTheDocument();
    expect(screen.getAllByText(/Presets still use this media server/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirm removal: Test NAS" }));
    expect(await screen.findAllByText("Removed.")).not.toHaveLength(0);
    expect(remove).toHaveBeenCalledTimes(2);
  });

  it("failure: shows the translated error with retry; unknown codes get the generic text", async () => {
    const remove = vi
      .fn()
      .mockRejectedValueOnce(codeError("dlna_native_remove_failed"))
      .mockRejectedValueOnce(codeError("something_else"));
    await open(mkApi({ remove }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm removal: Test NAS" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The media server could not be removed. Nothing was changed.");

    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("That did not work."));
  });

  it("failure while loading the presets ends in the error step", async () => {
    await open(mkApi({ slots: vi.fn().mockRejectedValue(codeError("device_unreachable")) }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("'Close, keeps running' closes the dialog and reports the running removal", async () => {
    let finish!: () => void;
    const remove = vi.fn(() => new Promise<void>((r) => (finish = r)));
    const onRemoving = vi.fn();
    const api = mkApi({ remove });
    panel(api, { onRemoving });
    fireEvent.click(screen.getByRole("button", { name: "Remove: Test NAS" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm removal: Test NAS" }));
    fireEvent.click(await screen.findByRole("button", { name: "Close, keeps running" }));
    expect(screen.queryByText("Remove the media server for this speaker?")).toBeNull();
    expect(onRemoving).toHaveBeenLastCalledWith(true);

    finish();
    await waitFor(() => expect(onRemoving).toHaveBeenLastCalledWith(false));
  });
});

describe("DlnaOrphanList", () => {
  it("renders nothing without orphans", () => {
    const { container } = render(<DlnaOrphanList api={mkApi()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists servers that are no longer found and removes one through the dialog", async () => {
    const api = mkApi({
      servers: [srv(), srv({ server_id: "gone", name: "Old NAS", server_known: false })],
    });
    render(<DlnaOrphanList api={api} />);
    const list = screen.getByRole("list", { name: "Media servers that are not found" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Remove: Old NAS" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm removal: Old NAS" }));
    await screen.findAllByText("Removed.");
    expect(api.remove).toHaveBeenCalledWith("gone", true);
  });
});
