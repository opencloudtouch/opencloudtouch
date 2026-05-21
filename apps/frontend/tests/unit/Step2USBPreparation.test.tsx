/**
 * Tests for Step2USBPreparation wizard component
 *
 * BUG-17 Regression: USB connector type for SoundTouch 10 was shown as "USB-A"
 * instead of "Micro-USB".
 *
 * BUG-20 Regression: UI showed "remote_services" file should contain "SSH=ENABLE".
 * Fix: File must be EMPTY (BusyBox checks file existence, not content).
 *
 * USB types now fetched from backend ModelInstructions API.
 * When API is unavailable (tests), falls back to Micro-USB as default.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

// Mock the setup API to return model-specific instructions
vi.mock("../../src/api/setup", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/setup")>();
  return {
    ...actual,
    getModelInstructions: vi.fn((model: string) => {
      const db: Record<string, { usb_port_type: string; usb_port_types: string[] }> = {
        "SoundTouch 10": { usb_port_type: "micro-usb", usb_port_types: ["micro-usb"] },
        "SoundTouch 20": {
          usb_port_type: "micro-usb",
          usb_port_types: ["micro-usb", "usb-a"],
        },
        "SoundTouch 30": {
          usb_port_type: "micro-usb",
          usb_port_types: ["micro-usb", "usb-a"],
        },
        "SoundTouch 300": { usb_port_type: "usb-a", usb_port_types: ["usb-a"] },
      };
      const entry = db[model] ?? { usb_port_type: "micro-usb", usb_port_types: ["micro-usb"] };
      return Promise.resolve({
        model_name: model,
        display_name: `Bose ${model}`,
        usb_port_type: entry.usb_port_type,
        usb_port_types: entry.usb_port_types,
        usb_port_location: "Rückseite",
        adapter_needed: entry.usb_port_type === "micro-usb",
        adapter_recommendation: "",
        notes: [],
      });
    }),
  };
});

const defaultProps = {
  onNext: vi.fn(),
  onPrevious: vi.fn(),
};

function getPageText(): string {
  return document.body.textContent ?? "";
}

describe("Step2USBPreparation - BUG-17: USB connector type", () => {
  it("shows Micro-USB for SoundTouch 10 model (BUG-17 regression)", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 10" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("MICRO-USB"));
    unmount();
  });

  it("shows USB-A for SoundTouch 30 model (has both types)", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("USB-A"));
    expect(getPageText()).toContain("MICRO-USB");
    unmount();
  });

  it("shows USB-A for SoundTouch 300 model", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 300" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("USB-A"));
    unmount();
  });

  it("shows both USB types for SoundTouch 20 (has both types)", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 20" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("MICRO-USB"));
    expect(getPageText()).toContain("USB-A");
    unmount();
  });

  it("displays the device model name in the page", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 10" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("SoundTouch 10"));
    unmount();
  });

});

describe("Step2USBPreparation - BUG-20: remote_services must be empty", () => {
  it("shows that remote_services file must be empty (not SSH=ENABLE)", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toMatch(/empty/i));
    unmount();
  });

  it("does not instruct user to write SSH=ENABLE content", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("remote_services"));
    expect(getPageText()).not.toContain("SSH=ENABLE");
    expect(getPageText()).not.toContain("TELNET=ENABLE");
    unmount();
  });
});

describe("Step2USBPreparation - General functionality", () => {
  it("renders the step title", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    expect(screen.getByText("Prepare USB drive")).toBeInTheDocument();
    unmount();
  });

  it("shows FAT32 format requirement", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("FAT32"));
    unmount();
  });

  it("shows remote_services filename in the page", async () => {
    const { unmount } = render(
      <Step2USBPreparation deviceModel="SoundTouch 30" {...defaultProps} />
    );
    await waitFor(() => expect(getPageText()).toContain("remote_services"));
    unmount();
  });
});
