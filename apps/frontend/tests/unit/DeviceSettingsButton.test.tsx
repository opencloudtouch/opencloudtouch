import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import DeviceSettingsButton from "../../src/components/DeviceSettingsButton";

const api = vi.hoisted(() => ({
  capabilities: vi.fn(),
  getBass: vi.fn(),
  setBass: vi.fn(),
}));

vi.mock("../../src/api/devices", () => ({
  getDeviceSettingsCapabilities: api.capabilities,
  getBass: api.getBass,
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

  it("ignores a delayed save response after unmounting", async () => {
    let resolveSave!: () => void;

    api.setBass.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveSave = resolve;
        })
    );

    const { unmount } = render(<DeviceSettingsButton deviceId="D1" deviceName="Kitchen" />);

    fireEvent.click(screen.getByRole("button", { name: "deviceSettings.open" }));
    const slider = await screen.findByRole("slider");

    fireEvent.input(slider, { target: { value: "-5" } });
    expect(screen.getByText("-5")).toBeInTheDocument();

    fireEvent.pointerUp(slider);
    await waitFor(() => {
      expect(api.setBass).toHaveBeenCalledExactlyOnceWith("D1", -5);
    });

    unmount();

    resolveSave();
    await Promise.resolve();

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
