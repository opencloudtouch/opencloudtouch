/**
 * DeviceImage Component Tests
 *
 * User Story: Als User sehe ich ein Bild meines Gerätetyps
 *
 * Focus: Correct image rendering based on device type
 */
import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DeviceImage from "./DeviceImage";

describe("DeviceImage Component", () => {
  it("renders correct image for known device types", () => {
    const { rerender } = render(<DeviceImage deviceType="SoundTouch 10" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/images/devices/st10.svg");

    rerender(<DeviceImage deviceType="SoundTouch 20" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/images/devices/st20.svg");

    rerender(<DeviceImage deviceType="SoundTouch 30" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/images/devices/st30.svg");
  });

  it("falls back to default image for unknown device types", () => {
    render(<DeviceImage deviceType="Unknown Model XYZ" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/images/devices/default.svg");
  });

  it("displays device label when showLabel is true", () => {
    const { rerender } = render(<DeviceImage deviceType="SoundTouch 20" showLabel={true} />);
    expect(screen.getByText("SoundTouch 20")).toBeInTheDocument();

    rerender(<DeviceImage deviceType="SoundTouch 30" showLabel={false} />);
    expect(screen.queryByText("SoundTouch 30")).not.toBeInTheDocument();
  });

  it("uses provided alt text for accessibility", () => {
    render(<DeviceImage deviceType="ST10" alt="Living Room Speaker" />);
    expect(screen.getByRole("img")).toHaveAttribute("alt", "Living Room Speaker");
  });

  it("uses lazy loading for performance", () => {
    render(<DeviceImage deviceType="ST300" />);
    expect(screen.getByRole("img")).toHaveAttribute("loading", "lazy");
  });
});
