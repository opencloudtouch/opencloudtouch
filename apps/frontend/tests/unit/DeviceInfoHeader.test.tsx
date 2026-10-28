import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import DeviceInfoHeader from "../../src/components/wizard/DeviceInfoHeader";
import type { Device } from "../../src/api/devices";

const device = {
  device_id: "AABBCC112233",
  name: "Living Room",
  model: "SoundTouch 20",
  ip: "192.168.1.101",
} as Device;

describe("DeviceInfoHeader", () => {
  it("links the device icon back to the device on the presets page", () => {
    render(
      <MemoryRouter>
        <DeviceInfoHeader device={device} />
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: /Living Room/ });
    expect(link).toHaveAttribute("href", "/?device=AABBCC112233");
    expect(link).toHaveClass("device-icon");
  });
});
