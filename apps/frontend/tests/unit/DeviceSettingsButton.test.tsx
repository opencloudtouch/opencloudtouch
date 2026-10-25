import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import DeviceSettingsButton from "../../src/components/DeviceSettingsButton";

const api = vi.hoisted(() => ({
  capabilities: vi.fn(),
  getBass: vi.fn(),
  offline: vi.fn(),
  setBass: vi.fn(),
}));

vi.mock("../../src/api/devices", () => ({
  getDeviceSettingsCapabilities: api.capabilities,
  getBass: api.getBass,
  isDeviceOfflineError: api.offline,
  setBass: api.setBass,
}));

vi.mock("react-i18next", () => {
  const t = (key: string) => key;
  return {
    useTranslation: () => ({ t }),
  };
});

describe("DeviceSettingsButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.offline.mockReturnValue(false);
    api.capabilities.mockResolvedValue({
      features: { bass_control: true },
      settings: { bass: { available: true, minimum: -9, maximum: 0, default: 0 } },
    });
    api.getBass.mockResolvedValue({ actual: -3, target: -3 });
    api.setBass.mockResolvedValue(undefined);
  });

  it("always displays the settings button, including for unsupported devices", async () => {
    api.capabilities.mockResolvedValue({ features: { bass_control: false } });
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    expect(await screen.findByText("deviceSettings.noOptions")).toBeInTheDocument();
    expect(api.getBass).not.toHaveBeenCalled();
  });

  it("loads device-reported range and saves only after pointer release", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    const slider = await screen.findByRole("slider");
    expect(slider).toHaveAttribute("min", "-9");
    expect(slider).toHaveAttribute("max", "0");
    expect(slider).toHaveValue("-3");
    fireEvent.input(slider, { target: { value: "-5" } });
    expect(slider).toHaveValue("-5");
    expect(screen.getByText("-5")).toBeInTheDocument();
    expect(api.setBass).not.toHaveBeenCalled();
    fireEvent.pointerUp(slider);
    await waitFor(() => expect(api.setBass).toHaveBeenCalledExactlyOnceWith("D1", -5));
  });

  it("restores last confirmed value when device write fails", async () => {
    api.setBass.mockRejectedValue(new Error("Connection lost"));
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    const slider = await screen.findByRole("slider");
    fireEvent.change(slider, { target: { value: "-6" } });
    fireEvent.pointerUp(slider, { target: { value: "-6" } });
    await waitFor(() => expect(slider).toHaveValue("-3"));
    expect(screen.getByRole("alert")).toHaveTextContent("deviceSettings.saveFailed");
  });

  it("ignores a late save rejection after closing and reopening", async () => {
    let rejectSave!: (error: Error) => void;
    api.setBass.mockImplementationOnce(() => new Promise<void>((_, reject) => { rejectSave = reject; }));
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    const trigger = screen.getByRole("button", { name: "deviceSettings.open" });
    fireEvent.click(trigger);
    const slider = await screen.findByRole("slider");
    fireEvent.change(slider, { target: { value: "-5" } });
    fireEvent.pointerUp(slider);
    await waitFor(() => expect(api.setBass).toHaveBeenCalledTimes(1));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    fireEvent.click(trigger);
    expect(await screen.findByRole("slider")).toHaveValue("-3");
    await act(async () => { rejectSave(new Error("late failure")); });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("slider")).toHaveValue("-3");
  });

  it("keeps keyboard focus while saving and queues the latest value", async () => {
    let resolveFirst!: () => void;
    api.setBass.mockImplementationOnce(() => new Promise<void>((resolve) => { resolveFirst = resolve; }));
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    const slider = await screen.findByRole("slider");
    slider.focus();
    fireEvent.change(slider, { target: { value: "-5" } });
    fireEvent.keyUp(slider, { key: "ArrowLeft" });
    expect(slider).toHaveFocus();
    expect(slider).not.toBeDisabled();
    fireEvent.change(slider, { target: { value: "-7" } });
    fireEvent.keyUp(slider, { key: "ArrowLeft" });
    expect(api.setBass).toHaveBeenCalledTimes(1);
    await act(async () => { resolveFirst(); });
    await waitFor(() => expect(api.setBass).toHaveBeenNthCalledWith(2, "D1", -7));
  });

  it("allows saving on a new device while the previous write is pending", async () => {
    api.setBass.mockImplementationOnce(() => new Promise<void>(() => {}));

    const { rerender } = render(
      <DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />
    );

    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));

    const firstSlider = await screen.findByRole("slider");
    fireEvent.change(firstSlider, { target: { value: "-5" } });
    fireEvent.pointerUp(firstSlider);

    await waitFor(() =>
      expect(api.setBass).toHaveBeenCalledExactlyOnceWith("D1", -5)
    );

    rerender(<DeviceSettingsButton deviceId="D2" deviceName="Living Room" />);

    const secondSlider = await screen.findByRole("slider");
    await waitFor(() => expect(api.getBass).toHaveBeenCalledWith("D2"));

    fireEvent.change(secondSlider, { target: { value: "-7" } });
    fireEvent.pointerUp(secondSlider);

    await waitFor(() =>
      expect(api.setBass).toHaveBeenNthCalledWith(2, "D2", -7)
    );
  });

  it("shows a load error when reading bass fails", async () => {
    api.getBass.mockRejectedValue(new Error("read failed"));
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("deviceSettings.loadFailed");
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
    expect(api.setBass).not.toHaveBeenCalled();
  });

  it("closes on Escape while a write remains pending", async () => {
    api.setBass.mockImplementationOnce(() => new Promise<void>(() => {}));
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    const trigger = screen.getByRole("button", { name: "deviceSettings.open" });
    fireEvent.click(trigger);
    const slider = await screen.findByRole("slider");
    fireEvent.change(slider, { target: { value: "-5" } });
    fireEvent.pointerUp(slider);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("cycles Tab focus inside the dialog", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));

    await screen.findByRole("slider");

    const close = screen.getByRole("button", { name: "deviceSettings.close" });
    const reset = screen.getByRole("button", { name: "deviceSettings.reset" });

    expect(reset).toBeEnabled();

    reset.focus();
    fireEvent.keyDown(reset, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(close, { key: "Tab", shiftKey: true });
    expect(reset).toHaveFocus();
  });

  it("closes with Escape when focus is outside the dialog", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);

    const trigger = screen.getByRole("button", {
      name: "deviceSettings.open",
    });

    fireEvent.click(trigger);
    await screen.findByRole("dialog");

    trigger.focus();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("returns Tab focus to the dialog when focus is outside", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);

    const trigger = screen.getByRole("button", {
      name: "deviceSettings.open",
    });

    fireEvent.click(trigger);
    await screen.findByRole("dialog");

    trigger.focus();
    fireEvent.keyDown(document, { key: "Tab" });

    expect(
      screen.getByRole("button", { name: "deviceSettings.close" })
    ).toHaveFocus();
  });

  it("shows the offline message when bass loading fails for an offline device", async () => {
    api.getBass.mockRejectedValue(new Error("Device offline"));
    api.offline.mockReturnValue(true);

    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "deviceSettings.offline"
    );
    expect(api.offline).toHaveBeenCalled();
  });

  it("saves changes without pointer or keyboard release", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));

    const slider = await screen.findByRole("slider");

    fireEvent.change(slider, { target: { value: "-6" } });

    expect(slider).toHaveValue("-6");
    expect(api.setBass).not.toHaveBeenCalled();

    await waitFor(
      () => expect(api.setBass).toHaveBeenCalledExactlyOnceWith("D1", -6),
      { timeout: 1500 }
    );
  });

  it("does not save a debounced change after closing", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));

    const slider = await screen.findByRole("slider");
    fireEvent.change(slider, { target: { value: "-6" } });

    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.close" }));

    await new Promise((resolve) => setTimeout(resolve, 550));

    expect(api.setBass).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("saves pointer changes only on release without a duplicate write", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));

    const slider = await screen.findByRole("slider");

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: "-6" } });

    await new Promise((resolve) => setTimeout(resolve, 550));
    expect(api.setBass).not.toHaveBeenCalled();

    fireEvent.pointerUp(slider);

    await waitFor(() =>
      expect(api.setBass).toHaveBeenCalledExactlyOnceWith("D1", -6)
    );

    await new Promise((resolve) => setTimeout(resolve, 550));
    expect(api.setBass).toHaveBeenCalledTimes(1);
  });

  it("cancels a pointer gesture without saving bass", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);

    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    const slider = await screen.findByRole("slider");

    fireEvent.input(slider, { target: { value: "-7" } });
    expect(screen.getByText("-7")).toBeInTheDocument();

    fireEvent.pointerCancel(slider);

    expect(slider).toHaveValue("-3");
    expect(screen.getByText("-3")).toBeInTheDocument();
    expect(api.setBass).not.toHaveBeenCalled();
  });

  it("closes the settings dialog with Escape", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);

    const trigger = screen.getByRole("button", {
      name: "deviceSettings.open",
    });

    fireEvent.click(trigger);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("resets to the default value in one write", async () => {
    render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);
    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    await screen.findByRole("slider");
    fireEvent.click(screen.getByText("deviceSettings.reset"));
    await waitFor(() => expect(api.setBass).toHaveBeenCalledExactlyOnceWith("D1", 0));
  });
});
