/**
 * Tests for DeviceNameEditor component.
 *
 * Covers: display, edit mode, save, cancel, validation, error handling.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DeviceNameEditor from "../../src/components/DeviceNameEditor";

// Mock i18n
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "deviceRename.clickToEdit": "Click to edit",
        "deviceRename.inputLabel": "Device name",
        "deviceRename.tooLong": "Name too long",
        "deviceRename.failed": "Rename failed",
      };
      return map[key] ?? key;
    },
  }),
}));

// Mock TanStack Query
const mockInvalidateQueries = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

// Mock API
const mockRenameDevice = vi.fn();
vi.mock("../../src/api/devices", () => ({
  renameDevice: (...args: unknown[]) => mockRenameDevice(...args),
}));

// ResizeObserver is not implemented in jsdom
vi.stubGlobal(
  "ResizeObserver",
  class {
    observe = vi.fn();
    disconnect = vi.fn();
    unobserve = vi.fn();
  },
);

describe("DeviceNameEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Simulate a 200px-wide container for font-size computation
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      value: 200,
    });

    // Canvas mock: measureText scales with font size
    // Normal text: 0.55 avg char width; emoji ✏️: treated as 1.0 × size (square)
    const mockCtx = {
      font: "",
      measureText(text: string) {
        const m = /(\d+)px/.exec(this.font);
        const size = m ? parseInt(m[1]) : 16;
        if (text === "✏️") return { width: size }; // emoji = square (1em)
        return { width: text.length * size * 0.55 };
      },
    };
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
      mockCtx as unknown as RenderingContext,
    );
  });

  it("renders device name as heading", () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("data-test", "device-name");
  });

  it("enters edit mode on click", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));

    expect(screen.getByLabelText("Device name")).toBeInTheDocument();
    expect(screen.getByLabelText("Device name")).toHaveValue("Living Room");
  });

  it("enters edit mode on Enter key", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    fireEvent.keyDown(screen.getByRole("button"), { key: "Enter" });

    expect(screen.getByLabelText("Device name")).toBeInTheDocument();
  });

  it("submits on Enter key and calls API", async () => {
    mockRenameDevice.mockResolvedValue({
      device_id: "ABC123",
      name: "Kitchen",
      previous_name: "Living Room",
    });
    const onRenamed = vi.fn();

    render(
      <DeviceNameEditor deviceId="ABC123" name="Living Room" onRenamed={onRenamed} />
    );

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Kitchen");
    // Prevent blur from firing cancel before Enter
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(mockRenameDevice).toHaveBeenCalledWith("ABC123", "Kitchen");
    });

    await waitFor(() => {
      expect(onRenamed).toHaveBeenCalledWith("Kitchen");
    });

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ["devices"] });
  });

  it("cancels on Escape key and reverts value", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Changed");
    fireEvent.keyDown(input, { key: "Escape" });

    // Should be back to display mode
    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("cancels when unchanged name is submitted", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    fireEvent.keyDown(input, { key: "Enter" });

    // Same name = cancel, no API call
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("shows validation error for names exceeding 30 chars", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    // The input has maxLength=30, so type a long name and validate via save
    // We need to set value directly since maxLength prevents typing
    fireEvent.change(input, { target: { value: "A".repeat(31) } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText("Name too long")).toBeInTheDocument();
    });

    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("shows error message when API call fails", async () => {
    mockRenameDevice.mockRejectedValue(new Error("Network error"));

    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "NewName");
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText("Rename failed")).toBeInTheDocument();
    });
  });

  it("disables input while saving", async () => {
    // Never-resolving promise to keep saving state
    mockRenameDevice.mockReturnValue(new Promise(() => {}));

    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "NewName");
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByLabelText("Device name")).toBeDisabled();
    });
  });

  // REGRESSION TESTS for onBlur auto-save (added 2026-06-05)
  it("auto-saves on blur when value changed", async () => {
    mockRenameDevice.mockResolvedValue({
      device_id: "ABC123",
      name: "Kitchen",
      previous_name: "Living Room",
    });
    const onRenamed = vi.fn();

    render(
      <DeviceNameEditor deviceId="ABC123" name="Living Room" onRenamed={onRenamed} />
    );

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Kitchen");

    // Blur without pressing Enter should trigger save
    fireEvent.blur(input);

    await waitFor(() => {
      expect(mockRenameDevice).toHaveBeenCalledWith("ABC123", "Kitchen");
    });

    await waitFor(() => {
      expect(onRenamed).toHaveBeenCalledWith("Kitchen");
    });
  });

  it("cancels on blur when value unchanged", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");

    // Blur without changing value should cancel
    fireEvent.blur(input);

    // Should be back to display mode, no API call
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("cancels on blur when value is empty", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);

    // Blur with empty value should cancel
    fireEvent.blur(input);

    // Should be back to display mode with original name, no API call
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("does not trigger blur handler while saving", async () => {
    // Slow-resolving promise to test saving state
    mockRenameDevice.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ name: "Kitchen" }), 100))
    );

    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Kitchen");
    fireEvent.keyDown(input, { key: "Enter" });

    // Try to blur while saving
    fireEvent.blur(input);

    // Should only call API once (from Enter, not from blur)
    await waitFor(() => {
      expect(mockRenameDevice).toHaveBeenCalledTimes(1);
    });
  });

  // REGRESSION TEST for edit icon visibility (updated 2026-06-06)
  it("renders edit icon always visible at low opacity", () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    const heading = screen.getByRole("button");
    const icons = heading.querySelectorAll('span[aria-hidden="true"]');

    // Should have exactly 1 icon: the pencil edit icon (always visible at 30% opacity)
    expect(icons).toHaveLength(1);
    expect(icons[0]).toHaveClass("device-name-edit-icon");
  });

  describe("font size scaling via canvas.measureText", () => {
    it("uses a font size between 17px and 24px for short names", () => {
      render(<DeviceNameEditor deviceId="ABC123" name="TV" />);
      const size = parseInt(screen.getByRole("button").style.fontSize);
      expect(size).toBeGreaterThanOrEqual(17);
      expect(size).toBeLessThanOrEqual(24);
    });

    it("longer names get a smaller or equal font size than shorter names", () => {
      const { unmount } = render(<DeviceNameEditor deviceId="ABC123" name="TV" />);
      const shortSize = parseInt(screen.getByRole("button").style.fontSize);
      unmount();

      render(<DeviceNameEditor deviceId="ABC123" name="Wohnzimmer Süd" />);
      const longSize = parseInt(screen.getByRole("button").style.fontSize);

      expect(longSize).toBeLessThanOrEqual(shortSize);
    });

    it("floors at 17px minimum for very long names", () => {
      render(<DeviceNameEditor deviceId="ABC123" name="My Very Long Device Name Here" />);
      expect(screen.getByRole("button").style.fontSize).toBe("17px");
    });

    it("font size is always a valid integer between 17 and 24", () => {
      const names = ["A", "Kitchen", "Wohnzimmer", "My Very Long Device Name Here"];
      for (const name of names) {
        const { unmount } = render(<DeviceNameEditor deviceId="ABC123" name={name} />);
        const size = parseInt(screen.getByRole("button").style.fontSize);
        expect(size).toBeGreaterThanOrEqual(17);
        expect(size).toBeLessThanOrEqual(24);
        unmount();
      }
    });
  });
});
