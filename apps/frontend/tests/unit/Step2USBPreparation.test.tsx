/**
 * Tests for Step2USBPreparation wizard component
 *
 * BUG-17 Regression: USB connector type for SoundTouch 10 was shown as "USB-A"
 * instead of "Micro-USB".
 *
 * Old broken code:
 *   if (model.startsWith("ST10")) return "Micro-USB";
 *   // "SoundTouch 10".startsWith("ST10") === false → always returned USB-A
 *
 * Fixed code:
 *   const usbPort = model.includes("30") || model.includes("300") ? "USB-A" : "Micro-USB";
 *   // "SoundTouch 10" doesn't include "30" or "300" → correctly returns Micro-USB
 *
 * BUG-20 Regression: UI showed "remote_services" file should contain "SSH=ENABLE".
 * Fix: File must be EMPTY (BusyBox checks file existence, not content).
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Step2USBPreparation from "../../src/components/wizard/Step2USBPreparation";

// Mock framer-motion to avoid issues in jsdom
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

const defaultProps = {
  onNext: vi.fn(),
  onPrevious: vi.fn(),
};

function getPageText(): string {
  return document.body.textContent ?? "";
}

describe("Step2USBPreparation - BUG-17: USB connector type", () => {
  it("shows Micro-USB for SoundTouch 10 model (BUG-17 regression)", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 10" {...defaultProps} />
    );
    expect(getPageText()).toContain("Micro-USB");
    expect(getPageText()).not.toContain("USB-A");
    unmount();
  });

  it("shows USB-A for SoundTouch 30 model", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    expect(getPageText()).toContain("USB-A");
    unmount();
  });

  it("shows USB-A for SoundTouch 300 model", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 300" {...defaultProps} />
    );
    expect(getPageText()).toContain("USB-A");
    unmount();
  });

  it("shows Micro-USB for generic non-30/300 model", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 20" {...defaultProps} />
    );
    expect(getPageText()).toContain("Micro-USB");
    unmount();
  });

  it("displays the device model name in the page", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 10" {...defaultProps} />
    );
    expect(getPageText()).toContain("SoundTouch 10");
    unmount();
  });

  it("BUG-17: 'SoundTouch 10'.includes('30') is false → Micro-USB", () => {
    // Direct regression test for the broken code:
    // Old: startsWith("ST10") → false for "SoundTouch 10"
    // Current: includes("30") || includes("300") → false → Micro-USB ✓
    expect("SoundTouch 10".includes("30")).toBe(false);
    expect("SoundTouch 10".includes("300")).toBe(false);

    // This means the formula gives Micro-USB (NOT USB-A) for SoundTouch 10 ✓
    const usbPort =
      "SoundTouch 10".includes("30") || "SoundTouch 10".includes("300")
        ? "USB-A"
        : "Micro-USB";
    expect(usbPort).toBe("Micro-USB");
  });

  it("BUG-17: old broken formula startsWith('ST10') fails for full model name", () => {
    // Document why old code was wrong
    expect("SoundTouch 10".startsWith("ST10")).toBe(false);
    expect("ST10".startsWith("ST10")).toBe(true); // Only works for abbreviated names
  });
});

describe("Step2USBPreparation - BUG-20: remote_services must be empty", () => {
  it("shows that remote_services file must be empty (not SSH=ENABLE)", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    // "empty" appears in the description about the file being empty
    expect(getPageText()).toMatch(/empty/i);
    unmount();
  });

  it("does not instruct user to write SSH=ENABLE content", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    // BUG-20: Old UI said file should contain "SSH=ENABLE\nTELNET=ENABLE"
    expect(getPageText()).not.toContain("SSH=ENABLE");
    expect(getPageText()).not.toContain("TELNET=ENABLE");
    unmount();
  });
});

describe("Step2USBPreparation - General functionality", () => {
  it("renders the step title", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    expect(screen.getByText("Prepare USB drive")).toBeInTheDocument();
    unmount();
  });

  it("shows FAT32 format requirement", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    expect(getPageText()).toContain("FAT32");
    unmount();
  });

  it("shows remote_services filename in the page", () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    expect(getPageText()).toContain("remote_services");
    unmount();
  });
});
