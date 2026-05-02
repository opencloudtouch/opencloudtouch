/**
 * Tests for DeviceOfflineBanner component
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DeviceOfflineBanner from "../../src/components/DeviceOfflineBanner";

describe("DeviceOfflineBanner", () => {
  it("renders offline banner with default text", () => {
    render(<DeviceOfflineBanner />);
    expect(screen.getByText("Device unreachable")).toBeInTheDocument();
    expect(
      screen.getByText("The device is offline or not on the network."),
    ).toBeInTheDocument();
  });

  it("renders offline banner with device name", () => {
    render(<DeviceOfflineBanner deviceName="Wohnzimmer" />);
    expect(screen.getByText("Device unreachable")).toBeInTheDocument();
    expect(
      screen.getByText(/Wohnzimmer.+is offline or not on the network/),
    ).toBeInTheDocument();
  });

  it("has role=alert for accessibility", () => {
    render(<DeviceOfflineBanner />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
